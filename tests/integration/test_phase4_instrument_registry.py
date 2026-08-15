from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

from packages.core.settings import load_settings
from packages.data.duckdb_connection import connect_utc
from packages.instruments.registry import InstrumentRegistryStore

ROOT = Path(__file__).resolve().parents[2]


class FakeReferenceProvider:
    def stock_snapshot(self, as_of_date, *, include_inactive=True):
        ticker = "OLD" if as_of_date == date(2026, 1, 2) else "NEW"
        return [
            {
                "ticker": ticker,
                "name": "Example Corp",
                "market": "stocks",
                "locale": "us",
                "currency_name": "usd",
                "primary_exchange": "XNAS",
                "type": "CS",
                "active": True,
                "composite_figi": "BBG000EXAMPLE",
                "share_class_figi": "BBG001EXAMPLE",
                "cik": "0001234567",
            }
        ]


def test_reference_snapshots_build_stable_registry_and_ticker_observations(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    store = InstrumentRegistryStore(settings, provider=FakeReferenceProvider())
    first = store.sync_snapshot(date(2026, 1, 2))
    second = store.sync_snapshot(date(2026, 8, 14))
    assert first.instrument_count == 1
    assert second.instrument_count == 1

    con = connect_utc(":memory:")
    try:
        registry = store.paths.instrument_registry_file().as_posix()
        aliases = store.paths.ticker_observations_file().as_posix()
        reg = con.execute(f"SELECT instrument_id, latest_ticker, first_observed_date, last_observed_date FROM read_parquet('{registry}')").fetchall()
        obs = con.execute(f"SELECT ticker FROM read_parquet('{aliases}') ORDER BY ticker").fetchall()
    finally:
        con.close()
    assert len(reg) == 1
    assert reg[0][1] == "NEW"
    assert obs == [("NEW",), ("OLD",)]


def test_reference_snapshot_is_idempotent(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    store = InstrumentRegistryStore(settings, provider=FakeReferenceProvider())
    d = date(2026, 8, 14)
    assert store.sync_snapshot(d).skipped is False
    assert store.sync_snapshot(d).skipped is True
