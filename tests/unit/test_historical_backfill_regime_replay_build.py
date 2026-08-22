from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from packages.regimes.historical_backfill_regime_replay import (
    GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN,
    GATE10_TICKER_ORIGIN,
)
from packages.regimes.historical_backfill_regime_replay_build import (
    GATE10_MARKET_SECTOR_MANIFEST_VERSION,
    GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION,
    GATE10_SPLIT_ORIGIN_POLICY_VERSION,
    _IsolatedTickerStateEngine,
    _frame_key_unique,
    _stable_hash,
)
from packages.regimes.historical_backfill_regime_replay_validation import (
    GATE10_REGIME_REPLAY_VALIDATION_CONTRACT_VERSION,
    _frames_equal,
)
from packages.regimes.ticker_state_engine import (
    TICKER_STATE_POLICY_CONTRACT_VERSION,
    TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
)


def test_gate10b_split_origin_contracts_are_explicit() -> None:
    assert GATE10_SPLIT_ORIGIN_POLICY_VERSION == (
        "historical-backfill-regime-split-policy-v1-market-sector-daily-2016-ticker-intraday-2021"
    )
    assert GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION == (
        "regime-state-policy-v2-expanding252-confirm2-dimensional-daily-origin-2016"
    )
    assert GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION == (
        "regime-state-snapshot-v2-market-sector-proxies-daily-origin-2016"
    )
    assert GATE10_MARKET_SECTOR_MANIFEST_VERSION == (
        "regime-state-manifest-v2-split-origin-source-lineage"
    )


def test_gate10b_build_and_validation_contracts_are_versioned() -> None:
    assert GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION == (
        "historical-backfill-regime-replay-v1-isolated-split-origin"
    )
    assert GATE10_REGIME_REPLAY_VALIDATION_CONTRACT_VERSION == (
        "historical-backfill-regime-replay-validation-v1-independent-disk-recompute-and-ticker-rebuild"
    )


def test_gate10b_market_sector_origin_precedes_locked_ticker_origin() -> None:
    assert GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN == date(2016, 1, 4)
    assert GATE10_TICKER_ORIGIN == date(2021, 8, 16)
    assert GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN < GATE10_TICKER_ORIGIN


def test_gate10b_does_not_version_bump_ticker_semantics() -> None:
    assert TICKER_STATE_POLICY_CONTRACT_VERSION == (
        "ticker-state-policy-v1-confirm2-dimensional-risk126-60"
    )
    assert TICKER_STATE_SNAPSHOT_CONTRACT_VERSION == (
        "ticker-state-snapshot-v1-routed-identity-persistence-risk"
    )


def test_gate10b_stable_hash_is_order_independent_and_sensitive() -> None:
    first = _stable_hash({"origin": "2016-01-04", "ticker": "2021-08-16"})
    second = _stable_hash({"ticker": "2021-08-16", "origin": "2016-01-04"})
    changed = _stable_hash({"origin": "2016-01-05", "ticker": "2021-08-16"})
    assert first == second
    assert first != changed
    assert len(first) == 64


def test_gate10b_frame_key_uniqueness_is_fail_closed() -> None:
    unique = pd.DataFrame({"symbol": ["XLB", "XLE"], "trading_date": [date(2026, 8, 14)] * 2})
    duplicate = pd.concat([unique, unique.iloc[[0]]], ignore_index=True)
    assert _frame_key_unique(unique, ["symbol", "trading_date"])
    assert not _frame_key_unique(duplicate, ["symbol", "trading_date"])


def test_gate10b_validation_frame_compare_normalizes_dates_and_small_float_noise() -> None:
    left = pd.DataFrame(
        {
            "symbol": ["XLB"],
            "trading_date": [date(2026, 8, 14)],
            "score": [0.5],
            "state": ["BULL"],
        }
    )
    right = pd.DataFrame(
        {
            "symbol": ["XLB"],
            "trading_date": [pd.Timestamp("2026-08-14", tz="UTC")],
            "score": [0.5 + 1e-13],
            "state": ["BULL"],
        }
    )
    assert _frames_equal(left, right, order_by=["symbol", "trading_date"])


def test_gate10b_validation_frame_compare_rejects_semantic_change() -> None:
    left = pd.DataFrame({"instrument_id": ["i1"], "effective_ticker_state": ["UPTREND"]})
    right = pd.DataFrame({"instrument_id": ["i1"], "effective_ticker_state": ["DOWNTREND"]})
    assert not _frames_equal(left, right, order_by=["instrument_id"])


def test_gate10b_isolated_ticker_engine_overrides_only_output_paths() -> None:
    engine = object.__new__(_IsolatedTickerStateEngine)
    engine._output_snapshot_path = Path("candidate/ticker.parquet")
    engine._output_manifest_path = Path("candidate/ticker.json")
    assert engine.snapshot_path(date(2026, 8, 14)) == Path("candidate/ticker.parquet")
    assert engine.manifest_path(date(2026, 8, 14)) == Path("candidate/ticker.json")
