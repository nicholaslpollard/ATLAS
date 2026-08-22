from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Callable

from packages.brokers.alpaca import AlpacaPaperBroker
from packages.brokers.base import BrokerAdapter, BrokerAdapterError
from packages.brokers.webull import WebullSandboxBroker
from packages.core.settings import AtlasSettings
from packages.execution.validator import ExecutionValidationError, reconcile_broker
from packages.schemas.control_plane import ControlPlaneActionKind, ControlPlaneActionState
from packages.schemas.control_plane_cleanup import (
    ControlPlaneCancelOrderTarget,
    ControlPlaneCleanupPlan,
    ControlPlaneCleanupPlanKind,
    ControlPlaneFlattenPositionTarget,
)
from packages.schemas.execution import BrokerName, BrokerOrderSide, ExecutionEnvironment

from .action_ledger import ControlPlaneActionLedger
from .cleanup_policy import (
    PHASE16_CANCEL_PROVIDER_WRITES_ENABLED,
    PHASE16_CLEANUP_PLAN_MAX_AGE_SECONDS,
    PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED,
    PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED,
    validate_cleanup_policy,
)
from .status import Phase16StatusService


CONTROL_PLANE_CLEANUP_PLANNER_CONTRACT_VERSION = (
    "control-plane-cleanup-planner-v1-authorized-action-fresh-reconciliation-review-only"
)


class ControlPlaneCleanupPlannerError(RuntimeError):
    pass


class ControlPlaneCleanupPlannerBlocked(ControlPlaneCleanupPlannerError):
    pass


BrokerFactory = Callable[[BrokerName], BrokerAdapter]


def _default_broker_factory(broker: BrokerName) -> BrokerAdapter:
    if broker == BrokerName.WEBULL:
        return WebullSandboxBroker()
    if broker == BrokerName.ALPACA:
        return AlpacaPaperBroker()
    raise ControlPlaneCleanupPlannerError(f"unsupported cleanup broker: {broker}")


def _account_ref(account_id: str) -> str:
    return hashlib.sha256(account_id.encode("utf-8")).hexdigest()[:16]


