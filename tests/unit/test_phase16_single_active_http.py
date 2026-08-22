from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime

from packages.control_plane.action_ledger import ControlPlaneActionLedger
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


NOW = datetime(2026, 8, 22, 23, 15, tzinfo=UTC)
TOKEN = "phase16-single-active-token-0123456789abcdef"


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


def _payload(action_id: str, target: str) -> dict[str, object]:
    return {
        "action_id": action_id,
        "action_kind": "BROKER_SWITCH",
        "requested_at_utc": NOW.isoformat(),
        "explicit_user_request": True,
        "idempotency_key": f"idem-{action_id}",
        "target_broker": target,
        "environment": "paper",
        "reason": "single active workflow test",
    }


def _post(port: int, payload: dict[str, object]):
    origin = f"http://127.0.0.1:{port}"
    request = urllib.request.Request(
        origin + "/api/v1/actions/request",
        data=json.dumps(payload).encode("utf-8"),
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


def test_http_exact_retry_is_idempotent_but_second_active_action_is_rejected(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW)
    service = Phase16StatusService(
        settings,
        env={},
        clock=lambda: NOW,
        action_ledger=ledger,
    )
    server = create_status_server(
        service=service,
        host="127.0.0.1",
        port=0,
        session_guard=ControlPlaneSessionGuard(token=TOKEN),
        action_ledger=ledger,
    )
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    port = int(server.server_address[1])
    first = _payload("switch-active-1", "webull")
    try:
        status, created = _post(port, first)
        assert status == 200
        assert created["record"]["state"] == "AWAITING_CONFIRMATION"
        assert ledger.verify()["action_count"] == 1
        assert ledger.verify()["active_action_count"] == 1

        retry_status, retry = _post(port, first)
        assert retry_status == 200
        assert retry["record"] == created["record"]
        assert ledger.verify()["action_count"] == 1
        assert ledger.verify()["event_count"] == 1

        try:
            _post(port, _payload("switch-active-2", "alpaca"))
            raise AssertionError("a distinct second action must be rejected while the first is active")
        except urllib.error.HTTPError as exc:
            assert exc.code == 409
            body = json.loads(exc.read().decode("utf-8"))
            assert body["error"] == "ACTION_CONFLICT"
            assert "nonterminal" in body["detail"]

        verification = ledger.verify()
        assert verification["action_count"] == 1
        assert verification["active_action_count"] == 1
        assert verification["uncertain_action_count"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
