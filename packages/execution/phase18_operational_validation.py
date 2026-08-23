from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from packages.brokers.base import (
    BrokerAdapter,
    BrokerAdapterError,
    BrokerMutationUncertain,
    BrokerOrderNotFound,
    BrokerSubmissionUncertain,
)
from packages.control_plane.phase18_authorization import (
    Phase18MutationAuthorization,
    require_phase18_mutation_authorization,
)
from packages.core.enums import LiveFeedMode, SessionSegment
from packages.execution.validator import reconcile_broker
from packages.portfolio.phase13_policy import (
    PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION,
    PHASE13_RISK_PER_TRADE_FRACTION,
)
from packages.schemas.execution import (
    BrokerName,
    BrokerOrderPlan,
    BrokerOrderSide,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPreflightResult,
    BrokerReconciliationSnapshot,
    ExecutionEnvironment,
)
from packages.schemas.live_market import LiveQuote


PHASE18_OPERATIONAL_VALIDATION_CONTRACT_VERSION = (
    "phase18-operational-validation-v1-one-share-buy-nonmarketable-bracket"
)
PHASE18_VALIDATION_QUANTITY = 1
PHASE18_ENTRY_OFFSET_FRACTION = 0.05
PHASE18_PROTECTIVE_FRACTION = 0.02
PHASE18_MAX_VALIDATION_NOTIONAL = 1_000.0


class Phase18OperationalValidationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        provider_state_uncertain: bool = False,
        reconciliation: BrokerReconciliationSnapshot | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.provider_state_uncertain = provider_state_uncertain
        self.reconciliation = reconciliation


@dataclass(frozen=True)
class Phase18OperationalValidationResult:
    broker: str
    ticker: str
    client_order_id: str
    preflight: BrokerPreflightResult
    submitted: BrokerOrderSnapshot
    exact_order_after_submit: BrokerOrderSnapshot
    cancellation: BrokerOrderSnapshot | None
    reconciliation_after: BrokerReconciliationSnapshot
    provider_write_count: int
    cleanup_required: bool
    disposition: str


def _price(value: float) -> float:
    rounded = round(float(value) + 1e-12, 2)
    if rounded <= 0.0:
        raise Phase18OperationalValidationError(
            "validation price rounded to a nonpositive value",
            stage="plan",
        )
    return rounded


