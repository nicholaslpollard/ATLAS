from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.literature_momseason_feasibility import MomSeasonSourceFeasibility
from packages.core.settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the source-only LIT-01 Heston-Sadka seasonality feasibility census. "
            "No target-month or protected return is read."
        )
    )
    parser.add_argument(
        "--acquire",
        action="store_true",
        help="Acquire missing research-only Massive historical reference and corporate-action sources.",
    )
    parser.add_argument(
        "--force-acquire",
        action="store_true",
        help="Re-acquire research-only source cache entries even when already materialized.",
    )
    args = parser.parse_args()
    if args.force_acquire and not args.acquire:
        parser.error("--force-acquire requires --acquire")

    settings = load_settings(PROJECT_ROOT, "development")
    report = MomSeasonSourceFeasibility(settings).run(
        acquire=args.acquire,
        force_acquire=args.force_acquire,
    )

    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01")
    print(f"  status:                             {report['status']}")
    print(f"  contract:                           {report['contract_version']}")
    print(f"  source fingerprint:                 {report['source_fingerprint']}")
    print(f"  hypotheses:                         {len(report['hypotheses'])}")

    temporal = report["temporal_capacity"]
    print("  temporal capacity:")
    print(
        "    development complete months:      "
        f"{temporal['development_complete_months']}"
    )
    print(
        "    protected predictor months:       "
        f"{temporal['protected_predictor_months']}"
    )
    print(
        "    protected complete target months: "
        f"{temporal['protected_complete_target_months']} / "
        f"{temporal['minimum_protected_complete_months']} required"
    )
    print(
        "    current holdout sufficient:        "
        f"{temporal['current_protected_temporal_capacity_sufficient']}"
    )

    refs = report["research_reference_inventory"]
    print("  historical PIT reference cache:")
    print(
        "    materialized / required:           "
        f"{refs['materialized_reference_dates']} / {refs['required_reference_dates']}"
    )

    actions = report["corporate_action_inventory"]
    for name in ("splits", "dividends"):
        item = actions[name]
        print(
            f"  {name:<10} source:                  "
            f"available={item['available']} rows={item['row_count']} "
            f"missing_factor={item['missing_historical_adjustment_factor']}"
        )

    census = report["predictor_input_census"]
    if census is None:
        print("  predictor input census:              NOT RUN — source inputs incomplete")
    else:
        print("  predictor input census:")
        for hypothesis in report["hypotheses"]:
            hypothesis_id = hypothesis["hypothesis_id"]
            item = census["hypotheses"][hypothesis_id]
            print(
                f"    {hypothesis_id}: "
                f"reconstructable={item.get('identity_price_reconstructable_rows', 0):,} / "
                f"formation={item.get('formation_rows', 0):,}"
            )
            for reason in (
                "formation_fallback_identity",
                "historical_identity_unavailable",
                "ticker_changed_inside_lag_month",
                "month_end_price_unavailable",
            ):
                if item.get(reason, 0):
                    print(f"      {reason}: {item[reason]:,}")

    print(f"  target outcome rows read:            {report['target_outcome_rows_read']}")
    print(f"  protected return rows read:          {report['protected_return_rows_read']}")
    print(f"  protected holdout consumed:          {report['protected_holdout_consumed']}")
    print(f"  report:                              {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
