from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Callable

from packages.brokers.alpaca import AlpacaPaperBroker
from packages.brokers.base import BrokerAdapter, BrokerAdapterError
from packages.brokers.webull import WebullSandboxBroker
from packages.core.settings import AtlasSettings
from packages.execution.validator import ExecutionValidationError, reconcile_broker
from packages.schemas.control_plane import ControlPlaneActionKind, ControlPlaneActionState
from packages.schemas.control_plane_cleanup import (
    ControlPlaneCleanupPlan,
    ControlPlaneCleanupPlanKind,
)
from packages.schemas.execution import BrokerName, BrokerOrderSide, ExecutionEnvironment

from .action_ledger import ControlPlaneActionConflict, ControlPlaneActionLedger
from .cleanup_plan_ledger import (
    ControlPlaneCleanupPlanLedger,
    ControlPlaneCleanupPlanLedgerError,
)
from .cleanup_policy import (
    PHASE16_CANCEL_PROVIDER_WRITES_ENABLED,
    PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED,
    PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED,
    validate_cleanup_policy,
)
from .status import Phase16StatusService


CONTROL_PLANE_CLEANUP_PROCESSOR_CONTRACT_VERSION = (
    "control-plane-cleanup-processor-v1-confirmed-exact-recheck-no-provider-writes"
)


class ControlPlaneCleanupProcessorError(RuntimeError):
    pass


class ControlPlaneCleanupProcessorBlocked(ControlPlaneCleanupProcessorError):
    pass


BrokerFactory = Callable[[BrokerName], BrokerAdapter]


def _default_broker_factory(broker: BrokerName) -> BrokerAdapter:
    if broker == BrokerName.WEBULL:
        return WebullSandboxBroker()
    if broker == BrokerName.ALPACA:
        return AlpacaPaperBroker()
    raise ControlPlaneCleanupProcessorError(f"unsupported cleanup broker: {broker}")


def _account_ref(account_id: str) -> str:
    return hashlib.sha256(account_id.encode("utf-8")).hexdigest()[:16]


def _cancel_scope(plan: ControlPlaneCleanupPlan) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (
                target.client_order_id,
                target.ticker,
                target.side.value,
                target.status.value,
                float(target.requested_quantity),
                float(target.filled_quantity),
            )
            for target in plan.cancel_targets
        )
    )


def _cancel_scope_from_reconciliation(reconciliation) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (
                row.client_order_id,
                row.ticker,
                row.side.value,
                row.status.value,
                float(row.requested_quantity),
                float(row.filled_quantity),
            )
            for row in reconciliation.open_orders
        )
    )


def _flatten_scope(plan: ControlPlaneCleanupPlan) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (
                target.ticker,
                float(target.quantity),
                target.required_close_side.value,
            )
            for target in plan.flatten_targets
        )
    )


def _flatten_scope_from_reconciliation(reconciliation) -> tuple[tuple[object, ...], ...]:
    return tuple(
        sorted(
            (
                row.ticker,
                float(row.quantity),
                (
                    BrokerOrderSide.SELL.value
                    if row.quantity > 0
                    else BrokerOrderSide.BUY_TO_COVER.value
                ),
            )
            for row in reconciliation.positions
            if abs(float(row.quantity)) > 1e-12
        )
    )


