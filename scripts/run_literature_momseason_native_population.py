from __future__ import annotations

import argparse

from packages.backtesting.literature_momseason_native_population import (
    MomSeasonNativePopulationSource,
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
            "Reconstruct the LIT-01 externally specified NYSE/AMEX common-stock "
            "source population, reuse accepted adjusted endpoints, and acquire only "
            "supplemental lag endpoints required by the available-history rule."
        )
    )
    parser.add_argument(
        "--acquire",
        action="store_true",
        help="Acquire only missing native endpoint keys not present in the accepted endpoint parquet.",
    )
    parser.add_argument(
        "--force-plan",
        action="store_true",
        help="Rebuild the native endpoint plan from PIT reference artifacts.",
    )
    parser.add_argument(
        "--force-acquire",
        action="store_true",
        help="Re-acquire completed supplemental endpoint units; requires --acquire.",
    )
    args = parser.parse_args()
    if args.force_acquire and not args.acquire:
        parser.error("--force-acquire requires --acquire")

    settings = load_settings()
    source = MomSeasonNativePopulationSource(settings)
    report = source.run(
        acquire=args.acquire,
        force_plan=args.force_plan,
        force_acquire=args.force_acquire,
    )

    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01 Native Population Source")
    print(f"  status:                              {report['status']}")
    print(f"  contract:                            {report['contract_version']}")

    native_plan = report.get("native_plan") or {}
    print(f"  native plan fingerprint:             {native_plan.get('plan_fingerprint')}")
    print(f"  native endpoint rows:                {int(native_plan.get('endpoint_plan_rows') or 0):,}")
    print("  externally specified formation rule:")
    formation_rule = native_plan.get("formation_rule") or {}
    print(f"    exchanges:                         {', '.join(formation_rule.get('primary_exchange') or [])}")
    print(f"    security type:                     {formation_rule.get('security_type')}")
    print("    discovery-route filter inherited:  False")
    print("  historical lag rule:")
    history_rule = native_plan.get("historical_lag_rule") or {}
    print(f"    master-table exchanges:            {', '.join(history_rule.get('primary_exchange') or [])}")
    print(f"    security type:                     {history_rule.get('security_type')}")
    print(f"    ticker changes inside lag:         {history_rule.get('ticker_change_inside_lag_month')}")
    print("  history availability rule:")
    availability_rule = native_plan.get("history_availability_rule") or {}
    print(f"    momseason_short_year1:              {availability_rule.get('momseason_short_year1')}")
    print(f"    momseason_years2_5:                 {availability_rule.get('momseason_years2_5')}")

    supplemental = report.get("supplemental_plan") or {}
    print("  endpoint reuse/supplement:")
    print(f"    reused accepted endpoint rows:     {int(supplemental.get('reused_prior_endpoint_rows') or 0):,}")
    print(f"    supplemental endpoint rows:        {int(supplemental.get('supplemental_endpoint_rows') or 0):,}")
    print(f"    supplemental fingerprint:          {supplemental.get('supplemental_plan_fingerprint')}")

    print("  native endpoint availability:")
    for key, value in sorted((report.get("endpoint_availability_counts") or {}).items()):
        print(f"    {key:<34} {int(value):,}")

    coverage = report.get("coverage") or {}
    hypotheses = coverage.get("hypotheses") or {}
    print("  literature-native predictor coverage:")
    for hypothesis_id, raw in hypotheses.items():
        if not isinstance(raw, dict):
            continue
        print(
            f"    {hypothesis_id:<28} "
            f"native={int(raw.get('native_eligible_rows') or 0):,} "
            f"identity={int(raw.get('identity_formula_defined_rows') or 0):,} "
            f"adjusted={int(raw.get('adjusted_formula_defined_rows') or 0):,} "
            f"adj/native={_ratio(raw.get('adjusted_ratio_of_native'))} "
            f"adj/identity={_ratio(raw.get('adjusted_ratio_of_identity'))}"
        )
        print(
            "      monthly adjusted cross-section:  "
            f"min={raw.get('monthly_adjusted_min')} "
            f"median={raw.get('monthly_adjusted_median')} "
            f"max={raw.get('monthly_adjusted_max')}"
        )
        print("      adjusted valid lag-count distribution:")
        for lag_count, count in sorted(
            (raw.get("adjusted_valid_lag_count_distribution") or {}).items(),
            key=lambda item: int(item[0]),
        ):
            print(f"        {lag_count} valid lag(s):              {int(count):,}")
        formation_failures = raw.get("formation_failure_counts") or {}
        if formation_failures:
            print("      formation-source failures:")
            for reason, count in sorted(
                formation_failures.items(), key=lambda item: (-int(item[1]), str(item[0]))
            ):
                if int(count):
                    print(f"        {reason:<32} {int(count):,}")
        lag_failures = raw.get("lag_identity_failure_counts") or {}
        if lag_failures:
            print("      lag identity/source failures:")
            for reason, count in sorted(
                lag_failures.items(), key=lambda item: (-int(item[1]), str(item[0]))
            ):
                if int(count):
                    print(f"        {reason:<32} {int(count):,}")
        print(
            "      ticker-change lags allowed:       "
            f"{int(raw.get('ticker_change_lags_allowed') or 0):,}"
        )

    population = coverage.get("population_coverage") or {}
    print("  population contract:")
    print(f"    valid contract:                    {population.get('valid_contract')}")
    print(f"    full native source scope proven:   {population.get('source_scope_proven')}")
    print(
        "    bottleneck explanation required: "
        f"{population.get('requires_bottleneck_explanation')}"
    )
    bottlenecks = population.get("bottleneck_stages") or []
    if bottlenecks:
        print(f"    bottleneck stages:                 {', '.join(map(str, bottlenecks))}")

    acquisition = report.get("acquisition")
    if isinstance(acquisition, dict):
        print("  supplemental acquisition this run:")
        print(
            "    executed/skipped units:           "
            f"{int(acquisition.get('executed_units_this_run') or 0):,}/"
            f"{int(acquisition.get('skipped_units_this_run') or 0):,}"
        )
        print(
            "    provider calls performed:         "
            f"{int(acquisition.get('provider_calls_performed') or 0):,}"
        )

    boundary = report.get("source_request_boundary") or {}
    print("  source request boundary:")
    print(f"    single-session requests only:      {boundary.get('single_session_requests_only')}")
    print(f"    adjustment:                        {boundary.get('adjustment')}")
    print(f"    feed:                              {boundary.get('feed')}")
    print(f"    price currency:                    {boundary.get('currency')}")
    print(f"    asof rule:                         {boundary.get('asof_rule')}")
    print(f"    date whitelist:                    {boundary.get('date_whitelist')}")
    print(f"  provider calls performed this run:   {report['provider_calls_performed_this_run']}")
    print(f"  canonical data mutated:              {report['existing_canonical_market_data_mutated']}")
    print(f"  global Alpaca adjustment mutated:    {report['global_alpaca_adjustment_mutated']}")
    print(f"  target outcome rows read:            {report['target_outcome_rows_read']}")
    print(f"  protected return rows read:          {report['protected_return_rows_read']}")
    print(f"  protected holdout consumed:          {report['protected_holdout_consumed']}")
    print(f"  broker reads performed:              {report['broker_reads_performed']}")
    print(f"  order writes performed:              {report['order_writes_performed']}")
    print(f"  PAPER submits performed:             {report['paper_submits_performed']}")
    print(f"  LIVE writes performed:               {report['live_writes_performed']}")
    print(f"  native endpoint parquet:             {report.get('native_endpoint_path')}")
    print(f"  report:                              {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
