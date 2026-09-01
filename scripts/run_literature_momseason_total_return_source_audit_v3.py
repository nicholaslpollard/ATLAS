from __future__ import annotations

from packages.backtesting.literature_momseason_total_return_source_v3 import (
    MomSeasonTotalReturnSourceAuditV3,
)
from packages.core.settings import load_settings


def main() -> int:
    settings = load_settings()
    report = MomSeasonTotalReturnSourceAuditV3(settings).run_v3()

    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01 Total Return Source v3")
    print(f"  status:                              {report['status']}")
    print(f"  audit version:                       {report['audit_version']}")
    print(f"  primary source if PASS:              {report['primary_total_return_source_if_pass']}")
    print("  source acceptance gates:")
    for name, value in report["gates"].items():
        print(f"    {name:<42} {value}")
    print("  complete price evidence:")
    for kind, values in report["case_counts"].items():
        print(
            f"    {kind:<28} selected={values['selected']} complete={values['complete']}"
        )
    print("  dividend currency relations:")
    for name, value in report["dividend_currency_relation_counts"].items():
        print(f"    {name:<28} {value}")
    same = report["same_currency_provider_value_relative_error"]
    massive = report["currency_valid_massive_scale_relative_error"]
    alpaca = report["currency_valid_alpaca_scale_relative_error"]
    split = report["split_scale_relative_error"]
    print(
        "  same-currency provider value error: "
        f"n={same['count']} median={same['median']} max={same['max']}"
    )
    print(
        "  currency-valid Massive scale error:  "
        f"n={massive['count']} median={massive['median']} max={massive['max']}"
    )
    print(
        "  currency-valid Alpaca scale error:   "
        f"n={alpaca['count']} median={alpaca['median']} max={alpaca['max']}"
    )
    print(
        "  split scale error:                    "
        f"n={split['count']} median={split['median']} max={split['max']}"
    )
    print("  cross-currency dividend examples:")
    for row in report["cross_currency_dividend_examples"]:
        print(
            "    "
            f"{row['case_id']} Massive={row['massive_currency']} "
            f"Alpaca={row['alpaca_currency']} raw_error={row['raw_provider_value_relative_error']}"
        )
    print(f"  provider calls performed:            {report['provider_calls_performed']}")
    print(f"  existing canonical data mutated:     {report['existing_canonical_market_data_mutated']}")
    print(f"  target outcome rows read:            {report['target_outcome_rows_read']}")
    print(f"  protected return rows read:          {report['protected_return_rows_read']}")
    print(f"  protected holdout consumed:          {report['protected_holdout_consumed']}")
    print(f"  broker reads performed:              {report['broker_reads_performed']}")
    print(f"  order writes performed:              {report['order_writes_performed']}")
    print(f"  PAPER submits performed:             {report['paper_submits_performed']}")
    print(f"  LIVE writes performed:               {report['live_writes_performed']}")
    print(f"  report:                              {report['report_path']}")
    print(f"  reconciled cases:                    {report['currency_cases_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
