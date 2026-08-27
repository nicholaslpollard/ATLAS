from __future__ import annotations

import pandas as pd
import pytest

from packages.backtesting.phase26_policy import PHASE26_CANDIDATES, SignalCondition
from packages.backtesting.phase26_signals import (
    Phase26SignalError,
    apply_composite_scores,
    candidate_mask,
    condition_mask,
)


def _base_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "direction": ["bullish", "bearish"],
            "d1_price_distance_ema_20": [0.05, -0.05],
            "d1_ema_20_slope_1": [0.01, -0.01],
            "d1_rsi_14": [60.0, 35.0],
            "d1_macd_hist_12_26_9": [0.2, -0.2],
            "d1_range_position_20": [0.8, 0.2],
            "d1_directional_efficiency_20": [0.5, 0.5],
            "d1_relative_dollar_volume_20": [1.5, 1.5],
            "d1_relative_volume_20": [1.4, 1.4],
            "h4_price_distance_ema_20": [0.03, -0.03],
            "h1_price_distance_ema_20": [0.02, -0.02],
            "h1_macd_hist_12_26_9": [0.1, -0.1],
        }
    )


def test_condition_mask_between_is_inclusive_and_missing_values_fail_closed() -> None:
    frame = pd.DataFrame({"x": [1.0, 2.0, 3.0, None]})
    mask = condition_mask(frame, SignalCondition("x", "BETWEEN", 1.0, 2.0))
    assert mask.tolist() == [True, True, False, False]


def test_condition_mask_rejects_missing_feature() -> None:
    with pytest.raises(Phase26SignalError, match="missing Phase26 signal field"):
        condition_mask(pd.DataFrame({"x": [1.0]}), SignalCondition("y", "GT", 0.0))


def test_bull_and_bear_composites_are_independently_directional() -> None:
    scored = apply_composite_scores(_base_frame())
    assert scored.loc[0, "bull_block_score"] == 5
    assert scored.loc[0, "bear_block_score"] == 1
    assert scored.loc[1, "bear_block_score"] == 5
    assert scored.loc[1, "bull_block_score"] == 1


def test_candidate_mask_enforces_discovery_direction_before_conditions() -> None:
    candidate = next(item for item in PHASE26_CANDIDATES if item.candidate_id == "composite_long_quality5_lowvol")
    frame = _base_frame()
    frame["bull_block_score"] = [5, 5]
    frame["d1_natr_14"] = [0.03, 0.03]
    mask = candidate_mask(frame, candidate)
    assert mask.tolist() == [True, False]
