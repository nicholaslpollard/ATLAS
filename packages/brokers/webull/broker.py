from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from packages.brokers.base import (
    BrokerAdapter,
    BrokerAdapterError,
    BrokerMutationUncertain,
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


WEBULL_SANDBOX_ENDPOINT = "api.sandbox.webull.com"


def _float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _json_response(response: Any, label: str) -> Any:
    if int(getattr(response, "status_code", 0)) != 200:
        try:
            body = response.json()
        except Exception:
            body = {"message": str(getattr(response, "text", ""))}
        raise BrokerAdapterError(f"Webull {label} failed: HTTP {getattr(response, 'status_code', '?')} {body}")
    try:
        return response.json()
    except Exception as exc:
        raise BrokerAdapterError(f"Webull {label} returned invalid JSON") from exc


def _orders_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        result: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("orders"), list):
                result.extend(row for row in item["orders"] if isinstance(row, dict))
            elif isinstance(item, dict):
                result.append(item)
        return result
    if isinstance(payload, dict):
        if isinstance(payload.get("orders"), list):
            return [row for row in payload["orders"] if isinstance(row, dict)]
        data = payload.get("data")
        if isinstance(data, list):
            return _orders_from_payload(data)
        return [payload]
    return []


def _status(raw: object, filled: float, requested: float) -> BrokerOrderStatus:
    text = str(raw or "").upper()
    if filled > 0.0 and filled + 1e-12 < requested:
        return BrokerOrderStatus.PARTIAL_FILLED
    if text in {"FILLED", "FINAL_FILLED"} or (requested > 0 and filled >= requested - 1e-12):
        return BrokerOrderStatus.FILLED
    if text in {"CANCELLED", "CANCELED"}:
        return BrokerOrderStatus.CANCELLED
    if text in {"FAILED", "REJECTED", "PLACE_FAILED"}:
        return BrokerOrderStatus.REJECTED
    if text in {"SUBMITTED", "PENDING", "NEW", "WORKING", "QUEUED"}:
        return BrokerOrderStatus.SUBMITTED
    return BrokerOrderStatus.SUBMITTED


def _side(raw: object) -> BrokerOrderSide:
    text = str(raw or "").upper()
    if text == "BUY":
        return BrokerOrderSide.BUY
    if text == "SHORT":
        return BrokerOrderSide.SHORT
    if text == "SELL":
        return BrokerOrderSide.SELL
    raise BrokerAdapterError(f"unsupported Webull order side: {raw}")


def _normalize_order(row: dict[str, Any], *, account_id: str) -> BrokerOrderSnapshot:
    requested = _float(row.get("total_quantity", row.get("quantity", row.get("qty", 0.0))))
    if requested <= 0.0:
        raise BrokerAdapterError("Webull order response is missing positive quantity")
    filled = _float(row.get("filled_quantity", row.get("filled_qty", 0.0)))
    filled_price = _float(row.get("filled_price", 0.0))
    client_id = str(row.get("client_order_id") or "").strip()
    ticker = str(row.get("symbol") or "").strip()
    if not client_id or not ticker:
        raise BrokerAdapterError("Webull order response is missing client_order_id/symbol")
    now = datetime.now(UTC)
    return BrokerOrderSnapshot(
        broker=BrokerName.WEBULL,
        account_id=account_id,
        client_order_id=client_id,
        provider_order_id=str(row.get("order_id") or "").strip() or None,
        ticker=ticker,
        side=_side(row.get("side")),
        status=_status(row.get("order_status", row.get("status")), filled, requested),
        requested_quantity=requested,
        filled_quantity=filled,
        average_fill_price=filled_price if filled > 0 and filled_price > 0 else None,
        submitted_at_utc=now,
        updated_at_utc=now,
        raw_status=str(row.get("order_status", row.get("status", ""))) or None,
    )


