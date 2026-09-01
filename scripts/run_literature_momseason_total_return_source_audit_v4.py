from __future__ import annotations

from packages.backtesting.literature_momseason_total_return_source_v4 import (
    MomSeasonTotalReturnSourceAuditV4,
)
from packages.core.settings import load_settings


def _fmt_metric(metric: dict[str, object]) -> str:
    return (
        f"n={metric.get('count')} median={metric.get('median')} "
        f"max={metric.get('max')}"
    )


def main() -> int:
    settings = load_settings()
    report = MomSeasonTotalReturnSourceAuditV4(settings).run_v4()

    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01 Total Return Source v4")
    print(f"  status:                              {report['status']}")
    print(f"  audit version:                       {report['audit_version']}")
    print(f"  primary source if PASS:              {report['primary_total_return_source_if_pass']}")
    print("  source acceptance gates:")
    for name, value in report["gates"].items():
        print(f"    {name:<44} {value}")
    print("  complete price evidence:")
    for kind, values in report["case_counts"].items():
        print(
            f"    {kind:<28} selected={values['selected']} "
            f"complete={values['complete']}"
        )
    print(
        "  Alpaca internal scale error:          "
        + _fmt_metric(report["alpaca_internal_scale_relative_error"])
    )
    print(
        "  Massive USD dividend scale error:    "
        + _fmt_metric(report["massive_usd_dividend_scale_relative_error"])
    )
    print(
        "  split scale error:                   "
        + _fmt_metric(report["split_scale_relative_error"])
    )
    print("  Massive USD dividend corroboration cases:")
    for row in report["massive_usd_dividend_cases"]:
        print(
            f"    {row['case_id']} currency={row['massive_currency']} "
            f"error={row['massive_scale_change_relative_error']}"
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
    print(f"  acceptance cases:                    {report['acceptance_cases_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
