from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation import (  # noqa: E402
    SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS,
    SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS,
)
from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation_v2 import (  # noqa: E402
    SEC13FOriginalEdgarReconciliationV2,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT,
)
from packages.core.settings import load_settings  # noqa: E402
from packages.providers.sec_edgar_archive import (  # noqa: E402
    SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES,
    SECEDGARArchiveClient,
)


def main() -> int:
    settings = load_settings()
    print("ATLAS Pre-Phase33 — SEC Form 13F Original-EDGAR CUSIP Reconciliation V2")
    print(f"Contract: {SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT}")
    print(f"Fingerprint: {SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT}")
    print(
        "Frozen scope unchanged: "
        f"{SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS} malformed accessions / "
        f"{SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS} malformed bulk rows"
    )
    print("Locator authority: official SEC 2016 Q1 master.idx exact archive filenames")
    print("V1 partial original-filings cache: reused only after master-index confirmation")
    print("CUSIP repair / ATLAS identity / market outcomes / protected returns: FORBIDDEN")
    print()

    client = SECEDGARArchiveClient(
        submission_max_response_bytes=SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES
    )
    result = SEC13FOriginalEdgarReconciliationV2(settings, client, progress=print).run()

    print()
    print(f"Original-EDGAR reconciliation V2: {result['status']}")
    print(f"Affected accessions reconciled: {result['affected_accessions']}")
    print(f"Master-index-resolved accessions: {result['master_index_resolved_accessions']}")
    print(
        "Master-index archive CIK differs from bulk CIK: "
        f"{result['master_index_archive_cik_differs_from_bulk_cik_accessions']}"
    )
    print(f"V1 cached originals reused: {result['v1_cache_reused_accessions']}")
    print(f"Bulk malformed rows: {result['bulk_malformed_rows']}")
    print(f"Original CUSIP rows: {result['original_cusip_rows']}")
    print(f"Original malformed CUSIP rows: {result['original_malformed_cusip_rows']}")
    print(f"Original nine-character CUSIP fraction: {result['original_nine_char_cusip_fraction']:.6f}")
    print(f"Row-count-match accessions: {result['row_count_match_accessions']}")
    print(f"Exact CUSIP-multiset-match accessions: {result['exact_cusip_multiset_match_accessions']}")
    print(
        "Bulk malformed rows exactly preserved in original: "
        f"{result['bulk_malformed_rows_exactly_preserved_in_original']}"
    )
    print(
        "Bulk short rows whose left-zero-pad candidate exists in original: "
        f"{result['bulk_short_rows_left_zero_pad_candidate_present_in_original']}"
    )
    print("Classification counts:")
    for name, count in result["classification_counts"].items():
        bad_rows = result["classification_bulk_malformed_rows"].get(name, 0)
        print(f"  {name}: accessions={count} bulk_malformed_rows={bad_rows}")

    governance = result["governance"]
    print(f"Provider reads performed this run: {governance['provider_reads_performed']}")
    print(f"  master.idx reads: {governance['master_index_reads_performed']}")
    print(f"  complete-submission reads: {governance['complete_submission_reads_performed']}")
    print(f"CUSIP repair performed: {governance['cusip_repair_performed']}")
    print(f"ATLAS identity granted: {governance['atlas_identity_granted']}")
    print(f"Target outcome rows read: {governance['target_outcome_rows_read']}")
    print(f"Protected return rows read: {governance['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {governance['protected_holdout_consumed']}")
    print(f"Scientific freeze allowed: {governance['scientific_freeze_allowed']}")
    print(f"Phase33 authority: {governance['phase33_signal_to_trade_authority']}")
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
