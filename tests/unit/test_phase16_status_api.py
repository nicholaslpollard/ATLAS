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

    def __init__(self, broker: BrokerName, *, flat: bool = False) -> None:
        self.broker = broker
        self.flat = flat
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
            gross_market_value=0.0 if self.flat else 15000.0,
            trading_blocked=False,
            shorting_enabled=True,
        )

    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        self.calls.append("open_orders")
        if self.flat:
            return ()
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

    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        self.calls.append("positions")
        if self.flat:
            return ()
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

    def preview(self, plan: object) -> None:
        raise AssertionError("status service must never call preview")

    def submit(self, plan: object) -> None:
        raise AssertionError("status service must never call submit")

    def order(self, client_order_id: str) -> None:
        raise AssertionError("status service must never call individual order query")

    def cancel(self, client_order_id: str) -> None:
        raise AssertionError("status service must never call cancel")


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _write_phase15_acceptance(tmp_path) -> None:
    root = tmp_path / "execution" / "phase15" / "v1"
    root.mkdir(parents=True, exist_ok=True)
    (root / "phase15_final_acceptance.json").write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )


def test_system_status_fails_closed_until_phase15_acceptance_is_present(tmp_path) -> None:
    status = Phase16StatusService(_settings_with_derived(tmp_path), env={}).system_status()
    assert status.health == ControlPlaneHealthState.BLOCKED
    assert status.phase15.accepted is False
    assert status.action_ledger_valid is True
    assert status.action_request_endpoints_present is True
    assert status.provider_write_endpoints_present is False
    assert status.live_execution_promoted is False
    assert status.automatic_cross_broker_failover_allowed is False


