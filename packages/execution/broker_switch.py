from __future__ import annotations

from datetime import UTC, datetime

from packages.execution.phase15_policy import (
    PHASE15_AUTOMATIC_BROKER_FAILOVER,
    PHASE15_BROKER_SWITCH_REQUIRES_RECONCILIATION,
    PHASE15_BROKER_SWITCH_REQUIRES_ZERO_OPEN_ORDERS,
    PHASE15_BROKER_SWITCH_REQUIRES_ZERO_POSITIONS,
)
from packages.schemas.broker_switch import BrokerSwitchAuthorization
from packages.schemas.execution import BrokerReconciliationSnapshot, ExecutionEnvironment


class BrokerSwitchError(ValueError):
    pass


def authorize_broker_switch(
    current: BrokerReconciliationSnapshot,
    target: BrokerReconciliationSnapshot,
    *,
    explicit_request: bool,
    now_utc: datetime | None = None,
) -> BrokerSwitchAuthorization:
    if PHASE15_AUTOMATIC_BROKER_FAILOVER:
        raise BrokerSwitchError("Phase 15 automatic broker failover unexpectedly enabled")
    if current.broker == target.broker:
        raise BrokerSwitchError("broker switch requires a distinct target broker")
    if current.environment != target.environment:
        raise BrokerSwitchError("broker switch cannot cross execution environments")
    if current.environment == ExecutionEnvironment.LIVE:
        raise BrokerSwitchError("Phase 15 live broker switching is not promoted")

    checks = {
        "explicit_request": bool(explicit_request),
        "current_reconciled": current.reconciled if PHASE15_BROKER_SWITCH_REQUIRES_RECONCILIATION else True,
        "target_reconciled": target.reconciled if PHASE15_BROKER_SWITCH_REQUIRES_RECONCILIATION else True,
        "current_zero_orders": current.zero_open_orders if PHASE15_BROKER_SWITCH_REQUIRES_ZERO_OPEN_ORDERS else True,
        "target_zero_orders": target.zero_open_orders if PHASE15_BROKER_SWITCH_REQUIRES_ZERO_OPEN_ORDERS else True,
        "current_zero_positions": current.zero_positions if PHASE15_BROKER_SWITCH_REQUIRES_ZERO_POSITIONS else True,
        "target_zero_positions": target.zero_positions if PHASE15_BROKER_SWITCH_REQUIRES_ZERO_POSITIONS else True,
    }
    authorized = all(checks.values())
    reasons = ["AUTOMATIC_BROKER_FAILOVER_DISABLED"]
    reasons.extend(f"{name.upper()}_{'PASS' if value else 'FAIL'}" for name, value in checks.items())
    return BrokerSwitchAuthorization(
        generated_at_utc=(now_utc or datetime.now(UTC)).astimezone(UTC),
        environment=current.environment,
        current_broker=current.broker,
        target_broker=target.broker,
        current_reconciliation=current,
        target_reconciliation=target,
        explicit_user_or_control_plane_request=explicit_request,
        authorized=authorized,
        reason_codes=tuple(reasons),
    )
