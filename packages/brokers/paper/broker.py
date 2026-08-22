from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock

from packages.brokers.base import BrokerAdapter, BrokerOrderNotFound
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderPlan,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    BrokerPreflightResult,
    ExecutionEnvironment,
)


class ShadowBroker(BrokerAdapter):
    """Deterministic local broker used to exercise Phase 15 without side effects.

    Entry orders fill immediately at the limit price. The protective stop/target remain
    on the immutable order plan for downstream simulation/outcome tests; this adapter
    deliberately does not invent a future exit path.
    """

    broker = BrokerName.SHADOW
    environment = ExecutionEnvironment.SHADOW

    def __init__(
        self,
        *,
        account_id: str = "atlas-shadow",
        equity: float = 100_000.0,
        cash: float = 100_000.0,
        buying_power: float = 100_000.0,
        shorting_enabled: bool = True,
    ) -> None:
        self.account_id = account_id
        self._equity = float(equity)
        self._cash = float(cash)
        self._buying_power = float(buying_power)
        self._shorting_enabled = bool(shorting_enabled)
        self._orders: dict[str, BrokerOrderSnapshot] = {}
        self._positions: dict[str, BrokerPositionSnapshot] = {}
        self._lock = RLock()

    def account(self) -> BrokerAccountSnapshot:
        with self._lock:
            gross = sum(abs(item.market_value) for item in self._positions.values())
            return BrokerAccountSnapshot(
                broker=self.broker,
                environment=self.environment,
                account_id=self.account_id,
                as_of_utc=datetime.now(UTC),
                equity=self._equity,
                cash=self._cash,
                buying_power=self._buying_power,
                gross_market_value=gross,
                trading_blocked=False,
                shorting_enabled=self._shorting_enabled,
            )

    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        with self._lock:
            return tuple(self._positions[key] for key in sorted(self._positions))

    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        open_statuses = {
            BrokerOrderStatus.PLANNED,
            BrokerOrderStatus.PREFLIGHTED,
            BrokerOrderStatus.SUBMITTED,
            BrokerOrderStatus.PARTIAL_FILLED,
        }
        with self._lock:
            return tuple(
                item
                for key, item in sorted(self._orders.items())
                if item.status in open_statuses
            )

    def preview(self, plan: BrokerOrderPlan) -> BrokerPreflightResult:
        account = self.account()
        estimated = float(plan.quantity) * float(plan.limit_price)
        accepted = not account.trading_blocked and estimated <= account.buying_power + 1e-12
        if plan.side.value == "SHORT" and account.shorting_enabled is False:
            accepted = False
        return BrokerPreflightResult(
            broker=self.broker,
            intent_id=plan.intent_id,
            accepted=accepted,
            as_of_utc=datetime.now(UTC),
            estimated_cost=estimated,
            estimated_fees=0.0,
            provider_code="SHADOW_ACCEPT" if accepted else "SHADOW_REJECT",
            provider_message="Deterministic local shadow preflight.",
            reason_codes=(
                "SHADOW_NO_EXTERNAL_PROVIDER",
                "BUYING_POWER_PASS" if estimated <= account.buying_power + 1e-12 else "BUYING_POWER_FAIL",
                "SHORTING_PASS" if plan.side.value != "SHORT" or account.shorting_enabled else "SHORTING_FAIL",
            ),
        )

    def submit(self, plan: BrokerOrderPlan) -> BrokerOrderSnapshot:
        with self._lock:
            if plan.client_order_id in self._orders:
                return self._orders[plan.client_order_id]
            now = datetime.now(UTC)
            order = BrokerOrderSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                client_order_id=plan.client_order_id,
                provider_order_id="shadow-" + plan.client_order_id,
                ticker=plan.ticker,
                side=plan.side,
                status=BrokerOrderStatus.SHADOW_FILLED,
                requested_quantity=float(plan.quantity),
                filled_quantity=float(plan.quantity),
                average_fill_price=float(plan.limit_price),
                submitted_at_utc=now,
                updated_at_utc=now,
                raw_status="SHADOW_FILLED",
            )
            signed_qty = float(plan.quantity) if plan.side.value == "BUY" else -float(plan.quantity)
            signed_value = signed_qty * float(plan.limit_price)
            self._positions[plan.ticker] = BrokerPositionSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                ticker=plan.ticker,
                quantity=signed_qty,
                market_value=signed_value,
                average_entry_price=float(plan.limit_price),
                as_of_utc=now,
            )
            self._orders[plan.client_order_id] = order
            return order

    def order(self, client_order_id: str) -> BrokerOrderSnapshot:
        with self._lock:
            try:
                return self._orders[client_order_id]
            except KeyError as exc:
                raise BrokerOrderNotFound(client_order_id) from exc

    def cancel(self, client_order_id: str) -> BrokerOrderSnapshot:
        with self._lock:
            current = self.order(client_order_id)
            if current.status in {BrokerOrderStatus.FILLED, BrokerOrderStatus.SHADOW_FILLED}:
                return current
            cancelled = current.model_copy(
                update={"status": BrokerOrderStatus.CANCELLED, "updated_at_utc": datetime.now(UTC)}
            )
            self._orders[client_order_id] = cancelled
            return cancelled
