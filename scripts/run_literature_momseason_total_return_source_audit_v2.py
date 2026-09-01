from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.literature_momseason_total_return_source_v2 import (
    MomSeasonTotalReturnSourceAuditV2,
)
from packages.core.settings import load_settings


def _metric_line(name: str, metric: dict[str, object]) -> None:
    print(
        f"  {name:<36} "
        f"n={metric['count']} median={metric['median']} max={metric['max']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the overlap-stratified source-only LIT-01 Massive/Alpaca total-return "
            "audit v2. No LIT-01 target-month or protected return is read."
        )
    )
    parser.add_argument(
        "--acquire",
        action="store_true",
        help="Acquire the v2 pre-target Alpaca raw/all price audit cases.",
    )
    parser.add_argument(
        "--force-acquire",
        action="store_true",
        help="Re-acquire v2 price cases even if the v2 cache already exists.",
    )
    args = parser.parse_args()
    if args.force_acquire and not args.acquire:
        parser.error("--force-acquire requires --acquire")

    settings = load_settings(PROJECT_ROOT, "development")
    report = MomSeasonTotalReturnSourceAuditV2(settings).run_v2(
        acquire=args.acquire,
        force_acquire=args.force_acquire,
    )

    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01 Total Return Source v2")
    print(f"  status:                              {report['status']}")
    print(f"  audit version:                       {report['audit_version']}")
    print(f"  safe Alpaca bar end:                 {report['safe_bar_audit_end']}")
    print(f"  first LIT-01 target month:           {report['first_lit01_target_month']}")
    print("  overlap-stratified source population:")
    for kind, values in report["selection_summary"].items():
        print(
            f"    {kind:<27} "
            f"massive={values['massive_candidate_rows']:,} "
            f"overlap={values['exact_alpaca_action_overlap_rows']:,} "
            f"nonoverlap={values['no_exact_alpaca_action_overlap_rows']:,} "
            f"selected={values['price_audit_selected_from_overlap']}"
        )
    print("  v2 price evidence:")
    for kind, values in report["case_counts"].items():
        print(
            f"    {kind:<27} "
            f"selected={values['selected_from_exact_action_overlap']} "
            f"complete={values['complete_price_cases']}"
        )
    _metric_line("provider value relative error:", report["provider_value_relative_error"])
    _metric_line(
        "Massive scale relative error:",
        report["massive_scale_change_relative_error"],
    )
    _metric_line(
        "Alpaca scale relative error:",
        report["alpaca_scale_change_relative_error"],
    )

    worst_provider = report["worst_provider_value_cases"]
    if worst_provider:
        print("  worst provider-value cases:")
        for item in worst_provider:
            print(
                f"    {item['case_id']} error={item['value_relative_error']}"
            )
    worst_scale = report["worst_massive_scale_cases"]
    if worst_scale:
        print("  worst Massive-vs-adjustment scale cases:")
        for item in worst_scale:
            print(
                f"    {item['case_id']} error={item['massive_scale_change_relative_error']}"
            )

    print(f"  existing canonical data mutated:     {report['existing_canonical_market_data_mutated']}")
    print(f"  global Alpaca adjustment mutated:    {report['alpaca_global_adjustment_config_mutated']}")
    print(f"  target outcome rows read:            {report['target_outcome_rows_read']}")
    print(f"  protected return rows read:          {report['protected_return_rows_read']}")
    print(f"  protected holdout consumed:          {report['protected_holdout_consumed']}")
    print(f"  broker reads performed:              {report['broker_reads_performed']}")
    print(f"  order writes performed:              {report['order_writes_performed']}")
    print(f"  PAPER submits performed:             {report['paper_submits_performed']}")
    print(f"  LIVE writes performed:               {report['live_writes_performed']}")
    print(f"  report:                              {report['report_path']}")
    print(f"  coverage examples:                   {report['coverage_examples_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
