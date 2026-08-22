from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.broker_switch_processor import Phase16BrokerSwitchProcessor
from packages.control_plane.http_server import create_status_server
from packages.control_plane.runtime_state import ControlPlaneRuntimeStateStore
from packages.control_plane.session import (
    CONTROL_PLANE_CSRF_HEADER,
    CONTROL_PLANE_SESSION_COOKIE,
    ControlPlaneSessionGuard,
)
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings
from packages.execution.phase15_closeout import PHASE15_CLOSEOUT_CONTRACT_VERSION
from packages.execution.phase15_foundation import PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT
from packages.execution.phase15_policy import phase15_policy_fingerprint
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderSide,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    ExecutionEnvironment,
)


NOW = datetime(2026, 8, 22, 22, 30, tzinfo=UTC)
TOKEN = "phase16-http-session-token-0123456789abcdef"


class FakeHTTPBroker:
    environment = ExecutionEnvironment.PAPER

    def __init__(
        self,
        broker: BrokerName,
        *,
        orders: bool = False,
        positions: bool = False,
    ) -> None:
        self.broker = broker
        self.has_orders = orders
        self.has_positions = positions
        self.account_id = f"{broker.value}-http-secret-account"
        self.read_calls: list[str] = []
        self.write_calls: list[str] = []

    def account(self) -> BrokerAccountSnapshot:
        self.read_calls.append("account")
        return BrokerAccountSnapshot(
            broker=self.broker,
            environment=self.environment,
            account_id=self.account_id,
            as_of_utc=NOW,
            equity=25000.0,
            cash=25000.0,
            buying_power=50000.0,
            gross_market_value=1000.0 if self.has_positions else 0.0,
            trading_blocked=False,
            shorting_enabled=True,
        )

    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        self.read_calls.append("open_orders")
        if not self.has_orders:
            return ()
        return (
            BrokerOrderSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                client_order_id=f"{self.broker.value}-http-order",
                provider_order_id=f"{self.broker.value}-provider-secret",
                ticker="SPY",
                side=BrokerOrderSide.BUY,
                status=BrokerOrderStatus.SUBMITTED,
                requested_quantity=1.0,
                filled_quantity=0.0,
                submitted_at_utc=NOW,
                updated_at_utc=NOW,
            ),
        )

    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        self.read_calls.append("positions")
        if not self.has_positions:
            return ()
        return (
            BrokerPositionSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                ticker="QQQ",
                quantity=1.0,
                market_value=1000.0,
                average_entry_price=500.0,
                as_of_utc=NOW,
            ),
        )

    def preview(self, plan):
        self.write_calls.append("preview")
        raise AssertionError("broker switch HTTP path must never preview")

    def submit(self, plan):
        self.write_calls.append("submit")
        raise AssertionError("broker switch HTTP path must never submit")

    def order(self, client_order_id):
        self.write_calls.append("order")
        raise AssertionError("broker switch HTTP path must never query an individual order")

    def cancel(self, client_order_id):
        self.write_calls.append("cancel")
        raise AssertionError("broker switch HTTP path must never cancel")


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


def _server(tmp_path, brokers):
    _write_phase15_acceptance(tmp_path)
    settings = _settings_with_derived(tmp_path)
    clock = lambda: NOW + timedelta(seconds=10)
    ledger = ControlPlaneActionLedger(settings, clock=clock)
    runtime = ControlPlaneRuntimeStateStore(settings, clock=clock)
    service = Phase16StatusService(
        settings,
        env={
            "WEBULL_APP_KEY": "wk",
            "WEBULL_APP_SECRET": "ws",
            "ALPACA_PAPER_API_KEY": "ak",
            "ALPACA_PAPER_API_SECRET": "as",
        },
        clock=clock,
        runtime_store=runtime,
        action_ledger=ledger,
    )
    processor = Phase16BrokerSwitchProcessor(
        settings,
        status_service=service,
        ledger=ledger,
        runtime_store=runtime,
        broker_factory=lambda broker: brokers[broker],
        clock=clock,
    )
    guard = ControlPlaneSessionGuard(token=TOKEN)
    server = create_status_server(
        service=service,
        host="127.0.0.1",
        port=0,
        session_guard=guard,
        action_ledger=ledger,
        broker_switch_processor=processor,
    )
    return server, ledger, runtime


