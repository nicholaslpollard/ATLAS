from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_13f_closeout import (  # noqa: E402
    SEC_13F_CLOSEOUT_CONTRACT,
    SEC_13F_CLOSEOUT_FINGERPRINT,
    close_sec_13f_source_only,
)
from packages.core.settings import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings()
    print("ATLAS Pre-Phase33 — SEC Form 13F Source-Integrity Closeout")
    print(f"Contract: {SEC_13F_CLOSEOUT_CONTRACT}")
    print(f"Fingerprint: {SEC_13F_CLOSEOUT_FINGERPRINT}")
    print("Input: persisted original-EDGAR reconciliation V2 report only")
    print("Provider / market / protected / broker reads: FORBIDDEN")
    print()

    result = close_sec_13f_source_only(settings)

    print(f"Closeout status: {result['status']}")
    print(f"Disposition: {result['source_disposition']}")
    print(f"Failure taxonomy: {result['failure_taxonomy']}")
    print(f"Affected accessions: {result['affected_accessions']}")
    print(f"Bulk malformed rows: {result['bulk_malformed_rows']}")
    print(f"Original malformed rows: {result['original_malformed_cusip_rows']}")
    print(f"Exact CUSIP-multiset-match accessions: {result['exact_cusip_multiset_match_accessions']}")
    print(
        "Malformed rows exactly preserved in original: "
        f"{result['bulk_malformed_rows_exactly_preserved_in_original']}"
    )
    print(f"V1 locator failure taxonomy: {result['v1_locator_failure_taxonomy']}")
    print(f"Reconciliation report SHA-256: {result['reconciliation_report_sha256']}")
    print(f"Provider reads performed by closeout: {result['provider_reads_performed']}")
    print(f"Target outcome rows read: {result['target_outcome_rows_read']}")
    print(f"Protected return rows read: {result['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {result['protected_holdout_consumed']}")
    print(f"Historical supported alpha: {result['historical_supported_alpha']}")
    print(f"Phase33 authority: {result['phase33_signal_to_trade_authority']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
