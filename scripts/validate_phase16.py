from __future__ import annotations

from packages.brokers.base import BrokerAdapterError, BrokerMutationUncertain
from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.broker_switch_processor import (
    BROKER_SWITCH_PROCESSOR_CONTRACT_VERSION,
)
from packages.control_plane.cleanup_plan_ledger import (
    CONTROL_PLANE_CLEANUP_PLAN_LEDGER_CONTRACT_VERSION,
)
from packages.control_plane.cleanup_planner import (
    CONTROL_PLANE_CLEANUP_PLANNER_CONTRACT_VERSION,
)
from packages.control_plane.cleanup_policy import (
    CONTROL_PLANE_CLEANUP_POLICY_VERSION,
    PHASE16_CANCEL_PROVIDER_WRITES_ENABLED,
    PHASE16_CLEANUP_REQUIRES_EXACT_PLAN_CONFIRMATION,
    PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED,
    PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED,
    cleanup_policy_fingerprint,
    validate_cleanup_policy,
)
from packages.control_plane.cleanup_processor import (
    CONTROL_PLANE_CLEANUP_PROCESSOR_CONTRACT_VERSION,
)
from packages.control_plane.http_server import (
    CONTROL_PLANE_HTTP_CONTRACT_VERSION,
    DEFAULT_CONTROL_PLANE_PORT,
    MAX_JSON_BODY_BYTES,
    MAX_STATIC_ASSET_BYTES,
    host_header_is_loopback,
    is_loopback_host,
)
from packages.control_plane.phase16_policy import (
    PHASE16_ACCEPTED_PHASE15_MERGE_SHA,
    PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT,
    PHASE16_ALLOWED_EXECUTION_ENVIRONMENTS,
    PHASE16_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE16_BROWSER_CAN_CREATE_EXECUTION_AUTHORITY,
    PHASE16_CANCEL_OPEN_ORDERS_REQUIRES_EXPLICIT_CONFIRMATION,
    PHASE16_CREDENTIAL_VALUES_EXPOSED_TO_BROWSER,
    PHASE16_DEFAULT_BIND_HOST,
    PHASE16_FLATTEN_REQUIRES_SEPARATE_EXPLICIT_CONFIRMATION,
    PHASE16_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE16_OPERATIONAL_ACTIONS_ARE_AUDITED,
    PHASE16_OPERATIONAL_ACTIONS_ARE_IDEMPOTENT,
    PHASE16_PHASE15_GATES_MAY_BE_BYPASSED,
    PHASE16_PRIMARY_BROKER,
    PHASE16_REMOTE_BIND_ENABLED_BY_DEFAULT,
    PHASE16_SECONDARY_BROKER,
    phase16_policy_fingerprint,
    validate_phase16_policy,
)
from packages.control_plane.recovery import (
    CONTROL_PLANE_RUNTIME_RECOVERY_CONTRACT_VERSION,
)
from packages.control_plane.session import CONTROL_PLANE_SESSION_CONTRACT_VERSION
from packages.schemas.control_plane_cleanup import (
    CONTROL_PLANE_CLEANUP_PLAN_CONFIRMATION_CONTRACT_VERSION,
    CONTROL_PLANE_CLEANUP_PLAN_CONTRACT_VERSION,
)
from packages.schemas.control_plane_ledger import (
    CONTROL_PLANE_ACTION_RECORD_CONTRACT_VERSION,
    CONTROL_PLANE_AUDIT_EVENT_CONTRACT_VERSION,
)
from packages.schemas.control_plane_runtime import (
    CONTROL_PLANE_RUNTIME_CONTRACT_VERSION,
    ControlPlaneRuntimeState,
)
from packages.schemas.control_plane_status import CONTROL_PLANE_STATUS_CONTRACT_VERSION


