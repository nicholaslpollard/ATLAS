from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_finra_short_interest_pit_audit import (
    FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_HEAD,
    FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT,
    FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT,
    FINRAShortInterestPITAudit,
    FINRAShortInterestPITAuditError,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.finra_short_interest import FINRAShortInterestClient
from packages.providers.massive.reference_data import MassiveReferenceProvider


def main() -> int:
    print("ATLAS Pre-Phase33 Alpha Gate — FINRA Consolidated Short Interest PIT Audit")
    print(f"PIT audit contract: {FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT}")
    print(f"PIT audit fingerprint: {FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT}")
    print(f"Accepted feasibility target head: {FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_HEAD}")
    print("Publication: FINRA 7th XNYS session after settlement; data available by 4:40 PM ET")
    print("Decision: next XNYS regular-session open after publication")
    print("Revision-flagged rows: EXCLUDED because FINRA exposes only the most recent corrected data")
    print("Stock-split-flagged rows: EXCLUDED from predictor eligibility")
    print("Identity: exact FINRA symbol + primary exchange; active Massive common stock at settlement and decision; same stable instrument")
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        settings = load_settings()
        report = FINRAShortInterestPITAudit(
            settings,
            FINRAShortInterestClient(),
            MassiveReferenceProvider(settings),
        ).run()
    except (FINRAShortInterestPITAuditError, ProviderError, OSError, ValueError) as exc:
        print("FINRA short-interest PIT audit: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No performance, protected, Phase33, or trading authority was granted.")
        return 2

    print()
    print(f"FINRA short-interest PIT audit: {report['status']}")
    print(f"Accepted feasibility report SHA-256: {report['accepted_feasibility_report']['sha256']}")
    print(f"Immutable exchange-listed rows: {report['immutable_exchange_listed_rows']}")
    print(f"PIT-eligible rows: {report['pit_eligible_rows']}")
    print(f"Unique PIT instruments: {report['unique_pit_instruments']}")
    print(f"Files with >=2500 PIT rows: {report['files_with_2500_pit_rows']}")
    print(f"Status counts: {report['status_counts']}")
    print(f"Gates: {report['gates']}")
    if report['failures']:
        print(f"Failures: {report['failures']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"FINRA source files / Massive PIT snapshots: {report['finra_source_files_read']} / {report['massive_reference_snapshots_read']}")
    print("Provider writes / broker reads / broker writes / orders / PAPER / LIVE / automation: 0 / 0 / 0 / 0 / 0 / 0 / 0")
    print(f"PIT audit report: {report['report_path']}")
    print(f"Next scientific action: {report['next_scientific_action']}")
    print(f"Pass: {report['pass']}")
    return 0 if report['pass'] else 1


if __name__ == "__main__":
    raise SystemExit(main())
