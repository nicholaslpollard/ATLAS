from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.cleanup_plan_ledger import ControlPlaneCleanupPlanLedger
from packages.control_plane.cleanup_planner import Phase16CleanupPlanner
from packages.control_plane.http_server import create_status_server
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


NOW = datetime(2026, 8, 23, 1, 0, tzinfo=UTC)
TOKEN = "phase16-cleanup-http-session-token-0123456789abcdef"


class FakeCleanupHTTPBroker:
    environment = ExecutionEnvironment.PAPER

    def __init__(
        self,
        broker: BrokerName,
        *,
        orders: bool = True,
        positions: bool = False,
    ) -> None:
        self.broker = broker
        self.account_id = f"{broker.value}-cleanup-http-account"
        self.has_orders = orders
        self.has_positions = positions
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
            cash=20000.0,
            buying_power=40000.0,
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
                client_order_id="cleanup-http-order-0001",
                provider_order_id="provider-cleanup-secret",
                ticker="SPY",
                side=BrokerOrderSide.BUY,
                status=BrokerOrderStatus.SUBMITTED,
                requested_quantity=2.0,
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
                quantity=2.0,
                market_value=1000.0,
                average_entry_price=490.0,
                as_of_utc=NOW,
            ),
        )

    def preview(self, plan):
        self.write_calls.append("preview")
        raise AssertionError("cleanup review HTTP must never preview")

    def submit(self, plan):
        self.write_calls.append("submit")
        raise AssertionError("cleanup review HTTP must never submit")

    def order(self, client_order_id):
        self.write_calls.append("order")
        raise AssertionError("cleanup review HTTP must not query individual order")

    def cancel(self, client_order_id):
        self.write_calls.append("cancel")
        raise AssertionError("cleanup review HTTP must never cancel")


def _settings(tmp_path):
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


def _server(tmp_path, fake: FakeCleanupHTTPBroker):
    _write_phase15_acceptance(tmp_path)
    settings = _settings(tmp_path)
    clock = lambda: NOW + timedelta(seconds=10)
    ledger = ControlPlaneActionLedger(settings, clock=clock)
    service = Phase16StatusService(
        settings,
        env=(
            {"WEBULL_APP_KEY": "wk", "WEBULL_APP_SECRET": "ws"}
            if fake.broker == BrokerName.WEBULL
            else {"ALPACA_PAPER_API_KEY": "ak", "ALPACA_PAPER_API_SECRET": "as"}
        ),
        clock=clock,
        action_ledger=ledger,
    )
    planner = Phase16CleanupPlanner(
        settings,
        status_service=service,
        ledger=ledger,
        broker_factory=lambda broker: fake,
        clock=clock,
    )
    plan_ledger = ControlPlaneCleanupPlanLedger(ledger, clock=clock)
    server = create_status_server(
        service=service,
        host="127.0.0.1",
        port=0,
        session_guard=ControlPlaneSessionGuard(token=TOKEN),
        action_ledger=ledger,
        cleanup_planner=planner,
        cleanup_plan_ledger=plan_ledger,
    )
    return server, ledger, plan_ledger


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


def _get(port: int, path: str):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method="GET",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _action_payload(action_id: str, kind: str, broker: BrokerName):
    return {
        "action_id": action_id,
        "action_kind": kind,
        "requested_at_utc": NOW.isoformat(),
        "explicit_user_request": True,
        "idempotency_key": f"idem-{action_id}",
        "target_broker": broker.value,
        "environment": "paper",
        "reason": "browser cleanup review test",
    }


def _action_confirm_payload(action_id: str, fingerprint: str, scope: str):
    return {
        "grant_id": f"action-grant-{action_id}",
        "action_id": action_id,
        "action_fingerprint": fingerprint,
        "scope": scope,
        "confirmed_at_utc": (NOW + timedelta(seconds=1)).isoformat(),
        "one_time": True,
    }


def _plan_confirm_payload(action_id: str, action_fingerprint: str, plan_fingerprint: str):
    return {
        "grant_id": f"plan-grant-{action_id}",
        "action_id": action_id,
        "action_fingerprint": action_fingerprint,
        "cleanup_plan_fingerprint": plan_fingerprint,
        "confirmed_at_utc": (NOW + timedelta(seconds=11)).isoformat(),
        "one_time": True,
    }


def _run_server(server):
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    return thread, int(server.server_address[1])