class Phase16CleanupPlanner:
    """Build immutable cleanup review plans using provider reads only."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        status_service: Phase16StatusService | None = None,
        ledger: ControlPlaneActionLedger | None = None,
        broker_factory: BrokerFactory | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self._clock = clock or (lambda: datetime.now(UTC))
        self.status_service = status_service or Phase16StatusService(settings)
        self.ledger = ledger or self.status_service.action_ledger
        self._broker_factory = broker_factory or _default_broker_factory

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ControlPlaneCleanupPlannerError("cleanup planner clock must be timezone-aware")
        return value.astimezone(UTC)

    def _authorized_record(self, action_id: str):
        validate_cleanup_policy()
        record = self.ledger.get(action_id)
        if record.request.action_kind not in {
            ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
            ControlPlaneActionKind.FLATTEN_POSITIONS,
        }:
            raise ControlPlaneCleanupPlannerError("action is not a cleanup request")
        if record.request.environment != ExecutionEnvironment.PAPER:
            raise ControlPlaneCleanupPlannerError("cleanup planning is paper-only")
        if record.request.target_broker not in {BrokerName.WEBULL, BrokerName.ALPACA}:
            raise ControlPlaneCleanupPlannerError("cleanup request must target Webull or Alpaca")
        if record.state != ControlPlaneActionState.AUTHORIZED:
            raise ControlPlaneCleanupPlannerBlocked(
                f"cleanup action must be explicitly confirmed before planning: {record.state}"
            )
        return record

    def _reconciliation(self, broker: BrokerName):
        if not self.status_service.phase15_acceptance().accepted:
            raise ControlPlaneCleanupPlannerBlocked("Phase 15 acceptance is required")
        if not self.status_service.credentials(broker).ready:
            raise ControlPlaneCleanupPlannerBlocked(
                f"credentials unavailable for {broker.value}"
            )
        adapter = self._broker_factory(broker)
        if adapter.broker != broker or adapter.environment != ExecutionEnvironment.PAPER:
            raise ControlPlaneCleanupPlannerError("cleanup broker adapter identity mismatch")
        try:
            return reconcile_broker(adapter, now_utc=self._now())
        except (BrokerAdapterError, ExecutionValidationError, OSError, RuntimeError, ValueError) as exc:
            raise ControlPlaneCleanupPlannerBlocked("broker reconciliation failed") from exc

    def build(self, action_id: str) -> ControlPlaneCleanupPlan:
        record = self._authorized_record(action_id)
        broker = record.request.target_broker
        assert broker is not None
        reconciliation = self._reconciliation(broker)
        generated = self._now()
        expires = generated + timedelta(seconds=PHASE16_CLEANUP_PLAN_MAX_AGE_SECONDS)
        account_ref = _account_ref(reconciliation.account.account_id)

        if record.request.action_kind == ControlPlaneActionKind.CANCEL_OPEN_ORDERS:
            targets = tuple(
                ControlPlaneCancelOrderTarget(
                    client_order_id=item.client_order_id,
                    ticker=item.ticker,
                    side=item.side,
                    status=item.status,
                    requested_quantity=item.requested_quantity,
                    filled_quantity=item.filled_quantity,
                    updated_at_utc=item.updated_at_utc,
                )
                for item in sorted(
                    reconciliation.open_orders,
                    key=lambda row: (row.ticker, row.client_order_id),
                )
            )
            return ControlPlaneCleanupPlan(
                action_id=record.request.action_id,
                action_fingerprint=record.request_fingerprint,
                action_kind=record.request.action_kind,
                plan_kind=ControlPlaneCleanupPlanKind.CANCEL_OPEN_ORDERS,
                broker=broker,
                account_ref=account_ref,
                generated_at_utc=generated,
                expires_at_utc=expires,
                reconciliation_as_of_utc=reconciliation.as_of_utc,
                zero_open_orders=reconciliation.zero_open_orders,
                zero_positions=reconciliation.zero_positions,
                cancel_targets=targets,
                flatten_targets=(),
                no_op=reconciliation.zero_open_orders,
                provider_write_authorized=PHASE16_CANCEL_PROVIDER_WRITES_ENABLED,
                flatten_close_order_method_accepted=False,
                reason_codes=(
                    "FRESH_PHASE15_BROKER_RECONCILIATION",
                    "EXACT_OPEN_ORDER_RESOURCE_SET_CAPTURED",
                    "PROVIDER_CANCEL_WRITES_DISABLED",
                ),
            )

        if not reconciliation.zero_open_orders:
            raise ControlPlaneCleanupPlannerBlocked(
                "open orders must be resolved by a separate confirmed cancel action before flatten planning"
            )
        targets = tuple(
            ControlPlaneFlattenPositionTarget(
                ticker=item.ticker,
                quantity=item.quantity,
                market_value=item.market_value,
                average_entry_price=item.average_entry_price,
                required_close_side=(
                    BrokerOrderSide.SELL
                    if item.quantity > 0
                    else BrokerOrderSide.BUY_TO_COVER
                ),
                as_of_utc=item.as_of_utc,
            )
            for item in sorted(reconciliation.positions, key=lambda row: row.ticker)
        )
        return ControlPlaneCleanupPlan(
            action_id=record.request.action_id,
            action_fingerprint=record.request_fingerprint,
            action_kind=record.request.action_kind,
            plan_kind=ControlPlaneCleanupPlanKind.FLATTEN_POSITIONS,
            broker=broker,
            account_ref=account_ref,
            generated_at_utc=generated,
            expires_at_utc=expires,
            reconciliation_as_of_utc=reconciliation.as_of_utc,
            zero_open_orders=True,
            zero_positions=reconciliation.zero_positions,
            cancel_targets=(),
            flatten_targets=targets,
            no_op=reconciliation.zero_positions,
            provider_write_authorized=PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED,
            flatten_close_order_method_accepted=PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED,
            reason_codes=(
                "FRESH_PHASE15_BROKER_RECONCILIATION",
                "ZERO_OPEN_ORDERS_CONFIRMED",
                "EXACT_POSITION_RESOURCE_SET_CAPTURED",
                "PROVIDER_FLATTEN_WRITES_DISABLED",
                "CLOSE_ORDER_METHOD_NOT_ACCEPTED",
            ),
        )
