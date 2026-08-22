from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

from packages.core.settings import load_settings
from packages.regimes.historical_backfill_regime_promotion import (
    GATE10_REGIME_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
    _classify_new_target,
    _manifest_rewrite_is_path_only,
)
from packages.regimes.historical_backfill_regime_replay_build import (
    GATE10_MARKET_SECTOR_MANIFEST_VERSION,
    GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION,
    GATE10_SPLIT_ORIGIN_POLICY_VERSION,
)
from packages.regimes.split_origin_policy import (
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    MARKET_SECTOR_MANIFEST_VERSION,
    MARKET_SECTOR_POLICY_GENESIS_BUILD_CONTRACT,
    MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    REGIME_HISTORY_DATASET_VERSION,
    SPLIT_ORIGIN_POLICY_VERSION,
    TICKER_HISTORY_ORIGIN_DATE,
)
from packages.regimes.split_origin_state_engine import SplitOriginRegimeStateEngine
from packages.regimes.threshold_policy import REGIME_HISTORY_ORIGIN_DATE


def test_gate10c_split_origin_production_contracts_match_accepted_gate10b() -> None:
    assert GATE10_REGIME_PROMOTION_PREFLIGHT_CONTRACT_VERSION == (
        "historical-backfill-regime-promotion-preflight-v1-v2-writer-rollback-history-publication"
    )
    assert SPLIT_ORIGIN_POLICY_VERSION == GATE10_SPLIT_ORIGIN_POLICY_VERSION
    assert MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION == GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION
    assert MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION == GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION
    assert MARKET_SECTOR_MANIFEST_VERSION == GATE10_MARKET_SECTOR_MANIFEST_VERSION
    assert MARKET_SECTOR_POLICY_GENESIS_BUILD_CONTRACT == GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION


def test_gate10c_split_origins_preserve_intraday_boundary() -> None:
    assert MARKET_SECTOR_HISTORY_ORIGIN_DATE == date(2016, 1, 4)
    assert TICKER_HISTORY_ORIGIN_DATE == date(2021, 8, 16)
    assert TICKER_HISTORY_ORIGIN_DATE == REGIME_HISTORY_ORIGIN_DATE


def test_gate10c_production_history_paths_are_versioned_and_asof_scoped() -> None:
    settings = load_settings()
    engine = SplitOriginRegimeStateEngine(settings)
    paths = engine.history_paths(date(2026, 8, 14))
    assert set(paths) == {"market_raw", "market_effective", "sector_raw", "sector_effective"}
    for path in paths.values():
        normalized = path.as_posix()
        assert f"/regimes/history/{REGIME_HISTORY_DATASET_VERSION}/as_of=2026-08-14/" in normalized


def test_gate10c_history_target_classification_is_fail_closed(tmp_path: Path) -> None:
    target = tmp_path / "market_raw.parquet"
    assert _classify_new_target(target, "abc") == "COPY_NEW"
    target.write_bytes(b"accepted")
    import hashlib

    accepted_sha = hashlib.sha256(b"accepted").hexdigest()
    assert _classify_new_target(target, accepted_sha) == "REUSE_EXACT"
    assert _classify_new_target(target, "0" * 64) == "FAIL_UNMANAGED_TARGET"


def test_gate10c_market_manifest_rewrite_allows_paths_only() -> None:
    candidate = {
        "manifest_version": MARKET_SECTOR_MANIFEST_VERSION,
        "dependency_fingerprint": "dep",
        "generated_at_utc": "old",
        "snapshot_path": "/candidate/snapshot.json",
        "snapshot_sha256": "snap",
        "history_files": {
            "market_raw": {"path": "/candidate/market_raw.parquet", "sha256": "a"},
            "sector_raw": {"path": "/candidate/sector_raw.parquet", "sha256": "b"},
        },
    }
    planned = {
        **candidate,
        "snapshot_path": "/production/snapshot.json",
        "history_files": {
            "market_raw": {"path": "/production/market_raw.parquet", "sha256": "a"},
            "sector_raw": {"path": "/production/sector_raw.parquet", "sha256": "b"},
        },
    }
    assert _manifest_rewrite_is_path_only(candidate, planned, market_sector=True)
    planned["dependency_fingerprint"] = "different"
    assert not _manifest_rewrite_is_path_only(candidate, planned, market_sector=True)


def test_gate10c_ticker_manifest_rewrite_allows_snapshot_path_only() -> None:
    candidate = {
        "manifest_version": "ticker-state-manifest-v1-policy-lineage",
        "dependency_fingerprint": "dep",
        "generated_at_utc": "old",
        "snapshot_path": "/candidate/part-000.parquet",
        "snapshot_sha256": "snap",
    }
    planned = {**candidate, "snapshot_path": "/production/part-000.parquet"}
    assert _manifest_rewrite_is_path_only(candidate, planned, market_sector=False)
    planned["snapshot_sha256"] = "different"
    assert not _manifest_rewrite_is_path_only(candidate, planned, market_sector=False)


def test_gate10c_active_build_script_routes_to_split_origin_engine() -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "build_regime_state.py"
    spec = importlib.util.spec_from_file_location("atlas_gate10c_build_regime_state", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.SplitOriginRegimeStateEngine is SplitOriginRegimeStateEngine
    assert "RegimeStateEngine" not in module.__dict__
