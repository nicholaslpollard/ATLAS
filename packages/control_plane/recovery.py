from __future__ import annotations

from dataclasses import dataclass

from packages.schemas.control_plane import ControlPlaneActionKind, ControlPlaneActionState
from packages.schemas.control_plane_runtime import ControlPlaneRuntimeState
from packages.schemas.execution import BrokerName, ExecutionEnvironment

from .action_ledger import (
    ControlPlaneActionLedger,
    ControlPlaneActionLedgerError,
    ControlPlaneActionNotFound,
)


CONTROL_PLANE_RUNTIME_RECOVERY_CONTRACT_VERSION = (
    "control-plane-runtime-recovery-v1-audit-bound-broker-selection-replay"
)


@dataclass(frozen=True, slots=True)
class RuntimeAuditBindingResult:
    valid: bool
    recovery_required: bool
    reason_code: str


class ControlPlaneRuntimeRecoveryVerifier:
    """Independently bind persisted local routing state back to the action audit chain.

    This verifier is read-only. It never completes actions or mutates runtime state. An
    EXECUTING broker-switch action whose exact runtime transition has already persisted is
    a valid recoverable state; the broker-switch processor may finish that action later
    without repeating broker reads. Any other mismatch fails closed.
    """

    def __init__(self, ledger: ControlPlaneActionLedger) -> None:
        self.ledger = ledger

    def verify(self, runtime: ControlPlaneRuntimeState) -> RuntimeAuditBindingResult:
        if runtime.source == "synthetic_default":
            return RuntimeAuditBindingResult(
                valid=True,
                recovery_required=False,
                reason_code="SYNTHETIC_DEFAULT_HAS_NO_PERSISTED_ROUTING_AUTHORITY",
            )

        if (
            runtime.selected_environment != ExecutionEnvironment.PAPER
            or runtime.selected_broker not in {BrokerName.WEBULL, BrokerName.ALPACA}
            or runtime.last_transition_action_id is None
            or runtime.last_transition_audit_hash is None
        ):
            return RuntimeAuditBindingResult(
                valid=False,
                recovery_required=False,
                reason_code="PERSISTED_ROUTING_SHAPE_NOT_SUPPORTED",
            )

        try:
            record = self.ledger.get(runtime.last_transition_action_id)
            events = self.ledger.runtime_transition_events(runtime.last_transition_action_id)
        except (ControlPlaneActionLedgerError, ControlPlaneActionNotFound):
            return RuntimeAuditBindingResult(
                valid=False,
                recovery_required=False,
                reason_code="ROUTING_ACTION_OR_AUDIT_EVENT_UNAVAILABLE",
            )

        request = record.request
        if (
            request.action_kind != ControlPlaneActionKind.BROKER_SWITCH
            or request.target_broker != runtime.selected_broker
            or request.environment != runtime.selected_environment
        ):
            return RuntimeAuditBindingResult(
                valid=False,
                recovery_required=False,
                reason_code="ROUTING_ACTION_DOES_NOT_MATCH_PERSISTED_SELECTION",
            )
        if record.provider_write_attempted or record.provider_write_uncertain:
            return RuntimeAuditBindingResult(
                valid=False,
                recovery_required=False,
                reason_code="ROUTING_ACTION_CARRIES_PROVIDER_WRITE_STATE",
            )
        if len(events) != 1:
            return RuntimeAuditBindingResult(
                valid=False,
                recovery_required=False,
                reason_code="ROUTING_TRANSITION_EVENT_COUNT_INVALID",
            )

        event = events[0]
        if event.event_hash != runtime.last_transition_audit_hash:
            return RuntimeAuditBindingResult(
                valid=False,
                recovery_required=False,
                reason_code="ROUTING_TRANSITION_AUDIT_HASH_MISMATCH",
            )
        details = event.details
        if (
            event.action_state != ControlPlaneActionState.EXECUTING
            or details.get("transition_kind") != "BROKER_SELECTION"
            or int(details.get("next_revision", -1)) != runtime.revision
            or details.get("selected_broker") != runtime.selected_broker.value
            or details.get("selected_environment") != runtime.selected_environment.value
            or details.get("provider_write_attempted") is not False
        ):
            return RuntimeAuditBindingResult(
                valid=False,
                recovery_required=False,
                reason_code="ROUTING_TRANSITION_EVENT_SEMANTICS_MISMATCH",
            )

        if record.state == ControlPlaneActionState.COMPLETED:
            return RuntimeAuditBindingResult(
                valid=True,
                recovery_required=False,
                reason_code="PERSISTED_ROUTING_AUDIT_BINDING_VERIFIED",
            )
        if record.state == ControlPlaneActionState.EXECUTING:
            return RuntimeAuditBindingResult(
                valid=True,
                recovery_required=True,
                reason_code="PERSISTED_ROUTING_VALID_RECOVERY_REQUIRED",
            )
        return RuntimeAuditBindingResult(
            valid=False,
            recovery_required=False,
            reason_code="ROUTING_ACTION_TERMINAL_STATE_INVALID",
        )
