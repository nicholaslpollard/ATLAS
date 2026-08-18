from __future__ import annotations

import pandas as pd
import pytest

from packages.discovery.directional_score import cross_sectional_tail_strength
from packages.discovery.state_machine import DiscoveryStatePolicy
from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState


def test_cross_sectional_relative_strength_only_rewards_outer_tails() -> None:
    values = pd.Series([-4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0])
    bull, bear = cross_sectional_tail_strength(values, tail_start=0.80)

    assert bull.iloc[-1] == pytest.approx(1.0)
    assert bull.iloc[4] == pytest.approx(0.0)
    assert bear.iloc[0] > 0.0
    assert bear.iloc[4] == pytest.approx(0.0)
    assert bull.iloc[0] == pytest.approx(0.0)
    assert bear.iloc[-1] == pytest.approx(0.0)
    assert int((bull > 0.0).sum()) < len(values) // 2
    assert int((bear > 0.0).sum()) < len(values) // 2


def test_cross_sectional_relative_strength_rejects_non_tail_cutoff() -> None:
    with pytest.raises(ValueError):
        cross_sectional_tail_strength(pd.Series([1.0, 2.0]), tail_start=0.50)


def test_sparse_timeframe_coverage_caps_state_promotion() -> None:
    policy = DiscoveryStatePolicy(
        watch_priority=0.20,
        warm_priority=0.30,
        hot_priority=0.40,
        hot_directional_evidence=0.40,
    )
    kwargs = {
        "priority_score": 0.90,
        "bull_evidence": 0.90,
        "bear_evidence": 0.05,
        "direction": DiscoveryDirection.BULLISH,
    }

    assert policy.classify(**kwargs, scored_timeframes=0) == DiscoveryState.NORMAL
    assert policy.classify(**kwargs, scored_timeframes=1) == DiscoveryState.WATCH
    assert policy.classify(**kwargs, scored_timeframes=2) == DiscoveryState.WARM
    assert policy.classify(**kwargs, scored_timeframes=3) == DiscoveryState.HOT


def test_state_policy_rejects_impossible_timeframe_coverage() -> None:
    with pytest.raises(ValueError):
        DiscoveryStatePolicy().classify(
            priority_score=0.5,
            bull_evidence=0.5,
            bear_evidence=0.1,
            direction=DiscoveryDirection.BULLISH,
            scored_timeframes=4,
        )
