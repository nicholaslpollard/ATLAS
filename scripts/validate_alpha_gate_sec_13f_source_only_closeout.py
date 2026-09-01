from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_13f_closeout import (  # noqa: E402
    SEC_13F_CLOSEOUT_CONTRACT,
    SEC_13F_CLOSEOUT_FINGERPRINT,
    SEC_13F_FAILURE_TAXONOMY,
    SEC_13F_SOURCE_DISPOSITION,
    SEC_13F_V1_LOCATOR_FAILURE_TAXONOMY,
    sec_13f_closeout_fingerprint,
)


def main() -> int:
    checks = {
        "fingerprint_exact": sec_13f_closeout_fingerprint() == SEC_13F_CLOSEOUT_FINGERPRINT,
        "contract_exact": SEC_13F_CLOSEOUT_CONTRACT
        == "alpha-gate-sec-13f-closeout-v1-as-filed-cusip-source-integrity-failure-no-market-outcomes",
        "source_disposition_exact": (
            SEC_13F_SOURCE_DISPOSITION == "ACCEPTED_NEGATIVE_SOURCE_INTEGRITY_FAILURE"
        ),
        "failure_taxonomy_exact": SEC_13F_FAILURE_TAXONOMY == "SOURCE_INTEGRITY_FAIL",
        "v1_locator_failure_is_implementation_defect": (
            SEC_13F_V1_LOCATOR_FAILURE_TAXONOMY == "IMPLEMENTATION_DEFECT_FIXED"
        ),
        "documentation_present": (
            PROJECT_ROOT / "docs" / "alpha_gate_sec_13f_source_integrity_closeout.md"
        ).is_file(),
    }
    for name, passed in checks.items():
        print(f"{name}: {passed}")
    if not all(checks.values()):
        return 2
    print("ATLAS SEC Form 13F source-integrity closeout contracts: PASS")
    print(f"Closeout contract: {SEC_13F_CLOSEOUT_CONTRACT}")
    print(f"Closeout fingerprint: {SEC_13F_CLOSEOUT_FINGERPRINT}")
    print(f"Source disposition: {SEC_13F_SOURCE_DISPOSITION}")
    print("Provider/market/protected reads by closeout: 0")
    print("Historical supported alpha: 0")
    print("Phase33 authority: BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
