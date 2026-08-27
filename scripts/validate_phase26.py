from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase26_closeout import (
    PHASE26_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
    PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION,
    phase26_architecture_audit_checks,
    phase26_disposition,
)
from packages.backtesting.phase26_policy import PHASE26_CANDIDATES, phase26_policy_fingerprint


def main() -> None:
    architecture = phase26_architecture_audit_checks(PROJECT_ROOT)
    negative_disposition, negative_phase27 = phase26_disposition(())
    positive_disposition, positive_phase27 = phase26_disposition(("supported-candidate",))
    checks = {
        "phase26_policy_fingerprint_present": len(phase26_policy_fingerprint()) == 64,
        "frozen_candidate_count_24": len(PHASE26_CANDIDATES) == 24,
        "architecture_audit_contract_present": bool(PHASE26_ARCHITECTURE_AUDIT_CONTRACT_VERSION),
        "closeout_contract_present": bool(PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION),
        "architecture_audit_checks_pass": all(architecture.values()),
        "negative_result_is_accepted_negative": negative_disposition == "ACCEPTED_NEGATIVE",
        "negative_result_blocks_phase27": negative_phase27 is False,
        "supported_result_is_accepted_positive": positive_disposition == "ACCEPTED_POSITIVE",
        "supported_result_can_satisfy_phase27_alpha_entry": positive_phase27 is True,
    }
    print(f"Phase 26 policy fingerprint: {phase26_policy_fingerprint()}")
    print(f"Phase 26 architecture audit contract: {PHASE26_ARCHITECTURE_AUDIT_CONTRACT_VERSION}")
    print(f"Phase 26 closeout contract: {PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION}")
    for name, value in architecture.items():
        print(f"  audit.{name}: {value}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit("Phase 26 closeout contract validation failed: " + ", ".join(failed))
    print("Phase 26 closeout and anti-workaround contracts: PASS")


if __name__ == "__main__":
    main()
