from __future__ import annotations

from datetime import date

import pandas as pd

from packages.core.enums import Timeframe
from packages.features.historical_backfill_feature_state_chain import (
    HistoricalBackfillDailyFeatureStateChain,
    state_chain_year_source_fingerprint,
)
from packages.features.incremental import IncrementalFeatureEngine
from packages.features.state_checkpoint import feature_state_fingerprint


def _canonical(session: str, sha: str) -> dict[str, object]:
    return {
        "session_date": session,
        "relative_path": f"stocks/1d/year={session[:4]}/date={session}/part-000.parquet",
        "sha256": sha,
    }


def test_state_chain_year_fingerprint_is_order_independent_for_sources() -> None:
    values = {
        "gate9c_preflight_source_fingerprint": "gate9c",
        "replay_source_fingerprint": "replay",
        "year": 2021,
        "input_state_fingerprint": "input",
        "expected_output_state_fingerprint": "output",
        "canonical_rows": [_canonical("2021-01-04", "a"), _canonical("2021-01-05", "b")],
        "lifecycle_events": [],
    }
    first = state_chain_year_source_fingerprint(**values)
    reversed_values = dict(values)
    reversed_values["canonical_rows"] = list(reversed(values["canonical_rows"]))
    assert state_chain_year_source_fingerprint(**reversed_values) == first


def test_state_chain_year_fingerprint_binds_expected_output_checkpoint() -> None:
    values = {
        "gate9c_preflight_source_fingerprint": "gate9c",
        "replay_source_fingerprint": "replay",
        "year": 2021,
        "input_state_fingerprint": "input",
        "expected_output_state_fingerprint": "output",
        "canonical_rows": [_canonical("2021-01-04", "a")],
        "lifecycle_events": [],
    }
    baseline = state_chain_year_source_fingerprint(**values)
    changed = dict(values)
    changed["expected_output_state_fingerprint"] = "changed"
    assert state_chain_year_source_fingerprint(**changed) != baseline


def test_state_only_update_matches_direct_incremental_state() -> None:
    bars = pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "timestamp_utc": pd.Timestamp("2021-01-04T14:30:00Z"),
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 1_000.0,
            },
            {
                "symbol": "SPY",
                "timestamp_utc": pd.Timestamp("2021-01-05T14:30:00Z"),
                "high": 103.0,
                "low": 100.0,
                "close": 102.0,
                "volume": 1_200.0,
            },
        ]
    )
    via_helper = IncrementalFeatureEngine()
    HistoricalBackfillDailyFeatureStateChain._update_state(via_helper, bars)

    direct = IncrementalFeatureEngine()
    for row in bars.itertuples(index=False):
        direct.update(
            symbol="SPY",
            state_key="SPY",
            timestamp_utc=row.timestamp_utc,
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )

    as_of = date(2021, 1, 5).isoformat()
    assert feature_state_fingerprint(
        via_helper, timeframe=Timeframe.DAY_1, as_of_date=as_of
    ) == feature_state_fingerprint(direct, timeframe=Timeframe.DAY_1, as_of_date=as_of)
