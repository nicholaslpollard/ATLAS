from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation import (  # noqa: E402
    SEC_13F_ORIGINAL_EDGAR_ATLAS_IDENTITY_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_CUSIP_REPAIR_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS,
    SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS,
    SEC_13F_ORIGINAL_EDGAR_PHASE33_AUTHORITY,
    SEC_13F_ORIGINAL_EDGAR_PROTECTED_OUTCOMES_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT,
    SEC_13F_ORIGINAL_EDGAR_SCIENTIFIC_FREEZE_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_SOURCE,
    SEC_13F_ORIGINAL_EDGAR_TARGET_OUTCOMES_ALLOWED,
    sec_13f_original_edgar_reconciliation_fingerprint,
)


def main() -> int:
    checks = {
        "fingerprint_exact": (
            sec_13f_original_edgar_reconciliation_fingerprint()
            == SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT
        ),
        "contract_exact": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT.startswith(
            "alpha-gate-sec-13f-original-edgar-reconciliation-v1"
        ),
        "scope_all_374_accessions": SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS == 374,
        "scope_all_10431_rows": SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS == 10_431,
        "original_edgar_only": SEC_13F_ORIGINAL_EDGAR_SOURCE == "SEC_EDGAR_COMPLETE_SUBMISSION",
        "cusip_repair_forbidden": not SEC_13F_ORIGINAL_EDGAR_CUSIP_REPAIR_ALLOWED,
        "atlas_identity_forbidden": not SEC_13F_ORIGINAL_EDGAR_ATLAS_IDENTITY_ALLOWED,
        "target_outcomes_forbidden": not SEC_13F_ORIGINAL_EDGAR_TARGET_OUTCOMES_ALLOWED,
        "protected_outcomes_forbidden": not SEC_13F_ORIGINAL_EDGAR_PROTECTED_OUTCOMES_ALLOWED,
        "science_freeze_forbidden": not SEC_13F_ORIGINAL_EDGAR_SCIENTIFIC_FREEZE_ALLOWED,
        "phase33_blocked": not SEC_13F_ORIGINAL_EDGAR_PHASE33_AUTHORITY,
        "documentation_present": (
            PROJECT_ROOT / "docs" / "alpha_gate_sec_13f_original_edgar_reconciliation.md"
        ).is_file(),
    }
    for name, passed in checks.items():
        print(f"{name}: {passed}")
    if not all(checks.values()):
        return 2
    print("ATLAS SEC Form 13F original-EDGAR reconciliation contracts: PASS")
    print(f"Reconciliation contract: {SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT}")
    print(f"Reconciliation fingerprint: {SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT}")
    print("Original EDGAR source reads: ALLOWED ONLY FOR THE FROZEN 374 ACCESSIONS")
    print("CUSIP repair / ATLAS identity / market outcomes: FORBIDDEN")
    print("Scientific freeze authority: NOT GRANTED")
    print("Phase33 authority: BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
