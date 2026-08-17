from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

from packages.core.settings import load_settings
from packages.instruments.registry import InstrumentRegistryStore
from packages.schemas.universe import UniverseReasonCode, UniverseRoute
from packages.universe.manager import UniverseManager

ROOT = Path(__file__).resolve().parents[2]


class UniverseReferenceProvider:
    def stock_snapshot(self, as_of_date, *, include_inactive=True):
        if as_of_date == date(2021, 8, 16):
            return [
                {
                    "ticker": "OLDX",
                    "name": "Historical Alias",
                    "market": "stocks",
                    "locale": "us",
                    "primary_exchange": "XNAS",
                    "type": "CS",
                    "active": True,
                    "composite_figi": "BBG_ALIAS_CONTINUITY",
                }
            ]
        return [
            {
                "ticker": "AAPL",
                "name": "Apple Example",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNAS",
                "type": "CS",
                "active": True,
                "composite_figi": "BBG_AAPL",
            },
            {
                "ticker": "ETF1",
                "name": "ETF Example",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "ARCX",
                "type": "ETF",
                "active": True,
                "composite_figi": "BBG_ETF1",
            },
            {
                "ticker": "PFDpA",
                "name": "Preferred Example",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNYS",
                "type": "PFD",
                "active": True,
                "cik": "0000000001",
            },
            {
                "ticker": "WARRW",
                "name": "Warrant Example",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNAS",
                "type": "WARRANT",
                "active": True,
                "composite_figi": "BBG_WARRANT",
            },
            {
                "ticker": "FALL",
                "name": "Fallback Example",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNAS",
                "type": "CS",
                "active": True,
            },
            {
                "ticker": "OLD",
                "name": "Inactive Example",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNYS",
                "type": "CS",
                "active": False,
                "composite_figi": "BBG_OLD",
            },
            {
                "ticker": "OLDX",
                "name": "Historical Alias",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNAS",
                "type": "CS",
                "active": False,
                "composite_figi": "BBG_ALIAS_CONTINUITY",
            },
            {
                "ticker": "NEWX",
                "name": "Current Alias",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNYS",
                "type": "CS",
                "active": True,
                "composite_figi": "BBG_ALIAS_CONTINUITY",
            },
            {
                "ticker": "AMB1",
                "name": "Ambiguous One",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNAS",
                "type": "CS",
                "active": True,
                "composite_figi": "BBG_AMBIG",
            },
            {
                "ticker": "AMB2",
                "name": "Ambiguous Two",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNAS",
                "type": "CS",
                "active": True,
                "composite_figi": "BBG_AMBIG",
            },
        ]


def _settings(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    return settings


def _rows(path):
    con = duckdb.connect(":memory:")
    try:
        return con.execute(f"SELECT * FROM read_parquet('{path.as_posix()}') ORDER BY instrument_id").fetchall()
    finally:
        con.close()


def test_builder_selects_one_active_alias_and_persists_full_exclusion_audit(tmp_path):
    settings = _settings(tmp_path)
    as_of = date(2026, 8, 14)
    InstrumentRegistryStore(settings, provider=UniverseReferenceProvider()).sync_snapshot(as_of)

    manager = UniverseManager(settings)
    first = manager.build(as_of)
    second = manager.build(as_of)

    assert not first.skipped
    assert second.skipped
    assert first.fingerprint == second.fingerprint
    assert first.source_row_count == 10
    assert first.source_instrument_count == 8
    assert first.discovery_count == 4
    assert first.routed_instrument_count == 4
    assert first.exclusion_count == 4
    assert first.discovery_security_type_counts == {"CS": 2, "ETF": 1, "PFD": 1}
    assert first.reason_counts[UniverseReasonCode.UNSUPPORTED_SECURITY_TYPE.value] == 1
    assert first.reason_counts[UniverseReasonCode.UNSUPPORTED_IDENTITY_QUALITY.value] == 1
    assert first.reason_counts[UniverseReasonCode.REFERENCE_INACTIVE.value] == 1
    assert first.reason_counts[UniverseReasonCode.AMBIGUOUS_ACTIVE_TICKER.value] == 1

    assert first.snapshot_path.exists()
    assert first.exclusion_path.exists()
    assert first.manifest_path.exists()

    con = duckdb.connect(":memory:")
    try:
        routed = con.execute(
            f"SELECT ticker FROM read_parquet('{first.snapshot_path.as_posix()}') ORDER BY ticker"
        ).fetchall()
        excluded = con.execute(
            f"SELECT tickers, reason_codes FROM read_parquet('{first.exclusion_path.as_posix()}')"
        ).fetchall()
    finally:
        con.close()

    assert ("NEWX",) in routed
    assert ("OLDX",) not in routed
    assert any(set(tickers) == {"AMB1", "AMB2"} and "ambiguous_active_ticker" in reasons for tickers, reasons in excluded)


def test_inactive_position_override_is_routed_without_becoming_discovery_eligible(tmp_path):
    settings = _settings(tmp_path)
    as_of = date(2026, 8, 14)
    store = InstrumentRegistryStore(settings, provider=UniverseReferenceProvider())
    store.sync_snapshot(as_of)
    old = store.resolve_ticker("OLD", as_of)[0]["instrument_id"]

    result = UniverseManager(settings).build(
        as_of,
        override_routes={old: (UniverseRoute.POSITION,)},
    )

    con = duckdb.connect(":memory:")
    try:
        row = con.execute(
            f"""
            SELECT ticker, discovery_eligible, reason_codes, routes
            FROM read_parquet('{result.snapshot_path.as_posix()}')
            WHERE instrument_id=?
            """,
            [old],
        ).fetchone()
    finally:
        con.close()

    assert row[0] == "OLD"
    assert row[1] is False
    assert set(row[2]) >= {"reference_inactive", "position_override"}
    assert row[3] == ["position"]
    assert result.position_count == 1
    assert result.discovery_count == 4


def test_exact_historical_snapshot_prevents_future_ticker_leakage(tmp_path):
    settings = _settings(tmp_path)
    store = InstrumentRegistryStore(settings, provider=UniverseReferenceProvider())
    historical = date(2021, 8, 16)
    current = date(2026, 8, 14)
    store.sync_snapshot(historical)
    store.sync_snapshot(current)

    manager = UniverseManager(settings)
    old_result = manager.build(historical)
    current_result = manager.build(current)

    con = duckdb.connect(":memory:")
    try:
        old_tickers = {
            row[0]
            for row in con.execute(
                f"SELECT ticker FROM read_parquet('{old_result.snapshot_path.as_posix()}')"
            ).fetchall()
        }
        current_tickers = {
            row[0]
            for row in con.execute(
                f"SELECT ticker FROM read_parquet('{current_result.snapshot_path.as_posix()}')"
            ).fetchall()
        }
    finally:
        con.close()

    assert old_tickers == {"OLDX"}
    assert "NEWX" in current_tickers
    assert "OLDX" not in current_tickers
