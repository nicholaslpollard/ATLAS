from __future__ import annotations

import http.cookiejar
import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

import pytest

from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.http_server import create_status_server
from packages.control_plane.session import CONTROL_PLANE_CSRF_HEADER, ControlPlaneSessionGuard
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings
from packages.execution.phase15_closeout import PHASE15_CLOSEOUT_CONTRACT_VERSION
from packages.execution.phase15_foundation import PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT
from packages.execution.phase15_policy import phase15_policy_fingerprint
from packages.schemas.control_plane import (
    ControlPlaneActionKind,
    ControlPlaneActionRequest,
    ControlPlaneActionState,
    ControlPlaneConfirmationGrant,
    ControlPlaneConfirmationScope,
)
from packages.schemas.execution import BrokerName, ExecutionEnvironment


NOW = datetime(2026, 8, 22, 21, 30, tzinfo=UTC)


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
    (root / "phase15_final_acceptance.json").write_text(json.dumps(payload), encoding="utf-8")


def _open_server(tmp_path):
    _write_phase15_acceptance(tmp_path)
    settings = _settings_with_derived(tmp_path)
    service = Phase16StatusService(settings, env={})
    ledger = ControlPlaneActionLedger(settings)
    guard = ControlPlaneSessionGuard(token="z" * 43)
    server = create_status_server(
        service=service,
        host="127.0.0.1",
        port=0,
        session_guard=guard,
        action_ledger=ledger,
    )
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    return server, thread, ledger, guard


def _session_opener(base_url: str):
    jar = http.cookiejar.CookieJar()
    # The control plane is loopback-only. Do not let ambient OS/user proxy
    # settings intercept deterministic 127.0.0.1 HTTP tests.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(jar),
    )
    with opener.open(f"{base_url}/api/v1/session", timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return opener, payload["csrf_token"]


def _post_json(opener, url: str, payload: dict, *, token: str, origin: str):
    raw = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Origin": origin,
            CONTROL_PLANE_CSRF_HEADER: token,
        },
    )
    return opener.open(request, timeout=5)


