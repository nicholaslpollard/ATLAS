from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

from packages.core.settings import load_settings
from packages.instruments.registry import InstrumentRegistryStore
from packages.universe.metadata import UniverseReferenceInventory

ROOT = Path(__file__).resolve().parents[2]


class InventoryReferenceProvider:
    def stock_snapshot(self, as_of_date, *, include_inactive=True):
        return [
            {
                "ticker": "AAPL",
                "name": "Apple Example",
                "market": "stocks",
                "locale": "us",
                "currency_name": "usd",
                "primary_exchange": "XNAS",
                "type": "CS",
                "active": True,
                "composite_figi": "BBG000APPLE",
            },
            {
                "ticker": "ETF1",
                "name": "Example ETF",
                "market": "stocks",
                "locale": "us",
                "currency_name": "usd",
                "primary_exchange": "ARCX",
                "type": "ETF",
                "active": True,
                "composite_figi": "BBG000ETF001",
            },
            {
                "ticker": "TPC",
                "name": "Duplicate Identity A",
                "market": "stocks",
                "locale": "us",
                "currency_name": "usd",
                "primary_exchange": "XNYS",
                "type": "CS",
                "active": True,
                "composite_figi": "BBG000DUP001",
            },
            {
                "ticker": "TpC",
                "name": "Duplicate Identity B",
                "market": "stocks",
                "locale": "us",
                "currency_name": "usd",
                "primary_exchange": "XNAS",
                "type": "PFD",
                "active": True,
                "composite_figi": "BBG000DUP001",
            },
            {
                "ticker": "OLD",
                "name": "Inactive Example",
                "market": "stocks",
                "locale": "us",
                "currency_name": "usd",
                "primary_exchange": None,
                "type": "CS",
                "active": False,
                "composite_figi": "BBG000OLD001",
            },
        ]


def test_reference_inventory_surfaces_real_value_distributions_and_identity_collisions(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    as_of = date(2026, 8, 14)
    InstrumentRegistryStore(settings, provider=InventoryReferenceProvider()).sync_snapshot(as_of)

    report = UniverseReferenceInventory(settings).inspect(
        as_of,
        duplicate_example_limit=5,
        samples_per_security_type=1,
    )

    assert report["row_count"] == 5
    assert report["instrument_count"] == 4
    assert report["repeated_identity_rows"] == 1
    assert report["inactive_rows"] == 1
    assert report["missing"]["primary_exchange"] == 1

    duplicate = report["duplicate_identity"]
    assert duplicate["groups"] == 1
    assert duplicate["rows"] == 2
    assert duplicate["multi_ticker_groups"] == 1
    assert duplicate["conflicting_exchange_groups"] == 1
    assert duplicate["conflicting_security_type_groups"] == 1
    assert duplicate["examples"][0]["tickers"] == ["TPC", "TpC"]

    security_counts = {
        row["value"]: row["row_count"]
        for row in report["distributions"]["security_type"]
    }
    assert security_counts == {"CS": 3, "ETF": 1, "PFD": 1}

    assert len(report["source_sha256"]) == 64
    assert Path(report["report_path"]).exists()


def test_reference_inventory_is_bound_to_exact_source_bytes(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    as_of = date(2026, 8, 14)
    InstrumentRegistryStore(settings, provider=InventoryReferenceProvider()).sync_snapshot(as_of)
    inventory = UniverseReferenceInventory(settings)

    first = inventory.inspect(as_of, persist=False)
    second = inventory.inspect(as_of, persist=False)

    assert first["source_sha256"] == second["source_sha256"]
    assert first["row_count"] == second["row_count"]
    assert first["duplicate_identity"] == second["duplicate_identity"]
