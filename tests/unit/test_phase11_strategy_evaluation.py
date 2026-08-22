from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from packages.backtesting.outcomes import strategy_outcome
from packages.backtesting.strategy_evaluation import StrategyEvaluationEngine
from packages.data.duckdb_connection import connect_utc
from packages.schemas.strategy import StrategyDirection


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "session_date": date(2024, 1, 2),
                "instrument_id": "i1",
                "symbol": "AAA",
                "forward_return": 0.03,
                "market_regime_composite": "BULL",
                "observation_close": 110.0,
                "ema_20": 105.0,
                "ema_50": 100.0,
                "ema_20_slope_1": 0.5,
                "macd_hist_12_26_9": 0.2,
            },
            {
                "session_date": date(2024, 2, 2),
                "instrument_id": "i2",
                "symbol": "BBB",
                "forward_return": 0.04,
                "market_regime_composite": "BEAR",
                "observation_close": 110.0,
                "ema_20": 105.0,
                "ema_50": 100.0,
                "ema_20_slope_1": 0.5,
                "macd_hist_12_26_9": 0.2,
            },
            {
                "session_date": date(2025, 1, 2),
                "instrument_id": "i3",
                "symbol": "CCC",
                "forward_return": 0.02,
                "market_regime_composite": "BULL",
                "observation_close": 110.0,
                "ema_20": 105.0,
                "ema_50": 100.0,
                "ema_20_slope_1": -0.5,
                "macd_hist_12_26_9": 0.2,
            },
            {
                "session_date": date(2025, 2, 2),
                "instrument_id": "i4",
                "symbol": "DDD",
                "forward_return": -0.01,
                "market_regime_composite": None,
                "observation_close": 110.0,
                "ema_20": 105.0,
                "ema_50": 100.0,
                "ema_20_slope_1": 0.5,
                "macd_hist_12_26_9": 0.2,
            },
        ]
    )


def test_direction_adjusted_outcome_and_costs() -> None:
    long = strategy_outcome(0.02, StrategyDirection.LONG)
    short = strategy_outcome(0.02, StrategyDirection.SHORT)
    assert long.directional_return == 0.02
    assert short.directional_return == -0.02
    assert long.net_return(10.0) == pytest.approx(0.019)
    with pytest.raises(ValueError):
        long.net_return(-1.0)


def test_strategy_evaluation_counts_fired_and_regime_routed_rows() -> None:
    con = connect_utc(":memory:")
    try:
        con.register("study", _frame())
        summary = StrategyEvaluationEngine().evaluate_source(
            con,
            source_sql="study",
            strategy_id="trend_following_long_v1",
            cost_grid_bps=(0.0, 10.0),
        )
    finally:
        con.close()

    assert summary.source_rows == 4
    assert summary.fired_rows == 3
    assert summary.routed_rows == 2
    raw = summary.aggregate_by_cost_bps["0"]
    assert raw.rows == 2
    assert raw.mean_return == pytest.approx(0.01)
    assert raw.positive_rate == pytest.approx(0.5)
    net10 = summary.aggregate_by_cost_bps["10"]
    assert net10.mean_return == pytest.approx(0.009)
    assert set(summary.by_year) == {"2024", "2025"}
    assert set(summary.by_market_regime) == {"BULL", "UNAVAILABLE"}


def test_strategy_evaluation_date_bounds_are_applied() -> None:
    con = connect_utc(":memory:")
    try:
        con.register("study", _frame())
        summary = StrategyEvaluationEngine().evaluate_source(
            con,
            source_sql="study",
            strategy_id="trend_following_long_v1",
            cost_grid_bps=(0.0,),
            start_date="2025-01-01",
            end_date="2025-12-31",
        )
    finally:
        con.close()
    assert summary.source_rows == 2
    assert summary.fired_rows == 1
    assert summary.routed_rows == 1
    assert summary.aggregate_by_cost_bps["0"].mean_return == pytest.approx(-0.01)


def test_short_strategy_flips_forward_return_direction() -> None:
    frame = pd.DataFrame(
        [
            {
                "session_date": date(2025, 1, 2),
                "instrument_id": "i1",
                "symbol": "AAA",
                "forward_return": -0.03,
                "market_regime_composite": "BEAR",
                "observation_close": 90.0,
                "ema_20": 95.0,
                "ema_50": 100.0,
                "ema_20_slope_1": -0.5,
                "macd_hist_12_26_9": -0.2,
            }
        ]
    )
    con = connect_utc(":memory:")
    try:
        con.register("study", frame)
        summary = StrategyEvaluationEngine().evaluate_source(
            con,
            source_sql="study",
            strategy_id="trend_following_short_v1",
            cost_grid_bps=(0.0,),
        )
    finally:
        con.close()
    assert summary.routed_rows == 1
    assert summary.aggregate_by_cost_bps["0"].mean_return == pytest.approx(0.03)
