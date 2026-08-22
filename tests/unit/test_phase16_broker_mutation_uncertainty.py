from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from packages.brokers.alpaca.broker import AlpacaPaperBroker
from packages.brokers.base import (
    BrokerAdapterError,
    BrokerMutationUncertain,
    BrokerOrderNotFound,
)
from packages.brokers.webull.broker import WebullSandboxBroker
from packages.schemas.execution import BrokerOrderStatus


NOW = datetime(2026, 8, 22, 22, 0, tzinfo=UTC)


class FakeResponse:
    def __init__(self, status_code: int = 200, payload=None) -> None:
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = str(self._payload)

    def json(self):
        return self._payload


class FakeWebullOrderAPI:
    def __init__(self) -> None:
        self.cancel_calls: list[str] = []
        self.cancel_error: Exception | None = None
        self.detail_error: Exception | None = None
        self.status = "CANCELLED"

    def cancel_order(self, account_id: str, client_order_id: str):
        self.cancel_calls.append(client_order_id)
        if self.cancel_error is not None:
            raise self.cancel_error
        return FakeResponse(200, {})

    def get_order_detail(self, account_id: str, client_order_id: str):
        if self.detail_error is not None:
            raise self.detail_error
        return FakeResponse(
            200,
            {
                "orders": [
                    {
                        "client_order_id": client_order_id,
                        "order_id": "provider-order-1",
                        "symbol": "SPY",
                        "side": "BUY",
                        "quantity": "1",
                        "filled_quantity": "0",
                        "order_status": self.status,
                    }
                ]
            },
        )


class FakeWebullClient:
    def __init__(self, order_api: FakeWebullOrderAPI) -> None:
        self.order_v3 = order_api


class FakeAlpacaError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FakeAlpacaClient:
    def __init__(self) -> None:
        self.cancel_calls: list[str] = []
        self.cancel_error: Exception | None = None
        self.lookup_error: Exception | None = None
        self.status = "new"
        self.provider_id: str | None = "provider-order-1"

    def get_account(self):
        return SimpleNamespace(id="alpaca-paper-account")

    def get_order_by_client_id(self, client_order_id: str):
        if self.lookup_error is not None:
            raise self.lookup_error
        return SimpleNamespace(
            id=self.provider_id,
            client_order_id=client_order_id,
            symbol="SPY",
            qty="1",
            filled_qty="0",
            filled_avg_price=None,
            submitted_at=NOW,
            updated_at=NOW,
            side="buy",
            status=self.status,
        )

    def cancel_order_by_id(self, provider_order_id: str) -> None:
        self.cancel_calls.append(provider_order_id)
        if self.cancel_error is not None:
            raise self.cancel_error
        self.status = "canceled"


def test_webull_cancel_requires_final_cancelled_reconciliation() -> None:
    api = FakeWebullOrderAPI()
    broker = WebullSandboxBroker(
        account_id="webull-sandbox-account",
        trade_client=FakeWebullClient(api),
    )
    result = broker.cancel("client-order-1")
    assert result.status == BrokerOrderStatus.CANCELLED
    assert api.cancel_calls == ["client-order-1"]


def test_webull_cancel_transport_or_reconciliation_failure_is_mutation_uncertain() -> None:
    api = FakeWebullOrderAPI()
    api.cancel_error = TimeoutError("transport timeout")
    broker = WebullSandboxBroker(
        account_id="webull-sandbox-account",
        trade_client=FakeWebullClient(api),
    )
    with pytest.raises(BrokerMutationUncertain):
        broker.cancel("client-order-transport")
    assert api.cancel_calls == ["client-order-transport"]

    api = FakeWebullOrderAPI()
    api.detail_error = TimeoutError("detail timeout")
    broker = WebullSandboxBroker(
        account_id="webull-sandbox-account",
        trade_client=FakeWebullClient(api),
    )
    with pytest.raises(BrokerMutationUncertain):
        broker.cancel("client-order-detail")
    assert api.cancel_calls == ["client-order-detail"]


def test_webull_cancel_nonterminal_reconciliation_is_mutation_uncertain() -> None:
    api = FakeWebullOrderAPI()
    api.status = "PENDING"
    broker = WebullSandboxBroker(
        account_id="webull-sandbox-account",
        trade_client=FakeWebullClient(api),
    )
    with pytest.raises(BrokerMutationUncertain):
        broker.cancel("client-order-pending")
    assert api.cancel_calls == ["client-order-pending"]


def test_webull_empty_client_order_id_fails_before_provider_mutation() -> None:
    api = FakeWebullOrderAPI()
    broker = WebullSandboxBroker(
        account_id="webull-sandbox-account",
        trade_client=FakeWebullClient(api),
    )
    with pytest.raises(BrokerAdapterError):
        broker.cancel(" ")
    assert api.cancel_calls == []


def test_alpaca_cancel_requires_final_cancelled_reconciliation() -> None:
    client = FakeAlpacaClient()
    broker = AlpacaPaperBroker(trading_client=client)
    result = broker.cancel("client-order-1")
    assert result.status == BrokerOrderStatus.CANCELLED
    assert client.cancel_calls == ["provider-order-1"]


def test_alpaca_cancel_transport_failure_is_mutation_uncertain() -> None:
    client = FakeAlpacaClient()
    client.cancel_error = TimeoutError("transport timeout")
    broker = AlpacaPaperBroker(trading_client=client)
    with pytest.raises(BrokerMutationUncertain):
        broker.cancel("client-order-timeout")
    assert client.cancel_calls == ["provider-order-1"]


def test_alpaca_post_cancel_lookup_failure_is_mutation_uncertain() -> None:
    class FailSecondLookupClient(FakeAlpacaClient):
        def __init__(self) -> None:
            super().__init__()
            self.lookup_count = 0

        def get_order_by_client_id(self, client_order_id: str):
            self.lookup_count += 1
            if self.lookup_count > 1:
                raise TimeoutError("post-cancel lookup timeout")
            return super().get_order_by_client_id(client_order_id)

    client = FailSecondLookupClient()
    broker = AlpacaPaperBroker(trading_client=client)
    with pytest.raises(BrokerMutationUncertain):
        broker.cancel("client-order-detail")
    assert client.cancel_calls == ["provider-order-1"]


def test_alpaca_definitive_missing_order_fails_before_cancel() -> None:
    client = FakeAlpacaClient()
    client.lookup_error = FakeAlpacaError("order does not exist", status_code=404)
    broker = AlpacaPaperBroker(trading_client=client)
    with pytest.raises(BrokerOrderNotFound):
        broker.cancel("missing-order")
    assert client.cancel_calls == []


def test_alpaca_missing_provider_order_id_fails_before_cancel() -> None:
    client = FakeAlpacaClient()
    client.provider_id = None
    broker = AlpacaPaperBroker(trading_client=client)
    with pytest.raises(BrokerAdapterError):
        broker.cancel("client-order-no-provider-id")
    assert client.cancel_calls == []
