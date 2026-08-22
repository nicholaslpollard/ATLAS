from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.cleanup_plan_ledger import (
    ControlPlaneCleanupPlanConflict,
    ControlPlaneCleanupPlanLedger,
    ControlPlaneCleanupPlanLedgerError,
)
from packages.core.settings import load_settings
from packages.schemas.control_plane import (
    ControlPlaneActionKind,
    ControlPlaneActionRequest,
    ControlPlaneConfirmationGrant,
    ControlPlaneConfirmationScope,
)
from packages.schemas.control_plane_cleanup import (
    ControlPlaneCancelOrderTarget,
    ControlPlaneCleanupPlan,
    ControlPlaneCleanupPlanConfirmationGrant,
    ControlPlaneCleanupPlanKind,
)
from packages.schemas.execution import (
    BrokerName,
    BrokerOrderSide,
    BrokerOrderStatus,
    ExecutionEnvironment,
)


NOW = datetime(2026, 8, 22, 23, 45, tzinfo=UTC)


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _authorized_action(ledger: ControlPlaneActionLedger, action_id: str = "cleanup-ledger"):
    request = ControlPlaneActionRequest(
        action_id=action_id,
        action_kind=ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
        requested_at_utc=NOW,
        idempotency_key=f"idem-{action_id}",
        target_broker=BrokerName.WEBULL,
        environment=ExecutionEnvironment.PAPER,
        reason="cleanup plan ledger test",
    )
    ledger.create_request(request)
    record = ledger.confirm(
        action_id,
        ControlPlaneConfirmationGrant(
            grant_id=f"grant-{action_id}",
            action_id=action_id,
            action_fingerprint=request.authority_fingerprint(),
            scope=ControlPlaneConfirmationScope.CANCEL_OPEN_ORDERS,
            confirmed_at_utc=NOW + timedelta(seconds=1),
        ),
    )
    return record


def _plan(record, *, client_id: str, generated_offset: int = 5):
    generated = NOW + timedelta(seconds=generated_offset)
    target = ControlPlaneCancelOrderTarget(
        client_order_id=client_id,
        ticker="SPY",
        side=BrokerOrderSide.BUY,
        status=BrokerOrderStatus.SUBMITTED,
        requested_quantity=1.0,
        filled_quantity=0.0,
        updated_at_utc=NOW,
    )
    return ControlPlaneCleanupPlan(
        action_id=record.request.action_id,
        action_fingerprint=record.request_fingerprint,
        action_kind=record.request.action_kind,
        plan_kind=ControlPlaneCleanupPlanKind.CANCEL_OPEN_ORDERS,
        broker=BrokerName.WEBULL,
        account_ref="a" * 16,
        generated_at_utc=generated,
        expires_at_utc=generated + timedelta(seconds=120),
        reconciliation_as_of_utc=generated,
        zero_open_orders=False,
        zero_positions=True,
        cancel_targets=(target,),
        flatten_targets=(),
        no_op=False,
        reason_codes=(
            "FRESH_PHASE15_BROKER_RECONCILIATION",
            "EXACT_OPEN_ORDER_RESOURCE_SET_CAPTURED",
            "PROVIDER_CANCEL_WRITES_DISABLED",
        ),
    )


def _grant(plan, *, grant_id: str = "cleanup-exact-grant", confirmed_offset: int = 10):
    return ControlPlaneCleanupPlanConfirmationGrant(
        grant_id=grant_id,
        action_id=plan.action_id,
        action_fingerprint=plan.action_fingerprint,
        cleanup_plan_fingerprint=plan.plan_fingerprint(),
        confirmed_at_utc=NOW + timedelta(seconds=confirmed_offset),
    )


