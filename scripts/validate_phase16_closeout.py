from __future__ import annotations

from packages.control_plane.phase16_closeout import (
    PHASE16_CLOSEOUT_CONTRACT_VERSION,
    PHASE16_NEXT_CHECKPOINT,
    Phase16Closeout,
)
from packages.control_plane.phase16_smoke import (
    PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION,
    Phase16OperationalSmoke,
)
from packages.control_plane.phase16_validation import (
    PHASE16_ACCEPTED_CLEANUP_POLICY_FINGERPRINT,
    PHASE16_ACCEPTED_HTTP_CONTRACT_VERSION,
    PHASE16_ACCEPTED_POLICY_FINGERPRINT,
    PHASE16_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
    Phase16IndependentValidator,
)
from packages.control_plane.cleanup_policy import cleanup_policy_fingerprint
from packages.control_plane.http_server import CONTROL_PLANE_HTTP_CONTRACT_VERSION
from packages.control_plane.phase16_policy import phase16_policy_fingerprint


def main() -> None:
    checks = {
        "independent_validation_contract_locked": PHASE16_INDEPENDENT_VALIDATION_CONTRACT_VERSION
        == "phase16-validation-v1-independent-source-authority-route-recovery-zero-provider-write",
        "operational_smoke_contract_locked": PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION
        == "phase16-smoke-v1-loopback-no-provider-default-explicit-readonly-broker-refresh",
        "closeout_contract_locked": PHASE16_CLOSEOUT_CONTRACT_VERSION
        == "phase16-closeout-v1-phase15-bound-independent-validation-loopback-smoke-zero-provider-mutation",
        "phase16_policy_fingerprint_exact": phase16_policy_fingerprint()
        == PHASE16_ACCEPTED_POLICY_FINGERPRINT,
        "cleanup_policy_fingerprint_exact": cleanup_policy_fingerprint()
        == PHASE16_ACCEPTED_CLEANUP_POLICY_FINGERPRINT,
        "http_contract_exact": CONTROL_PLANE_HTTP_CONTRACT_VERSION
        == PHASE16_ACCEPTED_HTTP_CONTRACT_VERSION,
        "provider_mutation_is_separate_checkpoint": PHASE16_NEXT_CHECKPOINT
        == "PROVIDER_MUTATION_REQUIRES_SEPARATE_EXPLICIT_USER_CHECKPOINT",
        "validator_class_present": callable(getattr(Phase16IndependentValidator, "run", None)),
        "smoke_class_present": callable(getattr(Phase16OperationalSmoke, "run", None)),
        "closeout_class_present": callable(getattr(Phase16Closeout, "run", None)),
    }
    print(f"Phase 16 independent validation: {PHASE16_INDEPENDENT_VALIDATION_CONTRACT_VERSION}")
    print(f"Phase 16 operational smoke: {PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION}")
    print(f"Phase 16 closeout: {PHASE16_CLOSEOUT_CONTRACT_VERSION}")
    print(f"Phase 16 next checkpoint: {PHASE16_NEXT_CHECKPOINT}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise SystemExit("Phase 16 closeout contract validation failed: " + ", ".join(failed))
    print("Phase 16 independent closeout contracts: PASS")


if __name__ == "__main__":
    main()