class Phase16CleanupProcessor:
    """Revalidate an exactly confirmed cleanup plan without provider mutation.

    Phase 16 v1 intentionally cannot cancel orders or flatten positions. The processor
    proves the authority/reconciliation path that any later provider-write implementation
    must pass. True no-op plans may complete locally; plans requiring provider mutation
    are terminally blocked while the write policy remains disabled.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        status_service: Phase16StatusService | None = None,
        action_ledger: ControlPlaneActionLedger | None = None,
        cleanup_plan_ledger: ControlPlaneCleanupPlanLedger | None = None,
        broker_factory: BrokerFactory | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self._clock = clock or (lambda: datetime.now(UTC))
        self.status_service = status_service or Phase16StatusService(settings)
        self.action_ledger = action_ledger or self.status_service.action_ledger
        self.cleanup_plan_ledger = cleanup_plan_ledger or ControlPlaneCleanupPlanLedger(
            self.action_ledger, clock=self._clock
        )
        self._broker_factory = broker_factory or _default_broker_factory

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ControlPlaneCleanupProcessorError("cleanup processor clock must be timezone-aware")
        return value.astimezone(UTC)

    def _block(self, action_id: str, code: str, *, details: dict[str, object]):
        return self.action_ledger.transition(
            action_id,
            ControlPlaneActionState.BLOCKED,
            error_code=code,
            event_details={
                **details,
                "provider_write_attempted": False,
                "provider_write_uncertain": False,
            },
        )

    def _reconcile(self, broker: BrokerName):
        if not self.status_service.phase15_acceptance().accepted:
            raise ControlPlaneCleanupProcessorBlocked("Phase 15 acceptance is required")
        if not self.status_service.credentials(broker).ready:
            raise ControlPlaneCleanupProcessorBlocked(
                f"credentials unavailable for {broker.value}"
            )
        adapter = self._broker_factory(broker)
        if adapter.broker != broker or adapter.environment != ExecutionEnvironment.PAPER:
            raise ControlPlaneCleanupProcessorError("cleanup broker adapter identity mismatch")
        try:
            return reconcile_broker(adapter, now_utc=self._now())
        except (BrokerAdapterError, ExecutionValidationError, OSError, RuntimeError, ValueError) as exc:
            raise ControlPlaneCleanupProcessorBlocked("broker reconciliation failed") from exc

    def process(self, action_id: str):
        validate_cleanup_policy()
        record = self.action_ledger.get(action_id)
        if record.request.action_kind not in {
            ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
            ControlPlaneActionKind.FLATTEN_POSITIONS,
        }:
            raise ControlPlaneCleanupProcessorError("action is not a cleanup request")
        if record.state in {
            ControlPlaneActionState.BLOCKED,
            ControlPlaneActionState.COMPLETED,
            ControlPlaneActionState.FAILED,
        }:
            return record
        if record.state != ControlPlaneActionState.AUTHORIZED:
            raise ControlPlaneActionConflict(
                f"cleanup action cannot process from state {record.state}"
            )
        if record.request.environment != ExecutionEnvironment.PAPER:
            raise ControlPlaneCleanupProcessorError("cleanup processing is paper-only")
        broker = record.request.target_broker
        if broker not in {BrokerName.WEBULL, BrokerName.ALPACA}:
            raise ControlPlaneCleanupProcessorError("cleanup request must target Webull or Alpaca")

        try:
            plan_state = self.cleanup_plan_ledger.state(action_id)
        except ControlPlaneCleanupPlanLedgerError as exc:
            raise ControlPlaneCleanupProcessorBlocked("cleanup plan ledger is invalid") from exc
        plan = plan_state.latest_plan
        if plan is None or plan_state.confirmation is None:
            raise ControlPlaneCleanupProcessorBlocked(
                "latest cleanup plan requires exact one-time confirmation"
            )
        if plan_state.confirmed_plan_fingerprint != plan.plan_fingerprint():
            raise ControlPlaneCleanupProcessorBlocked(
                "confirmed cleanup plan is not the latest exact plan"
            )
        now = self._now()
        if now > plan.expires_at_utc:
            return self._block(
                action_id,
                "CLEANUP_PLAN_EXPIRED",
                details={"cleanup_plan_fingerprint": plan.plan_fingerprint()},
            )
        if (
            plan.action_id != action_id
            or plan.action_fingerprint != record.request_fingerprint
            or plan.action_kind != record.request.action_kind
            or plan.broker != broker
            or plan.environment != ExecutionEnvironment.PAPER
        ):
            return self._block(
                action_id,
                "CLEANUP_PLAN_ACTION_BINDING_INVALID",
                details={"cleanup_plan_fingerprint": plan.plan_fingerprint()},
            )

        try:
            reconciliation = self._reconcile(broker)
        except ControlPlaneCleanupProcessorBlocked:
            return self._block(
                action_id,
                "BROKER_RECONCILIATION_FAILED",
                details={"cleanup_plan_fingerprint": plan.plan_fingerprint()},
            )
        if _account_ref(reconciliation.account.account_id) != plan.account_ref:
            return self._block(
                action_id,
                "CLEANUP_ACCOUNT_CHANGED",
                details={"cleanup_plan_fingerprint": plan.plan_fingerprint()},
            )

        if plan.plan_kind == ControlPlaneCleanupPlanKind.CANCEL_OPEN_ORDERS:
            if _cancel_scope(plan) != _cancel_scope_from_reconciliation(reconciliation):
                return self._block(
                    action_id,
                    "CLEANUP_RESOURCE_SET_DRIFT",
                    details={"cleanup_plan_fingerprint": plan.plan_fingerprint()},
                )
            if reconciliation.zero_open_orders:
                return self.action_ledger.transition(
                    action_id,
                    ControlPlaneActionState.COMPLETED,
                    result_reference=f"cleanup-noop:{plan.plan_fingerprint()}",
                    event_details={
                        "cleanup_plan_fingerprint": plan.plan_fingerprint(),
                        "cleanup_no_op": True,
                        "provider_write_attempted": False,
                    },
                )
            if PHASE16_CANCEL_PROVIDER_WRITES_ENABLED:
                raise ControlPlaneCleanupProcessorError(
                    "cancel writes cannot be enabled under cleanup processor v1"
                )
            return self._block(
                action_id,
                "CANCEL_PROVIDER_WRITES_DISABLED",
                details={"cleanup_plan_fingerprint": plan.plan_fingerprint()},
            )

        if plan.plan_kind != ControlPlaneCleanupPlanKind.FLATTEN_POSITIONS:
            raise ControlPlaneCleanupProcessorError("unsupported cleanup plan kind")
        if not reconciliation.zero_open_orders:
            return self._block(
                action_id,
                "OPEN_ORDERS_PRESENT_BEFORE_FLATTEN",
                details={"cleanup_plan_fingerprint": plan.plan_fingerprint()},
            )
        if _flatten_scope(plan) != _flatten_scope_from_reconciliation(reconciliation):
            return self._block(
                action_id,
                "CLEANUP_RESOURCE_SET_DRIFT",
                details={"cleanup_plan_fingerprint": plan.plan_fingerprint()},
            )
        if reconciliation.zero_positions:
            return self.action_ledger.transition(
                action_id,
                ControlPlaneActionState.COMPLETED,
                result_reference=f"cleanup-noop:{plan.plan_fingerprint()}",
                event_details={
                    "cleanup_plan_fingerprint": plan.plan_fingerprint(),
                    "cleanup_no_op": True,
                    "provider_write_attempted": False,
                },
            )
        if PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED or PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED:
            raise ControlPlaneCleanupProcessorError(
                "flatten writes cannot be enabled under cleanup processor v1"
            )
        return self._block(
            action_id,
            "FLATTEN_PROVIDER_WRITES_DISABLED",
            details={"cleanup_plan_fingerprint": plan.plan_fingerprint()},
        )
