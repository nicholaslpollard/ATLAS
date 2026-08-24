from __future__ import annotations

import logging

import pytest

from packages.brokers.base import BrokerAdapterError, BrokerOrderNotFound
from packages.brokers.webull import WebullSandboxBroker, harden_webull_sdk_logging


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