def build_phase18_operational_validation_plan(
    quote: LiveQuote,
    *,
    broker: BrokerName,
) -> BrokerOrderPlan:
    """Build a validation-only one-share BUY bracket from a fresh Phase 15 quote.

    This plan is deliberately distinct from a strategy-generated ExecutionIntent: it has
    no Phase 13/14 lineage and must never be persisted or interpreted as a trade signal.
    The entry is placed 5% below the current bid so the normal expected outcome is an
    accepted open paper order that can be reconciled and cancelled.
    """

    if broker not in {BrokerName.WEBULL, BrokerName.ALPACA}:
        raise Phase18OperationalValidationError(
            "operational validation broker must be Webull or Alpaca",
            stage="plan",
        )
    if quote.feed_mode != LiveFeedMode.REALTIME or quote.expected_delay_seconds != 0:
        raise Phase18OperationalValidationError(
            "operational validation requires an undelayed realtime quote",
            stage="plan",
        )
    if quote.session_segment != SessionSegment.REGULAR:
        raise Phase18OperationalValidationError(
            "operational validation requires a regular-session quote",
            stage="plan",
        )
    if quote.bid_price <= 0.0 or quote.ask_price <= 0.0:
        raise Phase18OperationalValidationError(
            "operational validation requires positive bid and ask",
            stage="plan",
        )
    if quote.ask_price < quote.bid_price:
        raise Phase18OperationalValidationError(
            "operational validation quote ask cannot be below bid",
            stage="plan",
        )

    entry = _price(quote.bid_price * (1.0 - PHASE18_ENTRY_OFFSET_FRACTION))
    stop = _price(entry * (1.0 - PHASE18_PROTECTIVE_FRACTION))
    target = _price(entry * (1.0 + PHASE18_PROTECTIVE_FRACTION))
    if not stop < entry < target:
        raise Phase18OperationalValidationError(
            "operational validation bracket geometry is invalid after tick rounding",
            stage="plan",
        )
    if entry * PHASE18_VALIDATION_QUANTITY > PHASE18_MAX_VALIDATION_NOTIONAL:
        raise Phase18OperationalValidationError(
            "operational validation notional exceeds the locked safety cap",
            stage="plan",
        )

    seed = (
        f"{PHASE18_OPERATIONAL_VALIDATION_CONTRACT_VERSION}|{broker.value}|"
        f"{quote.symbol}|{quote.provider_timestamp_utc.isoformat()}|{entry:.2f}|"
        f"{stop:.2f}|{target:.2f}"
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    intent_id = f"phase18-validation-{digest[:24]}"
    client_order_id = f"p18v-{digest[:27]}"[:32]

    return BrokerOrderPlan(
        intent_id=intent_id,
        client_order_id=client_order_id,
        ticker=quote.symbol,
        instrument_type="EQUITY",
        side=BrokerOrderSide.BUY,
        quantity=PHASE18_VALIDATION_QUANTITY,
        order_type="LIMIT",
        limit_price=entry,
        stop_price=stop,
        target_price=target,
        time_in_force="DAY",
        extended_hours=False,
        bracket_required=True,
    )


def _safe_reconcile(adapter: BrokerAdapter, now: datetime) -> BrokerReconciliationSnapshot | None:
    try:
        return reconcile_broker(adapter, now_utc=now)
    except Exception:
        return None


def _validate_operational_risk(
    plan: BrokerOrderPlan,
    reconciliation: BrokerReconciliationSnapshot,
) -> None:
    account = reconciliation.account
    equity = float(account.equity)
    notional = float(plan.limit_price) * int(plan.quantity)
    loss_at_stop = (float(plan.limit_price) - float(plan.stop_price)) * int(plan.quantity)

    if account.trading_blocked:
        raise Phase18OperationalValidationError(
            "operational validation broker account reports trading blocked",
            stage="risk_revalidation",
            reconciliation=reconciliation,
        )
    if equity <= 0.0:
        raise Phase18OperationalValidationError(
            "operational validation requires positive broker equity",
            stage="risk_revalidation",
            reconciliation=reconciliation,
        )
    if notional > float(account.buying_power) + 1e-12:
        raise Phase18OperationalValidationError(
            "operational validation exceeds current broker buying power",
            stage="risk_revalidation",
            reconciliation=reconciliation,
        )
    if notional / equity > PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION + 1e-12:
        raise Phase18OperationalValidationError(
            "operational validation exceeds accepted single-name notional risk limit",
            stage="risk_revalidation",
            reconciliation=reconciliation,
        )
    if loss_at_stop / equity > PHASE13_RISK_PER_TRADE_FRACTION + 1e-12:
        raise Phase18OperationalValidationError(
            "operational validation exceeds accepted loss-at-stop risk limit",
            stage="risk_revalidation",
            reconciliation=reconciliation,
        )


def run_phase18_operational_validation_lifecycle(
    plan: BrokerOrderPlan,
    adapter: BrokerAdapter,
    *,
    authorization: Phase18MutationAuthorization,
    now_utc: datetime | None = None,
) -> Phase18OperationalValidationResult:
    """Run one validation-only paper submit/reconcile/cancel lifecycle.

    This function never auto-flattens filled exposure and never performs cross-broker
    failover. Any uncertain mutation stops the lifecycle and requires exact reconciliation
    before a later separately authorized action.
    """

    auth = require_phase18_mutation_authorization(authorization)
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)

    if adapter.environment != ExecutionEnvironment.PAPER:
        raise Phase18OperationalValidationError(
            "operational validation adapter must be paper/sandbox",
            stage="authority",
        )
    if adapter.broker.value != auth.normalized_broker:
        raise Phase18OperationalValidationError(
            "operational validation authorization does not match adapter broker",
            stage="authority",
        )
    if adapter.broker not in {BrokerName.WEBULL, BrokerName.ALPACA}:
        raise Phase18OperationalValidationError(
            "operational validation adapter must be Webull or Alpaca",
            stage="authority",
        )
    if plan.quantity != PHASE18_VALIDATION_QUANTITY or plan.side != BrokerOrderSide.BUY:
        raise Phase18OperationalValidationError(
            "operational validation plan must remain the locked one-share BUY shape",
            stage="authority",
        )
    if plan.limit_price * plan.quantity > PHASE18_MAX_VALIDATION_NOTIONAL:
        raise Phase18OperationalValidationError(
            "operational validation plan exceeds locked notional cap",
            stage="authority",
        )

    before = reconcile_broker(adapter, now_utc=now)
    if not before.reconciled or not before.zero_open_orders or not before.zero_positions:
        raise Phase18OperationalValidationError(
            "operational validation requires a reconciled flat broker with zero open orders",
            stage="pre_reconciliation",
            reconciliation=before,
        )
    _validate_operational_risk(plan, before)

    try:
        existing = adapter.order(plan.client_order_id)
    except BrokerOrderNotFound:
        existing = None
    except BrokerAdapterError as exc:
        raise Phase18OperationalValidationError(
            "cannot prove validation client order id is absent",
            stage="idempotency_query",
            reconciliation=before,
        ) from exc
    if existing is not None:
        raise Phase18OperationalValidationError(
            "validation client order id already exists; a new provider write is blocked",
            stage="idempotency_query",
            reconciliation=before,
        )

    try:
        preflight = adapter.preview(plan)
    except BrokerAdapterError as exc:
        raise Phase18OperationalValidationError(
            "operational validation provider preflight failed closed",
            stage="preflight",
            reconciliation=before,
        ) from exc
    if not preflight.accepted:
        raise Phase18OperationalValidationError(
            "operational validation provider preflight rejected the plan",
            stage="preflight",
            reconciliation=before,
        )

    try:
        submitted = adapter.submit(plan)
    except BrokerSubmissionUncertain as exc:
        reconciled = _safe_reconcile(adapter, now)
        raise Phase18OperationalValidationError(
            "operational validation submit is uncertain; no retry, cancel, flatten, or failover is allowed",
            stage="submit",
            provider_state_uncertain=True,
            reconciliation=reconciled,
        ) from exc
    except BrokerAdapterError as exc:
        raise Phase18OperationalValidationError(
            "operational validation submit was definitively rejected/failed",
            stage="submit",
            reconciliation=before,
        ) from exc

    if submitted.client_order_id != plan.client_order_id or submitted.broker != adapter.broker:
        reconciled = _safe_reconcile(adapter, now)
        raise Phase18OperationalValidationError(
            "provider acknowledgement changed validation order identity; further mutation is blocked",
            stage="submit_acknowledgement",
            provider_state_uncertain=True,
            reconciliation=reconciled,
        )

    try:
        exact = adapter.order(plan.client_order_id)
    except BrokerAdapterError as exc:
        reconciled = _safe_reconcile(adapter, now)
        raise Phase18OperationalValidationError(
            "validation submission cannot be reconciled by exact client order id",
            stage="post_submit_reconciliation",
            provider_state_uncertain=True,
            reconciliation=reconciled,
        ) from exc

    allowed_post_submit = {
        BrokerOrderStatus.SUBMITTED,
        BrokerOrderStatus.PARTIAL_FILLED,
        BrokerOrderStatus.FILLED,
    }
    if exact.status not in allowed_post_submit:
        reconciled = _safe_reconcile(adapter, now)
        raise Phase18OperationalValidationError(
            "validation submission reached an unexpected terminal/non-open status",
            stage="post_submit_reconciliation",
            reconciliation=reconciled,
        )

    cancellation: BrokerOrderSnapshot | None = None
    writes = 1
    if exact.status in {BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.PARTIAL_FILLED}:
        try:
            cancellation = adapter.cancel(plan.client_order_id)
            writes += 1
        except BrokerMutationUncertain as exc:
            reconciled = _safe_reconcile(adapter, now)
            raise Phase18OperationalValidationError(
                "validation cancellation is uncertain; no retry, flatten, or failover is allowed",
                stage="cancel",
                provider_state_uncertain=True,
                reconciliation=reconciled,
            ) from exc
        except BrokerAdapterError as exc:
            reconciled = _safe_reconcile(adapter, now)
            raise Phase18OperationalValidationError(
                "validation cancellation failed closed",
                stage="cancel",
                reconciliation=reconciled,
            ) from exc

    after = reconcile_broker(adapter, now_utc=now)

    if exact.status in {BrokerOrderStatus.FILLED, BrokerOrderStatus.PARTIAL_FILLED}:
        return Phase18OperationalValidationResult(
            broker=adapter.broker.value,
            ticker=plan.ticker,
            client_order_id=plan.client_order_id,
            preflight=preflight,
            submitted=submitted,
            exact_order_after_submit=exact,
            cancellation=cancellation,
            reconciliation_after=after,
            provider_write_count=writes,
            cleanup_required=not after.safe_to_switch_broker,
            disposition="VALIDATION_FILL_REQUIRES_SEPARATE_EXPLICIT_CLEANUP",
        )

    if cancellation is not None and cancellation.status != BrokerOrderStatus.CANCELLED:
        raise Phase18OperationalValidationError(
            "validation cancellation did not reconcile to CANCELLED",
            stage="post_cancel_reconciliation",
            provider_state_uncertain=True,
            reconciliation=after,
        )

    if not after.zero_open_orders or not after.zero_positions:
        return Phase18OperationalValidationResult(
            broker=adapter.broker.value,
            ticker=plan.ticker,
            client_order_id=plan.client_order_id,
            preflight=preflight,
            submitted=submitted,
            exact_order_after_submit=exact,
            cancellation=cancellation,
            reconciliation_after=after,
            provider_write_count=writes,
            cleanup_required=True,
            disposition="VALIDATION_BROKER_NOT_FLAT_REQUIRES_SEPARATE_EXPLICIT_CLEANUP",
        )

    return Phase18OperationalValidationResult(
        broker=adapter.broker.value,
        ticker=plan.ticker,
        client_order_id=plan.client_order_id,
        preflight=preflight,
        submitted=submitted,
        exact_order_after_submit=exact,
        cancellation=cancellation,
        reconciliation_after=after,
        provider_write_count=writes,
        cleanup_required=False,
        disposition="VALIDATION_SUBMIT_RECONCILE_CANCEL_RECONCILE_COMPLETE",
    )
