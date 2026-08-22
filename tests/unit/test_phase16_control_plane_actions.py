from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.schemas.control_plane import (
    ControlPlaneActionKind,
    ControlPlaneActionRequest,
    ControlPlaneConfirmationGrant,
    ControlPlaneConfirmationScope,
    confirmation_matches_request,
    required_confirmation_scope,
)
from packages.schemas.execution import BrokerName, ExecutionEnvironment


NOW = datetime(2026, 8, 22, 20, 50, tzinfo=UTC)


def _request(
    action_kind: ControlPlaneActionKind,
    *,
    broker: BrokerName,
    environment: ExecutionEnvironment,
) -> ControlPlaneActionRequest:
    return ControlPlaneActionRequest(
        action_id="action-001",
        action_kind=action_kind,
        requested_at_utc=NOW,
        idempotency_key="idem-action-001",
        target_broker=broker,
        environment=environment,
    )


def test_live_environment_is_rejected_at_control_plane_contract() -> None:
    with pytest.raises(ValidationError):
        _request(
            ControlPlaneActionKind.EXECUTE_PAPER,
            broker=BrokerName.WEBULL,
            environment=ExecutionEnvironment.LIVE,
        )


def test_broker_switch_requires_explicit_target_and_nonlive_environment() -> None:
    request = _request(
        ControlPlaneActionKind.BROKER_SWITCH,
        broker=BrokerName.ALPACA,
        environment=ExecutionEnvironment.PAPER,
    )
    assert request.explicit_user_request is True
    assert request.target_broker == BrokerName.ALPACA
    assert required_confirmation_scope(request.action_kind) == ControlPlaneConfirmationScope.BROKER_SWITCH


def test_shadow_execution_does_not_require_destructive_confirmation() -> None:
    request = _request(
        ControlPlaneActionKind.EXECUTE_SHADOW,
        broker=BrokerName.SHADOW,
        environment=ExecutionEnvironment.SHADOW,
    )
    assert required_confirmation_scope(request.action_kind) is None


def test_paper_execution_requires_action_bound_confirmation() -> None:
    request = _request(
        ControlPlaneActionKind.EXECUTE_PAPER,
        broker=BrokerName.WEBULL,
        environment=ExecutionEnvironment.PAPER,
    )
    grant = ControlPlaneConfirmationGrant(
        grant_id="grant-001",
        action_id=request.action_id,
        action_fingerprint=request.authority_fingerprint(),
        scope=ControlPlaneConfirmationScope.PAPER_EXECUTION,
        confirmed_at_utc=NOW,
    )
    assert confirmation_matches_request(request, grant) is True


def test_confirmation_cannot_be_reused_for_a_different_action_payload() -> None:
    first = _request(
        ControlPlaneActionKind.EXECUTE_PAPER,
        broker=BrokerName.WEBULL,
        environment=ExecutionEnvironment.PAPER,
    )
    grant = ControlPlaneConfirmationGrant(
        grant_id="grant-001",
        action_id=first.action_id,
        action_fingerprint=first.authority_fingerprint(),
        scope=ControlPlaneConfirmationScope.PAPER_EXECUTION,
        confirmed_at_utc=NOW,
    )
    changed = first.model_copy(update={"target_broker": BrokerName.ALPACA})
    assert confirmation_matches_request(changed, grant) is False


def test_cancel_and_flatten_require_distinct_confirmation_scopes() -> None:
    cancel = _request(
        ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
        broker=BrokerName.WEBULL,
        environment=ExecutionEnvironment.PAPER,
    )
    flatten = _request(
        ControlPlaneActionKind.FLATTEN_POSITIONS,
        broker=BrokerName.WEBULL,
        environment=ExecutionEnvironment.PAPER,
    )
    assert required_confirmation_scope(cancel.action_kind) == ControlPlaneConfirmationScope.CANCEL_OPEN_ORDERS
    assert required_confirmation_scope(flatten.action_kind) == ControlPlaneConfirmationScope.FLATTEN_POSITIONS
    assert cancel.authority_fingerprint() != flatten.authority_fingerprint()


def test_naive_action_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ControlPlaneActionRequest(
            action_id="action-001",
            action_kind=ControlPlaneActionKind.EXECUTE_SHADOW,
            requested_at_utc=datetime(2026, 8, 22, 20, 50),
            idempotency_key="idem-action-001",
            target_broker=BrokerName.SHADOW,
            environment=ExecutionEnvironment.SHADOW,
        )
