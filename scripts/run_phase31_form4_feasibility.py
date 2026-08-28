from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase31_feasibility import (
    PHASE31_DECLARED_MASSIVE_PLAN,
    PHASE31_PUBLIC_AVAILABILITY_RULE,
    Phase31FeasibilityError,
    Phase31Form4Feasibility,
    phase31_feasibility_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.phase31 import MassivePhase31Form4Client
from packages.providers.massive.rest import MassiveRESTClient


def main() -> int:
    print("ATLAS Phase 31 — SEC Form-4 Insider-Transaction Feasibility")
    print(f"Frozen feasibility fingerprint: {phase31_feasibility_fingerprint()}")
    print(f"Declared Massive plan: {PHASE31_DECLARED_MASSIVE_PLAN}")
    print("Source: accepted MassiveRESTClient -> /stocks/filings/vX/form-4")
    print("Provider endpoint status: EARLY ACCESS / BETA")
    print(f"Conservative public-availability rule: {PHASE31_PUBLIC_AVAILABILITY_RULE}")
    print("Scope: historical coverage/pagination/identity/field completeness/provenance only")
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Target/protected market outcomes: FORBIDDEN / UNREAD")
    print("Broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    client = MassivePhase31Form4Client(MassiveRESTClient(settings))
    try:
        report = Phase31Form4Feasibility(settings, client).run()
    except (Phase31FeasibilityError, ProviderError, OSError, ValueError) as exc:
        print("Phase 31 Form-4 feasibility: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No alpha hypothesis or trading authority was granted.")
        return 2

    print("Phase 31 Form-4 feasibility: PASS")
    for window in report["windows"]:
        print(
            f"  {window['label']}: rows={window['rows']} transactions={window['transaction_rows']} "
            f"tickers={window['unique_tickers']} P={window['purchase_rows_P']} S={window['sale_rows_S']} "
            f"pages={window['successful_pages']} sha256={window['evidence_sha256']}"
        )
        lag = window["filing_transaction_lag"]
        print(
            f"    filing lag rows={lag['rows_with_transaction_and_filing_dates']} "
            f"min={lag['min_calendar_days']} max={lag['max_calendar_days']} "
            f"late>2d={lag['late_over_two_day_rows']}"
        )
    print(f"Total raw rows: {report['total_rows']}")
    print(f"Total transaction rows: {report['total_transaction_rows']}")
    print(f"Total ticker-linked rows: {report['total_ticker_linked_rows']}")
    print(f"Transaction code counts: {report['aggregate_transaction_code_counts']}")
    print(f"Successful provider pages: {report['successful_provider_pages']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print("Provider writes / broker reads / broker writes / orders / PAPER / LIVE: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Feasibility report: {report['report_path']}")
    print("Next scientific action: use the observed non-performance field/population evidence to freeze a finite Phase31 scientific contract before any return read.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
