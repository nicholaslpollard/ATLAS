from __future__ import annotations

from datetime import UTC, datetime

from packages.brokers.base import BrokerAdapter
from packages.execution.phase15_policy import (
    PHASE15_ALLOWED_BROKERS,
    PHASE15_LIVE_EXECUTION_ENABLED,
    PHASE15_REQUIRE_BROKER_PREFLIGHT,
    PHASE15_REQUIRE_BROKER_RECONCILIATION_BEFORE_SUBMIT,
)
from packages.schemas.execution import (
    BrokerName,
    BrokerOrderPlan,
    BrokerPreflightResult,
    BrokerReconciliationSnapshot,
    ExecutionEnvironment,
    ExecutionIntent,
)


class ExecutionValidationError(ValueError):
    pass


def reconcile_broker(
    adapter: BrokerAdapter,
    *,
    now_utc: datetime | None = None,
) -> BrokerReconciliationSnapshot:
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    account = adapter.account()
    open_orders = tuple(adapter.open_orders())
    positions = tuple(adapter.positions())
    if account.broker != adapter.broker or account.environment != adapter.environment:
        raise ExecutionValidationError("broker account normalization differs from adapter identity")
    if any(item.broker != adapter.broker or item.account_id != account.account_id for item in open_orders):
        raise ExecutionValidationError("open-order normalization differs from broker/account identity")
    if any(item.broker != adapter.broker or item.account_id != account.account_id for item in positions):
        raise ExecutionValidationError("position normalization differs from broker/account identity")
    zero_orders = len(open_orders) == 0
    zero_positions = len(positions) == 0
    reasons = ["BROKER_ACCOUNT_ORDERS_POSITIONS_RECONCILED"]
    reasons.append("ZERO_OPEN_ORDERS" if zero_orders else "OPEN_ORDERS_PRESENT")
    reasons.append("ZERO_POSITIONS" if zero_positions else "POSITIONS_PRESENT")
    reasons.append("SAFE_TO_SWITCH_BROKER" if zero_orders and zero_positions else "BROKER_SWITCH_BLOCKED_BY_EXPOSURE")
    return BrokerReconciliationSnapshot(
        broker=adapter.broker,
        environment=adapter.environment,
        account=account,
        open_orders=open_orders,
        positions=positions,
        as_of_utc=now,
        reconciled=True,
        zero_open_orders=zero_orders,
        zero_positions=zero_positions,
        safe_to_switch_broker=zero_orders and zero_positions,
        reason_codes=tuple(reasons),
    )


def validate_submission_gate(
    intent: ExecutionIntent,
    plan: BrokerOrderPlan,
    *,
    adapter: BrokerAdapter,
    reconciliation: BrokerReconciliationSnapshot,
    preflight: BrokerPreflightResult,
) -> None:
    if plan.intent_id != intent.intent_id:
        raise ExecutionValidationError("order plan does not belong to execution intent")
    if intent.environment == ExecutionEnvironment.LIVE or adapter.environment == ExecutionEnvironment.LIVE:
        raise ExecutionValidationError("Phase 15 live execution is not promoted")
    if PHASE15_LIVE_EXECUTION_ENABLED:
        raise ExecutionValidationError("Phase 15 policy unexpectedly enables live execution")
    if adapter.broker != intent.broker or reconciliation.broker != intent.broker:
        raise ExecutionValidationError("execution broker differs from explicit intent broker")
    if adapter.environment != intent.environment or reconciliation.environment != intent.environment:
        raise ExecutionValidationError("execution environment differs from explicit intent environment")
    if intent.environment == ExecutionEnvironment.PAPER and intent.broker.value not in PHASE15_ALLOWED_BROKERS:
        raise ExecutionValidationError("paper execution broker is not allowed by Phase 15 policy")
    if intent.environment == ExecutionEnvironment.SHADOW and intent.broker != BrokerName.SHADOW:
        raise ExecutionValidationError("shadow execution broker identity changed")
    if PHASE15_REQUIRE_BROKER_RECONCILIATION_BEFORE_SUBMIT and not reconciliation.reconciled:
        raise ExecutionValidationError("broker reconciliation is required before submission")
    if reconciliation.account.trading_blocked:
        raise ExecutionValidationError("broker account reports trading blocked")
    if intent.direction.value == "bearish" and reconciliation.account.shorting_enabled is False:
        raise ExecutionValidationError("broker account explicitly reports shorting disabled")
    if PHASE15_REQUIRE_BROKER_PREFLIGHT and not preflight.accepted:
        raise ExecutionValidationError("broker preflight rejected execution plan")
    if preflight.broker != intent.broker or preflight.intent_id != intent.intent_id:
        raise ExecutionValidationError("broker preflight does not bind execution intent")
