from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from packages.backtesting.phase26_observations import (
    Phase26ObservationError,
    add_phase26_derived_fields,
    require_native_bool_checks,
)


def _row(*, ticker: str, close: float, close20: float, vol: float) -> dict[str, object]:
    return {
        "as_of_date": date(2026, 1, 5),
        "ticker": ticker,
        "direction": "bullish",
        "daily_open": close * 0.99,
        "daily_close": close,
        "prior_close": close * 0.98,
        "close_5_sessions_ago": close * 0.95,
        "close_20_sessions_ago": close20,
        "d1_realized_volatility_20": vol,
        "d1_bb_width_20": 0.08,
        "d1_dollar_volume": close * 1_000_000,
        "d1_price_distance_ema_20": 0.05,
        "d1_ema_20_slope_1": 0.01,
        "d1_rsi_14": 60.0,
        "d1_macd_hist_12_26_9": 0.2,
        "d1_range_position_20": 0.8,
        "d1_directional_efficiency_20": 0.5,
        "d1_relative_dollar_volume_20": 1.5,
        "d1_relative_volume_20": 1.4,
        "h4_price_distance_ema_20": 0.03,
        "h1_price_distance_ema_20": 0.02,
        "h1_macd_hist_12_26_9": 0.1,
    }


def test_phase26_derived_fields_use_only_observation_and_lagged_values() -> None:
    frame = pd.DataFrame(
        [
            _row(ticker="AAA", close=110.0, close20=100.0, vol=0.20),
            _row(ticker="BBB", close=105.0, close20=100.0, vol=0.25),
        ]
    )
    result = add_phase26_derived_fields(frame)

    assert result.loc[0, "return_20d"] == pytest.approx(0.10)
    assert result.loc[1, "return_20d"] == pytest.approx(0.05)
    assert result.loc[0, "cs_return_20d_pct"] == 1.0
    assert result.loc[1, "cs_return_20d_pct"] == 0.5
    assert result.loc[0, "vol_scaled_return_20d"] == pytest.approx(0.5)
    assert result.loc[0, "gap_return"] > 0
    assert result.loc[0, "intraday_return"] > 0
    assert result.loc[0, "bull_block_score"] == 5


def test_phase26_cross_sectional_rank_excludes_missing_values() -> None:
    rows = [
        _row(ticker="AAA", close=110.0, close20=100.0, vol=0.20),
        _row(ticker="BBB", close=105.0, close20=100.0, vol=0.25),
        _row(ticker="CCC", close=100.0, close20=100.0, vol=0.30),
    ]
    rows[2]["close_20_sessions_ago"] = None
    result = add_phase26_derived_fields(pd.DataFrame(rows))

    assert pd.isna(result.loc[2, "return_20d"])
    assert pd.isna(result.loc[2, "cs_return_20d_pct"])
    assert result.loc[0, "cs_return_20d_pct"] == 1.0
    assert result.loc[1, "cs_return_20d_pct"] == 0.5


def test_phase26_persisted_checks_reject_numpy_boolean_scalars() -> None:
    with pytest.raises(Phase26ObservationError, match="native Python bool"):
        require_native_bool_checks({"sector_mapping_not_fabricated": np.bool_(True)})


def test_phase26_native_check_map_is_json_serializable() -> None:
    checks = require_native_bool_checks({"first": True, "second": False})
    assert json.loads(json.dumps({"checks": checks})) == {
        "checks": {"first": True, "second": False}
    }