def main() -> None:
    validate_phase16_policy()
    validate_cleanup_policy()
    default_state = ControlPlaneRuntimeState.synthetic_default()
    checks = {
        "accepted_phase15_merge_bound": len(PHASE16_ACCEPTED_PHASE15_MERGE_SHA) == 40,
        "accepted_phase15_policy_bound": len(PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT) == 64,
        "webull_primary": PHASE16_PRIMARY_BROKER == "webull",
        "alpaca_secondary": PHASE16_SECONDARY_BROKER == "alpaca",
        "shadow_paper_only": PHASE16_ALLOWED_EXECUTION_ENVIRONMENTS == ("shadow", "paper"),
        "live_not_promoted": PHASE16_LIVE_EXECUTION_PROMOTION_ALLOWED is False,
        "automatic_cross_broker_failover_disabled": PHASE16_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False,
        "browser_not_execution_authority": PHASE16_BROWSER_CAN_CREATE_EXECUTION_AUTHORITY is False,
        "phase15_gates_not_bypassable": PHASE16_PHASE15_GATES_MAY_BE_BYPASSED is False,
        "flatten_requires_explicit_confirmation": PHASE16_FLATTEN_REQUIRES_SEPARATE_EXPLICIT_CONFIRMATION is True,
        "cancel_requires_explicit_confirmation": PHASE16_CANCEL_OPEN_ORDERS_REQUIRES_EXPLICIT_CONFIRMATION is True,
        "actions_idempotent": PHASE16_OPERATIONAL_ACTIONS_ARE_IDEMPOTENT is True,
        "actions_audited": PHASE16_OPERATIONAL_ACTIONS_ARE_AUDITED is True,
        "action_abandon_present": callable(getattr(ControlPlaneActionLedger, "abandon", None)),
        "credential_values_hidden": PHASE16_CREDENTIAL_VALUES_EXPOSED_TO_BROWSER is False,
        "loopback_default": PHASE16_DEFAULT_BIND_HOST == "127.0.0.1",
        "remote_bind_disabled_default": PHASE16_REMOTE_BIND_ENABLED_BY_DEFAULT is False,
        "policy_fingerprint_present": len(phase16_policy_fingerprint()) == 64,
        "status_contract_locked": CONTROL_PLANE_STATUS_CONTRACT_VERSION
        == "control-plane-status-v3-sanitized-lineage-runtime-audit-binding-reconciliation",
        "runtime_contract_locked": CONTROL_PLANE_RUNTIME_CONTRACT_VERSION
        == "control-plane-runtime-v2-explicit-selection-audit-bound-uncertainty-fail-closed",
        "runtime_recovery_contract_locked": CONTROL_PLANE_RUNTIME_RECOVERY_CONTRACT_VERSION
        == "control-plane-runtime-recovery-v1-audit-bound-broker-selection-replay",
        "runtime_default_unselected": default_state.selected_broker is None
        and default_state.selected_environment is None,
        "runtime_default_not_persisted": default_state.source == "synthetic_default",
        "runtime_default_not_uncertain": default_state.provider_write_uncertain is False,
        "runtime_default_not_audit_bound": default_state.last_transition_action_id is None
        and default_state.last_transition_audit_hash is None,
        "action_record_contract_locked": CONTROL_PLANE_ACTION_RECORD_CONTRACT_VERSION
        == "control-plane-action-record-v1-idempotent-confirmed-provider-uncertainty",
        "audit_event_contract_locked": CONTROL_PLANE_AUDIT_EVENT_CONTRACT_VERSION
        == "control-plane-audit-event-v1-hash-chain-append-only",
        "session_contract_locked": CONTROL_PLANE_SESSION_CONTRACT_VERSION
        == "control-plane-session-v1-same-origin-double-submit-csrf",
        "broker_switch_processor_locked": BROKER_SWITCH_PROCESSOR_CONTRACT_VERSION
        == "control-plane-broker-switch-v1-phase15-reconciled-flat-local-routing-only",
        "cleanup_policy_locked": CONTROL_PLANE_CLEANUP_POLICY_VERSION
        == "control-plane-cleanup-policy-v1-exact-plan-confirmation-rereconcile-no-writes",
        "cleanup_policy_fingerprint_present": len(cleanup_policy_fingerprint()) == 64,
        "cleanup_plan_contract_locked": CONTROL_PLANE_CLEANUP_PLAN_CONTRACT_VERSION
        == "control-plane-cleanup-plan-v1-reconciled-exact-resource-review-no-provider-authority",
        "cleanup_plan_confirmation_locked": CONTROL_PLANE_CLEANUP_PLAN_CONFIRMATION_CONTRACT_VERSION
        == "control-plane-cleanup-plan-confirmation-v1-action-and-plan-fingerprint-bound",
        "cleanup_plan_ledger_locked": CONTROL_PLANE_CLEANUP_PLAN_LEDGER_CONTRACT_VERSION
        == "control-plane-cleanup-plan-ledger-v1-shared-audit-latest-plan-one-time-confirmation",
        "cleanup_planner_locked": CONTROL_PLANE_CLEANUP_PLANNER_CONTRACT_VERSION
        == "control-plane-cleanup-planner-v1-authorized-action-fresh-reconciliation-review-only",
        "cleanup_processor_locked": CONTROL_PLANE_CLEANUP_PROCESSOR_CONTRACT_VERSION
        == "control-plane-cleanup-processor-v1-confirmed-exact-recheck-no-provider-writes",
        "broker_mutation_uncertainty_is_adapter_error": issubclass(
            BrokerMutationUncertain, BrokerAdapterError
        ),
        "cleanup_exact_plan_confirmation_required": PHASE16_CLEANUP_REQUIRES_EXACT_PLAN_CONFIRMATION is True,
        "cancel_provider_writes_disabled": PHASE16_CANCEL_PROVIDER_WRITES_ENABLED is False,
        "flatten_provider_writes_disabled": PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED is False,
        "flatten_close_method_unaccepted": PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED is False,
        "http_contract_locked": CONTROL_PLANE_HTTP_CONTRACT_VERSION
        == "control-plane-http-v7-loopback-browser-cleanup-review-abandon-no-provider-writes",
        "http_json_body_cap_locked": MAX_JSON_BODY_BYTES == 64 * 1024,
        "http_static_asset_cap_locked": MAX_STATIC_ASSET_BYTES == 1024 * 1024,
        "http_default_port_locked": DEFAULT_CONTROL_PLANE_PORT == 8765,
        "loopback_ipv4_accepted": is_loopback_host("127.0.0.1"),
        "loopback_ipv6_accepted": is_loopback_host("::1"),
        "wildcard_bind_rejected": not is_loopback_host("0.0.0.0"),
        "localhost_host_header_accepted": host_header_is_loopback("localhost:8765"),
        "foreign_host_header_rejected": not host_header_is_loopback("example.com"),
    }
    print(f"Phase 16 accepted Phase 15 merge: {PHASE16_ACCEPTED_PHASE15_MERGE_SHA}")
    print(f"Phase 16 accepted Phase 15 policy: {PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT}")
    print(f"Phase 16 policy fingerprint: {phase16_policy_fingerprint()}")
    print(f"Phase 16 status contract: {CONTROL_PLANE_STATUS_CONTRACT_VERSION}")
    print(f"Phase 16 runtime contract: {CONTROL_PLANE_RUNTIME_CONTRACT_VERSION}")
    print(f"Phase 16 runtime recovery: {CONTROL_PLANE_RUNTIME_RECOVERY_CONTRACT_VERSION}")
    print(f"Phase 16 action record contract: {CONTROL_PLANE_ACTION_RECORD_CONTRACT_VERSION}")
    print(f"Phase 16 audit event contract: {CONTROL_PLANE_AUDIT_EVENT_CONTRACT_VERSION}")
    print(f"Phase 16 session contract: {CONTROL_PLANE_SESSION_CONTRACT_VERSION}")
    print(f"Phase 16 broker switch processor: {BROKER_SWITCH_PROCESSOR_CONTRACT_VERSION}")
    print(f"Phase 16 cleanup policy: {CONTROL_PLANE_CLEANUP_POLICY_VERSION}")
    print(f"Phase 16 cleanup policy fingerprint: {cleanup_policy_fingerprint()}")
    print(f"Phase 16 cleanup plan: {CONTROL_PLANE_CLEANUP_PLAN_CONTRACT_VERSION}")
    print(f"Phase 16 cleanup plan ledger: {CONTROL_PLANE_CLEANUP_PLAN_LEDGER_CONTRACT_VERSION}")
    print(f"Phase 16 cleanup planner: {CONTROL_PLANE_CLEANUP_PLANNER_CONTRACT_VERSION}")
    print(f"Phase 16 cleanup processor: {CONTROL_PLANE_CLEANUP_PROCESSOR_CONTRACT_VERSION}")
    print(f"Phase 16 HTTP contract: {CONTROL_PLANE_HTTP_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise SystemExit("Phase 16 static validation failed: " + ", ".join(failed))
    print("Phase 16 Browser Control Plane authority/status/runtime/recovery/audit/session/UI/switch/cleanup contracts: PASS")


if __name__ == "__main__":
    main()