def test_http_cleanup_plan_review_and_confirmation_never_exposes_processing(tmp_path) -> None:
    fake = FakeCleanupHTTPBroker(BrokerName.WEBULL, orders=True)
    server, ledger, plan_ledger = _server(tmp_path, fake)
    thread, port = _run_server(server)
    action_id = "cleanup-http-cancel-1"
    try:
        _, requested = _post(
            port,
            "/api/v1/actions/request",
            _action_payload(action_id, "CANCEL_OPEN_ORDERS", fake.broker),
        )
        action_fp = requested["record"]["request_fingerprint"]
        assert requested["record"]["state"] == "AWAITING_CONFIRMATION"

        _post(
            port,
            f"/api/v1/actions/{action_id}/confirm",
            _action_confirm_payload(action_id, action_fp, "CANCEL_OPEN_ORDERS"),
        )
        _, planned = _post(
            port,
            f"/api/v1/actions/{action_id}/cleanup-plan",
            {"plan": True},
        )
        assert planned["cleanup_plan"]["cancel_targets"][0]["client_order_id"] == "cleanup-http-order-0001"
        assert planned["provider_write_authorized"] is False
        assert planned["provider_write_endpoint_invoked"] is False
        assert planned["provider_write_endpoints_present"] is False
        plan_fp = planned["cleanup_plan_fingerprint"]
        assert len(plan_fp) == 64
        assert fake.read_calls == ["account", "open_orders", "positions"]
        assert fake.write_calls == []

        _, before = _get(port, f"/api/v1/actions/{action_id}/cleanup-plan")
        assert before["cleanup_plan_fingerprint"] == plan_fp
        assert before["cleanup_plan_confirmed"] is False
        assert before["provider_write_authorized"] is False

        _, confirmed = _post(
            port,
            f"/api/v1/actions/{action_id}/cleanup-plan/confirm",
            _plan_confirm_payload(action_id, action_fp, plan_fp),
        )
        assert confirmed["cleanup_plan_confirmed"] is True
        assert confirmed["provider_write_authorized"] is False
        assert confirmed["provider_write_endpoints_present"] is False
        assert fake.write_calls == []

        _, after = _get(port, f"/api/v1/actions/{action_id}/cleanup-plan")
        assert after["cleanup_plan_confirmed"] is True
        assert after["confirmed_plan_fingerprint"] == plan_fp
        assert plan_ledger.verify()["provider_write_authority_count"] == 0

        try:
            _post(
                port,
                f"/api/v1/actions/{action_id}/process",
                {"process": True},
            )
            raise AssertionError("cleanup provider processing must not be exposed")
        except urllib.error.HTTPError as exc:
            assert exc.code == 409
            payload = json.loads(exc.read().decode("utf-8"))
            assert payload["error"] == "PROCESSOR_NOT_AVAILABLE_FOR_ACTION"
        assert ledger.get(action_id).state.value == "AUTHORIZED"
        assert fake.write_calls == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_cleanup_plan_cannot_build_before_action_confirmation(tmp_path) -> None:
    fake = FakeCleanupHTTPBroker(BrokerName.ALPACA, orders=True)
    server, ledger, _ = _server(tmp_path, fake)
    thread, port = _run_server(server)
    action_id = "cleanup-http-unconfirmed"
    try:
        _post(
            port,
            "/api/v1/actions/request",
            _action_payload(action_id, "CANCEL_OPEN_ORDERS", fake.broker),
        )
        try:
            _post(
                port,
                f"/api/v1/actions/{action_id}/cleanup-plan",
                {"plan": True},
            )
            raise AssertionError("unconfirmed cleanup action must not plan")
        except urllib.error.HTTPError as exc:
            assert exc.code == 409
            payload = json.loads(exc.read().decode("utf-8"))
            assert payload["error"] == "CLEANUP_PLAN_CONFLICT"
        assert fake.read_calls == []
        assert fake.write_calls == []
        assert ledger.get(action_id).state.value == "AWAITING_CONFIRMATION"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_cleanup_plan_confirmation_rejects_wrong_fingerprint(tmp_path) -> None:
    fake = FakeCleanupHTTPBroker(BrokerName.ALPACA, orders=True)
    server, _, plan_ledger = _server(tmp_path, fake)
    thread, port = _run_server(server)
    action_id = "cleanup-http-bad-plan-fp"
    try:
        _, requested = _post(
            port,
            "/api/v1/actions/request",
            _action_payload(action_id, "CANCEL_OPEN_ORDERS", fake.broker),
        )
        action_fp = requested["record"]["request_fingerprint"]
        _post(
            port,
            f"/api/v1/actions/{action_id}/confirm",
            _action_confirm_payload(action_id, action_fp, "CANCEL_OPEN_ORDERS"),
        )
        _post(port, f"/api/v1/actions/{action_id}/cleanup-plan", {"plan": True})
        try:
            _post(
                port,
                f"/api/v1/actions/{action_id}/cleanup-plan/confirm",
                _plan_confirm_payload(action_id, action_fp, "0" * 64),
            )
            raise AssertionError("wrong cleanup plan fingerprint must not confirm")
        except urllib.error.HTTPError as exc:
            assert exc.code == 409
            payload = json.loads(exc.read().decode("utf-8"))
            assert payload["error"] == "CLEANUP_PLAN_CONFLICT"
        assert plan_ledger.state(action_id).confirmation is None
        assert fake.write_calls == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_flatten_plan_refuses_open_orders_without_provider_write(tmp_path) -> None:
    fake = FakeCleanupHTTPBroker(BrokerName.WEBULL, orders=True, positions=True)
    server, _, plan_ledger = _server(tmp_path, fake)
    thread, port = _run_server(server)
    action_id = "cleanup-http-flatten-open-orders"
    try:
        _, requested = _post(
            port,
            "/api/v1/actions/request",
            _action_payload(action_id, "FLATTEN_POSITIONS", fake.broker),
        )
        action_fp = requested["record"]["request_fingerprint"]
        _post(
            port,
            f"/api/v1/actions/{action_id}/confirm",
            _action_confirm_payload(action_id, action_fp, "FLATTEN_POSITIONS"),
        )
        try:
            _post(
                port,
                f"/api/v1/actions/{action_id}/cleanup-plan",
                {"plan": True},
            )
            raise AssertionError("flatten plan must refuse unresolved open orders")
        except urllib.error.HTTPError as exc:
            assert exc.code == 409
            payload = json.loads(exc.read().decode("utf-8"))
            assert payload["error"] == "CLEANUP_PLAN_CONFLICT"
        assert fake.read_calls == ["account", "open_orders", "positions"]
        assert fake.write_calls == []
        assert plan_ledger.state(action_id).latest_plan is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
