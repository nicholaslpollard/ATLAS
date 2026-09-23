from __future__ import annotations

import io
import json
import urllib.error

import pytest

from packages.providers.czar28 import client


class _FakeResponse:
    def __init__(self, payload: dict[str, object], *, status: int = 200) -> None:
        self.status = status
        self.headers = {
            "X-RateLimit-Limit": "1000",
            "X-RateLimit-Remaining": "999",
        }
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def _http_error(code: int, payload: dict[str, object]) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://czar28.com/v1/options/chain",
        code=code,
        msg="test",
        hdrs={},
        fp=io.BytesIO(json.dumps(payload).encode("utf-8")),
    )


def test_czar28_base_url_matches_authoritative_openapi() -> None:
    assert client.CZAR28_BASE_URL == "https://czar28.com/v1"


def test_health_request_can_be_unauthenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[object] = []

    def fake_urlopen(request, timeout):
        captured.append(request)
        return _FakeResponse(
            {
                "status": "ok",
                "upstream": {
                    "mdds_status": "CONNECTED",
                    "upstream_ms": 12,
                },
            }
        )

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    response = client.get_json(
        "options/health",
        authenticate=False,
        max_attempts=1,
    )

    assert response.http_status == 200
    assert len(captured) == 1
    assert captured[0].full_url == "https://czar28.com/v1/options/health"
    assert captured[0].get_header("Authorization") is None


def test_czar28_default_retry_policy_matches_documented_guidance() -> None:
    assert client.CZAR28_DEFAULT_MAX_ATTEMPTS == 5
    assert client.CZAR28_DEFAULT_INITIAL_RETRY_SECONDS == 0.25
    assert client.CZAR28_DEFAULT_MAX_RETRY_SECONDS == 2.0


def test_get_json_retries_transient_502_with_same_logical_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    sleeps: list[float] = []
    outcomes: list[object] = [
        _http_error(502, {"error": "upstream_error"}),
        _http_error(502, {"error": "upstream_error"}),
        _FakeResponse(
            {
                "header": {"format": ["root", "expiration", "strike", "right"]},
                "response": [["SPY", 20160617, 200000, "C"]],
            }
        ),
    ]

    def fake_urlopen(request, timeout):
        calls.append(request)
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    response = client.get_json(
        "options/chain",
        params={"root": "SPY", "exp": "20160617"},
        idempotency_key="stable-probe-id",
        api_key="test-key",
        max_attempts=6,
        initial_retry_seconds=2.0,
        max_retry_seconds=20.0,
        sleep=sleeps.append,
    )

    assert response.http_status == 200
    assert response.transport_attempts == 3
    assert len(calls) == 3
    assert sleeps == [2.0, 4.0]
    assert all(
        request.get_header("Idempotency-key") == "stable-probe-id"
        for request in calls
    )


def test_get_json_stops_after_bounded_transient_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        raise _http_error(503, {"error": "upstream_error"})

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(client.Czar28Error, match="after 3 transport attempts") as captured:
        client.get_json(
            "options/chain",
            params={"root": "SPY", "exp": "20160617"},
            idempotency_key="stable-probe-id",
            api_key="test-key",
            max_attempts=3,
            initial_retry_seconds=1.0,
            max_retry_seconds=4.0,
            sleep=sleeps.append,
        )

    assert captured.value.transport_attempts == 3
    assert captured.value.http_status == 503
    assert captured.value.error_code == "upstream_error"
    assert calls == 3
    assert sleeps == [1.0, 2.0]


def test_get_json_does_not_retry_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        raise _http_error(429, {"error": "quota_exceeded"})

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(client.Czar28QuotaExhausted):
        client.get_json(
            "options/chain",
            params={"root": "SPY", "exp": "20160617"},
            idempotency_key="stable-probe-id",
            api_key="test-key",
            sleep=lambda _seconds: None,
        )

    assert calls == 1


def test_health_is_ready_requires_ok_and_connected() -> None:
    assert client.health_is_ready(
        {
            "status": "ok",
            "upstream": {"mdds_status": "CONNECTED"},
        }
    )
    assert not client.health_is_ready(
        {
            "status": "degraded",
            "upstream": {"mdds_status": "UNDETERMINED"},
        }
    )
    assert not client.health_is_ready(
        {
            "status": "ok",
            "upstream": {"mdds_status": "DISCONNECTED"},
        }
    )
