from __future__ import annotations

import logging

import pytest

from packages.brokers.base import BrokerAdapterError, BrokerOrderNotFound
from packages.brokers.webull import WebullSandboxBroker, harden_webull_sdk_logging
from packages.brokers.webull.broker import _normalize_order


class _Response:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _RaisingOrderApi:
    def __init__(self, message: str) -> None:
        self.message = message
        self.calls = 0

    def get_order_detail(self, account_id: str, client_order_id: str):
        self.calls += 1
        raise RuntimeError(self.message)


class _FakeTradeClient:
    def __init__(self, message: str) -> None:
        self.order_v3 = _RaisingOrderApi(message)


class _CancelHistoryApi:
    def __init__(self, history_payload: object) -> None:
        self.history_payload = history_payload
        self.cancel_calls = 0
        self.history_calls = 0

    def cancel_order(self, account_id: str, client_order_id: str):
        self.cancel_calls += 1
        return _Response({"message": "accepted"})

    def get_order_history(self, account_id: str):
        self.history_calls += 1
        return _Response(self.history_payload)


class _CancelTradeClient:
    def __init__(self, history_payload: object) -> None:
        self.order_v3 = _CancelHistoryApi(history_payload)


def _order_row(status: str) -> dict[str, str]:
    return {
        "client_order_id": "p18-test-client-id",
        "order_id": "provider-order-redacted",
        "symbol": "AAPL",
        "side": "BUY",
        "status": status,
        "total_quantity": "1",
        "filled_quantity": "0",
    }


def test_explicit_order_not_present_maps_to_broker_order_not_found() -> None:
    client = _FakeTradeClient(
        "ServerException:HTTP Status: 417, Code: OPENAPI_PARAM_ERR, "
        "Msg: Parameter error, Order not present."
    )
    broker = WebullSandboxBroker(account_id="sanitized-test-account", trade_client=client)

    with pytest.raises(BrokerOrderNotFound):
        broker.order("p18-test-client-id")

    assert client.order_v3.calls == 1


def test_other_417_provider_error_remains_fail_closed() -> None:
    client = _FakeTradeClient(
        "ServerException:HTTP Status: 417, Code: OPENAPI_PARAM_ERR, "
        "Msg: Parameter error, invalid request."
    )
    broker = WebullSandboxBroker(account_id="sanitized-test-account", trade_client=client)

    with pytest.raises(BrokerAdapterError, match="Webull order-detail request failed"):
        broker.order("p18-test-client-id")

    assert client.order_v3.calls == 1


def test_cancel_uses_exact_history_fallback_without_second_cancel(monkeypatch) -> None:
    history_payload = [{"combo_type": "MASTER", "orders": [_order_row("CANCELLED")]}]
    client = _CancelTradeClient(history_payload)
    broker = WebullSandboxBroker(account_id="sanitized-test-account", trade_client=client)
    submitted = _normalize_order(_order_row("SUBMITTED"), account_id=broker.account_id)
    calls = 0

    def scripted_order(client_order_id: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            return submitted
        raise BrokerOrderNotFound(client_order_id)

    monkeypatch.setattr(broker, "order", scripted_order)

    cancelled = broker.cancel("p18-test-client-id")

    assert cancelled.status.value == "CANCELLED"
    assert cancelled.filled_quantity == 0.0
    assert client.order_v3.cancel_calls == 1
    assert client.order_v3.history_calls == 1


def test_webull_sensitive_sdk_loggers_are_disabled() -> None:
    names = (
        "webull.core.client",
        "webull.core.http.initializer.client_initializer",
    )
    prior = {name: logging.getLogger(name).disabled for name in names}
    try:
        for name in names:
            logging.getLogger(name).disabled = False
        harden_webull_sdk_logging()
        assert all(logging.getLogger(name).disabled for name in names)
    finally:
        for name, disabled in prior.items():
            logging.getLogger(name).disabled = disabled
