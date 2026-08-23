from __future__ import annotations

from packages.control_plane.phase18_authorization import (
    Phase18AuthorizationError,
    Phase18MutationAuthorization,
    require_phase18_mutation_authorization,
)
from packages.control_plane.phase18_policy import (
    PHASE18_ACCEPTED_PHASE17_MERGE_SHA,
    PHASE18_ACCEPTED_PHASE17_POLICY_FINGERPRINT,
    PHASE18_ACCEPTED_PHASE17_READINESS_CONTRACT,
    PHASE18_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE18_CONFIRMATION_TEXT,
    PHASE18_EXPLICIT_TARGET_MACHINE_AUTHORIZATION_REQUIRED,
    PHASE18_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE18_PROVIDER_MUTATIONS_ALLOWED_BY_DEFAULT,
    PHASE18_PROVIDER_READS_ALLOWED,
    PHASE18_REQUIRED_BROKERS,
    phase18_policy_fingerprint,
    validate_phase18_policy,
)


EXPECTED_PHASE18_POLICY_FINGERPRINT = (
    "9a992246fe60526295a714c8b6762eebf131680f5a6fb21d579503757be613b7"
)
EXPECTED_PHASE17_POLICY_FINGERPRINT = (
    "693113bbb09458ed2939e486f9f6e0a0bda44e331c6419065760586047b93ff8"
)
EXPECTED_PHASE17_READINESS_CONTRACT = (
    "phase17-readiness-v1-phase16-artifact-preserving-dual-broker-readonly-reconciliation"
)


def _default_mutation_is_denied() -> bool:
    try:
        require_phase18_mutation_authorization(
            Phase18MutationAuthorization(broker="webull")
        )
    except Phase18AuthorizationError:
        return True
    return False


def main() -> None:
    validate_phase18_policy()
    checks = {
        "accepted_phase17_merge_locked": len(PHASE18_ACCEPTED_PHASE17_MERGE_SHA) == 40,
        "accepted_phase17_policy_exact": PHASE18_ACCEPTED_PHASE17_POLICY_FINGERPRINT
        == EXPECTED_PHASE17_POLICY_FINGERPRINT,
        "accepted_phase17_readiness_exact": PHASE18_ACCEPTED_PHASE17_READINESS_CONTRACT
        == EXPECTED_PHASE17_READINESS_CONTRACT,
        "phase18_policy_fingerprint_exact": phase18_policy_fingerprint()
        == EXPECTED_PHASE18_POLICY_FINGERPRINT,
        "required_brokers_exact": PHASE18_REQUIRED_BROKERS == ("webull", "alpaca"),
        "provider_reads_allowed": PHASE18_PROVIDER_READS_ALLOWED is True,
        "provider_mutations_disabled_by_default": PHASE18_PROVIDER_MUTATIONS_ALLOWED_BY_DEFAULT
        is False,
        "explicit_target_machine_authorization_required": PHASE18_EXPLICIT_TARGET_MACHINE_AUTHORIZATION_REQUIRED
        is True,
        "default_mutation_gate_denies": _default_mutation_is_denied(),
        "exact_confirmation_text_locked": PHASE18_CONFIRMATION_TEXT
        == "AUTHORIZE_PAPER_PROVIDER_MUTATION",
        "live_execution_not_promoted": PHASE18_LIVE_EXECUTION_PROMOTION_ALLOWED is False,
        "automatic_failover_disabled": PHASE18_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED
        is False,
    }
    print(f"Phase 18 accepted Phase 17 merge: {PHASE18_ACCEPTED_PHASE17_MERGE_SHA}")
    print(f"Phase 18 policy fingerprint: {phase18_policy_fingerprint()}")
    print("Provider mutations default: DISABLED")
    print("Live execution: DISABLED")
    print("Automatic cross-broker failover: DISABLED")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    failed = [name for name, value in checks.items() if not value]
    if failed:
        raise SystemExit("Phase 18 validation failed: " + ", ".join(failed))
    print("Phase 18 Paper Provider Mutation Lifecycle contracts: PASS")


if __name__ == "__main__":
    main()
