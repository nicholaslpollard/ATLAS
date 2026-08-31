from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_finra_short_interest_feasibility import (
    FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT,
    FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES,
    FINRA_SHORT_INTEREST_MECHANISM,
    FINRA_SHORT_INTEREST_MIN_EXCHANGE_LISTED_ROWS,
    FINRA_SHORT_INTEREST_MIN_SUCCESSFUL_FILES,
    FINRA_SHORT_INTEREST_MIN_TOTAL_ROWS,
    FINRA_SHORT_INTEREST_MIN_UNIQUE_EXCHANGE_LISTED_SYMBOLS,
    FINRA_SHORT_INTEREST_MIN_YEARS_REPRESENTED,
    FINRAShortInterestFeasibility,
    FINRAShortInterestFeasibilityError,
    finra_short_interest_feasibility_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.finra_short_interest import FINRAShortInterestClient


def main() -> int:
    print("ATLAS Pre-Phase33 Alpha Gate — FINRA Consolidated Short Interest Feasibility")
    print(f"Feasibility contract: {FINRA_SHORT_INTEREST_FEASIBILITY_CONTRACT}")
    print(f"Feasibility fingerprint: {finra_short_interest_feasibility_fingerprint()}")
    print(f"Mechanism: {FINRA_SHORT_INTEREST_MECHANISM}")
    print("Source: official FINRA cdn.finra.org historical biweekly short-interest files")
    print(
        "Frozen source-only settlement dates: "
        + ", ".join(FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES)
    )
    print(
        "Source gates: "
        f"successful_files>={FINRA_SHORT_INTEREST_MIN_SUCCESSFUL_FILES} "
        f"years>={FINRA_SHORT_INTEREST_MIN_YEARS_REPRESENTED} "
        f"rows>={FINRA_SHORT_INTEREST_MIN_TOTAL_ROWS} "
        f"exchange_listed_rows>={FINRA_SHORT_INTEREST_MIN_EXCHANGE_LISTED_ROWS} "
        "unique_exchange_listed_symbols>="
        f"{FINRA_SHORT_INTEREST_MIN_UNIQUE_EXCHANGE_LISTED_SYMBOLS}"
    )
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        settings = load_settings()
        report = FINRAShortInterestFeasibility(
            settings, FINRAShortInterestClient()
        ).run()
    except (
        FINRAShortInterestFeasibilityError,
        ProviderError,
        OSError,
        ValueError,
    ) as exc:
        print("FINRA short-interest source feasibility: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print(
            "No alpha hypothesis, Phase33 entry, protected read, or trading authority was granted."
        )
        return 2

    summary = report["source_summary"]
    print()
    print(f"FINRA short-interest source feasibility: {report['status']}")
    print(f"Successful files: {summary['successful_files']}")
    print(f"Failed files: {len(report['failures'])}")
    print(f"Years represented: {summary['years_represented']}")
    print(f"Total rows: {summary['total_rows']}")
    print(f"Exchange-listed rows: {summary['exchange_listed_rows']}")
    print(
        "Unique exchange-listed symbols: "
        f"{summary['unique_exchange_listed_symbols']}"
    )
    print(f"Revision-flagged rows: {summary['revised_rows']}")
    print(f"Stock-split-flagged rows: {summary['stock_split_flagged_rows']}")
    print(f"Gates: {report['gates']}")
    if report["failures"]:
        print(f"Source failures: {report['failures']}")
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
