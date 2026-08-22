from __future__ import annotations

import http.client
import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime

import pytest

from packages.control_plane.http_server import create_status_server
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings
from packages.execution.phase15_closeout import PHASE15_CLOSEOUT_CONTRACT_VERSION
from packages.execution.phase15_foundation import PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT
from packages.execution.phase15_policy import phase15_policy_fingerprint
from packages.schemas.control_plane_status import ControlPlaneHealthState, ControlPlaneReadState
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderSide,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    ExecutionEnvironment,
)


NOW = datetime(2026, 8, 22, 20, 0, tzinfo=UTC)


class FakeReadBroker:
    environment = ExecutionEnvironment.PAPER

    def __init__(self, broker: BrokerName) -> None:
        self.broker = broker
        self.calls: list[str] = []
        self.account_id = "acct-super-secret-1234"

    def account(self) -> BrokerAccountSnapshot:
        self.calls.append("account")
        return BrokerAccountSnapshot(
            broker=self.broker,
            environment=self.environment,
            account_id=self.account_id,
            as_of_utc=NOW,
            equity=25000.0,
            cash=10000.0,
            buying_power=20000.0,
            gross_market_value=15000.0,
            trading_blocked=False,
            shorting_enabled=True,
        )

    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        self.calls.append("positions")
        return (
            BrokerPositionSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                ticker="SPY",
                quantity=2.0,
                market_value=1200.0,
                average_entry_price=590.0,
                as_of_utc=NOW,
            ),
        )

    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        self.calls.append("open_orders")
        return (
            BrokerOrderSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                client_order_id="atlas-read-123456",
                provider_order_id="provider-secret-id",
                ticker="QQQ",
                side=BrokerOrderSide.BUY,
                status=BrokerOrderStatus.SUBMITTED,
                requested_quantity=1.0,
                filled_quantity=0.0,
                submitted_at_utc=NOW,
                updated_at_utc=NOW,
                raw_status="provider-raw-status",
            ),
        )

    def preview(self, plan: object) -> None:
        raise AssertionError("read-only status service must never call preview")

    def submit(self, plan: object) -> None:
        raise AssertionError("read-only status service must never call submit")

    def order(self, client_order_id: str) -> None:
        raise AssertionError("read-only status service must never query individual orders")

    def cancel(self, client_order_id: str) -> None:
        raise AssertionError("read-only status service must never call cancel")


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _write_phase15_acceptance(tmp_path) -> None:
    root = tmp_path / "execution" / "phase15" / "v1"
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_version": PHASE15_CLOSEOUT_CONTRACT_VERSION,
        "pass": True,
        "as_of_date": "2026-08-14",
        "phase15_policy_fingerprint": phase15_policy_fingerprint(),
        "cumulative_foundation_fingerprint": PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
        "execution_case_count": 0,
        "final_disposition": {
            "phase15_accepted": True,
            "actual_broker_execution_exercised_in_acceptance": False,
            "live_execution_promoted": False,
            "automatic_cross_broker_failover_allowed": False,
        },
    }
    (root / "phase15_final_acceptance.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_system_status_fails_closed_until_phase15_acceptance_is_present(tmp_path) -> None:
    service = Phase16StatusService(_settings_with_derived(tmp_path), env={})
    status = service.system_status()
    assert status.health == ControlPlaneHealthState.BLOCKED
    assert status.phase15.accepted is False
    assert status.write_actions_enabled is False
    assert status.live_execution_promoted is False
    assert status.automatic_cross_broker_failover_allowed is False


def test_system_status_accepts_exact_phase15_closeout_artifact(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    service = Phase16StatusService(_settings_with_derived(tmp_path), env={})
    status = service.system_status()
    assert status.health == ControlPlaneHealthState.HEALTHY
    assert status.phase15.accepted is True
    assert status.phase15.execution_case_count == 0


def test_broker_status_is_lazy_and_never_exposes_credential_values(tmp_path) -> None:
    calls: list[BrokerName] = []

    def factory(broker: BrokerName):
        calls.append(broker)
        raise AssertionError("factory must not be called without refresh")

    env = {
        "WEBULL_APP_KEY": "webull-key-secret-value",
        "WEBULL_APP_SECRET": "webull-secret-value",
        "WEBULL_ACCOUNT_ID": "webull-account-secret-value",
        "ALPACA_PAPER_API_KEY": "alpaca-key-secret-value",
        "ALPACA_PAPER_API_SECRET": "alpaca-secret-value",
    }
    service = Phase16StatusService(
        _settings_with_derived(tmp_path), env=env, broker_factory=factory
    )
    rows = service.brokers_status(refresh=False)
    assert calls == []
    assert all(row.state == ControlPlaneReadState.UNPOLLED for row in rows)
    encoded = json.dumps([row.model_dump(mode="json") for row in rows])
    for secret in env.values():
        assert secret not in encoded


def test_refresh_uses_only_read_methods_and_sanitizes_provider_identifiers(tmp_path) -> None:
    fake = FakeReadBroker(BrokerName.WEBULL)
    env = {"WEBULL_APP_KEY": "k", "WEBULL_APP_SECRET": "s"}
    service = Phase16StatusService(
        _settings_with_derived(tmp_path),
        env=env,
        broker_factory=lambda broker: fake,
        clock=lambda: NOW,
    )
    status = service.broker_status(BrokerName.WEBULL, refresh=True)
    assert status.state == ControlPlaneReadState.AVAILABLE
    assert fake.calls == ["account", "positions", "open_orders"]
    assert status.account is not None
    assert len(status.account.account_ref) == 16
    assert status.positions[0].ticker == "SPY"
    assert status.open_orders[0].ticker == "QQQ"
    encoded = status.model_dump_json()
    assert fake.account_id not in encoded
    assert "provider-secret-id" not in encoded
    assert "provider-raw-status" not in encoded


def test_refresh_without_credentials_does_not_initialize_adapter(tmp_path) -> None:
    called = False

    def factory(broker: BrokerName):
        nonlocal called
        called = True
        raise AssertionError("missing credentials must fail before adapter construction")

    service = Phase16StatusService(
        _settings_with_derived(tmp_path), env={}, broker_factory=factory, clock=lambda: NOW
    )
    status = service.broker_status(BrokerName.ALPACA, refresh=True)
    assert status.state == ControlPlaneReadState.UNAVAILABLE
    assert status.error_code == "CREDENTIALS_UNAVAILABLE"
    assert called is False


def test_http_server_is_get_only_loopback_and_host_validated(tmp_path) -> None:
    service = Phase16StatusService(_settings_with_derived(tmp_path), env={})
    server = create_status_server(service=service, host="127.0.0.1", port=0)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    port = int(server.server_address[1])
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=5) as response:
            assert response.status == 200
            payload = json.loads(response.read().decode("utf-8"))
            assert payload["phase15_accepted"] is False
            assert payload["live_execution_promoted"] is False
            assert response.headers.get("Access-Control-Allow-Origin") is None
            assert response.headers["Cache-Control"] == "no-store"

        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/v1/status", data=b"{}", method="POST"
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(request, timeout=5)
        assert exc_info.value.code == 405
        assert exc_info.value.headers["Allow"] == "GET, HEAD"

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.putrequest("GET", "/healthz", skip_host=True)
        connection.putheader("Host", "evil.example")
        connection.endheaders()
        response = connection.getresponse()
        assert response.status == 403
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_server_rejects_non_loopback_bind(tmp_path) -> None:
    service = Phase16StatusService(_settings_with_derived(tmp_path), env={})
    with pytest.raises(ValueError, match="loopback"):
        create_status_server(service=service, host="0.0.0.0", port=0)
