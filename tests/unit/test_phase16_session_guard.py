from __future__ import annotations

import http.cookiejar
import json
import threading
import urllib.request

from packages.control_plane.http_server import create_status_server
from packages.control_plane.session import (
    CONTROL_PLANE_CSRF_HEADER,
    CONTROL_PLANE_SESSION_COOKIE,
    ControlPlaneSessionGuard,
)
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def test_session_guard_requires_json_same_origin_header_and_cookie() -> None:
    guard = ControlPlaneSessionGuard(token="x" * 43)
    expected = "http://127.0.0.1:8765"
    valid = {
        "Content-Type": "application/json",
        "Origin": expected,
        CONTROL_PLANE_CSRF_HEADER: guard.csrf_token,
        "Cookie": f"{CONTROL_PLANE_SESSION_COOKIE}={guard.csrf_token}",
    }
    assert guard.authorize_write(valid, expected_origin=expected).allowed is True

    for field, replacement, code in (
        ("Content-Type", "text/plain", "JSON_CONTENT_TYPE_REQUIRED"),
        ("Origin", "https://evil.example", "SAME_ORIGIN_REQUIRED"),
        (CONTROL_PLANE_CSRF_HEADER, "wrong", "CSRF_HEADER_INVALID"),
        ("Cookie", "", "SESSION_COOKIE_INVALID"),
    ):
        changed = dict(valid)
        changed[field] = replacement
        result = guard.authorize_write(changed, expected_origin=expected)
        assert result.allowed is False
        assert result.error_code == code


def test_session_endpoint_issues_httponly_strict_cookie_and_token(tmp_path) -> None:
    service = Phase16StatusService(_settings_with_derived(tmp_path), env={})
    guard = ControlPlaneSessionGuard(token="y" * 43)
    server = create_status_server(
        service=service, host="127.0.0.1", port=0, session_guard=guard
    )
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    port = int(server.server_address[1])
    try:
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        with opener.open(f"http://127.0.0.1:{port}/api/v1/session", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            cookie_header = response.headers["Set-Cookie"]
            assert payload["csrf_token"] == guard.csrf_token
            assert payload["live_execution_promoted"] is False
            assert "HttpOnly" in cookie_header
            assert "SameSite=Strict" in cookie_header
            assert response.headers.get("Access-Control-Allow-Origin") is None
        cookies = list(jar)
        assert len(cookies) == 1
        assert cookies[0].name == CONTROL_PLANE_SESSION_COOKIE
        assert cookies[0].value == guard.csrf_token
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
