from __future__ import annotations

import io
import json

import pytest

from packages.providers.marketdata_app import client


class FakeResponse:
    def __init__(self, raw: bytes):
        self.status = 203
        self.headers = {
            "X-Api-Ratelimit-Consumed": "1",
            "X-Api-Ratelimit-Remaining": "9999",
        }
        self._stream = io.BytesIO(raw)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size: int = -1):
        return self._stream.read(size)


def test_exact_raw_http_body_is_preserved(monkeypatch):
    raw = b'{"s":"ok", "optionSymbol":["SPY261016C00100000"]}'
    monkeypatch.setattr(
        client.urllib.request, "urlopen",
        lambda *_args, **_kwargs: FakeResponse(raw),
    )
    response = client.get_json(
        "options/chain/SPY/", params={"date": "2026-09-14"},
        token="test-token", max_response_bytes=1024,
    )
    assert response.http_status == 203
    assert response.raw_body == raw
    assert response.response_bytes == len(raw)
    assert response.payload == json.loads(raw)


def test_maximum_http_response_size_fails_before_json_processing(monkeypatch):
    raw = b'{"s":"ok","rows":[' + b"0," * 100 + b"0]}"
    monkeypatch.setattr(
        client.urllib.request, "urlopen",
        lambda *_args, **_kwargs: FakeResponse(raw),
    )
    with pytest.raises(client.MarketDataError, match="bounded byte limit"):
        client.get_json(
            "options/chain/SPY/", params={"date": "2026-09-14"},
            token="test-token", max_response_bytes=32,
        )
