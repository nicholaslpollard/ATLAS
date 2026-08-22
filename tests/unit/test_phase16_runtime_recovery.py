from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.recovery import ControlPlaneRuntimeRecoveryVerifier
from packages.control_plane.runtime_state import ControlPlaneRuntimeStateStore
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings
from packages.execution.phase15_closeout import PHASE15_CLOSEOUT_CONTRACT_VERSION
from packages.execution.phase15_foundation import PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT
from packages.execution.phase15_policy import phase15_policy_fingerprint
from packages.schemas.control_plane import (
    ControlPlaneActionKind,
    ControlPlaneActionRequest,
    ControlPlaneActionState,
    ControlPlaneConfirmationGrant,
    ControlPlaneConfirmationScope,
)
from packages.schemas.control_plane_runtime import ControlPlaneRuntimeState
from packages.schemas.control_plane_status import ControlPlaneHealthState
from packages.schemas.execution import BrokerName, ExecutionEnvironment


NOW = datetime(2026, 8, 22, 23, 0, tzinfo=UTC)


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _write_phase15_acceptance(tmp_path) -> None:
    root = tmp_path / "execution" / "phase15" / "v1"
    root.mkdir(parents=True, exist_ok=True)
    (root / "phase15_final_acceptance.json").write_text(
        json.dumps(
            {
                "contract_version": PHASE15_CLOSEOUT_CONTRACT_VERSION,
                "pass": True,
                "as_of_date": "2026-08-14",
                "phase15_policy_fingerprint": phase15_policy_fingerprint(),
                "cumulative_foundation_fingerprint": PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
                "execution_case_count": 0,
                "final_disposition": {
                    "phase15_accepted": True,
                    "actual_broker_execution_exercised_in_acceptance": False,
                    "live_execution_promoted": False,
                    "automatic_cross_broker_failover_allowed": False,
                },
            }
        ),
        encoding="utf-8",
    )


def _authorized_switch(ledger: ControlPlaneActionLedger, action_id: str = "recovery-switch"):
    request = ControlPlaneActionRequest(
        action_id=action_id,
        action_kind=ControlPlaneActionKind.BROKER_SWITCH,
        requested_at_utc=NOW,
        idempotency_key=f"idem-{action_id}",
        target_broker=BrokerName.ALPACA,
        environment=ExecutionEnvironment.PAPER,
        reason="runtime recovery test",
    )
    ledger.create_request(request)
    return ledger.confirm(
        action_id,
        ControlPlaneConfirmationGrant(
            grant_id=f"grant-{action_id}",
            action_id=action_id,
            action_fingerprint=request.authority_fingerprint(),
            scope=ControlPlaneConfirmationScope.BROKER_SWITCH,
            confirmed_at_utc=NOW + timedelta(seconds=1),
        ),
    )


def _persist_executing_route(ledger, runtime, action_id="recovery-switch"):
    ledger.transition(action_id, ControlPlaneActionState.EXECUTING)
    event = ledger.append_runtime_transition_intent(
        action_id,
        prior_revision=0,
        next_revision=1,
        selected_broker=BrokerName.ALPACA.value,
        selected_environment=ExecutionEnvironment.PAPER.value,
    )
    state = ControlPlaneRuntimeState(
        revision=1,
        updated_at_utc=NOW + timedelta(seconds=10),
        selected_broker=BrokerName.ALPACA,
        selected_environment=ExecutionEnvironment.PAPER,
        provider_write_uncertain=False,
        last_transition_action_id=action_id,
        last_transition_audit_hash=event.event_hash,
        source="persisted",
    )
    runtime.persist_transition(state, expected_prior_revision=0)
    return state, event


def _status_service(tmp_path, ledger, runtime):
    _write_phase15_acceptance(tmp_path)
    return Phase16StatusService(
        _settings_with_derived(tmp_path),
        env={},
        clock=lambda: NOW + timedelta(seconds=20),
        runtime_store=runtime,
        action_ledger=ledger,
    )


def test_synthetic_default_has_valid_no_authority_binding(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW)
    runtime = ControlPlaneRuntimeStateStore(settings, clock=lambda: NOW)
    result = ControlPlaneRuntimeRecoveryVerifier(ledger).verify(runtime.load())
    assert result.valid is True
    assert result.recovery_required is False
    assert result.reason_code == "SYNTHETIC_DEFAULT_HAS_NO_PERSISTED_ROUTING_AUTHORITY"


def test_completed_audit_bound_route_is_healthy(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=10))
    runtime = ControlPlaneRuntimeStateStore(settings, clock=lambda: NOW + timedelta(seconds=10))
    _authorized_switch(ledger)
    _persist_executing_route(ledger, runtime)
    ledger.transition("recovery-switch", ControlPlaneActionState.COMPLETED)

    status = _status_service(tmp_path, ledger, runtime).system_status()
    assert status.health == ControlPlaneHealthState.HEALTHY
    assert status.runtime_audit_binding_valid is True
    assert status.runtime_recovery_required is False
    assert status.runtime_audit_binding_reason == "PERSISTED_ROUTING_AUDIT_BINDING_VERIFIED"
    assert status.provider_write_uncertain is False
    assert status.selected_broker == BrokerName.ALPACA


def test_exact_persisted_executing_transition_is_degraded_and_recoverable(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=10))
    runtime = ControlPlaneRuntimeStateStore(settings, clock=lambda: NOW + timedelta(seconds=10))
    _authorized_switch(ledger)
    _persist_executing_route(ledger, runtime)

    status = _status_service(tmp_path, ledger, runtime).system_status()
    assert status.health == ControlPlaneHealthState.DEGRADED
    assert status.runtime_audit_binding_valid is True
    assert status.runtime_recovery_required is True
    assert status.runtime_audit_binding_reason == "PERSISTED_ROUTING_VALID_RECOVERY_REQUIRED"
    assert status.provider_write_uncertain is False
    assert status.active_action_count == 1


def test_tampered_runtime_audit_hash_blocks_control_plane(tmp_path) -> None:
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=10))
    runtime = ControlPlaneRuntimeStateStore(settings, clock=lambda: NOW + timedelta(seconds=10))
    _authorized_switch(ledger)
    _persist_executing_route(ledger, runtime)
    ledger.transition("recovery-switch", ControlPlaneActionState.COMPLETED)

    raw = json.loads(runtime.state_path.read_text(encoding="utf-8"))
    raw["last_transition_audit_hash"] = "f" * 64
    runtime.state_path.write_text(json.dumps(raw), encoding="utf-8")

    status = _status_service(tmp_path, ledger, runtime).system_status()
    assert status.health == ControlPlaneHealthState.BLOCKED
    assert status.runtime_state_valid is True
    assert status.runtime_audit_binding_valid is False
    assert status.runtime_recovery_required is False
    assert status.runtime_audit_binding_reason == "ROUTING_TRANSITION_AUDIT_HASH_MISMATCH"
    assert status.provider_write_uncertain is True
