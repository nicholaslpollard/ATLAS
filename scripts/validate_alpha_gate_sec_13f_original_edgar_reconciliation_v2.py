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
    SEC_13F_ORIGINAL_EDGAR_TARGET_OUTCOMES_ALLOWED,
)
from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation_v2 import (  # noqa: E402
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT,
    SEC_13F_ORIGINAL_EDGAR_V2_LOCATOR_SOURCE,
    SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_QUARTER,
    SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_URL,
    SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_YEAR,
    SEC_13F_ORIGINAL_EDGAR_V2_REUSE_V1_CACHE_AFTER_LOCATOR_CONFIRMATION,
    sec_13f_original_edgar_reconciliation_v2_fingerprint,
)


def main() -> int:
    checks = {
        "fingerprint_exact": (
            sec_13f_original_edgar_reconciliation_v2_fingerprint()
            == SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT
        ),
        "contract_v2_exact": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT.startswith(
            "alpha-gate-sec-13f-original-edgar-reconciliation-v2-master-index-authoritative-locator"
        ),
        "v1_contract_preserved": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT.startswith(
            "alpha-gate-sec-13f-original-edgar-reconciliation-v1"
        ),
        "v1_fingerprint_preserved": (
            SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT
            == "6b28e6e7eac599d1f795fed2de200c0886f49b91af29a699faa98a043521c91c"
        ),
        "scope_same_374_accessions": SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS == 374,
        "scope_same_10431_rows": SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS == 10_431,
        "official_master_index_locator": (
            SEC_13F_ORIGINAL_EDGAR_V2_LOCATOR_SOURCE == "SEC_EDGAR_2016_Q1_MASTER_INDEX"
            and SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_YEAR == 2016
            and SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_QUARTER == 1
            and SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_URL
            == "https://www.sec.gov/Archives/edgar/full-index/2016/QTR1/master.idx"
        ),
        "v1_cache_reuse_requires_locator_confirmation": (
            SEC_13F_ORIGINAL_EDGAR_V2_REUSE_V1_CACHE_AFTER_LOCATOR_CONFIRMATION
        ),
        "cusip_repair_forbidden": not SEC_13F_ORIGINAL_EDGAR_CUSIP_REPAIR_ALLOWED,
        "atlas_identity_forbidden": not SEC_13F_ORIGINAL_EDGAR_ATLAS_IDENTITY_ALLOWED,
        "target_outcomes_forbidden": not SEC_13F_ORIGINAL_EDGAR_TARGET_OUTCOMES_ALLOWED,
        "protected_outcomes_forbidden": not SEC_13F_ORIGINAL_EDGAR_PROTECTED_OUTCOMES_ALLOWED,
        "science_freeze_forbidden": not SEC_13F_ORIGINAL_EDGAR_SCIENTIFIC_FREEZE_ALLOWED,
        "phase33_blocked": not SEC_13F_ORIGINAL_EDGAR_PHASE33_AUTHORITY,
        "documentation_present": (
            PROJECT_ROOT / "docs" / "alpha_gate_sec_13f_original_edgar_reconciliation_v2.md"
        ).is_file(),
    }
    for name, passed in checks.items():
        print(f"{name}: {passed}")
    if not all(checks.values()):
        return 2
    print("ATLAS SEC Form 13F original-EDGAR reconciliation V2 contracts: PASS")
    print(f"Reconciliation V2 contract: {SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT}")
    print(f"Reconciliation V2 fingerprint: {SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT}")
    print("Frozen population: unchanged 374 accessions / 10431 malformed rows")
    print("Locator: official SEC 2016 Q1 master.idx exact archive filename")
    print("V1 partial cache: preserved and reusable only after locator confirmation")
    print("Market/protected outcomes: FORBIDDEN / UNREAD")
    print("Scientific freeze authority: NOT GRANTED")
    print("Phase33 authority: BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