def _post(port: int, path: str, payload: dict[str, object]):
    raw = json.dumps(payload).encode("utf-8")
    origin = f"http://127.0.0.1:{port}"
    request = urllib.request.Request(
        origin + path,
        data=raw,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Origin": origin,
            CONTROL_PLANE_CSRF_HEADER: TOKEN,
            "Cookie": f"{CONTROL_PLANE_SESSION_COOKIE}={TOKEN}",
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _request_payload(action_id: str, target: str) -> dict[str, object]:
    return {
        "action_id": action_id,
        "action_kind": "BROKER_SWITCH",
        "requested_at_utc": NOW.isoformat(),
        "explicit_user_request": True,
        "idempotency_key": f"idem-{action_id}",
        "target_broker": target,
        "environment": "paper",
        "reason": "manual browser broker selection",
    }


def _confirm_payload(action_id: str, fingerprint: str) -> dict[str, object]:
    return {
        "grant_id": f"grant-{action_id}",
        "action_id": action_id,
        "action_fingerprint": fingerprint,
        "scope": "BROKER_SWITCH",
        "confirmed_at_utc": (NOW + timedelta(seconds=1)).isoformat(),
        "one_time": True,
    }


def test_http_request_confirm_process_switches_local_routing_with_zero_provider_writes(tmp_path) -> None:
    brokers = {
        BrokerName.WEBULL: FakeHTTPBroker(BrokerName.WEBULL),
        BrokerName.ALPACA: FakeHTTPBroker(BrokerName.ALPACA),
    }
    server, ledger, runtime = _server(tmp_path, brokers)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    port = int(server.server_address[1])
    try:
        status, requested = _post(
            port,
            "/api/v1/actions/request",
            _request_payload("switch-http-1", "alpaca"),
        )
        assert status == 200
        record = requested["record"]
        assert record["state"] == "AWAITING_CONFIRMATION"
        assert requested["provider_write_attempted"] is False

        status, confirmed = _post(
            port,
            "/api/v1/actions/switch-http-1/confirm",
            _confirm_payload("switch-http-1", record["request_fingerprint"]),
        )
        assert status == 200
        assert confirmed["record"]["state"] == "AUTHORIZED"

        status, processed = _post(
            port,
            "/api/v1/actions/switch-http-1/process",
            {"process": True},
        )
        assert status == 200
        assert processed["record"]["state"] == "COMPLETED"
        assert processed["record"]["provider_write_attempted"] is False
        assert processed["provider_write_attempted"] is False
        assert processed["provider_write_endpoint_invoked"] is False
        assert processed["provider_write_endpoints_present"] is False
        assert processed["runtime"]["selected_broker"] == "alpaca"
        assert processed["runtime"]["selected_environment"] == "paper"
        assert runtime.load().selected_broker == BrokerName.ALPACA
        assert ledger.verify()["active_action_count"] == 0
        assert all(broker.write_calls == [] for broker in brokers.values())
        assert all(
            broker.read_calls == ["account", "open_orders", "positions"]
            for broker in brokers.values()
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_process_blocks_on_exposure_without_cleanup_or_runtime_write(tmp_path) -> None:
    brokers = {
        BrokerName.WEBULL: FakeHTTPBroker(BrokerName.WEBULL, positions=True),
        BrokerName.ALPACA: FakeHTTPBroker(BrokerName.ALPACA),
    }
    server, ledger, runtime = _server(tmp_path, brokers)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    port = int(server.server_address[1])
    try:
        _, requested = _post(
            port,
            "/api/v1/actions/request",
            _request_payload("switch-http-exposure", "alpaca"),
        )
        _post(
            port,
            "/api/v1/actions/switch-http-exposure/confirm",
            _confirm_payload(
                "switch-http-exposure",
                requested["record"]["request_fingerprint"],
            ),
        )
        _, processed = _post(
            port,
            "/api/v1/actions/switch-http-exposure/process",
            {"process": True},
        )
        assert processed["record"]["state"] == "BLOCKED"
        assert processed["record"]["error_code"] == "BROKER_SWITCH_NOT_AUTHORIZED"
        assert processed["provider_write_attempted"] is False
        assert runtime.load().source == "synthetic_default"
        assert not runtime.state_path.exists()
        assert ledger.verify()["active_action_count"] == 0
        assert all(broker.write_calls == [] for broker in brokers.values())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_process_requires_confirmation_and_does_not_read_brokers_early(tmp_path) -> None:
    brokers = {
        BrokerName.WEBULL: FakeHTTPBroker(BrokerName.WEBULL),
        BrokerName.ALPACA: FakeHTTPBroker(BrokerName.ALPACA),
    }
    server, _, runtime = _server(tmp_path, brokers)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    port = int(server.server_address[1])
    try:
        _post(
            port,
            "/api/v1/actions/request",
            _request_payload("switch-http-unconfirmed", "webull"),
        )
        try:
            _post(
                port,
                "/api/v1/actions/switch-http-unconfirmed/process",
                {"process": True},
            )
            raise AssertionError("unconfirmed action must not process")
        except urllib.error.HTTPError as exc:
            assert exc.code == 409
            payload = json.loads(exc.read().decode("utf-8"))
            assert payload["error"] == "ACTION_CONFLICT"
        assert all(broker.read_calls == [] for broker in brokers.values())
        assert all(broker.write_calls == [] for broker in brokers.values())
        assert runtime.load().source == "synthetic_default"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
