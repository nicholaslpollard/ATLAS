from __future__ import annotations

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


def main() -> None:
    validate_phase16_policy()
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
        "credential_values_hidden": PHASE16_CREDENTIAL_VALUES_EXPOSED_TO_BROWSER is False,
        "loopback_default": PHASE16_DEFAULT_BIND_HOST == "127.0.0.1",
        "remote_bind_disabled_default": PHASE16_REMOTE_BIND_ENABLED_BY_DEFAULT is False,
        "policy_fingerprint_present": len(phase16_policy_fingerprint()) == 64,
    }
    print(f"Phase 16 accepted Phase 15 merge: {PHASE16_ACCEPTED_PHASE15_MERGE_SHA}")
    print(f"Phase 16 accepted Phase 15 policy: {PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT}")
    print(f"Phase 16 policy fingerprint: {phase16_policy_fingerprint()}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise SystemExit("Phase 16 static validation failed: " + ", ".join(failed))
    print("Phase 16 Browser Control Plane authority contracts: PASS")


if __name__ == "__main__":
    main()
