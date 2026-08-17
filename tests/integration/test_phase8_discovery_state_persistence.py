from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

duckdb = pytest.importorskip("duckdb")

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.discovery.persistence import DiscoveryStateManager
from packages.discovery.scoring import DISCOVERY_SCORE_MANIFEST_VERSION
from packages.discovery.state_machine import DISCOVERY_STATE_POLICY_VERSION
from packages.features.partition_store import sha256_file

ROOT = Path(__file__).resolve().parents[2]


def _settings(tmp_path: Path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    return settings


def _write_score(paths: MarketDataPaths, as_of: date, raw_state: str) -> None:
    score_path = paths.discovery_score_file(as_of)
    score_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [
            {
                "instrument_id": "i-a",
                "ticker": "AAA",
                "raw_state": raw_state,
                "scored_timeframes": 3,
                "priority_score": 0.52,
                "bull_evidence": 0.44,
                "bear_evidence": 0.10,
                "direction": "bullish",
                "top_setup": "momentum",
            }
        ]
    )
    con = duckdb.connect(":memory:")
    try:
        con.register("scores", frame)
        con.execute(f"COPY scores TO '{score_path.as_posix()}' (FORMAT PARQUET)")
    finally:
        con.close()

    manifest_path = paths.discovery_score_manifest(as_of)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": DISCOVERY_SCORE_MANIFEST_VERSION,
                "state_policy_version": DISCOVERY_STATE_POLICY_VERSION,
                "snapshot_sha256": sha256_file(score_path),
                "dependency_fingerprint": f"score-{as_of}",
            }
        ),
        encoding="utf-8",
    )


def _read_effective(path: Path) -> tuple[str, int, int, str]:
    con = duckdb.connect(":memory:")
    try:
        row = con.execute(
            f"SELECT effective_state, warm_confirmation_streak, demotion_streak, transition "
            f"FROM read_parquet('{path.as_posix()}')"
        ).fetchone()
        return str(row[0]), int(row[1]), int(row[2]), str(row[3])
    finally:
        con.close()


def test_state_manager_bootstraps_then_uses_exact_previous_session(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    paths = MarketDataPaths(settings)
    thursday = date(2026, 8, 13)
    friday = date(2026, 8, 14)
    _write_score(paths, thursday, "warm")
    _write_score(paths, friday, "warm")

    manager = DiscoveryStateManager(settings)
    first = manager.build(thursday)
    assert first.skipped is False
    assert first.continuity_used is False
    assert first.previous_session_date == date(2026, 8, 12)
    assert first.effective_state_counts == {"watch": 1}
    assert _read_effective(first.snapshot_path) == (
        "watch",
        1,
        0,
        "bootstrap_warm_pending",
    )

    second = manager.build(thursday)
    assert second.skipped is True
    assert second.snapshot_sha256 == first.snapshot_sha256
    assert second.dependency_fingerprint == first.dependency_fingerprint

    friday_result = manager.build(friday)
    assert friday_result.skipped is False
    assert friday_result.continuity_used is True
    assert friday_result.previous_session_date == thursday
    assert friday_result.effective_state_counts == {"warm": 1}
    assert _read_effective(friday_result.snapshot_path) == (
        "warm",
        0,
        0,
        "promote_warm",
    )
