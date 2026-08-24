from __future__ import annotations

import argparse
from datetime import date

from packages.core.settings import load_settings
from packages.execution.phase22_operator import (
    PHASE22_DEFAULT_BROKER,
    Phase22OperatorError,
    Phase22PaperOperator,
    phase22_policy_fingerprint,
)
from packages.schemas.execution import BrokerName


def _print_preparation(preparation) -> None:
    print(f"Phase 22 policy: {phase22_policy_fingerprint()}")
    print(f"As-of date: {preparation.as_of_date}")
    print(f"Selected broker: {preparation.broker.value}")
    print("Environment: PAPER/SANDBOX ONLY")
    print("Webull primary: YES")
    print("Alpaca selection: MANUAL ONLY")
    print("Live execution: DISABLED")
    print("Automatic cross-broker failover: DISABLED")
    print("Browser execution authority: DISABLED")
    print("Scheduler execution authority: DISABLED")
    print(f"Accepted execution cases: {preparation.execution_case_count}")
    print(f"Explicit run authority required: {preparation.authority_required}")
    if preparation.challenge is not None:
        print(f"Phase 21 execution scope: {preparation.challenge.execution_scope_id}")
        print("Required exact confirmation:")
        print(preparation.challenge.required_confirmation)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "ATLAS Phase 22 operator binding for accepted Phase 15/21 PAPER execution. "
            "No arbitrary ticker, order geometry, LIVE mode, or automatic broker failover is exposed."
        )
    )
    parser.add_argument(
        "command",
        choices=("prepare", "execute"),
        help="prepare is local/read-only; execute requires exact interactive confirmation when cases exist.",
    )
    parser.add_argument(
        "--broker",
        choices=(BrokerName.WEBULL.value, BrokerName.ALPACA.value),
        default=PHASE22_DEFAULT_BROKER.value,
        help="PAPER broker. Webull is the default/primary; Alpaca is explicit manual selection only.",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Optional exact accepted Phase 14 date (YYYY-MM-DD). Defaults to the accepted closeout date.",
    )
    args = parser.parse_args()

    settings = load_settings()
    operator = Phase22PaperOperator(settings)
    try:
        preparation = operator.prepare(as_of_date=args.as_of, broker=BrokerName(args.broker))
    except (Phase22OperatorError, ValueError) as exc:
        print("Preparation status: BLOCKED")
        print(f"Reason: {exc}")
        print("Provider mutation attempted: NO")
        raise SystemExit(2) from None

    print("ATLAS Phase 22 Operational PAPER Runner")
    _print_preparation(preparation)

    if args.command == "prepare":
        print("Disposition: PREPARED_ZERO_PROVIDER_CALLS")
        return

    confirmation = ""
    if preparation.authority_required:
        print("Execution is default-deny until the exact run-scoped text above is typed.")
        confirmation = input("Type exact confirmation: ").strip()

    try:
        result = operator.execute(
            preparation,
            confirmation=confirmation,
            progress=lambda message: print(f"  {message}"),
        )
    except Phase22OperatorError as exc:
        print("Execution status: BLOCKED")
        print(f"Reason: {exc}")
        print("Do not retry uncertain provider mutations; reconcile exact deterministic client ids first.")
        raise SystemExit(2) from None

    public = result.public_dict()
    print("Execution status: COMPLETE")
    print(f"Manifest: {public['manifest_path']}")
    print(f"Execution cases: {public['execution_case_count']}")
    print(f"Records: {public['record_count']}")
    print(f"Blocked: {public['blocked_count']}")
    print(f"PAPER submitted: {public['paper_submitted_count']}")
    print(f"Existing reconciled: {public['existing_reconciled_count']}")
    print(f"Provider uncertain: {public['provider_uncertain_count']}")
    print(f"Provider submission attempts: {public['provider_submission_attempts']}")
    print(f"Known broker writes: {public['known_broker_writes']}")
    print(f"Unknown write records: {public['unknown_write_record_count']}")
    print(f"Pass: {public['pass']}")


if __name__ == "__main__":
    main()
