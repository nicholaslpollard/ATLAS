from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from packages.control_plane.action_ledger import (
    ControlPlaneActionConflict,
    ControlPlaneActionLedger,
    ControlPlaneActionLedgerError,
)
from packages.control_plane.audit_log import ControlPlaneAuditLog, ControlPlaneAuditLogError
from packages.core.settings import load_settings
from packages.schemas.control_plane import (
    ControlPlaneActionKind,
    ControlPlaneActionRequest,
    ControlPlaneActionState,
    ControlPlaneConfirmationGrant,
    ControlPlaneConfirmationScope,
)
from packages.schemas.control_plane_ledger import ControlPlaneAuditEventType
from packages.schemas.execution import BrokerName, ExecutionEnvironment


NOW = datetime(2026, 8, 22, 21, 0, tzinfo=UTC)


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _switch_request(*, action_id: str = "switch-1", idempotency_key: str = "idem-1"):
    return ControlPlaneActionRequest(
        action_id=action_id,
        action_kind=ControlPlaneActionKind.BROKER_SWITCH,
        requested_at_utc=NOW,
        idempotency_key=idempotency_key,
        target_broker=BrokerName.ALPACA,
        environment=ExecutionEnvironment.PAPER,
        reason="manual fallback selection",
    )


def _grant(request: ControlPlaneActionRequest, *, grant_id: str = "grant-1"):
    return ControlPlaneConfirmationGrant(
        grant_id=grant_id,
        action_id=request.action_id,
        action_fingerprint=request.authority_fingerprint(),
        scope=ControlPlaneConfirmationScope.BROKER_SWITCH,
        confirmed_at_utc=NOW + timedelta(seconds=5),
    )


def test_audit_log_hash_chain_detects_tampering(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    log = ControlPlaneAuditLog(path, clock=lambda: NOW)
    first = log.append(
        event_type=ControlPlaneAuditEventType.RUNTIME_STATE_CHANGED,
        actor="atlas_system",
        details={"revision": 1},
    )
    second = log.append(
        event_type=ControlPlaneAuditEventType.RUNTIME_STATE_CHANGED,
        actor="atlas_system",
        details={"revision": 2},
    )
    assert second.previous_event_hash == first.event_hash
    assert [event.sequence for event in log.read_verified()] == [1, 2]

    lines = path.read_text(encoding="utf-8").splitlines()
    raw = json.loads(lines[0])
    raw["details"]["revision"] = 999
    lines[0] = json.dumps(raw, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ControlPlaneAuditLogError):
        log.read_verified()


def test_action_request_is_idempotent_and_recoverable_from_audit(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW)
    request = _switch_request()
    first = ledger.create_request(request)
    second = ledger.create_request(request)
    assert first == second
    assert first.state == ControlPlaneActionState.AWAITING_CONFIRMATION
    assert first.revision == 1
    assert ledger.verify()["event_count"] == 1

    reopened = ControlPlaneActionLedger(settings, clock=lambda: NOW)
    recovered = reopened.get(request.action_id)
    assert recovered == first
    assert reopened.verify()["hash_chain_valid"] is True


def test_idempotency_key_cannot_authorize_different_request(tmp_path) -> None:
    ledger = ControlPlaneActionLedger(_settings_with_derived(tmp_path), clock=lambda: NOW)
    ledger.create_request(_switch_request())
    changed = ControlPlaneActionRequest(
        action_id="switch-2",
        action_kind=ControlPlaneActionKind.BROKER_SWITCH,
        requested_at_utc=NOW,
        idempotency_key="idem-1",
        target_broker=BrokerName.WEBULL,
        environment=ExecutionEnvironment.PAPER,
    )
    with pytest.raises(ControlPlaneActionConflict, match="idempotency"):
        ledger.create_request(changed)


def test_exact_confirmation_authorizes_once_without_provider_write(tmp_path) -> None:
    ledger = ControlPlaneActionLedger(_settings_with_derived(tmp_path), clock=lambda: NOW)
    request = _switch_request()
    requested = ledger.create_request(request)
    grant = _grant(request)
    authorized = ledger.confirm(request.action_id, grant)
    assert requested.state == ControlPlaneActionState.AWAITING_CONFIRMATION
    assert authorized.state == ControlPlaneActionState.AUTHORIZED
    assert authorized.confirmation == grant
    assert authorized.revision == 2
    assert authorized.provider_write_attempted is False
    assert authorized.provider_write_uncertain is False
    assert ledger.verify()["event_count"] == 2

    duplicate = ledger.confirm(request.action_id, grant)
    assert duplicate == authorized
    assert ledger.verify()["event_count"] == 2


def test_confirmation_for_modified_action_is_rejected(tmp_path) -> None:
    ledger = ControlPlaneActionLedger(_settings_with_derived(tmp_path), clock=lambda: NOW)
    request = _switch_request()
    ledger.create_request(request)
    wrong = ControlPlaneConfirmationGrant(
        grant_id="grant-wrong",
        action_id=request.action_id,
        action_fingerprint="a" * 64,
        scope=ControlPlaneConfirmationScope.BROKER_SWITCH,
        confirmed_at_utc=NOW + timedelta(seconds=5),
    )
    with pytest.raises(ControlPlaneActionConflict, match="exact"):
        ledger.confirm(request.action_id, wrong)
    assert ledger.get(request.action_id).state == ControlPlaneActionState.AWAITING_CONFIRMATION


def test_shadow_request_is_authorized_by_explicit_request_without_extra_confirmation(tmp_path) -> None:
    ledger = ControlPlaneActionLedger(_settings_with_derived(tmp_path), clock=lambda: NOW)
    request = ControlPlaneActionRequest(
        action_id="shadow-1",
        action_kind=ControlPlaneActionKind.EXECUTE_SHADOW,
        requested_at_utc=NOW,
        idempotency_key="shadow-idem-1",
        target_broker=BrokerName.SHADOW,
        environment=ExecutionEnvironment.SHADOW,
    )
    record = ledger.create_request(request)
    assert record.state == ControlPlaneActionState.AUTHORIZED
    assert record.confirmation_scope is None
    assert record.confirmation is None
    assert record.provider_write_attempted is False


def test_corrupt_audit_chain_blocks_action_recovery(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW)
    ledger.create_request(_switch_request())
    ledger.audit_log.path.write_text("{broken\n", encoding="utf-8")
    with pytest.raises(ControlPlaneActionLedgerError, match="verification"):
        ledger.records()
