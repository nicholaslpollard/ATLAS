from __future__ import annotations

from packages.discovery.persistence import DiscoveryPersistencePolicy
from packages.discovery.state_machine import ACTIVE_DISCOVERY_STATE_POLICY
from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState


def test_locked_absolute_thresholds_match_calibration_contract() -> None:
    policy = ACTIVE_DISCOVERY_STATE_POLICY
    assert policy.watch_priority == 0.35
    assert policy.warm_priority == 0.50
    assert policy.hot_priority == 0.60
    assert policy.hot_directional_evidence == 0.50

    assert policy.classify(
        priority_score=0.349,
        bull_evidence=0.30,
        bear_evidence=0.10,
        direction=DiscoveryDirection.BULLISH,
        scored_timeframes=3,
    ) == DiscoveryState.NORMAL
    assert policy.classify(
        priority_score=0.35,
        bull_evidence=0.30,
        bear_evidence=0.10,
        direction=DiscoveryDirection.BULLISH,
        scored_timeframes=3,
    ) == DiscoveryState.WATCH
    assert policy.classify(
        priority_score=0.50,
        bull_evidence=0.40,
        bear_evidence=0.10,
        direction=DiscoveryDirection.BULLISH,
        scored_timeframes=3,
    ) == DiscoveryState.WARM
    assert policy.classify(
        priority_score=0.60,
        bull_evidence=0.50,
        bear_evidence=0.10,
        direction=DiscoveryDirection.BULLISH,
        scored_timeframes=3,
    ) == DiscoveryState.HOT


def test_bootstrap_requires_warm_confirmation_but_hot_is_immediate() -> None:
    policy = DiscoveryPersistencePolicy()
    effective, warm_streak, demotion_streak, transition = policy.bootstrap(
        raw_state=DiscoveryState.WARM,
        scored_timeframes=3,
    )
    assert effective == DiscoveryState.WATCH
    assert warm_streak == 1
    assert demotion_streak == 0
    assert transition == "bootstrap_warm_pending"

    effective, warm_streak, demotion_streak, transition = policy.bootstrap(
        raw_state=DiscoveryState.HOT,
        scored_timeframes=3,
    )
    assert effective == DiscoveryState.HOT
    assert warm_streak == 0
    assert demotion_streak == 0
    assert transition == "bootstrap_hot"


def test_warm_requires_two_consecutive_qualifying_observations() -> None:
    policy = DiscoveryPersistencePolicy()
    first = policy.transition(
        previous_effective_state=DiscoveryState.WATCH,
        previous_warm_confirmation_streak=0,
        previous_demotion_streak=0,
        raw_state=DiscoveryState.WARM,
        scored_timeframes=3,
    )
    assert first == (DiscoveryState.WATCH, 1, 0, "warm_confirmation_pending")

    second = policy.transition(
        previous_effective_state=first[0],
        previous_warm_confirmation_streak=first[1],
        previous_demotion_streak=first[2],
        raw_state=DiscoveryState.WARM,
        scored_timeframes=3,
    )
    assert second == (DiscoveryState.WARM, 0, 0, "promote_warm")


def test_hot_promotion_is_immediate_and_demotion_needs_two_observations() -> None:
    policy = DiscoveryPersistencePolicy()
    hot = policy.transition(
        previous_effective_state=DiscoveryState.NORMAL,
        previous_warm_confirmation_streak=0,
        previous_demotion_streak=0,
        raw_state=DiscoveryState.HOT,
        scored_timeframes=3,
    )
    assert hot == (DiscoveryState.HOT, 0, 0, "promote_hot")

    pending = policy.transition(
        previous_effective_state=hot[0],
        previous_warm_confirmation_streak=hot[1],
        previous_demotion_streak=hot[2],
        raw_state=DiscoveryState.WARM,
        scored_timeframes=3,
    )
    assert pending == (DiscoveryState.HOT, 0, 1, "demotion_pending")

    demoted = policy.transition(
        previous_effective_state=pending[0],
        previous_warm_confirmation_streak=pending[1],
        previous_demotion_streak=pending[2],
        raw_state=DiscoveryState.WARM,
        scored_timeframes=3,
    )
    assert demoted == (DiscoveryState.WARM, 0, 0, "demote_hot_to_warm")


def test_coverage_loss_caps_effective_state_immediately() -> None:
    policy = DiscoveryPersistencePolicy()
    result = policy.transition(
        previous_effective_state=DiscoveryState.HOT,
        previous_warm_confirmation_streak=0,
        previous_demotion_streak=0,
        raw_state=DiscoveryState.WARM,
        scored_timeframes=2,
    )
    assert result == (DiscoveryState.WARM, 0, 0, "coverage_cap")

    result = policy.transition(
        previous_effective_state=DiscoveryState.WARM,
        previous_warm_confirmation_streak=0,
        previous_demotion_streak=0,
        raw_state=DiscoveryState.WATCH,
        scored_timeframes=1,
    )
    assert result == (DiscoveryState.WATCH, 0, 0, "coverage_cap")
