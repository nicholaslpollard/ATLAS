from __future__ import annotations

import argparse
from datetime import date

from packages.core.settings import load_settings
from packages.operations.phase23_current_run import (
    Phase23CurrentAnalysisCycle,
    Phase23CurrentRunError,
)
from packages.operations.phase23_policy import (
    PHASE23_DEFAULT_BROKER,
    Phase23AuthorizationError,
    authorize_phase23_reads,
    phase23_policy_fingerprint,
)
from packages.operations.phase23_validation import (
    Phase23IndependentValidationError,
    Phase23RunIndependentValidator,
)
from packages.schemas.execution import BrokerName


def _print_preparation(preparation) -> None:
    print(f"Phase 23 policy: {phase23_policy_fingerprint()}")
    print(f"As-of finalized session: {preparation.as_of_date}")
    print(f"Selected PAPER context: {preparation.broker.value}")
    print(f"Baseline discovery session: {preparation.baseline_discovery_date}")
    print(f"Sessions to advance: {len(preparation.sessions_to_advance)}")
    if preparation.sessions_to_advance:
        print("  " + ", ".join(item.isoformat() for item in preparation.sessions_to_advance))
    print(f"Missing reference snapshots: {len(preparation.missing_reference_sessions)}")
    print(f"Missing Massive daily files: {len(preparation.missing_daily_sessions)}")
    print(f"Missing Massive minute files: {len(preparation.missing_minute_sessions)}")
    print(f"External read classes: {', '.join(preparation.external_read_classes) or 'NONE'}")
    print(f"Explicit read authority required: {preparation.authority_required}")
    print("Broker reads/writes: DISABLED")
    print("Broker/order mutations: DISABLED")
    print("Phase 22 PAPER execution: SEPARATE / NOT INVOKED")
    print("Live execution: DISABLED")
    print("Automatic cross-broker failover: DISABLED")
    print("Scheduler execution authority: DISABLED")
    print(f"Run scope: {preparation.run_scope_fingerprint}")
    if preparation.challenge is not None:
        print(f"Phase 23 read scope: {preparation.challenge.execution_scope_id}")
        print("Required exact confirmation:")
        print(preparation.challenge.required_confirmation)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "ATLAS Phase 23 finalized-session analytical operator. Preparation is provider-free; "
            "execution may perform only exact run-scoped Massive market/reference reads and never "
            "broker/order mutations."
        )
    )
    parser.add_argument("command", choices=("prepare", "execute"))
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument(
        "--broker",
        choices=(BrokerName.WEBULL.value, BrokerName.ALPACA.value),
        default=PHASE23_DEFAULT_BROKER.value,
        help="PAPER broker context carried forward to the later separate Phase22 boundary. Webull is default.",
    )
    args = parser.parse_args()

    settings = load_settings()
    cycle = Phase23CurrentAnalysisCycle(settings)
    try:
        preparation = cycle.prepare(as_of_date=args.as_of, broker=BrokerName(args.broker))
    except (Phase23CurrentRunError, ValueError) as exc:
        print("Preparation status: BLOCKED")
        print(f"Reason: {exc}")
        print("External calls attempted: NO")
        raise SystemExit(2) from None

    print("ATLAS Phase 23 Operational Current Analysis Cycle")
    _print_preparation(preparation)
    if args.command == "prepare":
        print("Disposition: PREPARED_ZERO_EXTERNAL_CALLS")
        return

    authority = None
    if preparation.challenge is not None:
        print("External reads are default-deny until the exact run-scoped text above is typed.")
        confirmation = input("Type exact confirmation: ").strip()
        try:
            authority = authorize_phase23_reads(
                preparation.challenge,
                confirmation=confirmation,
                explicitly_authorized=True,
            )
        except Phase23AuthorizationError as exc:
            print("Execution status: BLOCKED")
            print(f"Reason: {exc}")
            raise SystemExit(2) from None

    try:
        result = cycle.execute(
            preparation,
            read_authority=authority,
            progress=lambda message: print(f"  {message}"),
        )
        validation = Phase23RunIndependentValidator(settings).run(
            as_of_date=preparation.as_of_date,
            broker=preparation.broker,
        )
    except (
        Phase23CurrentRunError,
        Phase23AuthorizationError,
        Phase23IndependentValidationError,
        ValueError,
    ) as exc:
        print("Execution status: BLOCKED")
        print(f"Reason: {exc}")
        print("No broker/order retry or failover is authorized by Phase 23.")
        raise SystemExit(2) from None

    print("Execution status: COMPLETE")
    print(f"Manifest: {result['manifest_path']}")
    print(f"Independent validation: {validation['report_path']}")
    print(f"Sessions advanced: {len(result['sessions_advanced'])}")
    print(f"Current WARM/HOT directional cases considered: {result['current_considered_warm_hot_directional']}")
    print(f"Promoted candidates: {result['promoted_count']}")
    print(f"Phase 12 research cases: {result['phase12_research_case_count']}")
    print(f"Phase 13 case files: {result['phase13_case_file_count']}")
    print(f"Phase 14 AI reviews: {result['phase14_ai_review_count']}")
    print(f"Phase 22-ready execution cases: {result['phase22_ready_execution_case_count']}")
    print(f"Broker reads: {result['broker_reads']}")
    print(f"Broker writes: {result['broker_writes']}")
    print(f"Order writes: {result['order_writes']}")
    print(f"PAPER submits: {result['paper_submits']}")
    print(f"LIVE writes: {result['live_writes']}")
    print(f"Independent validation pass: {validation['pass']}")
    print(f"Pass: {result['pass'] and validation['pass']}")


if __name__ == "__main__":
    main()
