from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from packages.core.settings import load_settings
from packages.instruments.registry import InstrumentRegistryStore
from packages.instruments.ticker_events import TickerEventStore

ROOT = Path(__file__).resolve().parents[2]


class FakeContinuityProvider:
    def __init__(self, *, ticker: str = "META", composite_figi: str | None = "BBG000MM2P62") -> None:
        self.ticker = ticker
        self.composite_figi = composite_figi
        self.event_queries: list[str] = []

    def stock_snapshot(self, as_of_date, *, include_inactive=True):
        return [
            {
                "ticker": self.ticker,
                "name": "Example Corp",
                "market": "stocks",
                "locale": "us",
                "currency_name": "usd",
                "primary_exchange": "XNAS",
                "type": "CS",
                "active": True,
                "composite_figi": self.composite_figi,
                "share_class_figi": "BBG001EXAMPLE" if self.composite_figi else None,
                "cik": "0001234567",
            }
        ]

    def ticker_events(self, identifier: str):
        self.event_queries.append(identifier)
        if self.ticker == "META":
            return [
                {"date": "2012-05-18", "type": "ticker_change", "ticker_change": {"ticker": "FB"}},
                {"date": "2022-06-09", "type": "ticker_change", "ticker_change": {"ticker": "META"}},
                # Exact duplicate must not create a second canonical event.
                {"date": "2022-06-09", "type": "ticker_change", "ticker_change": {"ticker": "META"}},
                {"date": "2020-01-01", "type": "unsupported", "ticker_change": {"ticker": "IGNORED"}},
            ]
        return [
            {"date": "2020-01-01", "type": "ticker_change", "ticker_change": {"ticker": self.ticker}}
        ]


def test_composite_figi_event_sync_is_authoritative_and_idempotent(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    provider = FakeContinuityProvider()
    snapshot_date = date(2026, 8, 14)

    InstrumentRegistryStore(settings, provider=provider).sync_snapshot(snapshot_date)
    store = TickerEventStore(settings, provider=provider)

    first = store.sync_for_ticker("META", snapshot_date)
    assert first.skipped is False
    assert first.query_identifier == "BBG000MM2P62"
    assert first.query_identifier_type == "composite_figi"
    assert first.continuity_authority is True
    assert first.event_count == 2
    assert provider.event_queries == ["BBG000MM2P62"]

    timeline = store.timeline_for_ticker("META", snapshot_date)
    assert [(item["event_date"], item["ticker"]) for item in timeline] == [
        (date(2012, 5, 18), "FB"),
        (date(2022, 6, 9), "META"),
    ]
    assert all(item["continuity_authority"] is True for item in timeline)

    second = store.sync_for_ticker("META", snapshot_date)
    assert second.skipped is True
    assert provider.event_queries == ["BBG000MM2P62"]
    assert store.paths.ticker_event_observations_file().is_file()


def test_ticker_only_event_sync_preserves_case_and_is_non_authoritative(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    provider = FakeContinuityProvider(ticker="TpC", composite_figi=None)
    snapshot_date = date(2026, 8, 14)

    InstrumentRegistryStore(settings, provider=provider).sync_snapshot(snapshot_date)
    result = TickerEventStore(settings, provider=provider).sync_for_ticker("TpC", snapshot_date)

    assert result.query_identifier == "TpC"
    assert result.query_identifier_type == "ticker"
    assert result.continuity_authority is False
    assert provider.event_queries == ["TpC"]
