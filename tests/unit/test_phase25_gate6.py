from __future__ import annotations

from datetime import date

import pytest

from packages.backtesting.phase25_gate6 import Phase25Gate6Error, _pair_state
from packages.backtesting.phase25_gate6_policy import (
    ACCEPTED_GATE5_POLICY_FINGERPRINT,
    PHASE25_GATE6_DISCOVERY_OVERRIDES_ALLOWED,
    PHASE25_GATE6_OPERATIONAL_DISCOVERY_STATE_WRITES_ALLOWED,
    PHASE25_GATE6_OVERWRITE_EXISTING_ARTIFACTS_ALLOWED,
    PHASE25_GATE6_PROVIDER_READS,
    PHASE25_GATE6_PROVIDER_WRITES,
    PHASE25_GATE6_REGIME_ROUTING_ALLOWED,
    PHASE25_GATE6_STRATEGY_RETURNS_READ_ALLOWED,
    PHASE25_GATE6_STRATEGY_RULE_EVALUATION_ALLOWED,
    PHASE25_GATE6_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate6_policy_fingerprint,
)
from packages.backtesting.phase25_gate5_policy import phase25_gate5_policy_fingerprint
from packages.discovery.persistence import ACTIVE_DISCOVERY_PERSISTENCE_POLICY
from packages.schemas.discovery_score import DiscoveryState


def test_gate6_freezes_gate5_and_has_zero_external_authority() -> None:
    assert ACCEPTED_GATE5_POLICY_FINGERPRINT == "0e2060d91838c506d8b7c720fd38c06186dac8e4b4587385079b49cae519b8a0"
    assert phase25_gate5_policy_fingerprint() == ACCEPTED_GATE5_POLICY_FINGERPRINT
    assert len(phase25_gate6_policy_fingerprint()) == 64
    assert PHASE25_GATE6_PROVIDER_READS == PHASE25_GATE6_PROVIDER_WRITES == 0
    assert PHASE25_GATE6_OVERWRITE_EXISTING_ARTIFACTS_ALLOWED is False
    assert PHASE25_GATE6_OPERATIONAL_DISCOVERY_STATE_WRITES_ALLOWED is False
    assert PHASE25_GATE6_DISCOVERY_OVERRIDES_ALLOWED is False
    assert PHASE25_GATE6_STRATEGY_RETURNS_READ_ALLOWED is False
    assert PHASE25_GATE6_REGIME_ROUTING_ALLOWED is False
    assert PHASE25_GATE6_STRATEGY_RULE_EVALUATION_ALLOWED is False
    assert PHASE25_GATE6_SUPPORT_REPLACEMENT_ALLOWED is False


def test_gate6_pair_state_fails_closed_on_partial_artifacts(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert _pair_state((first, second), label="test", session=date(2021, 8, 16)) is False
    first.write_text("x", encoding="utf-8")
    with pytest.raises(Phase25Gate6Error):
        _pair_state((first, second), label="test", session=date(2021, 8, 16))
    second.write_text("y", encoding="utf-8")
    assert _pair_state((first, second), label="test", session=date(2021, 8, 16)) is True


def test_gate6_uses_accepted_discovery_hysteresis_semantics() -> None:
    policy = ACTIVE_DISCOVERY_PERSISTENCE_POLICY
    effective, warm_streak, demotion_streak, transition = policy.bootstrap(
        raw_state=DiscoveryState.WARM,
        scored_timeframes=3,
    )
    assert effective == DiscoveryState.WATCH
    assert warm_streak == 1
    assert demotion_streak == 0
    assert transition == "bootstrap_warm_pending"

    effective, warm_streak, demotion_streak, transition = policy.transition(
        previous_effective_state=DiscoveryState.WATCH,
        previous_warm_confirmation_streak=1,
        previous_demotion_streak=0,
        raw_state=DiscoveryState.WARM,
        scored_timeframes=3,
    )
    assert effective == DiscoveryState.WARM
    assert warm_streak == 0
    assert demotion_streak == 0
    assert transition == "promote_warm"
