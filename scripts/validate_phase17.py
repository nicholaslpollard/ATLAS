from __future__ import annotations

from packages.control_plane.phase16_smoke import Phase16OperationalSmoke
from packages.control_plane.phase17_policy import (
    PHASE17_ACCEPTED_PHASE16_MERGE_SHA,
    PHASE17_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE17_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE17_PROVIDER_MUTATIONS_ALLOWED,
    PHASE17_PROVIDER_READS_ALLOWED,
    PHASE17_READONLY_REPORT_MUST_BE_SEPARATE,
    PHASE17_REQUIRED_BROKERS,
    phase17_policy_fingerprint,
    validate_phase17_policy,
)
from packages.control_plane.phase17_readiness import PHASE17_READINESS_CONTRACT_VERSION
from packages.core.settings import load_settings


EXPECTED_PHASE17_POLICY_FINGERPRINT = (
    "693113bbb09458ed2939e486f9f6e0a0bda44e331c6419065760586047b93ff8"
)
EXPECTED_PHASE17_READINESS_CONTRACT = (
    "phase17-readiness-v1-phase16-artifact-preserving-dual-broker-readonly-reconciliation"
)


def main() -> None:
    validate_phase17_policy()
    settings = load_settings()
    smoke = Phase16OperationalSmoke(settings)
    checks = {
        "accepted_phase16_merge_locked": len(PHASE17_ACCEPTED_PHASE16_MERGE_SHA) == 40,
        "policy_fingerprint_exact": phase17_policy_fingerprint()
        == EXPECTED_PHASE17_POLICY_FINGERPRINT,
        "readiness_contract_exact": PHASE17_READINESS_CONTRACT_VERSION
        == EXPECTED_PHASE17_READINESS_CONTRACT,
        "required_brokers_exact": PHASE17_REQUIRED_BROKERS == ("webull", "alpaca"),
        "provider_reads_enabled": PHASE17_PROVIDER_READS_ALLOWED is True,
        "provider_mutations_disabled": PHASE17_PROVIDER_MUTATIONS_ALLOWED is False,
        "live_execution_not_promoted": PHASE17_LIVE_EXECUTION_PROMOTION_ALLOWED is False,
        "automatic_failover_disabled": PHASE17_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False,
        "readonly_report_separation_required": PHASE17_READONLY_REPORT_MUST_BE_SEPARATE is True,
        "runtime_report_paths_separate": smoke.output_path(refresh_brokers=True)
        != smoke.output_path(refresh_brokers=False),
        "accepted_smoke_filename_stable": smoke.report_path.name
        == "phase16_operational_smoke.json",
        "readonly_smoke_filename_distinct": smoke.readonly_report_path.name
        == "phase16_provider_readonly_smoke.json",
    }
    print(f"Phase 17 accepted Phase 16 merge: {PHASE17_ACCEPTED_PHASE16_MERGE_SHA}")
    print(f"Phase 17 policy fingerprint: {phase17_policy_fingerprint()}")
    print(f"Phase 17 readiness contract: {PHASE17_READINESS_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    failed = [name for name, value in checks.items() if not value]
    if failed:
        raise SystemExit("Phase 17 validation failed: " + ", ".join(failed))
    print("Phase 17 Provider-Readonly Operational Readiness contracts: PASS")


if __name__ == "__main__":
    main()
