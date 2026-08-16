from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from packages.core.settings import load_settings
from packages.instruments.continuity import IdentityContinuityReconciler
from packages.instruments.registry import InstrumentRegistryStore
from packages.instruments.ticker_events import TickerEventStore

ROOT = Path(__file__).resolve().parents[2]


class RenameProvider:
    def __init__(self, events=None) -> None:
        self.events = events or [
            {"date": "2012-05-18", "type": "ticker_change", "ticker_change": {"ticker": "FB"}},
            {"date": "2022-06-09", "type": "ticker_change", "ticker_change": {"ticker": "META"}},
        ]

    def stock_snapshot(self, as_of_date, *, include_inactive=True):
        ticker = "FB" if as_of_date < date(2022, 6, 9) else "META"
        return [
            {
                "ticker": ticker,
                "name": "Meta Platforms, Inc.",
                "market": "stocks",
                "locale": "us",
                "currency_name": "usd",
                "primary_exchange": "XNAS",
                "type": "CS",
                "active": True,
                "composite_figi": "BBG000MM2P62",
                "share_class_figi": "BBG001SQCQC5",
                "cik": "0001326801",
            }
        ]

    def ticker_events(self, identifier: str):
        assert identifier == "BBG000MM2P62"
        return list(self.events)


class ReuseProvider:
    def stock_snapshot(self, as_of_date, *, include_inactive=True):
        figi = "BBG000OLD001" if as_of_date.year == 2021 else "BBG000NEW001"
        cik = "0000000001" if as_of_date.year == 2021 else "0000000002"
        return [
            {
                "ticker": "ABC",
                "name": "Old ABC" if as_of_date.year == 2021 else "New ABC",
                "market": "stocks",
                "locale": "us",
                "currency_name": "usd",
                "primary_exchange": "XNYS",
                "type": "CS",
                "active": True,
                "composite_figi": figi,
                "share_class_figi": None,
                "cik": cik,
            }
        ]


def test_meta_snapshot_aliases_are_confirmed_by_authoritative_events(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    provider = RenameProvider()
    registry = InstrumentRegistryStore(settings, provider=provider)
    old_date = date(2021, 8, 16)
    current_date = date(2026, 8, 14)
    registry.sync_snapshot(old_date)
    registry.sync_snapshot(current_date)

    TickerEventStore(settings, provider=provider).sync_for_ticker("META", current_date)
    report = IdentityContinuityReconciler(settings).reconcile_ticker("META", current_date)

    assert report.status == "confirmed_ticker_change"
    assert report.continuity_confirmed is True
    assert report.blocking_anomaly is False
    assert [item.ticker for item in report.observed_tickers] == ["FB", "META"]
    assert [(item.event_date, item.ticker) for item in report.authoritative_events] == [
        (date(2012, 5, 18), "FB"),
        (date(2022, 6, 9), "META"),
    ]
    assert [(item.ticker, item.valid_from_date, item.valid_to_date_exclusive) for item in report.authoritative_intervals] == [
        ("FB", date(2012, 5, 18), date(2022, 6, 9)),
        ("META", date(2022, 6, 9), None),
    ]
    assert report.unresolved_observed_tickers == []


def test_multiple_snapshot_aliases_without_events_require_authoritative_evidence(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    provider = RenameProvider()
    registry = InstrumentRegistryStore(settings, provider=provider)
    registry.sync_snapshot(date(2021, 8, 16))
    current_date = date(2026, 8, 14)
    registry.sync_snapshot(current_date)

    report = IdentityContinuityReconciler(settings).reconcile_ticker("META", current_date)
    assert report.status == "needs_authoritative_evidence"
    assert report.continuity_confirmed is False
    assert report.blocking_anomaly is False
    assert report.authoritative_events == []


def test_conflicting_authoritative_event_date_is_blocking_and_has_no_intervals(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    provider = RenameProvider(
        events=[
            {"date": "2022-06-09", "type": "ticker_change", "ticker_change": {"ticker": "META"}},
            {"date": "2022-06-09", "type": "ticker_change", "ticker_change": {"ticker": "META2"}},
        ]
    )
    current_date = date(2026, 8, 14)
    InstrumentRegistryStore(settings, provider=provider).sync_snapshot(current_date)
    event_store = TickerEventStore(settings, provider=provider)
    event_store.sync_for_ticker("META", current_date)

    report = IdentityContinuityReconciler(settings).reconcile_ticker("META", current_date)
    assert report.status == "blocking_identity_anomaly"
    assert report.blocking_anomaly is True
    assert report.authoritative_intervals == []

    import duckdb

    con = duckdb.connect()
    try:
        interval_file = event_store.paths.authoritative_ticker_intervals_file().as_posix()
        rows = con.execute(f"SELECT * FROM read_parquet('{interval_file}')").fetchall()
    finally:
        con.close()
    assert rows == []


def test_nonoverlapping_exact_ticker_reuse_is_recorded_without_merge(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    provider = ReuseProvider()
    registry = InstrumentRegistryStore(settings, provider=provider)
    registry.sync_snapshot(date(2021, 8, 16))
    current_date = date(2026, 8, 14)
    registry.sync_snapshot(current_date)

    report = IdentityContinuityReconciler(settings).reconcile_ticker("ABC", current_date)
    assert report.blocking_anomaly is False
    assert report.status == "single_observed_ticker"
    assert len(report.ticker_reuse_observations) == 1
    reuse = report.ticker_reuse_observations[0]
    assert reuse.ticker == "ABC"
    assert reuse.other_instrument_id != report.instrument_id
    assert reuse.observation_ranges_overlap is False
