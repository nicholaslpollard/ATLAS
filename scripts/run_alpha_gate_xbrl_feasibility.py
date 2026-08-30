from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_feasibility import (
    XBRL_CONCEPT_GROUPS,
    XBRL_FEASIBILITY_CONTRACT,
    XBRL_MECHANISM,
    XBRL_MIN_ACCRUAL_HISTORY_READY,
    XBRL_MIN_PROFITABILITY_HISTORY_READY,
    XBRL_MIN_SUCCESSFUL_DOCUMENTS,
    XBRL_SAMPLE_SIZE,
    XBRLFeasibilityError,
    XBRLFundamentalFeasibility,
    xbrl_feasibility_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.sec_edgar import SEC_EDGAR_CONTACT_EMAIL_ENV
from packages.providers.sec_xbrl import SECXBRLCompanyFactsClient


def main() -> int:
    print("ATLAS Pre-Phase33 Alpha Gate — SEC XBRL Fundamental Quality Feasibility")
    print(f"Feasibility contract: {XBRL_FEASIBILITY_CONTRACT}")
    print(f"Feasibility fingerprint: {xbrl_feasibility_fingerprint()}")
    print(f"Mechanism: {XBRL_MECHANISM}")
    print("Source: official SEC data.sec.gov/api/xbrl/companyfacts")
    print(f"SEC fair-access identity: ATLAS + local {SEC_EDGAR_CONTACT_EMAIL_ENV} contact")
    print(f"Deterministic source-only issuer sample: {XBRL_SAMPLE_SIZE}")
    print(
        "Source gates: "
        f"successful_documents>={XBRL_MIN_SUCCESSFUL_DOCUMENTS} "
        f"accrual_history_ready>={XBRL_MIN_ACCRUAL_HISTORY_READY} "
        f"profitability_history_ready>={XBRL_MIN_PROFITABILITY_HISTORY_READY}"
    )
    print(
        "Concept groups: "
        + ", ".join(f"{group.group_id}={list(group.tags)}" for group in XBRL_CONCEPT_GROUPS)
    )
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        settings = load_settings()
        report = XBRLFundamentalFeasibility(
            settings, SECXBRLCompanyFactsClient()
        ).run()
    except (XBRLFeasibilityError, ProviderError, OSError, ValueError) as exc:
        print("XBRL source feasibility: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No alpha hypothesis, Phase33 entry, protected read, or trading authority was granted.")
        return 2

    print()
    print(f"XBRL source feasibility: {report['status']}")
    print(f"Source inventory unique CIKs: {report['source_inventory_unique_ciks']}")
    print(f"Sample size: {report['sample_size']}")
    print(f"Successful companyfacts documents: {report['successful_documents']}")
    print(f"Failed companyfacts documents: {report['failed_documents']}")
    print(f"Accrual-history-ready issuers: {report['accrual_history_ready']}")
    print(f"Profitability-history-ready issuers: {report['profitability_history_ready']}")
    print(f"Group history-ready counts: {report['group_history_ready_counts']}")
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
