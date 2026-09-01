from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.literature_momseason_total_return_source import (
    MomSeasonTotalReturnSourceAudit,
)
from packages.core.settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the source-only LIT-01 Massive/Alpaca total-return semantics audit. "
            "All bar reads are frozen before September 2021, so no LIT-01 target or "
            "protected return is opened."
        )
    )
    parser.add_argument(
        "--acquire",
        action="store_true",
        help=(
            "Acquire research-only Alpaca corporate actions plus deterministic raw/all "
            "pre-target price audit cases."
        ),
    )
    parser.add_argument(
        "--force-acquire",
        action="store_true",
        help="Re-acquire the isolated Alpaca research source cache.",
    )
    args = parser.parse_args()
    if args.force_acquire and not args.acquire:
        parser.error("--force-acquire requires --acquire")

    settings = load_settings(PROJECT_ROOT, "development")
    report = MomSeasonTotalReturnSourceAudit(settings).run(
        acquire=args.acquire,
        force_acquire=args.force_acquire,
    )

    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01 Total Return Source")
    print(f"  status:                              {report['status']}")
    print(f"  audit version:                       {report['audit_version']}")
    if "safe_bar_audit_start" in report:
        print(
            "  safe Alpaca bar interval:            "
            f"{report['safe_bar_audit_start']} .. {report['safe_bar_audit_end']}"
        )
        print(
            "  first LIT-01 target month:            "
            f"{report['first_lit01_target_month']}"
        )
        print(
            "  selected / complete price cases:      "
            f"{report['selected_case_count']} / {report['complete_price_case_count']}"
        )
        print(
            "  Alpaca corporate-action matches:      "
            f"{report['alpaca_action_match_count']}"
        )
        for kind, counts in report["case_counts"].items():
            print(
                f"    {kind:<27} "
                f"selected={counts['selected']} "
                f"action_match={counts['alpaca_action_matched']} "
                f"complete={counts['complete_price_cases']}"
            )
        value_error = report["value_relative_error"]
        scale_error = report["scale_change_relative_error"]
        print(
            "  provider value relative error:        "
            f"n={value_error['count']} median={value_error['median']} max={value_error['max']}"
        )
        print(
            "  adjustment scale relative error:      "
            f"n={scale_error['count']} median={scale_error['median']} max={scale_error['max']}"
        )
        print(
            "  existing canonical data mutated:      "
            f"{report['existing_canonical_market_data_mutated']}"
        )
        print(
            "  global Alpaca adjustment mutated:     "
            f"{report['alpaca_global_adjustment_config_mutated']}"
        )

    print(f"  target outcome rows read:             {report['target_outcome_rows_read']}")
    print(f"  protected return rows read:           {report['protected_return_rows_read']}")
    print(f"  protected holdout consumed:           {report['protected_holdout_consumed']}")
    print(f"  broker reads performed:               {report['broker_reads_performed']}")
    print(f"  order writes performed:               {report['order_writes_performed']}")
    print(f"  PAPER submits performed:              {report['paper_submits_performed']}")
    print(f"  LIVE writes performed:                {report['live_writes_performed']}")
    print(f"  report:                               {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
