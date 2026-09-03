from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from packages.schemas.opportunity_ledger import OpportunityEvent, OpportunityEventType
from packages.schemas.strategy import StrategyFamily
from packages.schemas.strategy_lab import (
    ResearchStrategyFamily,
    StrategyAuthority,
    StrategyEvidenceSource,
    StrategyExecutionMode,
    execution_mode_permitted,
    validate_authority_transition,
)
from packages.strategies.research_catalog import DEFAULT_REFERENCE_SPECIFICATION_REGISTRY


def _event(**overrides: object) -> OpportunityEvent:
    payload: dict[str, object] = {
        "opportunity_id": "opp-1",
        "sequence": 0,
        "occurred_at": datetime(2026, 9, 2, 20, 0, tzinfo=timezone.utc),
        "signal_session": "2026-09-02",
        "instrument_id": "figi:TEST",
        "symbol": "TEST",
        "strategy_id": "ma_trend_cross_50_200_long_v1",
        "strategy_version": "1",
        "strategy_authority": StrategyAuthority.RESEARCH,
        "execution_mode": StrategyExecutionMode.HISTORICAL_REPLAY,
        "event_type": OpportunityEventType.FIRED,
        "reason_codes": ("signal_transition",),
        "data_version": "data-v1",
        "feature_version": "features-v1",
        "strategy_code_version": "strategy-code-v1",
        "cost_model_version": "cost-v1",
        "risk_model_version": "risk-v1",
    }
    payload.update(overrides)
    return OpportunityEvent.model_validate(payload)


def test_a33_reference_catalog_contains_exact_six_starting_specs() -> None:
    specifications = DEFAULT_REFERENCE_SPECIFICATION_REGISTRY.all()
    assert {item.strategy_id for item in specifications} == {
        "ma_trend_cross_50_200_long_v1",
        "ema_pullback_20_50_long_v1",
        "macd_shift_12_26_9_v1",
        "rsi_recovery_14_trend_long_v1",
        "donchian_breakout_20_volume_v1",
        "bollinger_squeeze_breakout_20_v1",
    }
    assert len(specifications) == 6
    assert len(DEFAULT_REFERENCE_SPECIFICATION_REGISTRY.fingerprint()) == 64
    assert all(item.evidence_source == StrategyEvidenceSource.PRACTITIONER_BASELINE for item in specifications)
    assert all(item.authority == StrategyAuthority.RESEARCH for item in specifications)
    assert all(item.governed_performance_accessed is False for item in specifications)
    assert all(item.outcome_access_permitted is False for item in specifications)


def test_a33_research_family_catalog_expands_without_mutating_phase11_runtime_enum() -> None:
    assert {item.value for item in StrategyFamily} == {
        "trend_following",
        "momentum",
        "breakout",
        "pullback",
    }
    assert ResearchStrategyFamily.MEAN_REVERSION.value == "mean_reversion"
    assert ResearchStrategyFamily.VOLATILITY_EXPANSION.value == "volatility_expansion"
    assert ResearchStrategyFamily.PAIRS_SPREAD.value == "pairs_spread"
    assert ResearchStrategyFamily.EVENT_DRIVEN.value == "event_driven"


def test_a33_pre_outcome_blockers_prevent_performance_access() -> None:
    specification = DEFAULT_REFERENCE_SPECIFICATION_REGISTRY.get("ema_pullback_20_50_long_v1")
    assert specification.pre_outcome_blockers
    invalid = specification.model_copy(update={"outcome_access_permitted": True}).model_dump()
    with pytest.raises(ValidationError):
        specification.__class__.model_validate(invalid)


def test_a33_authority_promotions_are_sequential_and_evidence_bound() -> None:
    validate_authority_transition(
        StrategyAuthority.RESEARCH,
        StrategyAuthority.CANDIDATE,
        evidence_id="candidate-acceptance-v1",
    )
    with pytest.raises(ValueError):
        validate_authority_transition(
            StrategyAuthority.RESEARCH,
            StrategyAuthority.HISTORICALLY_VALIDATED,
            evidence_id="skip",
        )
    with pytest.raises(ValueError):
        validate_authority_transition(
            StrategyAuthority.RESEARCH,
            StrategyAuthority.CANDIDATE,
            evidence_id=None,
        )


def test_a33_execution_modes_keep_operational_paper_separate_from_qualification() -> None:
    assert execution_mode_permitted(StrategyAuthority.RESEARCH, StrategyExecutionMode.HISTORICAL_REPLAY)
    assert execution_mode_permitted(StrategyAuthority.RESEARCH, StrategyExecutionMode.OPERATIONAL_PAPER)
    assert not execution_mode_permitted(StrategyAuthority.RESEARCH, StrategyExecutionMode.QUALIFYING_PAPER)
    assert not execution_mode_permitted(StrategyAuthority.PAPER_VALIDATED, StrategyExecutionMode.LIVE)
    assert execution_mode_permitted(StrategyAuthority.LIVE_ELIGIBLE, StrategyExecutionMode.LIVE)


def test_b33_opportunity_event_requires_explicit_versions_and_aware_time() -> None:
    event = _event()
    assert event.event_type == OpportunityEventType.FIRED
    assert event.strategy_authority == StrategyAuthority.RESEARCH
    with pytest.raises(ValidationError):
        _event(occurred_at=datetime(2026, 9, 2, 20, 0))


def test_b33_counterfactuals_can_be_recorded_but_never_filled() -> None:
    shadow = _event(
        event_type=OpportunityEventType.SHADOW_COUNTERFACTUAL,
        is_counterfactual=True,
    )
    assert shadow.is_counterfactual is True
    with pytest.raises(ValidationError):
        _event(
            event_type=OpportunityEventType.FILLED,
            is_counterfactual=True,
        )


def test_b33_qualifying_and_live_events_fail_closed_on_insufficient_authority() -> None:
    with pytest.raises(ValidationError):
        _event(execution_mode=StrategyExecutionMode.QUALIFYING_PAPER)
    with pytest.raises(ValidationError):
        _event(execution_mode=StrategyExecutionMode.LIVE)
