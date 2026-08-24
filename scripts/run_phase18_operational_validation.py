from __future__ import annotations

import argparse
import hashlib

from packages.brokers.alpaca import AlpacaPaperBroker
from packages.brokers.webull import WebullSandboxBroker
from packages.control_plane.phase18_authorization import (
    Phase18AuthorizationError,
    Phase18MutationAuthorization,
    require_phase18_mutation_authorization,
)
from packages.control_plane.phase18_policy import PHASE18_CONFIRMATION_TEXT
from packages.core.settings import load_settings
from packages.execution.phase18_operational_validation import (
    Phase18OperationalValidationError,
    build_phase18_operational_validation_plan,
    run_phase18_operational_validation_lifecycle,
)
from packages.execution.phase18_webull_quote import Phase18WebullQuoteResolver
from packages.execution.quote_source import ExecutionQuoteError, Phase15LiveQuoteResolver
from packages.schemas.execution import BrokerName


QUOTE_SOURCE_MASSIVE = "massive-live-state"
QUOTE_SOURCE_WEBULL = "webull-snapshot"


def _ref(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _build_adapter(broker: BrokerName):
    if broker == BrokerName.WEBULL:
        return WebullSandboxBroker()
    if broker == BrokerName.ALPACA:
        return AlpacaPaperBroker()
    raise RuntimeError("Phase 18 operational validation supports only Webull or Alpaca")


def _print_reconciliation(prefix: str, reconciliation) -> None:
    if reconciliation is None:
        print(f"{prefix}_reconciliation_available: False")
        return
    print(f"{prefix}_reconciliation_available: True")
    print(f"{prefix}_broker: {reconciliation.broker.value}")
    print(f"{prefix}_account_ref: {_ref(reconciliation.account.account_id)}")
    print(f"{prefix}_reconciled: {reconciliation.reconciled}")
    print(f"{prefix}_open_order_count: {len(reconciliation.open_orders)}")
    print(f"{prefix}_position_count: {len(reconciliation.positions)}")
    print(f"{prefix}_safe_to_switch_broker: {reconciliation.safe_to_switch_broker}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 18 validation-only paper-provider runner. Without the explicit "
            "authorization flag and exact confirmation text, this script reads only "
            "local quote evidence and performs zero broker/provider calls."
        )
    )
    parser.add_argument(
        "--broker",
        choices=("webull", "alpaca"),
        required=True,
        help="Exactly one paper/sandbox broker to validate.",
    )
    parser.add_argument(
        "--ticker",
        required=True,
        help=(
            "Exact provider-native equity ticker used only for the one-share validation "
            "order. No default ticker is supplied."
        ),
    )
    parser.add_argument(
        "--quote-source",
        choices=(QUOTE_SOURCE_MASSIVE, QUOTE_SOURCE_WEBULL),
        default=QUOTE_SOURCE_MASSIVE,
        help=(
            "Explicit local quote-evidence source. massive-live-state reads the accepted "
            "Phase 5/15 snapshot; webull-snapshot reads the sanitized file created by "
            "capture_phase18_webull_quote.py. Neither choice performs a provider call here."
        ),
    )
    parser.add_argument(
        "--authorize-paper-provider-mutation",
        action="store_true",
        help=(
            "Permit the validation-only paper-provider lifecycle after all local gates "
            "pass. Omit this for a zero-provider-call plan preview."
        ),
    )
    parser.add_argument(
        "--confirmation",
        default="",
        help=f"Must exactly equal {PHASE18_CONFIRMATION_TEXT} for a real provider mutation.",
    )
    args = parser.parse_args()

    ticker = args.ticker.strip()
    if not ticker:
        raise SystemExit("Phase 18 validation ticker cannot be blank")
    broker = BrokerName(args.broker)
    quote_source = getattr(args, "quote_source", QUOTE_SOURCE_MASSIVE)

    print("ATLAS Phase 18 operational validation")
    print("Environment: PAPER/SANDBOX ONLY")
    print("Live execution: DISABLED")
    print("Automatic cross-broker failover: DISABLED")
    print("Validation quantity: 1 share (locked)")
    print("Validation entry: 5% below fresh realtime bid (locked)")
    print("Automatic flatten on fill: DISABLED")
    print(f"Selected broker: {broker.value}")
    print(f"Selected ticker: {ticker}")
    print(f"Quote source: {quote_source}")

    settings = load_settings()
    try:
        if quote_source == QUOTE_SOURCE_WEBULL:
            quote = Phase18WebullQuoteResolver(settings).quote(ticker)
        else:
            quote = Phase15LiveQuoteResolver(settings).quote(ticker)
        plan = build_phase18_operational_validation_plan(quote, broker=broker)
    except (ExecutionQuoteError, Phase18OperationalValidationError, ValueError) as exc:
        print("Plan status: BLOCKED")
        print(f"Reason: {exc}")
        print("Broker adapter initialized: NO")
        print("Provider calls performed: 0")
        print("Provider writes performed: 0")
        raise SystemExit(2) from None

    print("Plan status: READY")
    print(f"Quote provider timestamp UTC: {quote.provider_timestamp_utc.isoformat()}")
    print(f"Quote received UTC: {quote.received_at_utc.isoformat()}")
    print(f"Quote bid/ask: {quote.bid_price}/{quote.ask_price}")
    print(f"Client order id: {plan.client_order_id}")
    print(f"Limit/stop/target: {plan.limit_price}/{plan.stop_price}/{plan.target_price}")
    print(f"Planned notional: {plan.limit_price * plan.quantity:.2f}")

    authorization = Phase18MutationAuthorization(
        broker=broker.value,
        authorize_provider_mutation=args.authorize_paper_provider_mutation,
        confirmation_text=args.confirmation,
    )

    if not args.authorize_paper_provider_mutation:
        print("Authorization gate: NOT REQUESTED")
        print("Broker adapter initialized: NO")
        print("Provider calls performed: 0")
        print("Provider writes performed: 0")
        print("Disposition: PLAN_ONLY_ZERO_PROVIDER_CALLS")
        return

    try:
        require_phase18_mutation_authorization(authorization)
    except Phase18AuthorizationError as exc:
        print("Authorization gate: DENIED")
        print(f"Reason: {exc}")
        print("Broker adapter initialized: NO")
        print("Provider calls performed: 0")
        print("Provider writes performed: 0")
        raise SystemExit(2) from None

    print("Authorization gate: ACCEPTED")
    print("Initializing exactly one selected paper/sandbox broker adapter...")
    try:
        adapter = _build_adapter(broker)
    except Exception:
        print("Broker adapter initialization: FAILED")
        print("Provider mutation attempted: NO")
        raise SystemExit(2) from None

    print("Broker adapter initialization: COMPLETE")
    try:
        result = run_phase18_operational_validation_lifecycle(
            plan,
            adapter,
            authorization=authorization,
        )
    except Phase18OperationalValidationError as exc:
        print("Lifecycle status: BLOCKED")
        print(f"Failure stage: {exc.stage}")
        print(f"Provider state uncertain: {exc.provider_state_uncertain}")
        _print_reconciliation("failure", exc.reconciliation)
        if exc.provider_state_uncertain:
            print("Disposition: STOP_NO_RETRY_NO_FAILOVER_RECONCILIATION_REQUIRED")
        else:
            print("Disposition: STOP_FAIL_CLOSED")
        raise SystemExit(2) from None

    print("Lifecycle status: COMPLETE")
    print(f"Disposition: {result.disposition}")
    print(f"Provider writes performed: {result.provider_write_count}")
    print(f"Submitted status: {result.submitted.status.value}")
    print(f"Exact post-submit status: {result.exact_order_after_submit.status.value}")
    print(
        "Cancellation status: "
        + (result.cancellation.status.value if result.cancellation is not None else "NOT_ATTEMPTED")
    )
    print(f"Cleanup required: {result.cleanup_required}")
    _print_reconciliation("final", result.reconciliation_after)
    if result.cleanup_required:
        print("Automatic cleanup/flatten performed: NO")
        print("Separate explicit cleanup authorization required: YES")


if __name__ == "__main__":
    main()
