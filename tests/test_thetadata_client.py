from __future__ import annotations

import io
import urllib.error

import pytest

from packages.providers.thetadata import client


class _Response:
    def __init__(self, body: bytes = b"[]") -> None:
        self.status = 200
        self.headers = {}
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _http_error(code: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="http://127.0.0.1:25503/test",
        code=code,
        msg="error",
        hdrs={},
        fp=io.BytesIO(body),
    )


def test_thetadata_base_url_rejects_non_loopback(monkeypatch):
    monkeypatch.setenv(client.THETADATA_BASE_URL_ENV, "https://example.com:25503")
    with pytest.raises(client.ThetaDataError, match="local http Theta Terminal"):
        client._base_url()


def test_no_data_472_is_explicit_empty_response(monkeypatch):
    monkeypatch.delenv(client.THETADATA_BASE_URL_ENV, raising=False)

    def urlopen(request, timeout):
        raise _http_error(472, b"NO_DATA")

    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    response = client.get_json("/v3/test", params={}, max_attempts=1)

    assert response.http_status == 472
    assert response.rows == ()
    assert response.raw_body == b"NO_DATA"


def test_os_limit_429_retries(monkeypatch):
    monkeypatch.delenv(client.THETADATA_BASE_URL_ENV, raising=False)
    attempts = {"count": 0}
    sleeps = []

    def urlopen(request, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise _http_error(429, b"OS_LIMIT")
        return _Response()

    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    response = client.get_json(
        "/v3/test",
        params={},
        max_attempts=2,
        initial_retry_seconds=0.01,
        sleep=sleeps.append,
    )

    assert attempts["count"] == 2
    assert sleeps == [0.01]
    assert response.http_status == 200


def test_surface_request_uses_wildcard_contract_and_bound(monkeypatch):
    captured = {}

    def fake_get(path, *, params, **kwargs):
        captured["path"] = path
        captured["params"] = params
        return client.ThetaDataResponse(
            http_status=200,
            rows=(),
            headers={},
            response_bytes=2,
            elapsed_seconds=0.01,
            raw_body=b"[]",
        )

    monkeypatch.setattr(client, "get_json", fake_get)
    client.option_at_time_quote_surface(
        symbol="AAPL",
        date_et="2025-01-06",
        time_of_day_et="09:35:00.000",
        max_dte=75,
    )

    assert captured["path"] == "/v3/option/at_time/quote"
    assert captured["params"]["expiration"] == "*"
    assert captured["params"]["strike"] == "*"
    assert captured["params"]["right"] == "call"
    assert captured["params"]["max_dte"] == 75
    assert captured["params"]["strike_range"] is None
