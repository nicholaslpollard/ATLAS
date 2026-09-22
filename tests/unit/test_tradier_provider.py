from __future__ import annotations

from pathlib import Path

import pytest

from packages.core.settings import load_settings
from packages.providers.tradier.client import (
    TradierApiResponse,
    TradierMarketDataClient,
)


ROOT = Path(__file__).resolve().parents[2]


def _settings():
    return load_settings(ROOT, "development")


def test_tradier_client_requires_local_token(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    monkeypatch.delenv(settings.tradier.credentials.api_key_env, raising=False)

    with pytest.raises(RuntimeError, match="TRADIER_API_KEY"):
        TradierMarketDataClient(settings)


def test_tradier_headers_do_not_expose_token_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    monkeypatch.setenv(settings.tradier.credentials.api_key_env, "secret-token")

    client = TradierMarketDataClient(settings)
    headers = client._headers()

    assert headers["Authorization"] == "Bearer secret-token"
    assert "secret-token" not in repr(client)
    assert "secret-token" not in settings.tradier.provider.production_base_url


def test_post_quotes_normalizes_single_quote_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    monkeypatch.setenv(settings.tradier.credentials.api_key_env, "token")
    client = TradierMarketDataClient(settings)

    response = TradierApiResponse(
        request_name="post_quotes",
        url="https://api.tradier.com/v1/markets/quotes",
        http_status=200,
        payload={"quotes": {"quote": {"symbol": "SPY", "last": 500.0}}},
        response_headers={"X-Ratelimit-Allowed": "120"},
        response_bytes=42,
        elapsed_seconds=0.1,
    )

    monkeypatch.setattr(client, "_request_json", lambda **_kwargs: response)
    batch = client.post_quotes(["SPY"])

    assert batch.requested_symbols == ("SPY",)
    assert batch.returned_symbols == ("SPY",)
    assert batch.returned_rows[0]["last"] == 500.0


def test_post_quotes_normalizes_multi_quote_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    monkeypatch.setenv(settings.tradier.credentials.api_key_env, "token")
    client = TradierMarketDataClient(settings)

    response = TradierApiResponse(
        request_name="post_quotes",
        url="https://api.tradier.com/v1/markets/quotes",
        http_status=200,
        payload={
            "quotes": {
                "quote": [
                    {"symbol": "SPY", "last": 500.0},
                    {"symbol": "QQQ", "last": 450.0},
                ]
            }
        },
        response_headers={},
        response_bytes=84,
        elapsed_seconds=0.2,
    )

    monkeypatch.setattr(client, "_request_json", lambda **_kwargs: response)
    batch = client.post_quotes(["SPY", "QQQ"])

    assert batch.returned_symbols == ("QQQ", "SPY")
    assert len(batch.returned_rows) == 2


def test_post_quotes_rejects_empty_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    monkeypatch.setenv(settings.tradier.credentials.api_key_env, "token")
    client = TradierMarketDataClient(settings)

    with pytest.raises(ValueError, match="at least one symbol"):
        client.post_quotes([])
