from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from packages.brokers.base import (
    BrokerAdapter,
    BrokerAdapterError,
    BrokerOrderNotFound,
    BrokerSubmissionUncertain,
)
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderPlan,
    BrokerOrderSide,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    BrokerPreflightResult,
    ExecutionEnvironment,
)


def _float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _enum_text(value: object) -> str:
    return str(getattr(value, "value", value) or "")


def _status(value: object) -> BrokerOrderStatus:
    text = _enum_text(value).lower()
    if text == "filled":
        return BrokerOrderStatus.FILLED
    if text == "partially_filled":
        return BrokerOrderStatus.PARTIAL_FILLED
    if text in {"canceled", "cancelled", "expired"}:
        return BrokerOrderStatus.CANCELLED
    if text in {"rejected", "suspended"}:
        return BrokerOrderStatus.REJECTED
    if text in {"new", "accepted", "pending_new", "accepted_for_bidding", "stopped", "calculated", "pending_replace", "pending_cancel"}:
        return BrokerOrderStatus.SUBMITTED
    return BrokerOrderStatus.SUBMITTED


def _side(value: object, *, override: BrokerOrderSide | None = None) -> BrokerOrderSide:
    if override is not None:
        return override
    text = _enum_text(value).lower()
    if text == "buy":
        return BrokerOrderSide.BUY
    if text == "sell":
        return BrokerOrderSide.SELL
    raise BrokerAdapterError(f"unsupported Alpaca order side: {value}")


def _normalize_order(
    order: Any,
    *,
    account_id: str,
    side_override: BrokerOrderSide | None = None,
) -> BrokerOrderSnapshot:
    client_id = str(getattr(order, "client_order_id", "") or "").strip()
    ticker = str(getattr(order, "symbol", "") or "").strip()
    qty = _float(getattr(order, "qty", None))
    filled = _float(getattr(order, "filled_qty", None))
    filled_price = _float(getattr(order, "filled_avg_price", None))
    if not client_id or not ticker or qty <= 0.0:
        raise BrokerAdapterError("Alpaca order response is missing client id/ticker/quantity")
    submitted = getattr(order, "submitted_at", None)
    updated = getattr(order, "updated_at", None) or getattr(order, "filled_at", None) or submitted
    now = datetime.now(UTC)
    return BrokerOrderSnapshot(
        broker=BrokerName.ALPACA,
        account_id=account_id,
        client_order_id=client_id,
        provider_order_id=str(getattr(order, "id", "") or "").strip() or None,
        ticker=ticker,
        side=_side(getattr(order, "side", None), override=side_override),
        status=_status(getattr(order, "status", None)),
        requested_quantity=qty,
        filled_quantity=filled,
        average_fill_price=filled_price if filled > 0.0 and filled_price > 0.0 else None,
        submitted_at_utc=submitted or now,
        updated_at_utc=updated or now,
        raw_status=_enum_text(getattr(order, "status", None)) or None,
    )


