from __future__ import annotations

from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.execution import (
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    ExecutionExitReason,
    ExecutionIntent,
    ExecutionOutcome,
)


class ExecutionOutcomeError(ValueError):
    pass


def build_execution_outcome(
    intent: ExecutionIntent,
    *,
    entry_order: BrokerOrderSnapshot,
    exit_order: BrokerOrderSnapshot,
    exit_reason: ExecutionExitReason,
) -> ExecutionOutcome:
    """Attribute a completed execution without feeding it back into authority.

    Slippage, realized return, and realized R are observational facts. Phase 15 never
    uses this function to recalibrate an ML model, strategy-support threshold, or route.
    """

    filled_statuses = {BrokerOrderStatus.FILLED, BrokerOrderStatus.SHADOW_FILLED}
    if entry_order.status not in filled_statuses or exit_order.status not in filled_statuses:
        raise ExecutionOutcomeError("execution outcome requires completely filled entry and exit")
    if entry_order.broker != intent.broker or exit_order.broker != intent.broker:
        raise ExecutionOutcomeError("execution outcome broker differs from execution intent")
    if entry_order.ticker != intent.ticker or exit_order.ticker != intent.ticker:
        raise ExecutionOutcomeError("execution outcome ticker differs from execution intent")
    if entry_order.average_fill_price is None or exit_order.average_fill_price is None:
        raise ExecutionOutcomeError("execution outcome requires average fill prices")
    quantity = min(float(entry_order.filled_quantity), float(exit_order.filled_quantity))
    if quantity <= 0.0:
        raise ExecutionOutcomeError("execution outcome has no matched filled quantity")
    if entry_order.submitted_at_utc is None or exit_order.submitted_at_utc is None:
        raise ExecutionOutcomeError("execution outcome requires submitted timestamps")

    entry = float(entry_order.average_fill_price)
    exit_price = float(exit_order.average_fill_price)
    if intent.direction == DiscoveryDirection.BULLISH:
        gross_pnl = (exit_price - entry) * quantity
        gross_return = (exit_price / entry) - 1.0
    elif intent.direction == DiscoveryDirection.BEARISH:
        gross_pnl = (entry - exit_price) * quantity
        gross_return = 1.0 - (exit_price / entry)
    else:
        raise ExecutionOutcomeError("neutral intent cannot have an execution outcome")

    initial_risk = float(intent.executable_risk_per_share) * quantity
    if initial_risk <= 0.0:
        raise ExecutionOutcomeError("execution outcome has invalid initial risk")
    realized_r = gross_pnl / initial_risk
    return ExecutionOutcome(
        intent_id=intent.intent_id,
        broker=intent.broker,
        environment=intent.environment,
        ticker=intent.ticker,
        direction=intent.direction,
        quantity=quantity,
        entry_fill_price=entry,
        exit_fill_price=exit_price,
        opened_at_utc=entry_order.submitted_at_utc,
        closed_at_utc=exit_order.updated_at_utc,
        exit_reason=exit_reason,
        gross_pnl=gross_pnl,
        gross_return=gross_return,
        realized_r=realized_r,
        descriptive_only=True,
        can_promote_model=False,
        can_change_strategy_support=False,
        can_change_thresholds=False,
    )
