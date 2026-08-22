from __future__ import annotations

import math
from datetime import UTC, datetime

from packages.brokers.base import BrokerAdapter
from packages.execution.phase15_policy import (
    PHASE15_ALLOWED_BROKERS,
    PHASE15_EXISTING_SAME_TICKER_ENTRY_ALLOWED,
    PHASE15_LIVE_EXECUTION_ENABLED,
    PHASE15_REQUIRE_BROKER_PREFLIGHT,
    PHASE15_REQUIRE_BROKER_RECONCILIATION_BEFORE_SUBMIT,
    PHASE15_REQUIRE_CURRENT_BROKER_RISK_REVALIDATION,
    PHASE15_REQUIRE_CURRENT_CORRELATION_WITH_EXISTING_POSITIONS,
)
from packages.portfolio.phase13_policy import (
    PHASE13_MAX_ABS_CORRELATION,
    PHASE13_MAX_GROSS_NOTIONAL_FRACTION,
    PHASE13_MAX_OPEN_POSITIONS,
    PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION,
    PHASE13_RISK_PER_TRADE_FRACTION,
)
from packages.schemas.execution import (
    BrokerName,
    BrokerOrderPlan,
    BrokerPreflightResult,
    BrokerReconciliationSnapshot,
    ExecutionEnvironment,
    ExecutionIntent,
)
from packages.schemas.execution_attempt import ExecutionRiskRevalidation


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


def revalidate_execution_risk(
    intent: ExecutionIntent,
    reconciliation: BrokerReconciliationSnapshot,
    *,
    max_abs_correlation: float | None = None,
    now_utc: datetime | None = None,
) -> ExecutionRiskRevalidation:
    if not PHASE15_REQUIRE_CURRENT_BROKER_RISK_REVALIDATION:
        raise ExecutionValidationError("Phase 15 current broker risk revalidation unexpectedly disabled")
    account = reconciliation.account
    equity = float(account.equity)
    if not math.isfinite(equity) or equity <= 0.0:
        raise ExecutionValidationError("current broker account equity must be positive")
    existing_same = [item for item in reconciliation.positions if item.ticker == intent.ticker]
    existing_value = sum(abs(float(item.market_value)) for item in existing_same)
    if existing_same and not PHASE15_EXISTING_SAME_TICKER_ENTRY_ALLOWED:
        same_ticker_pass = False
    else:
        same_ticker_pass = True

    current_positions = len(reconciliation.positions)
    if current_positions > 0 and PHASE15_REQUIRE_CURRENT_CORRELATION_WITH_EXISTING_POSITIONS:
        if max_abs_correlation is None:
            raise ExecutionValidationError(
                "current broker positions require fresh max-absolute-correlation evidence"
            )
    corr = None if max_abs_correlation is None else float(max_abs_correlation)
    if corr is not None and (not math.isfinite(corr) or not 0.0 <= corr <= 1.0):
        raise ExecutionValidationError("current max_abs_correlation must be finite within [0, 1]")

    loss = float(intent.executable_risk_per_share) * int(intent.executable_quantity)
    notional = float(intent.entry_limit) * int(intent.executable_quantity)
    projected_loss_fraction = loss / equity
    projected_single = (existing_value + notional) / equity
    projected_gross = (float(account.gross_market_value) + notional) / equity
    projected_position_count = current_positions + (0 if existing_same else 1)

    checks = {
        "same_ticker": same_ticker_pass,
        "risk_budget": projected_loss_fraction <= PHASE13_RISK_PER_TRADE_FRACTION + 1e-12,
        "single_name": projected_single <= PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION + 1e-12,
        "gross": projected_gross <= PHASE13_MAX_GROSS_NOTIONAL_FRACTION + 1e-12,
        "position_count": projected_position_count <= PHASE13_MAX_OPEN_POSITIONS,
        "correlation": corr is None or corr <= PHASE13_MAX_ABS_CORRELATION + 1e-12,
    }
    reasons = ["CURRENT_BROKER_RISK_ENVELOPE_RECOMPUTED"]
    reasons.extend(f"{name.upper()}_{'PASS' if passed else 'FAIL'}" for name, passed in checks.items())
    return ExecutionRiskRevalidation(
        checked_at_utc=(now_utc or datetime.now(UTC)).astimezone(UTC),
        account_equity=equity,
        account_gross_market_value=float(account.gross_market_value),
        open_positions_before=current_positions,
        existing_same_name_market_value=existing_value,
        proposed_loss_at_stop=loss,
        proposed_notional=notional,
        projected_loss_fraction=projected_loss_fraction,
        projected_single_name_fraction=projected_single,
        projected_gross_fraction=projected_gross,
        projected_position_count=projected_position_count,
        max_abs_correlation=corr,
        admissible=all(checks.values()),
        reason_codes=tuple(reasons),
    )


def validate_submission_gate(
    intent: ExecutionIntent,
    plan: BrokerOrderPlan,
    *,
    adapter: BrokerAdapter,
    reconciliation: BrokerReconciliationSnapshot,
    risk_revalidation: ExecutionRiskRevalidation,
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
    if not risk_revalidation.admissible:
        raise ExecutionValidationError("current broker portfolio risk revalidation rejected execution plan")
    if intent.direction.value == "bearish" and reconciliation.account.shorting_enabled is False:
        raise ExecutionValidationError("broker account explicitly reports shorting disabled")
    if PHASE15_REQUIRE_BROKER_PREFLIGHT and not preflight.accepted:
        raise ExecutionValidationError("broker preflight rejected execution plan")
    if preflight.broker != intent.broker or preflight.intent_id != intent.intent_id:
        raise ExecutionValidationError("broker preflight does not bind execution intent")
