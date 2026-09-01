from __future__ import annotations

import argparse

from packages.backtesting.literature_momseason_adjusted_predictor_source import (
    MomSeasonAdjustedPredictorSource,
)
from packages.core.settings import load_settings


def _ratio(value: object) -> str:
    if value is None:
        return "None"
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build/materialize the LIT-01 single-session Alpaca adjustment=all lag-predictor "
            "endpoint source without reading target or protected returns."
        )
    )
    parser.add_argument(
        "--acquire",
        action="store_true",
        help="Acquire any missing deterministic endpoint units from Alpaca.",
    )
    parser.add_argument(
        "--force-plan",
        action="store_true",
        help="Rebuild the deterministic endpoint plan from accepted PIT source artifacts.",
    )
    parser.add_argument(
        "--force-acquire",
        action="store_true",
        help="Re-acquire completed endpoint units; requires --acquire.",
    )
    args = parser.parse_args()
    if args.force_acquire and not args.acquire:
        parser.error("--force-acquire requires --acquire")

    settings = load_settings()
    source = MomSeasonAdjustedPredictorSource(settings)
    report = source.run(
        acquire=args.acquire,
        force_plan=args.force_plan,
        force_acquire=args.force_acquire,
    )

    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01 Adjusted Predictor Source")
    print(f"  status:                              {report['status']}")
    print(f"  contract:                            {report['contract_version']}")
    print(f"  plan fingerprint:                    {report['plan_fingerprint']}")
    print(f"  unique endpoint/instrument rows:     {report['plan_rows']:,}")
    print(f"  endpoint sessions:                   {report['planned_endpoint_sessions']}")
    print(
        "  acquisition units:                  "
        f"planned={report['planned_units']:,} complete={report['completed_units']:,} "
        f"missing={report['missing_units']:,}"
    )
    print("  endpoint availability:")
    for key, value in sorted((report.get("endpoint_status_counts") or {}).items()):
        print(f"    {key:<28} {int(value):,}")

    coverage = report.get("coverage")
    if isinstance(coverage, dict):
        hypotheses = coverage.get("hypotheses")
        if isinstance(hypotheses, dict):
            print("  predictor population coverage:")
            for hypothesis_id, raw in hypotheses.items():
                if not isinstance(raw, dict):
                    continue
                print(
                    f"    {hypothesis_id:<28} "
                    f"eligible={int(raw.get('eligible_predictor_rows') or 0):,} "
                    f"identity={int(raw.get('identity_reconstructable_predictor_rows') or 0):,} "
                    f"adjusted={int(raw.get('adjusted_endpoint_reconstructable_predictor_rows') or 0):,} "
                    f"adj/eligible={_ratio(raw.get('adjusted_reconstructable_ratio_of_eligible'))} "
                    f"adj/identity={_ratio(raw.get('adjusted_reconstructable_ratio_of_identity'))}"
                )
                failures = raw.get("failure_counts")
                if isinstance(failures, dict):
                    for reason, count in sorted(
                        failures.items(), key=lambda item: (-int(item[1]), str(item[0]))
                    ):
                        if int(count) > 0:
                            print(f"      {reason:<34} {int(count):,}")
        population = coverage.get("population_coverage")
        if isinstance(population, dict):
            print("  population contract:")
            print(f"    valid contract:                    {population.get('valid_contract')}")
            print(f"    full source scope proven:          {population.get('source_scope_proven')}")
            print(
                "    bottleneck explanation required: "
                f"{population.get('requires_bottleneck_explanation')}"
            )
            bottlenecks = population.get("bottleneck_stages") or []
            if bottlenecks:
                print(f"    bottleneck stages:                 {', '.join(map(str, bottlenecks))}")

    acquisition = report.get("acquisition")
    if isinstance(acquisition, dict):
        print("  acquisition this run:")
        print(
            "    executed/skipped units:           "
            f"{int(acquisition.get('executed_units_this_run') or 0):,}/"
            f"{int(acquisition.get('skipped_units_this_run') or 0):,}"
        )
        print(
            "    provider calls performed:         "
            f"{int(acquisition.get('provider_calls_performed') or 0):,}"
        )

    semantics = report.get("request_semantics") or {}
    print("  source request boundary:")
    print(f"    single-session requests only:      {semantics.get('start_equals_end_endpoint_session')}")
    print(f"    adjustment:                        {semantics.get('adjustment')}")
    print(f"    feed:                              {semantics.get('feed')}")
    print(f"    price currency:                    {semantics.get('currency')}")
    print(f"    asof rule:                         {semantics.get('asof_rule')}")
    print(f"    date whitelist:                    {semantics.get('date_whitelist_source')}")
    print(f"  canonical data mutated:              {report['existing_canonical_market_data_mutated']}")
    print(f"  global Alpaca adjustment mutated:    {report['global_alpaca_adjustment_config_mutated']}")
    print(f"  target outcome rows read:            {report['target_outcome_rows_read']}")
    print(f"  protected return rows read:          {report['protected_return_rows_read']}")
    print(f"  protected holdout consumed:          {report['protected_holdout_consumed']}")
    print(f"  broker reads performed:              {report['broker_reads_performed']}")
    print(f"  order writes performed:              {report['order_writes_performed']}")
    print(f"  PAPER submits performed:             {report['paper_submits_performed']}")
    print(f"  LIVE writes performed:               {report['live_writes_performed']}")
    print(f"  endpoint parquet:                    {report['endpoint_parquet_path']}")
    print(f"  report:                              {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
