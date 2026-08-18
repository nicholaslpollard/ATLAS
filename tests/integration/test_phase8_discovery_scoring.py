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
from packages.discovery.scanner import DISCOVERY_FOUNDATION_MANIFEST_VERSION
from packages.discovery.scoring import DiscoverySetupScanner
from packages.features.feature_registry import CORE_FEATURE_CONTRACT_VERSION, CORE_FEATURE_REGISTRY
from packages.features.partition_store import (
    FEATURE_PARTITION_CONTRACT_VERSION,
    FEATURE_PARTITION_SCHEMA_VERSION,
    sha256_file,
)

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
        row = con.execute(
            f"SELECT count(*), count(DISTINCT symbol) FROM read_parquet('{path.as_posix()}')"
        ).fetchone()
        return int(row[0]), int(row[1])
    finally:
        con.close()


def _write_feature_manifest(paths: MarketDataPaths, timeframe: Timeframe, as_of: date) -> None:
    feature_path = paths.feature_file(timeframe, as_of)
    source_path = (
        paths.canonical_file(Timeframe.DAY_1, as_of)
        if timeframe == Timeframe.DAY_1
        else feature_path
    )
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


def _features(symbol: str, *, bullish: bool, session_segment: str | None = None) -> dict[str, object]:
    sign = 1.0 if bullish else -1.0
    row: dict[str, object] = {
        "symbol": symbol,
        "timestamp_utc": datetime(2026, 8, 14, 20, 0, tzinfo=UTC),
        "return_1": sign * 0.04,
        "rsi_14": 68.0 if bullish else 32.0,
        "true_range": 5.0,
        "atr_14": 2.0,
        "natr_14": 0.02,
        "bb_position_20": 1.05 if bullish else -0.05,
        "relative_volume_20": 3.0,
        "relative_dollar_volume_20": 3.2,
        "volume_zscore_20": 3.0,
        "range_position_20": 0.95 if bullish else 0.05,
        "breakout_distance_20": 0.03 if bullish else -0.40,
        "breakdown_distance_20": 0.40 if bullish else -0.03,
        "ema_20_slope_1": sign * 0.01,
        "price_distance_ema_20": sign * 0.04,
        "directional_efficiency_20": 0.80,
    }
    if session_segment is not None:
        row["session_segment"] = session_segment
    return row


def test_discovery_scoring_builds_directional_records_and_skips(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    paths = MarketDataPaths(settings)
    as_of = date(2026, 8, 14)

    _write_frame(
        paths.canonical_file(Timeframe.DAY_1, as_of),
        pd.DataFrame(
            [
                {"symbol": "AAA", "timestamp_utc": datetime(2026, 8, 14, 20, 0, tzinfo=UTC)},
                {"symbol": "BBB", "timestamp_utc": datetime(2026, 8, 14, 20, 0, tzinfo=UTC)},
            ]
        ),
    )
    _write_frame(
        paths.feature_file(Timeframe.DAY_1, as_of),
        pd.DataFrame([_features("AAA", bullish=True), _features("BBB", bullish=False)]),
    )
    for timeframe in (Timeframe.HOUR_4, Timeframe.HOUR_1):
        _write_frame(
            paths.feature_file(timeframe, as_of),
            pd.DataFrame(
                [
                    _features("AAA", bullish=True, session_segment="regular"),
                    _features("BBB", bullish=False, session_segment="regular"),
                ]
            ),
        )
    for timeframe in (Timeframe.DAY_1, Timeframe.HOUR_4, Timeframe.HOUR_1):
        _write_feature_manifest(paths, timeframe, as_of)

    foundation_path = paths.discovery_snapshot_file(as_of)
    _write_frame(
        foundation_path,
        pd.DataFrame(
            [
                {
                    "instrument_id": "i-a",
                    "ticker": "AAA",
                    "security_type": "CS",
                    "routes": ["discovery"],
                    "activity_tier": "active",
                    "broad_discovery_ready": True,
                    "mandatory_route": False,
                    "consideration_required": True,
                },
                {
                    "instrument_id": "i-b",
                    "ticker": "BBB",
                    "security_type": "CS",
                    "routes": ["discovery"],
                    "activity_tier": "active",
                    "broad_discovery_ready": True,
                    "mandatory_route": False,
                    "consideration_required": True,
                },
            ]
        ),
    )
    manifests = {
        key: json.loads(paths.feature_manifest_file(tf, as_of).read_text(encoding="utf-8"))
        for tf, key in (
            (Timeframe.DAY_1, "1d"),
            (Timeframe.HOUR_4, "4h"),
            (Timeframe.HOUR_1, "1h"),
        )
    }
    foundation_manifest = paths.discovery_snapshot_manifest(as_of)
    foundation_manifest.parent.mkdir(parents=True, exist_ok=True)
    foundation_manifest.write_text(
        json.dumps(
            {
                "manifest_version": DISCOVERY_FOUNDATION_MANIFEST_VERSION,
                "snapshot_sha256": sha256_file(foundation_path),
                "upstream_lineage": {
                    "features_1d_sha256": manifests["1d"]["feature_sha256"],
                    "features_4h_sha256": manifests["4h"]["feature_sha256"],
                    "features_1h_sha256": manifests["1h"]["feature_sha256"],
                },
            }
        ),
        encoding="utf-8",
    )

    scanner = DiscoverySetupScanner(settings)
    first = scanner.build(as_of)
    assert first.skipped is False
    assert first.scored_count == 2
    assert first.timeframe_coverage_counts == {"3": 2}

    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            f"SELECT ticker, direction, bull_evidence, bear_evidence, scored_timeframes "
            f"FROM read_parquet('{first.snapshot_path.as_posix()}') ORDER BY ticker"
        ).fetchall()
    finally:
        con.close()
    assert rows[0][0] == "AAA"
    assert rows[0][1] == "bullish"
    assert rows[0][2] > rows[0][3]
    assert rows[0][4] == 3
    assert rows[1][0] == "BBB"
    assert rows[1][1] == "bearish"
    assert rows[1][3] > rows[1][2]
    assert rows[1][4] == 3

    second = scanner.build(as_of)
    assert second.skipped is True
    assert second.dependency_fingerprint == first.dependency_fingerprint
    assert second.snapshot_sha256 == first.snapshot_sha256
