from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from packages.backtesting.successor_conditioning_analysis import (
    _selector_assignments_sql,
    build_walk_forward_folds,
    normalization_query,
)
from packages.strategies.successor_conditioning_contract import (
    ACCEPTED_GROUP_COUNT,
    ACCEPTED_STANDALONE_RECORD_COUNT,
    AUTHORITY,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
    successor_conditioning_manifest,
)


def _write_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def test_conditioning_contract_binds_exact_completed_standalone_without_authority() -> None:
    manifest = successor_conditioning_manifest()
    assert len(SUCCESSOR_CONDITIONING_FINGERPRINT) == 64
    assert manifest["accepted_standalone"]["group_count"] == ACCEPTED_GROUP_COUNT == 546
    assert (
        manifest["accepted_standalone"]["record_count"]
        == ACCEPTED_STANDALONE_RECORD_COUNT
        == 54_618_427
    )
    assert manifest["raw_market_data_reread"] is False
    assert manifest["supported_nonpositive_cell_may_fallback"] is False
    assert AUTHORITY["consumed_master_rows_permitted"] == 0
    assert AUTHORITY["future_blind_rows_permitted"] == 0
    assert AUTHORITY["paper_authority"] is False
    assert AUTHORITY["live_authority"] is False
    assert AUTHORITY["selector_promotion"] is False
    assert AUTHORITY["confluence_opened"] is False


def test_daily_normalization_uses_five_session_ten_bps_primary(tmp_path: Path) -> None:
    source = tmp_path / "daily.jsonl"
    _write_jsonl(
        source,
        {
            "route": {
                "policy_id": "daily_policy",
                "economic_family_id": "daily_family",
                "native_timeframe": "1d",
            },
            "signal": {
                "instrument_id": "iid-1",
                "ticker": "AAA",
                "direction": "LONG",
                "universe_eligible": True,
            },
            "outcome": {
                "instrument_id": "iid-1",
                "ticker": "AAA",
                "signal_session": "2020-01-02",
                "direction": "LONG",
                "status": "COMPLETE",
                "gross_directional_returns": {"1": 0.01, "5": 0.03, "20": 0.04},
                "net_directional_returns_by_cost_bps": {
                    "0": {"1": 0.01, "5": 0.03, "20": 0.04},
                    "10": {"1": 0.009, "5": 0.029, "20": 0.039},
                    "25": {"1": 0.0075, "5": 0.0275, "20": 0.0375},
                    "50": {"1": 0.005, "5": 0.025, "20": 0.035},
                    "100": {"1": 0.0, "5": 0.02, "20": 0.03},
                },
                "maximum_favorable_excursion_20": 0.08,
                "maximum_adverse_excursion_20": -0.02,
                "common_context": {
                    "market_direction_alignment": "BULL",
                    "market_volatility_state": "NORMAL",
                    "ticker_relative_strength_vs_spy_short_horizon": 0.04,
                    "ticker_relative_strength_vs_spy_medium_horizon": 0.12,
                    "higher_timeframe_ticker_trend": "BULL",
                    "atr_normalized_trend_maturity_extension": 1.25,
                    "opening_same_time_volume_participation": "UNAVAILABLE_DAILY",
                    "premarket_volume_participation": "UNAVAILABLE_DAILY",
                    "prior_dollar_volume_liquidity": 60_000_000.0,
                    "overnight_gap": 0.03,
                    "price_band": "25_50",
                    "signal_time": "DAILY_CLOSE",
                    "realized_volatility": 0.35,
                    "execution_liquidity_quality": "HIGH",
                },
            },
        },
    )
    con = duckdb.connect()
    try:
        row = con.execute(normalization_query(source, "daily", 1)).fetchdf().iloc[0]
    finally:
        con.close()
    assert row["policy_id"] == "daily_policy"
    assert row["primary_net_return"] == 0.029
    assert row["stress_net_return"] == 0.0275
    assert row["daily_h1_primary"] == 0.009
    assert row["daily_h20_primary"] == 0.039
    assert bool(row["comparable"]) is True
    assert row["relative_strength_20_bucket"] == "P3_TO_P10PCT"
    assert row["relative_strength_63_bucket"] == "GE_P10PCT"
    assert row["liquidity_bucket"] == "50M_TO_250M"
    assert row["signal_time_bucket"] == "DAILY_CLOSE"
    assert row["context_provenance"] == "SUCCESSOR_SHARED"


