from __future__ import annotations

import pandas as pd

from packages.discovery.directional_score import aggregate_multitimeframe, weighted_available
from packages.discovery.setup_scores import score_timeframe
from packages.discovery.state_machine import DiscoveryStatePolicy
from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState


def _bullish_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "return_1": 0.04,
                "rsi_14": 68.0,
                "true_range": 5.0,
                "atr_14": 2.0,
                "natr_14": 0.02,
                "bb_position_20": 1.05,
                "relative_volume_20": 3.0,
                "relative_dollar_volume_20": 3.2,
                "volume_zscore_20": 3.0,
                "range_position_20": 0.95,
                "breakout_distance_20": 0.03,
                "breakdown_distance_20": 0.40,
                "ema_20_slope_1": 0.01,
                "price_distance_ema_20": 0.04,
                "directional_efficiency_20": 0.80,
            }
        ]
    )


def _bearish_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "return_1": -0.04,
                "rsi_14": 32.0,
                "true_range": 5.0,
                "atr_14": 2.0,
                "natr_14": 0.02,
                "bb_position_20": -0.05,
                "relative_volume_20": 3.0,
                "relative_dollar_volume_20": 3.2,
                "volume_zscore_20": 3.0,
                "range_position_20": 0.05,
                "breakout_distance_20": -0.40,
                "breakdown_distance_20": -0.03,
                "ema_20_slope_1": -0.01,
                "price_distance_ema_20": -0.04,
                "directional_efficiency_20": 0.80,
            }
        ]
    )


def test_vectorized_setup_scores_are_bounded_and_directional() -> None:
    bullish = score_timeframe(_bullish_frame())
    bearish = score_timeframe(_bearish_frame())

    assert bool(bullish.loc[0, "score_input_available"])
    assert bool(bearish.loc[0, "score_input_available"])
    assert bullish.loc[0, "trend_bull"] > bullish.loc[0, "trend_bear"]
    assert bullish.loc[0, "breakout_bull"] > 0.5
    assert bearish.loc[0, "trend_bear"] > bearish.loc[0, "trend_bull"]
    assert bearish.loc[0, "breakdown_bear"] > 0.5

    for frame in (bullish, bearish):
        numeric = frame.drop(columns=["score_input_available"])
        assert numeric.min().min() >= 0.0
        assert numeric.max().max() <= 1.0


def test_multitimeframe_aggregation_renormalizes_missing_timeframes() -> None:
    one_d = score_timeframe(_bullish_frame())
    four_h = one_d.copy()
    one_h = one_d.copy()
    one_h.loc[:, one_h.columns != "score_input_available"] = float("nan")
    one_h["score_input_available"] = False

    aggregate = aggregate_multitimeframe({"1d": one_d, "4h": four_h, "1h": one_h})
    expected = weighted_available({"1d": one_d, "4h": four_h, "1h": one_h}, "trend_bull")
    assert aggregate.loc[0, "trend_bull"] == expected.loc[0]
    assert aggregate.loc[0, "bull_evidence"] > aggregate.loc[0, "bear_evidence"]
    assert aggregate.loc[0, "direction"] == DiscoveryDirection.BULLISH.value
    assert 0.0 <= aggregate.loc[0, "priority_score"] <= 1.0


def test_state_policy_uses_absolute_not_population_caps() -> None:
    policy = DiscoveryStatePolicy()
    assert policy.classify(
        priority_score=0.20,
        bull_evidence=0.20,
        bear_evidence=0.10,
        direction=DiscoveryDirection.BULLISH,
    ) == DiscoveryState.NORMAL
    assert policy.classify(
        priority_score=policy.watch_priority,
        bull_evidence=0.45,
        bear_evidence=0.20,
        direction=DiscoveryDirection.BULLISH,
    ) == DiscoveryState.WATCH
    assert policy.classify(
        priority_score=policy.warm_priority,
        bull_evidence=0.60,
        bear_evidence=0.20,
        direction=DiscoveryDirection.BULLISH,
    ) == DiscoveryState.WARM
    assert policy.classify(
        priority_score=policy.hot_priority,
        bull_evidence=policy.hot_directional_evidence,
        bear_evidence=0.10,
        direction=DiscoveryDirection.BULLISH,
    ) == DiscoveryState.HOT
    assert policy.classify(
        priority_score=0.95,
        bull_evidence=0.80,
        bear_evidence=0.79,
        direction=DiscoveryDirection.NEUTRAL,
    ) != DiscoveryState.HOT