class AlpacaPaperBroker(BrokerAdapter):
    """Alpaca paper adapter; the `paper=True` client mode is not configurable here."""

    broker = BrokerName.ALPACA
    environment = ExecutionEnvironment.PAPER

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        trading_client: Any | None = None,
    ) -> None:
        self._submitted_sides: dict[str, BrokerOrderSide] = {}
        if trading_client is not None:
            self._client = trading_client
        else:
            key = (api_key or os.getenv("ALPACA_PAPER_API_KEY") or "").strip()
            secret = (api_secret or os.getenv("ALPACA_PAPER_API_SECRET") or "").strip()
            if not key or not secret:
                raise BrokerAdapterError("Alpaca paper credentials are unavailable")
            try:
                from alpaca.trading.client import TradingClient
            except ImportError as exc:
                raise BrokerAdapterError("alpaca-py is required for Alpaca paper execution") from exc
            self._client = TradingClient(key, secret, paper=True)
        self._account_id: str | None = None

    def _account_model(self) -> Any:
        try:
            return self._client.get_account()
        except Exception as exc:
            raise BrokerAdapterError("Alpaca paper account request failed") from exc

    @property
    def account_id(self) -> str:
        if self._account_id is None:
            account = self._account_model()
            self._account_id = str(getattr(account, "id", "") or getattr(account, "account_number", "")).strip()
            if not self._account_id:
                raise BrokerAdapterError("Alpaca account response is missing account identity")
        return self._account_id

    def account(self) -> BrokerAccountSnapshot:
        account = self._account_model()
        account_id = str(getattr(account, "id", "") or getattr(account, "account_number", "")).strip()
        if not account_id:
            raise BrokerAdapterError("Alpaca account response is missing account identity")
        self._account_id = account_id
        return BrokerAccountSnapshot(
            broker=self.broker,
            environment=self.environment,
            account_id=account_id,
            as_of_utc=datetime.now(UTC),
            equity=_float(getattr(account, "equity", None)),
            cash=_float(getattr(account, "cash", None)),
            buying_power=_float(getattr(account, "buying_power", None)),
            gross_market_value=abs(_float(getattr(account, "long_market_value", None)))
            + abs(_float(getattr(account, "short_market_value", None))),
            trading_blocked=bool(getattr(account, "trading_blocked", False)),
            shorting_enabled=bool(getattr(account, "shorting_enabled", False)),
        )

    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        try:
            positions = self._client.get_all_positions()
        except Exception as exc:
            raise BrokerAdapterError("Alpaca paper positions request failed") from exc
        now = datetime.now(UTC)
        result: list[BrokerPositionSnapshot] = []
        for item in positions:
            ticker = str(getattr(item, "symbol", "") or "").strip()
            qty = _float(getattr(item, "qty", None))
            market_value = _float(getattr(item, "market_value", None))
            side = _enum_text(getattr(item, "side", None)).lower()
            if side == "short" and qty > 0:
                qty = -qty
                market_value = -abs(market_value)
            result.append(
                BrokerPositionSnapshot(
                    broker=self.broker,
                    account_id=self.account_id,
                    ticker=ticker,
                    quantity=qty,
                    market_value=market_value,
                    average_entry_price=_float(getattr(item, "avg_entry_price", None)) or None,
                    as_of_utc=now,
                )
            )
        return tuple(result)

    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        try:
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest
            orders = self._client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
        except Exception as exc:
            raise BrokerAdapterError("Alpaca paper open-orders request failed") from exc
        return tuple(
            _normalize_order(
                item,
                account_id=self.account_id,
                side_override=self._submitted_sides.get(str(getattr(item, "client_order_id", ""))),
            )
            for item in orders
        )

    def preview(self, plan: BrokerOrderPlan) -> BrokerPreflightResult:
        account = self.account()
        accepted = not account.trading_blocked
        reasons = ["ALPACA_LOCAL_PREFLIGHT_NO_PROVIDER_PREVIEW_ENDPOINT"]
        estimated = float(plan.quantity) * float(plan.limit_price)
        if estimated > account.buying_power + 1e-12:
            accepted = False
            reasons.append("BUYING_POWER_FAIL")
        else:
            reasons.append("BUYING_POWER_PASS")
        if plan.side == BrokerOrderSide.SHORT:
            try:
                asset = self._client.get_asset(plan.ticker)
            except Exception as exc:
                raise BrokerAdapterError("Alpaca asset preflight request failed") from exc
            tradable = bool(getattr(asset, "tradable", False))
            shortable = bool(getattr(asset, "shortable", False))
            if not tradable or not shortable or account.shorting_enabled is False:
                accepted = False
            reasons.append("ASSET_TRADABLE" if tradable else "ASSET_NOT_TRADABLE")
            reasons.append("ASSET_SHORTABLE" if shortable else "ASSET_NOT_SHORTABLE")
        else:
            try:
                asset = self._client.get_asset(plan.ticker)
            except Exception as exc:
                raise BrokerAdapterError("Alpaca asset preflight request failed") from exc
            tradable = bool(getattr(asset, "tradable", False))
            if not tradable:
                accepted = False
            reasons.append("ASSET_TRADABLE" if tradable else "ASSET_NOT_TRADABLE")
        return BrokerPreflightResult(
            broker=self.broker,
            intent_id=plan.intent_id,
            accepted=accepted,
            as_of_utc=datetime.now(UTC),
            estimated_cost=estimated,
            estimated_fees=None,
            provider_code="LOCAL_PREFLIGHT_ACCEPT" if accepted else "LOCAL_PREFLIGHT_REJECT",
            provider_message="Alpaca paper preflight based on account and asset trading state.",
            reason_codes=tuple(reasons),
        )

    def submit(self, plan: BrokerOrderPlan) -> BrokerOrderSnapshot:
        try:
            from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
            from alpaca.trading.requests import LimitOrderRequest, StopLossRequest, TakeProfitRequest
            request = LimitOrderRequest(
                symbol=plan.ticker,
                qty=plan.quantity,
                side=OrderSide.BUY if plan.side == BrokerOrderSide.BUY else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=plan.limit_price,
                extended_hours=False,
                client_order_id=plan.client_order_id,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=plan.target_price),
                stop_loss=StopLossRequest(stop_price=plan.stop_price),
            )
            order = self._client.submit_order(order_data=request)
        except Exception as exc:
            # Transport/API exceptions around submission are not retried because the
            # request may have reached Alpaca. Reconcile by client_order_id first.
            raise BrokerSubmissionUncertain(
                "Alpaca submit_order outcome is uncertain; reconcile client order id before any retry"
            ) from exc
        self._submitted_sides[plan.client_order_id] = plan.side
        return _normalize_order(order, account_id=self.account_id, side_override=plan.side)

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        status = getattr(exc, "status_code", None)
        code = getattr(exc, "code", None)
        text = str(exc).lower()
        return status == 404 or code == 40410000 or "not found" in text or "order does not exist" in text

    def order(self, client_order_id: str) -> BrokerOrderSnapshot:
        try:
            order = self._client.get_order_by_client_id(client_order_id)
        except Exception as exc:
            if self._is_not_found(exc):
                raise BrokerOrderNotFound(client_order_id) from exc
            raise BrokerAdapterError("Alpaca order-by-client-id request failed") from exc
        return _normalize_order(
            order,
            account_id=self.account_id,
            side_override=self._submitted_sides.get(client_order_id),
        )

    def cancel(self, client_order_id: str) -> BrokerOrderSnapshot:
        order = self.order(client_order_id)
        if order.provider_order_id is None:
            raise BrokerAdapterError("Alpaca order is missing provider order id for cancellation")
        try:
            self._client.cancel_order_by_id(order.provider_order_id)
        except Exception as exc:
            raise BrokerAdapterError("Alpaca paper cancel request failed") from exc
        return self.order(client_order_id)