def test_plan_events_share_action_hash_chain_without_mutating_action_revision(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    action_ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=10))
    record = _authorized_action(action_ledger)
    plan_ledger = ControlPlaneCleanupPlanLedger(
        action_ledger, clock=lambda: NOW + timedelta(seconds=10)
    )
    plan = _plan(record, client_id="cleanup-order-aaaa")

    stored = plan_ledger.record_plan(plan)
    assert stored == plan
    assert action_ledger.get(record.request.action_id).revision == record.revision
    assert action_ledger.verify()["action_count"] == 1
    assert action_ledger.verify()["active_action_count"] == 1
    assert plan_ledger.verify() == {
        "plan_count": 1,
        "confirmed_plan_count": 0,
        "provider_write_authority_count": 0,
        "shared_audit_chain_valid": True,
        "pass": True,
    }

    event_count = action_ledger.verify()["event_count"]
    assert plan_ledger.record_plan(plan) == plan
    assert action_ledger.verify()["event_count"] == event_count


def test_only_latest_refreshed_plan_can_receive_exact_confirmation(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    action_ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=15))
    record = _authorized_action(action_ledger)
    plan_ledger = ControlPlaneCleanupPlanLedger(
        action_ledger, clock=lambda: NOW + timedelta(seconds=15)
    )
    first = _plan(record, client_id="cleanup-order-first", generated_offset=5)
    second = _plan(record, client_id="cleanup-order-second", generated_offset=8)
    plan_ledger.record_plan(first)
    plan_ledger.record_plan(second)

    with pytest.raises(ControlPlaneCleanupPlanConflict, match="latest exact resource plan"):
        plan_ledger.confirm_latest(record.request.action_id, _grant(first))

    grant = _grant(second, confirmed_offset=15)
    assert plan_ledger.confirm_latest(record.request.action_id, grant) == second
    state = plan_ledger.state(record.request.action_id)
    assert state.latest_plan == second
    assert state.confirmation == grant
    assert state.confirmed_plan_fingerprint == second.plan_fingerprint()
    assert plan_ledger.verify()["confirmed_plan_count"] == 1

    event_count = action_ledger.verify()["event_count"]
    assert plan_ledger.confirm_latest(record.request.action_id, grant) == second
    assert action_ledger.verify()["event_count"] == event_count

    third = _plan(record, client_id="cleanup-order-third", generated_offset=20)
    with pytest.raises(ControlPlaneCleanupPlanConflict, match="cannot be silently superseded"):
        plan_ledger.record_plan(third)


def test_expired_plan_confirmation_is_rejected_without_audit_authority(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    action_ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=200))
    record = _authorized_action(action_ledger)
    plan_ledger = ControlPlaneCleanupPlanLedger(
        action_ledger, clock=lambda: NOW + timedelta(seconds=200)
    )
    plan = _plan(record, client_id="cleanup-order-expired", generated_offset=5)
    plan_ledger.record_plan(plan)
    before = action_ledger.verify()["event_count"]

    with pytest.raises(ControlPlaneCleanupPlanConflict, match="expired"):
        plan_ledger.confirm_latest(
            record.request.action_id,
            _grant(plan, confirmed_offset=125),
        )
    assert action_ledger.verify()["event_count"] == before
    assert plan_ledger.state(record.request.action_id).confirmation is None


def test_cleanup_plan_audit_tampering_fails_shared_chain_verification(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    action_ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=10))
    record = _authorized_action(action_ledger)
    plan_ledger = ControlPlaneCleanupPlanLedger(action_ledger, clock=lambda: NOW + timedelta(seconds=10))
    plan_ledger.record_plan(_plan(record, client_id="cleanup-order-tamper"))

    lines = action_ledger.audit_log.path.read_text(encoding="utf-8").splitlines()
    last = json.loads(lines[-1])
    last["details"]["cleanup_plan"]["cancel_targets"][0]["ticker"] = "QQQ"
    lines[-1] = json.dumps(last)
    action_ledger.audit_log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ControlPlaneCleanupPlanLedgerError, match="verification"):
        plan_ledger.state(record.request.action_id)