def test_new_minute_normalization_uses_fifty_bps_primary(tmp_path: Path) -> None:
    source = tmp_path / "minute.jsonl"
    _write_jsonl(
        source,
        {
            "route": {
                "policy_id": "minute_policy",
                "economic_family_id": "minute_family",
                "native_timeframe": "1m",
            },
            "signal": {"symbol": "AAA", "session_date": "2021-02-03", "direction": "LONG"},
            "context": {
                "market_direction_alignment": "UNAVAILABLE",
                "market_volatility_state": "UNAVAILABLE",
                "ticker_relative_strength_vs_spy_short_horizon": None,
                "ticker_relative_strength_vs_spy_medium_horizon": None,
                "higher_timeframe_ticker_trend": "BULL",
                "atr_normalized_trend_maturity_extension": None,
                "opening_same_time_volume_participation": 2.5,
                "premarket_volume_participation": 4.2,
                "prior_dollar_volume_liquidity": 25_000_000.0,
                "overnight_gap": -0.06,
                "price_band": "10_25",
                "signal_time": "09:52:00",
                "realized_volatility": 0.60,
                "execution_liquidity_quality": "MEDIUM",
            },
            "outcome": {
                "symbol": "AAA",
                "session_date": "2021-02-03",
                "direction": "LONG",
                "status": "EXITED",
                "entry_bar_timestamp_utc": "2021-02-03T14:53:00+00:00",
                "exit_bar_timestamp_utc": "2021-02-03T15:23:00+00:00",
                "entry_price": 10.0,
                "stop_price": 9.5,
                "gross_directional_return": 0.02,
                "net_directional_returns_by_cost_bps": {
                    "0": 0.02,
                    "10": 0.019,
                    "25": 0.0175,
                    "50": 0.015,
                    "100": 0.01,
                },
                "maximum_favorable_excursion": 0.04,
                "maximum_adverse_excursion": -0.01,
            },
        },
    )
    con = duckdb.connect()
    try:
        row = con.execute(normalization_query(source, "minute", 1)).fetchdf().iloc[0]
    finally:
        con.close()
    assert row["primary_net_return"] == 0.015
    assert row["stress_net_return"] == 0.01
    assert bool(row["comparable"]) is True
    assert abs(float(row["net_r_primary"]) - 0.3) < 1e-12
    assert row["opening_participation_bucket"] == "2_TO_4"
    assert row["premarket_participation_bucket"] == "GE_4"
    assert row["overnight_gap_magnitude_bucket"] == "5_TO_10PCT"
    assert row["signal_time_bucket"] == "0945_TO_1000"
    assert row["realized_volatility_bucket"] == "50_TO_100PCT"
    assert row["context_provenance"] == "SUCCESSOR_SHARED"


def test_retained_b35_context_is_preserved_without_post_result_reconstruction(tmp_path: Path) -> None:
    source = tmp_path / "legacy.jsonl"
    _write_jsonl(
        source,
        {
            "route": {
                "policy_id": "b34_opening_range_breakout_15m_v1",
                "economic_family_id": "opening_range",
                "native_timeframe": "1m",
            },
            "signal": {"symbol": "BBB", "session_date": "2022-03-04", "direction": "SHORT"},
            "context": {
                "contract": "atlas-b35-development-context-v2-prior-only-split-clock-corrected",
                "prior_market_regime": "UNAVAILABLE",
                "prior_close_price": "20_TO_100",
                "median_dollar_volume_20": "50M_TO_250M",
                "realized_volatility_20": "25_TO_50PCT",
                "prior_trend_20_50": "DOWN",
                "absolute_gap_pct": "2_TO_5PCT",
                "premarket_relvol_20": "2_TO_4",
                "signal_time_et": "0945_TO_1000",
            },
            "outcome": {
                "symbol": "BBB",
                "session_date": "2022-03-04",
                "direction": "SHORT",
                "comparable": True,
                "status": "EXITED",
                "entry_bar_timestamp_utc": "2022-03-04T14:50:00+00:00",
                "exit_bar_timestamp_utc": "2022-03-04T15:20:00+00:00",
                "entry_price": 50.0,
                "stop_price": 51.0,
                "gross_directional_return": 0.01,
                "net_directional_returns_by_cost_bps": {
                    "0": 0.01,
                    "10": 0.009,
                    "25": 0.0075,
                    "50": 0.005,
                    "100": 0.0,
                },
                "maximum_favorable_excursion": 0.02,
                "maximum_adverse_excursion": -0.005,
            },
        },
    )
    con = duckdb.connect()
    try:
        row = con.execute(normalization_query(source, "minute", 1)).fetchdf().iloc[0]
    finally:
        con.close()
    assert row["context_provenance"] == "B35_LEGACY_BUCKETED"
    assert row["higher_timeframe_ticker_trend"] == "BEAR"
    assert row["liquidity_bucket"] == "50M_TO_250M"
    assert row["overnight_gap_magnitude_bucket"] == "2_TO_5PCT"
    assert row["premarket_participation_bucket"] == "2_TO_4"
    assert row["signal_time_bucket"] == "0945_TO_1000"
    assert row["price_band"] == "UNAVAILABLE"
    assert row["relative_strength_20_bucket"] == "UNAVAILABLE"
    assert row["market_volatility_state"] == "UNAVAILABLE"
    assert row["legacy_prior_close_bucket"] == "20_TO_100"


