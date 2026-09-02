from __future__ import annotations

import argparse

from packages.backtesting.literature_momseason_development_identity_repair import (
    MomSeasonDevelopmentResearchIdentitySafe,
)
from packages.core.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run frozen LIT-01 development holdings, target acquisition, and native evaluation."
    )
    parser.add_argument(
        "--acquire",
        action="store_true",
        help=(
            "Permit source-only FIGI ticker-event continuity reads as needed, then open only "
            "the frozen development target endpoints and evaluate the native family."
        ),
    )
    parser.add_argument("--force-plan", action="store_true")
    parser.add_argument("--force-acquire", action="store_true")
    args = parser.parse_args()

    result = MomSeasonDevelopmentResearchIdentitySafe(load_settings()).run(
        acquire=args.acquire,
        force_plan=args.force_plan,
        force_acquire=args.force_acquire,
    )
    print("ATLAS Literature-Anchored Alpha Exploration — LIT-01 Development")
    print(f"  status:                              {result['status']}")
    print(f"  contract:                            {result['contract_version']}")
    print(f"  freeze fingerprint:                  {result['freeze_fingerprint']}")
    identity_source = result.get("identity_continuity_source")
    if identity_source is not None:
        print("  pre-outcome identity continuity:")
        print(
            "    provider calls this run:           "
            f"{identity_source['provider_calls_performed_this_run']}"
        )
        print(
            "    cache hits this run:               "
            f"{identity_source['cache_hits_this_run']}"
        )
        print(
            "    authoritative endpoint resolutions:"
            f" {identity_source['authoritative_endpoint_resolutions_this_run']}"
        )
        print(
            "    canonical ticker store mutated:    "
            f"{identity_source['canonical_ticker_event_store_mutated']}"
        )
    plan = result["plan"]
    print("  frozen holdings/target plan:")
    print(f"    development months:                {plan['development_month_count']}")
    print(f"    range:                             {plan['development_month_start']} through {plan['development_month_end']}")
    print(f"    holdings rows:                     {plan['holdings_rows']}")
    print(f"    holdings fingerprint:              {plan['holdings_fingerprint']}")
    print(f"    target endpoint rows:              {plan['target_plan_rows']}")
    print(f"    target plan fingerprint:           {plan['target_plan_fingerprint']}")
    acquisition = result.get("acquisition")
    if acquisition is not None:
        print("  target acquisition:")
        print(f"    planned units:                     {acquisition['planned_units']}")
        print(f"    executed this run:                 {acquisition['executed_units_this_run']}")
        print(f"    skipped this run:                  {acquisition['skipped_units_this_run']}")
        print(f"    provider calls this run:           {acquisition['provider_calls_performed_this_run']}")
        print(f"    availability:                      {acquisition['availability_counts']}")
    print(f"  target endpoint availability:        {result['target_endpoint_availability_counts']}")
    print(f"  missing target units:                {result['missing_target_units']}")
    evaluation = result.get("evaluation")
    if evaluation is not None:
        print("  development evaluation:")
        print(f"    source complete:                   {evaluation['source_complete']}")
        print(f"    complete holding returns:          {evaluation['complete_holding_returns']}")
        print(f"    unavailable holding returns:       {evaluation['unavailable_holding_returns']}")
        if evaluation.get("source_complete"):
            print(f"    family finalist:                   {evaluation['family_finalist']}")
            print(f"    finalists:                         {evaluation['finalist_hypotheses']}")
            for hypothesis_id, item in evaluation["hypotheses"].items():
                print(f"    {hypothesis_id}:")
                print(f"      gross mean:                      {item['gross_mean']:.8f}")
                print(f"      primary after-cost mean:         {item['primary_mean']:.8f}")
                print(f"      primary 90% LCB:                 {item['primary_lcb']:.8f}")
                print(f"      one-sided bootstrap p:           {item['primary_p_value']:.8f}")
                print(f"      Holm threshold:                  {item['holm_threshold']:.8f}")
                print(f"      Holm rejected:                   {item['holm_rejected_null']}")
                print(f"      stress mean:                     {item['stress_mean']:.8f}")
                print(f"      passed all primary checks:       {item['passed_all_primary_checks']}")
    print("  safety boundary:")
    print(f"    development outcome rows read:     {result['development_outcome_rows_read']}")
    print(f"    protected return rows read:        {result['protected_return_rows_read']}")
    print(f"    protected holdout consumed:        {result['protected_holdout_consumed']}")
    print(f"    provider reads this run:           {result['provider_reads_performed_this_run']}")
    print(f"    broker reads performed:            {result['broker_reads_performed']}")
    print(f"    order writes performed:            {result['order_writes_performed']}")
    print(f"    PAPER submits performed:           {result['paper_submits_performed']}")
    print(f"    LIVE writes performed:             {result['live_writes_performed']}")
    print(f"  report:                              {result['report_path']}")


if __name__ == "__main__":
    main()