def test_http_request_and_confirmation_are_audited_but_provider_inert(tmp_path) -> None:
    server, thread, ledger, guard = _open_server(tmp_path)
    port = int(server.server_address[1])
    base = f"http://127.0.0.1:{port}"
    try:
        opener, token = _session_opener(base)
        request_model = ControlPlaneActionRequest(
            action_id="switch-http-1",
            action_kind=ControlPlaneActionKind.BROKER_SWITCH,
            requested_at_utc=NOW,
            idempotency_key="switch-http-idem-1",
            target_broker=BrokerName.ALPACA,
            environment=ExecutionEnvironment.PAPER,
            reason="manual broker selection",
        )
        with _post_json(
            opener,
            f"{base}/api/v1/actions/request",
            request_model.model_dump(mode="json"),
            token=token,
            origin=base,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["record"]["state"] == ControlPlaneActionState.AWAITING_CONFIRMATION.value
        assert payload["provider_write_attempted"] is False
        assert payload["provider_write_endpoint_invoked"] is False
        assert ledger.verify()["event_count"] == 1

        grant = ControlPlaneConfirmationGrant(
            grant_id="grant-http-1",
            action_id=request_model.action_id,
            action_fingerprint=request_model.authority_fingerprint(),
            scope=ControlPlaneConfirmationScope.BROKER_SWITCH,
            confirmed_at_utc=NOW + timedelta(seconds=5),
        )
        with _post_json(
            opener,
            f"{base}/api/v1/actions/{request_model.action_id}/confirm",
            grant.model_dump(mode="json"),
            token=token,
            origin=base,
        ) as response:
            confirmed = json.loads(response.read().decode("utf-8"))
        assert confirmed["record"]["state"] == ControlPlaneActionState.AUTHORIZED.value
        assert confirmed["provider_write_attempted"] is False
        assert ledger.verify()["event_count"] == 2

        with opener.open(f"{base}/api/v1/actions/{request_model.action_id}", timeout=5) as response:
            readback = json.loads(response.read().decode("utf-8"))
        assert readback["state"] == ControlPlaneActionState.AUTHORIZED.value
        assert readback["provider_write_attempted"] is False
        assert readback["provider_write_uncertain"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_prewrite_abandon_is_audited_and_releases_active_workflow(tmp_path) -> None:
    server, thread, ledger, guard = _open_server(tmp_path)
    port = int(server.server_address[1])
    base = f"http://127.0.0.1:{port}"
    try:
        opener, token = _session_opener(base)
        request_model = ControlPlaneActionRequest(
            action_id="switch-http-abandon-1",
            action_kind=ControlPlaneActionKind.BROKER_SWITCH,
            requested_at_utc=NOW,
            idempotency_key="switch-http-abandon-idem-1",
            target_broker=BrokerName.ALPACA,
            environment=ExecutionEnvironment.PAPER,
            reason="abandon browser review before provider activity",
        )
        with _post_json(
            opener,
            f"{base}/api/v1/actions/request",
            request_model.model_dump(mode="json"),
            token=token,
            origin=base,
        ) as response:
            requested = json.loads(response.read().decode("utf-8"))
        assert requested["record"]["state"] == ControlPlaneActionState.AWAITING_CONFIRMATION.value

        with _post_json(
            opener,
            f"{base}/api/v1/actions/{request_model.action_id}/abandon",
            {"abandon": True},
            token=token,
            origin=base,
        ) as response:
            abandoned = json.loads(response.read().decode("utf-8"))
        assert abandoned["record"]["state"] == ControlPlaneActionState.BLOCKED.value
        assert abandoned["record"]["error_code"] == "ACTION_ABANDONED_BY_USER"
        assert abandoned["abandoned"] is True
        assert abandoned["provider_write_attempted"] is False
        assert abandoned["provider_write_endpoint_invoked"] is False
        assert abandoned["provider_write_endpoints_present"] is False
        assert ledger.verify()["active_action_count"] == 0

        with _post_json(
            opener,
            f"{base}/api/v1/actions/{request_model.action_id}/abandon",
            {"abandon": True},
            token=token,
            origin=base,
        ) as response:
            duplicate = json.loads(response.read().decode("utf-8"))
        assert duplicate["record"] == abandoned["record"]

        next_request = ControlPlaneActionRequest(
            action_id="switch-http-after-abandon",
            action_kind=ControlPlaneActionKind.BROKER_SWITCH,
            requested_at_utc=NOW + timedelta(seconds=10),
            idempotency_key="switch-http-after-abandon-idem",
            target_broker=BrokerName.WEBULL,
            environment=ExecutionEnvironment.PAPER,
        )
        with _post_json(
            opener,
            f"{base}/api/v1/actions/request",
            next_request.model_dump(mode="json"),
            token=token,
            origin=base,
        ) as response:
            next_payload = json.loads(response.read().decode("utf-8"))
        assert next_payload["record"]["state"] == ControlPlaneActionState.AWAITING_CONFIRMATION.value
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_abandon_refuses_executing_action(tmp_path) -> None:
    server, thread, ledger, guard = _open_server(tmp_path)
    port = int(server.server_address[1])
    base = f"http://127.0.0.1:{port}"
    try:
        opener, token = _session_opener(base)
        request_model = ControlPlaneActionRequest(
            action_id="switch-http-executing",
            action_kind=ControlPlaneActionKind.BROKER_SWITCH,
            requested_at_utc=NOW,
            idempotency_key="switch-http-executing-idem",
            target_broker=BrokerName.ALPACA,
            environment=ExecutionEnvironment.PAPER,
        )
        ledger.create_request(request_model)
        ledger.confirm(
            request_model.action_id,
            ControlPlaneConfirmationGrant(
                grant_id="grant-http-executing",
                action_id=request_model.action_id,
                action_fingerprint=request_model.authority_fingerprint(),
                scope=ControlPlaneConfirmationScope.BROKER_SWITCH,
                confirmed_at_utc=NOW + timedelta(seconds=1),
            ),
        )
        ledger.transition(request_model.action_id, ControlPlaneActionState.EXECUTING)

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _post_json(
                opener,
                f"{base}/api/v1/actions/{request_model.action_id}/abandon",
                {"abandon": True},
                token=token,
                origin=base,
            )
        assert exc_info.value.code == 409
        payload = json.loads(exc_info.value.read().decode("utf-8"))
        assert payload["error"] == "ACTION_CONFLICT"
        assert ledger.get(request_model.action_id).state == ControlPlaneActionState.EXECUTING
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_csrf_failure_creates_no_action_event(tmp_path) -> None:
    server, thread, ledger, guard = _open_server(tmp_path)
    port = int(server.server_address[1])
    base = f"http://127.0.0.1:{port}"
    try:
        opener, token = _session_opener(base)
        request_model = ControlPlaneActionRequest(
            action_id="switch-http-2",
            action_kind=ControlPlaneActionKind.BROKER_SWITCH,
            requested_at_utc=NOW,
            idempotency_key="switch-http-idem-2",
            target_broker=BrokerName.WEBULL,
            environment=ExecutionEnvironment.PAPER,
        )
        raw = json.dumps(request_model.model_dump(mode="json")).encode("utf-8")
        missing_header = urllib.request.Request(
            f"{base}/api/v1/actions/request",
            data=raw,
            method="POST",
            headers={"Content-Type": "application/json", "Origin": base},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            opener.open(missing_header, timeout=5)
        assert exc_info.value.code == 403
        assert ledger.verify()["event_count"] == 0

        foreign_origin = urllib.request.Request(
            f"{base}/api/v1/actions/request",
            data=raw,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": "https://evil.example",
                CONTROL_PLANE_CSRF_HEADER: token,
            },
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            opener.open(foreign_origin, timeout=5)
        assert exc_info.value.code == 403
        assert ledger.verify()["event_count"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
