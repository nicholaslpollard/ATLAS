from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_feasibility import (
    PHASE32_DECLARED_MASSIVE_PLAN,
    PHASE32_PUBLIC_AVAILABILITY_RULE,
    Phase32EightKFeasibility,
    Phase32FeasibilityError,
    phase32_feasibility_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.phase32 import MassivePhase32SECIndexClient
from packages.providers.massive.rest import MassiveRESTClient
from packages.providers.sec_edgar import SECEDGARClient, SEC_EDGAR_CONTACT_EMAIL_ENV


def main() -> int:
    print("ATLAS Phase 32 — SEC 8-K Material Corporate-Event Feasibility")
    print(f"Frozen feasibility fingerprint: {phase32_feasibility_fingerprint()}")
    print(f"Declared Massive plan: {PHASE32_DECLARED_MASSIVE_PLAN}")
    print("Discovery source: MassiveRESTClient -> /stocks/filings/vX/index (form_type=8-K)")
    print("Timestamp/item source: official SEC data.sec.gov company submissions metadata")
    print(f"SEC fair-access identity: ATLAS + local {SEC_EDGAR_CONTACT_EMAIL_ENV} contact")
    print(f"Conservative public-availability rule: {PHASE32_PUBLIC_AVAILABILITY_RULE}")
    print("Scope: source access/history/ticker linkage/acceptance timestamp/item-code provenance only")
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Target/protected market outcomes: FORBIDDEN / UNREAD")
    print("Broker/order/PAPER/LIVE activity: DISABLED")
    print()

    try:
        settings = load_settings()
        index_client = MassivePhase32SECIndexClient(MassiveRESTClient(settings))
        sec_client = SECEDGARClient()
        report = Phase32EightKFeasibility(settings, index_client, sec_client).run()
    except (Phase32FeasibilityError, ProviderError, OSError, ValueError) as exc:
        print("Phase 32 8-K feasibility: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No alpha hypothesis, Phase33 entry, or trading authority was granted.")
        return 2

    print("Phase 32 8-K feasibility: PASS")
    for window in report["windows"]:
        print(
            f"  {window['label']}: index_rows={window['index_rows']} "
            f"tickers={window['unique_tickers']} massive_pages={window['successful_massive_pages']} "
            f"sec_records={window['sec_records_fetched']} item_records={window['sec_records_with_item_codes']} "
            f"acceptance_date_mismatches={window['acceptance_date_massive_filing_date_mismatch_count']} "
            f"sec_filing_date_mismatches={window['sec_filing_date_massive_filing_date_mismatch_count']} "
            f"index_sha256={window['massive_index_sha256']}"
        )
        print(f"    item_codes={window['unique_item_codes']}")
    print(f"Total 8-K index rows: {report['total_index_rows']}")
    print(f"Total ticker-linked rows: {report['total_ticker_linked_rows']}")
    print(f"Total sampled SEC records: {report['total_sec_records_fetched']}")
    print(f"Total sampled SEC item codes: {report['total_item_codes']}")
    print(f"Successful Massive pages: {report['successful_massive_pages']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print("Provider writes / broker reads / broker writes / orders / PAPER / LIVE: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Feasibility report: {report['report_path']}")
    print(
        "Next scientific action: freeze a finite SEC-item-code Phase32 hypothesis family "
        "only after this non-performance source evidence is accepted."
    )
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
