from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

duckdb = pytest.importorskip("duckdb")

from packages.core.enums import Timeframe
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.discovery.scanner import DiscoveryFoundationScanner
from packages.features.feature_registry import CORE_FEATURE_CONTRACT_VERSION, CORE_FEATURE_REGISTRY
from packages.features.partition_store import FEATURE_PARTITION_CONTRACT_VERSION, FEATURE_PARTITION_SCHEMA_VERSION, sha256_file
from packages.schemas.universe import UNIVERSE_CONTRACT_VERSION
from packages.universe.manager import UNIVERSE_MANIFEST_VERSION

ROOT = Path(__file__).resolve().parents[2]


def _settings(tmp_path: Path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    return settings


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        con.register("t", frame)
        con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)")
    finally:
        con.close()


def _parquet_counts(path: Path) -> tuple[int, int]:
    con = duckdb.connect(":memory:")
    try:
        row = con.execute(f"SELECT count(*), count(DISTINCT symbol) FROM read_parquet('{path.as_posix()}')").fetchone()
        return int(row[0]), int(row[1])
    finally:
        con.close()


def _write_feature_manifest(paths: MarketDataPaths, timeframe: Timeframe, as_of: date) -> None:
    feature_path = paths.feature_file(timeframe, as_of)
    source_path = paths.canonical_file(Timeframe.DAY_1, as_of) if timeframe == Timeframe.DAY_1 else feature_path
    row_count, symbol_count = _parquet_counts(feature_path)
    payload = {
        "schema_version": FEATURE_PARTITION_SCHEMA_VERSION,
        "partition_contract_version": FEATURE_PARTITION_CONTRACT_VERSION,
        "feature_contract_version": CORE_FEATURE_CONTRACT_VERSION,
        "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
        "timeframe": timeframe.value,
        "trading_date": as_of.isoformat(),
        "source_path": str(source_path.resolve()),
        "source_sha256": sha256_file(source_path),
        "input_state_fingerprint": "synthetic-in",
        "output_state_fingerprint": "synthetic-out",
        "dependency_fingerprint": "synthetic-dependency",
        "feature_path": str(feature_path.resolve()),
        "feature_sha256": sha256_file(feature_path),
        "row_count": row_count,
        "symbol_count": symbol_count,
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    manifest = paths.feature_manifest_file(timeframe, as_of)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload), encoding="utf-8")


def test_discovery_foundation_builds_and_skips_from_upstream_lineage(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    paths = MarketDataPaths(settings)
    as_of = date(2026, 8, 14)
    ts = datetime(2026, 8, 14, 20, 0, tzinfo=UTC)

    _write_frame(paths.universe_snapshot_file(as_of), pd.DataFrame([
        {"instrument_id":"i-a","ticker":"AAA","security_type":"CS","discovery_eligible":True,"routes":["discovery"]},
        {"instrument_id":"i-b","ticker":"BBB","security_type":"CS","discovery_eligible":True,"routes":["discovery"]},
        {"instrument_id":"i-c","ticker":"CCC","security_type":"CS","discovery_eligible":False,"routes":["position"]},
    ]))
    universe_manifest = paths.universe_snapshot_manifest(as_of)
    universe_manifest.parent.mkdir(parents=True, exist_ok=True)
    universe_manifest.write_text(json.dumps({
        "manifest_version": UNIVERSE_MANIFEST_VERSION,
        "universe_contract_version": UNIVERSE_CONTRACT_VERSION,
        "snapshot_sha256": sha256_file(paths.universe_snapshot_file(as_of)),
    }), encoding="utf-8")

    _write_frame(paths.canonical_file(Timeframe.DAY_1, as_of), pd.DataFrame([
        {"symbol":"AAA","timestamp_utc":ts,"close":0.50,"volume":4_000_000.0},
        {"symbol":"BBB","timestamp_utc":ts,"close":10.0,"volume":10_000.0},
    ]))
    _write_frame(paths.feature_file(Timeframe.DAY_1, as_of), pd.DataFrame([
        {"symbol":"AAA","timestamp_utc":ts,"dollar_volume":2_000_000.0,"relative_volume_20":1.5,"relative_dollar_volume_20":1.6,"natr_14":0.04,"realized_volatility_20":0.03},
        {"symbol":"BBB","timestamp_utc":ts,"dollar_volume":100_000.0,"relative_volume_20":2.5,"relative_dollar_volume_20":2.6,"natr_14":0.05,"realized_volatility_20":0.04},
    ]))
    for timeframe in (Timeframe.HOUR_4, Timeframe.HOUR_1):
        _write_frame(paths.feature_file(timeframe, as_of), pd.DataFrame([{"symbol":"AAA","session_segment":"regular"}]))
    for timeframe in (Timeframe.DAY_1, Timeframe.HOUR_4, Timeframe.HOUR_1):
        _write_feature_manifest(paths, timeframe, as_of)

    scanner = DiscoveryFoundationScanner(settings)
    first = scanner.build(as_of)
    assert first.skipped is False
    assert first.source_universe_count == 3
    assert first.data_health_pass_count == 2
    assert first.activity_pass_count == 1
    assert first.broad_discovery_ready_count == 1
    assert first.mandatory_route_count == 1
    assert first.consideration_required_count == 2
    assert first.intraday_ready_count == 1

    second = scanner.build(as_of)
    assert second.skipped is True
    assert second.dependency_fingerprint == first.dependency_fingerprint
    assert second.snapshot_sha256 == first.snapshot_sha256

    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(f"SELECT ticker, broad_discovery_ready, mandatory_route, consideration_required, activity_tier FROM read_parquet('{first.snapshot_path.as_posix()}') ORDER BY ticker").fetchall()
    finally:
        con.close()
    assert rows == [
        ("AAA", True, False, True, "active"),
        ("BBB", False, False, False, "below_floor"),
        ("CCC", False, True, True, "below_floor"),
    ]
