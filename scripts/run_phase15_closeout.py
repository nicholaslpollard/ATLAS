from __future__ import annotations

import argparse
from datetime import date

from packages.core.settings import load_settings
from packages.execution.phase15_closeout import Phase15Closeout


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the complete ATLAS Phase 15 broker-neutral execution/outcome-learning closeout."
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Optional accepted Phase 14 date (YYYY-MM-DD). Defaults to accepted Phase 14 closeout.",
    )
    args = parser.parse_args()
    settings = load_settings()

    print("ATLAS Phase 15 Broker Execution and Outcome Learning Closeout")
    print(
        "  safety: exact accepted cumulative foundation + accepted Phase 14 only; "
        "zero-case acceptance performs no quote/broker initialization and no provider submissions; "
        "live execution remains disabled"
    )
    closeout = Phase15Closeout(settings).run(
        as_of_date=args.as_of,
        progress=lambda message: print(f"  {message}"),
    )
    if closeout.get("pass") is not True:
        raise SystemExit("  Phase 15 closeout: FAIL")

    print("  acceptance evidence:")
    print(f"    as-of:                         {closeout['as_of_date']}")
    print(f"    cumulative foundation:         {closeout['cumulative_foundation_fingerprint']}")
    print(f"    cumulative policy:             {closeout['cumulative_policy_fingerprint']}")
    print(f"    execution cases:               {int(closeout['execution_case_count']):,}")
    print(f"    disposition records:           {int(closeout['record_count']):,}")
    print(f"    quote source initialized:       {closeout['quote_source_initialized']}")
    print(f"    quote reads:                    {int(closeout['quote_reads']):,}")
    print(f"    broker initialized:             {closeout['broker_initialized']}")
    print(f"    provider submission attempts:   {int(closeout['provider_submission_attempts']):,}")
    print(f"    broker writes:                  {int(closeout['broker_writes']):,}")
    print(f"    order writes:                   {int(closeout['order_writes']):,}")
    print(f"    unknown write records:          {int(closeout['unknown_write_record_count']):,}")
    print(f"    production ML writes:           {int(closeout['production_ml_writes']):,}")
    print(f"    live writes:                    {int(closeout['live_writes']):,}")
    print(f"    zero-case no-op:                {closeout['zero_case_noop']}")

    print("  independent final checks:")
    for name, value in closeout["checks"].items():
        print(f"    {name}: {value}")

    disposition = closeout["final_disposition"]
    print("  final disposition:")
    print(f"    Phase 15 accepted:                         {disposition['phase15_accepted']}")
    print(
        "    cumulative foundation required:          "
        f"{disposition['cumulative_foundation_is_execution_prerequisite']}"
    )
    print(
        "    broker-neutral shadow/paper accepted:     "
        f"{disposition['broker_neutral_shadow_paper_architecture_accepted']}"
    )
    print(
        "    actual broker execution exercised:        "
        f"{disposition['actual_broker_execution_exercised_in_acceptance']}"
    )
    print(f"    live execution promoted:                   {disposition['live_execution_promoted']}")
    print(
        "    automatic cross-broker failover allowed:  "
        f"{disposition['automatic_cross_broker_failover_allowed']}"
    )
    print(
        "    outcome learning descriptive only:        "
        f"{disposition['outcome_learning_is_descriptive_only']}"
    )
    print(f"    next phase:                                {disposition['next_phase']}")
    print(f"  final acceptance report: {closeout['report_path']}")
    print("  Phase 15 Broker Execution and Outcome Learning: PASS")
    print("  Phase 16 Browser Control Plane and Production Operations: NEXT")


if __name__ == "__main__":
    main()
