from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase31_diagnostics import (
    PHASE31_FAILED_TARGET_FINGERPRINT,
    PHASE31_FAILED_TARGET_HEAD,
    Phase31Form4LagDiagnostic,
    Phase31Form4LagDiagnosticError,
)
from packages.core.settings import load_settings


def _compact(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def main() -> int:
    print("ATLAS Phase 31 — Form-4 Chronology Root-Cause Diagnostic")
    print(f"Failed target head: {PHASE31_FAILED_TARGET_HEAD}")
    print(f"Frozen feasibility fingerprint: {PHASE31_FAILED_TARGET_FINGERPRINT}")
    print("Input: immutable local Form-4 evidence from the failed target run")
    print("Provider calls: DISABLED / ZERO")
    print("Target/protected market outcomes: FORBIDDEN / UNREAD")
    print("Chronology acceptance rule: UNCHANGED")
    print()

    settings = load_settings(PROJECT_ROOT)
    diagnostic = Phase31Form4LagDiagnostic(settings)
    try:
        report = diagnostic.run()
    except Phase31Form4LagDiagnosticError as exc:
        print("Phase 31 Form-4 chronology diagnostic: FAILED")
        print(f"Reason: {exc}")
        return 1

    print("Phase 31 Form-4 chronology diagnostic: COMPLETE")
    print(f"Source failed checks: {_compact(report['source_failed_checks'])}")
    print(
        "Transaction rows with filing + transaction dates: "
        f"{report['total_transaction_rows_with_both_dates']}"
    )
    print(f"Lag relation counts: {_compact(report['lag_relation_counts'])}")
    print(
        "Violations (transaction_date > filing_date): "
        f"{report['violating_rows']} rows / "
        f"{report['violating_unique_accessions']} accessions / "
        f"{report['violating_unique_issuers']} issuers / "
        f"{report['violating_unique_owners']} owners"
    )
    print(f"Violation windows: {_compact(report['violation_window_counts'])}")
    print(f"Violation transaction codes: {_compact(report['violation_transaction_code_counts'])}")
    print(f"Violation security types: {_compact(report['violation_security_type_counts'])}")
    print(f"Violation acquired/disposed: {_compact(report['violation_acquired_disposed_counts'])}")
    print(f"Violation direct/indirect: {_compact(report['violation_direct_or_indirect_counts'])}")
    print(f"Violation 10b5-1 flags: {_compact(report['violation_10b5_1_counts'])}")
    print(f"Violation timeliness: {_compact(report['violation_timeliness_counts'])}")
    print(f"Violation insider roles: {_compact(report['violation_role_counts'])}")
    print(
        "Violation transaction-after-filing gap days: "
        f"{_compact(report['violation_transaction_after_filing_gap_days'])}"
    )
    print(
        "Violation filing->transaction date pairs: "
        f"{_compact(report['violation_filing_to_transaction_date_pairs'])}"
    )
    print(f"Violation tickers: {_compact(report['violation_ticker_counts'])}")
    print()
    print("Deterministic violating-row samples (max 20):")
    for index, sample in enumerate(report["violation_samples"], start=1):
        print(f"  [{index}] {_compact(sample)}")
    print()
    print(f"Violation artifact: {report['violation_artifact_path']}")
    print(f"Violation artifact SHA256: {report['violation_artifact_sha256']}")
    print(f"Diagnostic report: {report['report_path']}")
    print(
        "Outcome/protected/provider/broker/order/PAPER/LIVE reads-writes: "
        f"{report['target_outcome_rows_read']} / "
        f"{report['protected_candidate_rows_read']} / "
        f"{report['protected_return_rows_read']} / "
        f"{report['provider_reads']} / "
        f"{report['provider_writes']} / "
        f"{report['broker_reads']} / "
        f"{report['broker_writes']} / "
        f"{report['order_writes']} / "
        f"{report['paper_submits']} / "
        f"{report['live_writes']}"
    )
    print(f"Pass: {report['pass']}")
    print()
    print("This diagnostic does not accept Phase31 and does not change the failed chronology gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
