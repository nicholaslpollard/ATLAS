from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_earnings_innovation_feasibility import (
    EARNINGS_INNOVATION_ANNOUNCEMENT_TIMING_CLAIM,
    EARNINGS_INNOVATION_DIRECT_QUARTER_DURATION_DAYS,
    EARNINGS_INNOVATION_EPS_CONCEPT,
    EARNINGS_INNOVATION_EPS_UNIT,
    EARNINGS_INNOVATION_FEASIBILITY_CONTRACT,
    EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT,
    EARNINGS_INNOVATION_HISTORY_READY_MIN_DIRECT_QUARTERS,
    EARNINGS_INNOVATION_MECHANISM,
    EARNINGS_INNOVATION_SAMPLE_SIZE,
    EARNINGS_INNOVATION_SUE_BASELINE_READY_MIN_DIRECT_QUARTERS,
    EarningsInnovationFeasibilityError,
    SECEarningsInnovationFeasibility,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.sec_edgar import SEC_EDGAR_CONTACT_EMAIL_ENV
from packages.providers.sec_xbrl import SECXBRLCompanyFactsClient


def main() -> int:
    print("ATLAS Pre-Phase33 Alpha Gate — SEC Diluted-EPS Earnings-Innovation Feasibility")
    print(f"Feasibility contract: {EARNINGS_INNOVATION_FEASIBILITY_CONTRACT}")
    print(f"Feasibility fingerprint: {EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT}")
    print(f"Mechanism: {EARNINGS_INNOVATION_MECHANISM}")
    print("Source: official SEC data.sec.gov/api/xbrl/companyfacts")
    print(f"SEC fair-access identity: ATLAS + local {SEC_EDGAR_CONTACT_EMAIL_ENV} contact")
    print(f"Deterministic source-only issuer sample: {EARNINGS_INNOVATION_SAMPLE_SIZE}")
    print(
        "EPS source rule: "
        f"{EARNINGS_INNOVATION_EPS_CONCEPT} / {EARNINGS_INNOVATION_EPS_UNIT}; "
        f"direct-quarter duration={EARNINGS_INNOVATION_DIRECT_QUARTER_DURATION_DAYS}"
    )
    print(
        "History depth: "
        f"history-ready>={EARNINGS_INNOVATION_HISTORY_READY_MIN_DIRECT_QUARTERS} direct quarters; "
        f"SUE-baseline-ready>={EARNINGS_INNOVATION_SUE_BASELINE_READY_MIN_DIRECT_QUARTERS}"
    )
    print(f"Earnings-announcement timing claim: {EARNINGS_INNOVATION_ANNOUNCEMENT_TIMING_CLAIM}")
    print("This is a periodic-filing source gate, not an earnings-announcement PEAD gate.")
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        report = SECEarningsInnovationFeasibility(
            load_settings(), SECXBRLCompanyFactsClient()
        ).run()
    except (EarningsInnovationFeasibilityError, ProviderError, OSError, ValueError) as exc:
        print("SEC earnings-innovation source feasibility: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No scientific hypothesis, protected read, Phase33 entry, or trading authority was granted.")
        return 2

    print()
    print(f"SEC earnings-innovation source feasibility: {report['status']}")
    print(f"Source inventory unique CIKs: {report['source_inventory_unique_ciks']}")
    print(f"Sample size: {report['sample_size']}")
    print(f"Successful companyfacts documents: {report['successful_documents']}")
    print(f"Failed companyfacts documents: {report['failed_documents']}")
    print(f"EPS-bearing documents: {report['eps_documents']}")
    print(f"History-ready issuers: {report['history_ready_issuers']}")
    print(f"SUE-baseline-ready issuers: {report['sue_baseline_ready_issuers']}")
    print(f"Direct-quarter observations: {report['direct_quarter_observations']}")
    print(f"Calendar years observed: {report['calendar_years_observed']}")
    print(f"Same-accession context conflicts: {report['same_accession_context_conflicts']}")
    print(f"Gates: {report['gates']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(
        "Provider reads / provider writes / broker reads / broker writes / orders / PAPER / LIVE / automation: "
        f"{report['provider_reads_performed']} / {report['provider_writes_performed']} / "
        f"{report['broker_reads_performed']} / {report['broker_writes_performed']} / "
        f"{report['order_writes_performed']} / {report['paper_submits_performed']} / "
        f"{report['live_writes_performed']} / {report['automation_writes_performed']}"
    )
    print(f"Feasibility report: {report['report_path']}")
    print(f"Next scientific action: {report['next_scientific_action']}")
    print(f"Pass: {report['pass']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