class WebullSandboxBroker(BrokerAdapter):
    """Webull US sandbox adapter. Phase 15 never points this class at production."""

    broker = BrokerName.WEBULL
    environment = ExecutionEnvironment.PAPER

    def __init__(
        self,
        *,
        app_key: str | None = None,
        app_secret: str | None = None,
        account_id: str | None = None,
        trade_client: Any | None = None,
    ) -> None:
        self._account_id = (account_id or os.getenv("WEBULL_ACCOUNT_ID") or "").strip() or None
        if trade_client is not None:
            self._client = trade_client
        else:
            key = (app_key or os.getenv("WEBULL_APP_KEY") or "").strip()
            secret = (app_secret or os.getenv("WEBULL_APP_SECRET") or "").strip()
            if not key or not secret:
                raise BrokerAdapterError("Webull sandbox credentials are unavailable")
            try:
                from webull.core.client import ApiClient
                from webull.trade.trade_client import TradeClient
            except ImportError as exc:
                raise BrokerAdapterError(
                    "webull-openapi-python-sdk is required for Webull sandbox execution"
                ) from exc
            api_client = ApiClient(key, secret, "us")
            api_client.add_endpoint("us", WEBULL_SANDBOX_ENDPOINT)
            self._client = TradeClient(api_client)
        self._account_id = self._account_id or self._resolve_account_id()

    @property
    def account_id(self) -> str:
        assert self._account_id is not None
        return self._account_id

    def _resolve_account_id(self) -> str:
        try:
            payload = _json_response(self._client.account_v2.get_account_list(), "account list")
        except Exception as exc:
            if isinstance(exc, BrokerAdapterError):
                raise
            raise BrokerAdapterError("Webull account-list request failed") from exc
        if not isinstance(payload, list):
            raise BrokerAdapterError("Webull account list has unexpected shape")
        candidates = [
            str(item.get("account_id") or "").strip()
            for item in payload
            if isinstance(item, dict) and str(item.get("account_id") or "").strip()
        ]
        if len(candidates) != 1:
            raise BrokerAdapterError(
                "Webull account selection is ambiguous; set WEBULL_ACCOUNT_ID explicitly"
            )
        return candidates[0]

    def account(self) -> BrokerAccountSnapshot:
        try:
            payload = _json_response(
                self._client.account_v2.get_account_balance(self.account_id), "account balance"
            )
        except Exception as exc:
            if isinstance(exc, BrokerAdapterError):
                raise
            raise BrokerAdapterError("Webull account-balance request failed") from exc
        if not isinstance(payload, dict):
            raise BrokerAdapterError("Webull balance response has unexpected shape")
        currency_assets = payload.get("account_currency_assets")
        usd = next(
            (
                item
                for item in currency_assets or []
                if isinstance(item, dict) and str(item.get("currency")) == "USD"
            ),
            {},
        )
        buying_power = max(
            _float(usd.get("buying_power")),
            _float(usd.get("day_buying_power")),
            _float(usd.get("overnight_buying_power")),
        )
        return BrokerAccountSnapshot(
            broker=self.broker,
            environment=self.environment,
            account_id=self.account_id,
            as_of_utc=datetime.now(UTC),
            equity=_float(payload.get("total_net_liquidation_value")),
            cash=_float(payload.get("total_cash_balance")),
            buying_power=buying_power,
            gross_market_value=abs(_float(payload.get("total_market_value"))),
            trading_blocked=False,
            shorting_enabled=None,
        )

    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        try:
            payload = _json_response(
                self._client.account_v2.get_account_position(self.account_id), "positions"
            )
        except Exception as exc:
            if isinstance(exc, BrokerAdapterError):
                raise
            raise BrokerAdapterError("Webull positions request failed") from exc
        if not isinstance(payload, list):
            raise BrokerAdapterError("Webull positions response has unexpected shape")
        now = datetime.now(UTC)
        result: list[BrokerPositionSnapshot] = []
        for row in payload:
            if not isinstance(row, dict) or str(row.get("instrument_type")) != "EQUITY":
                continue
            qty = _float(row.get("quantity"))
            last = _float(row.get("last_price"))
            result.append(
                BrokerPositionSnapshot(
                    broker=self.broker,
                    account_id=self.account_id,
                    ticker=str(row.get("symbol") or "").strip(),
                    quantity=qty,
                    market_value=qty * last,
                    average_entry_price=_float(row.get("cost_price")) or None,
                    as_of_utc=now,
                )
            )
        return tuple(result)

    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        try:
            payload = _json_response(
                self._client.order_v3.get_order_open(account_id=self.account_id), "open orders"
            )
        except Exception as exc:
            if isinstance(exc, BrokerAdapterError):
                raise
            raise BrokerAdapterError("Webull open-order request failed") from exc
        return tuple(_normalize_order(row, account_id=self.account_id) for row in _orders_from_payload(payload))

    @staticmethod
    def _leg_id(master: str, suffix: str) -> str:
        return (master[:29] + suffix)[:32]

    def _provider_orders(self, plan: BrokerOrderPlan) -> list[dict[str, str]]:
        exit_side = "SELL" if plan.side == BrokerOrderSide.BUY else "BUY"
        common = {
            "symbol": plan.ticker,
            "instrument_type": "EQUITY",
            "market": "US",
            "quantity": str(plan.quantity),
            "support_trading_session": "CORE",
            "time_in_force": "DAY",
            "entrust_type": "QTY",
        }
        return [
            {
                **common,
                "client_order_id": plan.client_order_id,
                "combo_type": "MASTER",
                "order_type": "LIMIT",
                "limit_price": str(plan.limit_price),
                "side": plan.side.value,
            },
            {
                **common,
                "client_order_id": self._leg_id(plan.client_order_id, "-p"),
                "combo_type": "STOP_PROFIT",
                "order_type": "LIMIT",
                "limit_price": str(plan.target_price),
                "side": exit_side,
            },
            {
                **common,
                "client_order_id": self._leg_id(plan.client_order_id, "-s"),
                "combo_type": "STOP_LOSS",
                "order_type": "STOP_LOSS",
                "stop_price": str(plan.stop_price),
                "side": exit_side,
            },
        ]

    def preview(self, plan: BrokerOrderPlan) -> BrokerPreflightResult:
        orders = self._provider_orders(plan)
        try:
            response = self._client.order_v3.preview_order(self.account_id, orders)
        except Exception as exc:
            raise BrokerAdapterError("Webull preview request failed") from exc
        accepted = int(getattr(response, "status_code", 0)) == 200
        try:
            payload = response.json()
        except Exception:
            payload = {}
        estimated_cost = None
        estimated_fees = None
        if isinstance(payload, dict):
            for key in ("estimated_cost", "estimated_amount", "cost", "order_cost"):
                if payload.get(key) not in (None, ""):
                    estimated_cost = _float(payload.get(key))
                    break
            for key in ("estimated_fees", "fees", "commission"):
                if payload.get(key) not in (None, "") and not isinstance(payload.get(key), (list, dict)):
                    estimated_fees = _float(payload.get(key))
                    break
        return BrokerPreflightResult(
            broker=self.broker,
            intent_id=plan.intent_id,
            accepted=accepted,
            as_of_utc=datetime.now(UTC),
            estimated_cost=estimated_cost,
            estimated_fees=estimated_fees,
            provider_code=str(payload.get("error_code") or "HTTP_200" if isinstance(payload, dict) else "HTTP_200"),
            provider_message=(str(payload.get("message")) if isinstance(payload, dict) and payload.get("message") else None),
            reason_codes=(
                "WEBULL_SANDBOX_PREVIEW_ACCEPTED" if accepted else "WEBULL_SANDBOX_PREVIEW_REJECTED",
                "PROTECTIVE_COMBO_INCLUDED",
            ),
        )

    def submit(self, plan: BrokerOrderPlan) -> BrokerOrderSnapshot:
        orders = self._provider_orders(plan)
        try:
            response = self._client.order_v3.place_order(self.account_id, orders)
        except Exception as exc:
            raise BrokerSubmissionUncertain(
                "Webull place_order transport/provider exception; reconcile client order id before any retry"
            ) from exc
        if int(getattr(response, "status_code", 0)) != 200:
            try:
                payload = response.json()
            except Exception:
                payload = {}
            raise BrokerAdapterError(
                f"Webull sandbox order rejected before acknowledgement: HTTP {getattr(response, 'status_code', '?')} {payload}"
            )
        return self.order(plan.client_order_id)

    def order(self, client_order_id: str) -> BrokerOrderSnapshot:
        try:
            response = self._client.order_v3.get_order_detail(self.account_id, client_order_id)
        except Exception as exc:
            raise BrokerAdapterError("Webull order-detail request failed") from exc
        status_code = int(getattr(response, "status_code", 0))
        if status_code != 200:
            try:
                payload = response.json()
            except Exception:
                payload = {"message": str(getattr(response, "text", ""))}
            text = str(payload).lower()
            if status_code == 404 or "not found" in text or "not exist" in text:
                raise BrokerOrderNotFound(client_order_id)
            raise BrokerAdapterError(f"Webull order detail failed: HTTP {status_code} {payload}")
        payload = response.json()
        rows = _orders_from_payload(payload)
        row = next((item for item in rows if str(item.get("client_order_id")) == client_order_id), None)
        if row is None:
            raise BrokerAdapterError("Webull order-detail response did not contain requested client order id")
        return _normalize_order(row, account_id=self.account_id)

    def cancel(self, client_order_id: str) -> BrokerOrderSnapshot:
        if not str(client_order_id).strip():
            raise BrokerAdapterError("Webull cancellation requires a client order id")
        try:
            response = self._client.order_v3.cancel_order(self.account_id, client_order_id)
        except Exception as exc:
            raise BrokerMutationUncertain(
                "Webull cancel request outcome is uncertain; reconcile exact client order id before any retry"
            ) from exc
        try:
            _json_response(response, "cancel order")
            reconciled = self.order(client_order_id)
        except BrokerAdapterError as exc:
            raise BrokerMutationUncertain(
                "Webull cancellation was attempted but exact order reconciliation failed; reconcile before any further mutation"
            ) from exc
        if reconciled.status != BrokerOrderStatus.CANCELLED:
            raise BrokerMutationUncertain(
                "Webull cancellation was attempted but final cancellation is not yet proven; reconcile before any further mutation"
            )
        return reconciled