def test_system_status_accepts_exact_phase15_closeout_artifact(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    status = Phase16StatusService(_settings_with_derived(tmp_path), env={}).system_status()
    assert status.health == ControlPlaneHealthState.HEALTHY
    assert status.phase15.accepted is True
    assert status.phase15.execution_case_count == 0
    assert status.selected_broker is None
    assert status.selected_environment is None
    assert status.action_count == 0
    assert status.active_action_count == 0
    assert status.uncertain_action_count == 0


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
    rows = Phase16StatusService(
        _settings_with_derived(tmp_path), env=env, broker_factory=factory
    ).brokers_status(refresh=False)
    assert calls == []
    assert all(row.state == ControlPlaneReadState.UNPOLLED for row in rows)
    encoded = json.dumps([row.model_dump(mode="json") for row in rows])
    assert all(secret not in encoded for secret in env.values())


def test_refresh_reuses_phase15_reconciliation_and_sanitizes_provider_ids(tmp_path) -> None:
    fake = FakeReadBroker(BrokerName.WEBULL)
    status = Phase16StatusService(
        _settings_with_derived(tmp_path),
        env={"WEBULL_APP_KEY": "k", "WEBULL_APP_SECRET": "s"},
        broker_factory=lambda broker: fake,
        clock=lambda: NOW,
    ).broker_status(BrokerName.WEBULL, refresh=True)
    assert fake.calls == ["account", "open_orders", "positions"]
    assert status.state == ControlPlaneReadState.AVAILABLE
    assert status.reconciled is True
    assert status.safe_to_switch_broker is False
    encoded = status.model_dump_json()
    assert fake.account_id not in encoded
    assert "provider-secret-id" not in encoded
    assert "provider-raw-status" not in encoded


def test_flat_reconciled_broker_is_safe_to_switch(tmp_path) -> None:
    fake = FakeReadBroker(BrokerName.ALPACA, flat=True)
    status = Phase16StatusService(
        _settings_with_derived(tmp_path),
        env={"ALPACA_PAPER_API_KEY": "k", "ALPACA_PAPER_API_SECRET": "s"},
        broker_factory=lambda broker: fake,
        clock=lambda: NOW,
    ).broker_status(BrokerName.ALPACA, refresh=True)
    assert status.reconciled is True
    assert status.zero_open_orders is True
    assert status.zero_positions is True
    assert status.safe_to_switch_broker is True


def test_missing_credentials_prevent_adapter_initialization(tmp_path) -> None:
    called = False

    def factory(broker: BrokerName):
        nonlocal called
        called = True
        raise AssertionError("must fail before adapter construction")

    status = Phase16StatusService(
        _settings_with_derived(tmp_path), env={}, broker_factory=factory, clock=lambda: NOW
    ).broker_status(BrokerName.ALPACA, refresh=True)
    assert status.state == ControlPlaneReadState.UNAVAILABLE
    assert status.error_code == "CREDENTIALS_UNAVAILABLE"
    assert called is False


def test_http_status_is_loopback_host_validated_and_non_action_post_is_405(tmp_path) -> None:
    service = Phase16StatusService(_settings_with_derived(tmp_path), env={})
    server = create_status_server(service=service, host="127.0.0.1", port=0)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    port = int(server.server_address[1])
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert payload["phase15_accepted"] is False
            assert payload["action_ledger_valid"] is True
            assert payload["provider_write_endpoints_present"] is False
            assert response.headers.get("Access-Control-Allow-Origin") is None
            assert response.headers["Cache-Control"] == "no-store"

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/v1/strategies/reference", timeout=5
        ) as response:
            strategy_payload = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert strategy_payload["family_count"] == 6
            assert strategy_payload["strategy_count"] == 9
            assert strategy_payload["execution_boundaries"] == {
                "broker_writes": 0,
                "live_allowed": False,
                "live_writes": 0,
                "operational_paper_allowed": False,
                "paper_submits": 0,
                "qualifying_paper_allowed": False,
                "research_replay_allowed": True,
            }

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/v1/research/reference-replay", timeout=5
        ) as response:
            replay_payload = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert replay_payload["status"] == "NOT_RUN"
            assert replay_payload["summary"] is None
            assert replay_payload["authority"]["broker_writes"] == 0
            assert replay_payload["authority"]["paper_submits"] == 0
            assert replay_payload["authority"]["live_writes"] == 0

        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/v1/status", data=b"{}", method="POST"
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(request, timeout=5)
        assert exc_info.value.code == 405
        assert exc_info.value.headers["Allow"] == "GET, HEAD, POST"

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.putrequest("GET", "/healthz", skip_host=True)
        connection.putheader("Host", "evil.example")
        connection.endheaders()
        assert connection.getresponse().status == 403
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_browser_dashboard_is_same_origin_csp_locked_and_fixed_allowlist(tmp_path) -> None:
    calls: list[BrokerName] = []

    def factory(broker: BrokerName):
        calls.append(broker)
        raise AssertionError("loading the dashboard must not initialize a broker")

    service = Phase16StatusService(
        _settings_with_derived(tmp_path), env={}, broker_factory=factory
    )
    server = create_status_server(service=service, host="127.0.0.1", port=0)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    port = int(server.server_address[1])
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
            body = response.read().decode("utf-8")
            csp = response.headers["Content-Security-Policy"]
            assert response.status == 200
            assert response.headers["Content-Type"].startswith("text/html")
            assert "ATLAS Control Plane" in body
            assert "style-src 'self'" in csp
            assert "script-src 'self'" in csp
            assert "connect-src 'self'" in csp
            assert "unsafe-inline" not in csp
            assert response.headers.get("Access-Control-Allow-Origin") is None
            assert response.headers["X-Frame-Options"] == "DENY"

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/assets/app.js", timeout=5
        ) as response:
            js = response.read().decode("utf-8")
            assert response.status == 200
            assert response.headers["Content-Type"].startswith("text/javascript")
            assert "/api/v1/status/full" in js
            assert "/api/v1/strategies/reference" in js
            assert "/api/v1/research/reference-replay" in js
            assert "https://" not in js
            assert "http://" not in js

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", "/assets/../.env")
        response = connection.getresponse()
        response.read()
        assert response.status == 404
        connection.close()
        assert calls == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_server_rejects_non_loopback_bind(tmp_path) -> None:
    service = Phase16StatusService(_settings_with_derived(tmp_path), env={})
    with pytest.raises(ValueError, match="loopback"):
        create_status_server(service=service, host="0.0.0.0", port=0)
