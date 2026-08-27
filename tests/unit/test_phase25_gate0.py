from __future__ import annotations

from datetime import date

import pytest

from packages.backtesting.phase25_gate0 import (
    ArtifactCoverage,
    Phase25Gate0Error,
    Phase25Gate0Inventory,
)
from packages.backtesting.phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_MARKET_DAILY_ORIGIN,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_PROVIDER_READS,
    PHASE25_PROVIDER_WRITES,
    PHASE25_ROUTE_REPLAY_ORIGIN,
    PHASE25_SECTOR_FABRICATION_ALLOWED,
    PHASE25_STRATEGY_RULE_CHANGES_ALLOWED,
    PHASE25_OUTCOME_DEFINITION_CHANGES_ALLOWED,
)


def test_phase25_gate0_authority_and_origin_are_locked() -> None:
    assert PHASE25_ROUTE_REPLAY_ORIGIN == date(2021, 8, 16)
    assert PHASE25_MARKET_DAILY_ORIGIN == date(2016, 1, 4)
    assert PHASE25_PROVIDER_READS == PHASE25_PROVIDER_WRITES == 0
    assert PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0
    assert PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0
    assert PHASE25_PHASE11_SUPPORT_WRITES == 0
    assert PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0
    assert PHASE25_STRATEGY_RULE_CHANGES_ALLOWED is False
    assert PHASE25_OUTCOME_DEFINITION_CHANGES_ALLOWED is False
    assert PHASE25_SECTOR_FABRICATION_ALLOWED is False


def test_artifact_coverage_preserves_missing_session_dates() -> None:
    sessions = (date(2021, 8, 16), date(2021, 8, 17), date(2021, 8, 18))
    coverage = ArtifactCoverage.from_presence(
        sessions,
        {
            sessions[0]: True,
            sessions[1]: False,
            sessions[2]: True,
        },
    )
    assert coverage.total_sessions == 3
    assert coverage.present_sessions == 2
    assert coverage.missing_sessions == 1
    assert coverage.missing_preview == ("2021-08-17",)


def test_gate0_rejects_through_date_before_locked_origin() -> None:
    inventory = object.__new__(Phase25Gate0Inventory)
    with pytest.raises(Phase25Gate0Error, match="predates Phase25 replay origin"):
        inventory.run(through_date=date(2021, 8, 13))
