from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.schemas.strategy import StrategyDirection
from packages.schemas.strategy_policy import (
    StrategyAuthority,
    StrategyAuthorityRecord,
    StrategyExecutionEnvironment,
)
from packages.strategies.reference_library import (
    REFERENCE_STRATEGY_AUTHORITIES,
    REFERENCE_STRATEGY_AUTHORITY_FINGERPRINT,
    REFERENCE_STRATEGY_CATALOG,
    REFERENCE_STRATEGY_POLICY_FINGERPRINT,
    reference_authority_fingerprint,
)
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY


def test_reference_catalog_freezes_six_families_and_nine_directional_policies() -> None:
    specifications = REFERENCE_STRATEGY_CATALOG.all()
    assert len(specifications) == 9
    assert len(REFERENCE_STRATEGY_CATALOG.family_ids()) == 6
    assert REFERENCE_STRATEGY_CATALOG.fingerprint() == REFERENCE_STRATEGY_POLICY_FINGERPRINT
    assert reference_authority_fingerprint() == REFERENCE_STRATEGY_AUTHORITY_FINGERPRINT
    assert {item.direction for item in specifications} == {
        StrategyDirection.LONG,
        StrategyDirection.SHORT,
    }
    assert len(DEFAULT_STRATEGY_REGISTRY.all()) == 8


def test_reference_policies_are_complete_research_replay_only_contracts() -> None:
    by_id = {item.strategy_id: item for item in REFERENCE_STRATEGY_AUTHORITIES}
    assert set(by_id) == {item.strategy_id for item in REFERENCE_STRATEGY_CATALOG.all()}
    for specification in REFERENCE_STRATEGY_CATALOG.all():
        authority = by_id[specification.strategy_id]
        assert authority.strategy_policy_fingerprint == specification.fingerprint()
        assert authority.authority == StrategyAuthority.RESEARCH
        assert authority.allowed_environments == (StrategyExecutionEnvironment.RESEARCH_REPLAY,)
        assert authority.operational_paper_is_qualifying is False
        assert authority.explicit_live_operator_enable is False
        assert specification.costs.round_trip_cost_grid_bps == (0.0, 5.0, 10.0, 25.0, 50.0)
        assert specification.costs.primary_cost_bps == 10.0
        assert specification.costs.stress_cost_bps == 25.0
        assert specification.execution.broker_writes == 0
        assert specification.execution.paper_submits == 0
        assert specification.execution.live_writes == 0


def test_qualifying_paper_and_live_fail_closed_without_required_authority() -> None:
    specification = REFERENCE_STRATEGY_CATALOG.get("ma_trend_cross_50_200_long_v1")
    common = dict(
        strategy_id=specification.strategy_id,
        strategy_policy_fingerprint=specification.fingerprint(),
        evidence_references=("test",),
    )
    with pytest.raises(ValidationError, match="qualifying PAPER requires historical validation"):
        StrategyAuthorityRecord(
            **common,
            authority=StrategyAuthority.RESEARCH,
            allowed_environments=(StrategyExecutionEnvironment.QUALIFYING_PAPER,),
        )
    with pytest.raises(ValidationError, match="LIVE permission requires LIVE_ELIGIBLE"):
        StrategyAuthorityRecord(
            **common,
            authority=StrategyAuthority.PAPER_VALIDATED,
            allowed_environments=(StrategyExecutionEnvironment.LIVE,),
            explicit_live_operator_enable=True,
        )
    with pytest.raises(ValidationError, match="explicit operator enable"):
        StrategyAuthorityRecord(
            **common,
            authority=StrategyAuthority.LIVE_ELIGIBLE,
            allowed_environments=(StrategyExecutionEnvironment.LIVE,),
        )


def test_short_policies_disclose_unmodeled_borrow_boundary() -> None:
    shorts = [
        item for item in REFERENCE_STRATEGY_CATALOG.all() if item.direction == StrategyDirection.SHORT
    ]
    assert len(shorts) == 3
    assert all(any("borrow" in limitation for limitation in item.limitations) for item in shorts)