def test_supported_nonpositive_specific_cell_cannot_fallback_to_positive_broader_cell() -> None:
    opportunities = pd.DataFrame(
        [
            {
                "session_date": date(2020, 1, 10),
                "calendar_year": 2020,
                "policy_id": "p",
                "economic_family_id": "f",
                "native_timeframe": "1m",
                "instrument_key": "AAA",
                "ticker": "AAA",
                "direction": "LONG",
                "eligible_opportunity": True,
                "comparable": True,
                "primary_net_return": 0.01,
                "stress_net_return": 0.0,
                "market_direction_alignment": "BULL",
                "market_volatility_state": "NORMAL",
                "higher_timeframe_ticker_trend": "BULL",
                "signal_time_bucket": "0945_TO_1000",
                "liquidity_bucket": "50M_TO_250M",
                "selector_key_1": "specific",
                "selector_key_2": "broader",
                "selector_key_3": "l3",
                "selector_key_4": "l4",
                "selector_key_5": "l5",
            }
        ]
    )
    folds = pd.DataFrame(
        [{"fold_id": 1, "test_start": date(2020, 1, 1), "test_end": date(2020, 1, 31)}]
    )
    scores = pd.DataFrame(
        [
            {
                "fold_id": 1,
                "hierarchy_level": 1,
                "cell_key": "specific",
                "minimum_support": True,
                "score_lcb_primary_net_return": -0.01,
            },
            {
                "fold_id": 1,
                "hierarchy_level": 2,
                "cell_key": "broader",
                "minimum_support": True,
                "score_lcb_primary_net_return": 0.02,
            },
        ]
    )
    con = duckdb.connect()
    try:
        con.register("opportunities", opportunities)
        con.register("folds", folds)
        con.register("selector_scores", scores)
        row = con.execute(_selector_assignments_sql()).fetchdf().iloc[0]
    finally:
        con.close()
    assert int(row["fallback_level"]) == 1
    assert float(row["selector_score"]) == -0.01
    assert bool(row["research_eligible"]) is False


def test_fallback_occurs_only_when_specific_cell_is_unsupported() -> None:
    opportunities = pd.DataFrame(
        [
            {
                "session_date": date(2020, 1, 10),
                "calendar_year": 2020,
                "policy_id": "p",
                "economic_family_id": "f",
                "native_timeframe": "1m",
                "instrument_key": "AAA",
                "ticker": "AAA",
                "direction": "LONG",
                "eligible_opportunity": True,
                "comparable": True,
                "primary_net_return": 0.01,
                "stress_net_return": 0.0,
                "market_direction_alignment": "BULL",
                "market_volatility_state": "NORMAL",
                "higher_timeframe_ticker_trend": "BULL",
                "signal_time_bucket": "0945_TO_1000",
                "liquidity_bucket": "50M_TO_250M",
                "selector_key_1": "specific",
                "selector_key_2": "broader",
                "selector_key_3": "l3",
                "selector_key_4": "l4",
                "selector_key_5": "l5",
            }
        ]
    )
    folds = pd.DataFrame(
        [{"fold_id": 1, "test_start": date(2020, 1, 1), "test_end": date(2020, 1, 31)}]
    )
    scores = pd.DataFrame(
        [
            {
                "fold_id": 1,
                "hierarchy_level": 1,
                "cell_key": "specific",
                "minimum_support": False,
                "score_lcb_primary_net_return": None,
            },
            {
                "fold_id": 1,
                "hierarchy_level": 2,
                "cell_key": "broader",
                "minimum_support": True,
                "score_lcb_primary_net_return": 0.02,
            },
        ]
    )
    con = duckdb.connect()
    try:
        con.register("opportunities", opportunities)
        con.register("folds", folds)
        con.register("selector_scores", scores)
        row = con.execute(_selector_assignments_sql()).fetchdf().iloc[0]
    finally:
        con.close()
    assert int(row["fallback_level"]) == 2
    assert float(row["selector_score"]) == 0.02
    assert bool(row["research_eligible"]) is True


def test_walk_forward_contract_forms_many_nonoverlapping_test_folds() -> None:
    folds = build_walk_forward_folds(date(2016, 1, 4), date(2026, 4, 30))
    assert len(folds) >= 30
    for fold in folds:
        assert fold.train_start <= fold.train_end < fold.embargo_session < fold.test_start <= fold.test_end
