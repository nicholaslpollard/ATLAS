from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from packages.core.settings import load_settings
from packages.providers.massive.reference_data import MassiveReferenceProvider
from packages.providers.massive.rest import MassiveRESTClient

ROOT = Path(__file__).resolve().parents[2]


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_rest_uses_bearer_header_and_strips_api_key_from_next_url(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "super-secret")
    settings = load_settings(ROOT, "development")
    calls = []
    payloads = [
        {
            "status": "OK",
            "results": [{"ticker": "A", "active": True}],
            "next_url": "https://api.massive.com/v3/reference/tickers?cursor=abc&apiKey=should-not-survive",
        },
        {"status": "OK", "results": [{"ticker": "B", "active": True}]},
    ]

    def opener(request, timeout):
        calls.append((request, timeout))
        return FakeResponse(payloads[len(calls) - 1])

    client = MassiveRESTClient(settings, opener=opener, sleeper=lambda _: None)
    rows = list(client.list_tickers(as_of_date="2026-08-14", active=True))
    assert [row["ticker"] for row in rows] == ["A", "B"]
    assert "super-secret" not in calls[0][0].full_url
    assert "should-not-survive" not in calls[1][0].full_url
    assert calls[0][0].get_header("Authorization") == "Bearer super-secret"


class FakeTickerClient:
    def list_tickers(self, *, as_of_date, active, market):
        assert as_of_date == "2026-08-14"
        assert market == "stocks"
        if active:
            yield {"ticker": "aapl", "active": True, "composite_figi": "bbg000b9xry4"}
        else:
            yield {"ticker": "old", "active": False, "composite_figi": "bbg000old123"}

    def ticker_events(self, identifier):
        return []


def test_reference_provider_combines_active_and_inactive_without_case_folding_tickers():
    settings = load_settings(ROOT, "development")
    provider = MassiveReferenceProvider(settings, client=FakeTickerClient())
    rows = provider.stock_snapshot(date(2026, 8, 14), include_inactive=True)
    assert [row["ticker"] for row in rows] == ["aapl", "old"]
    # Stable code-like identifiers are normalized; ticker text is not.
    assert rows[0]["composite_figi"] == "BBG000B9XRY4"
