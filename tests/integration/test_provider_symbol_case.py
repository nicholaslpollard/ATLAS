from __future__ import annotations

import csv
import gzip
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

from packages.core.enums import DatasetType, Timeframe
from packages.core.settings import load_settings
from packages.data.duckdb_repository import DuckDBMarketRepository
from packages.data.materializer import MarketDataMaterializer
from packages.instruments.registry import InstrumentRegistryStore


def ns(ts: datetime) -> int:
    return int(ts.timestamp() * 1_000_000_000)


def write_gzip_csv(path: Path, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ticker", "volume", "open", "close", "high", "low", "window_start", "transactions"])
        writer.writerows(rows)


def make_settings(tmp_path: Path):
    settings = load_settings()
    settings.project_root = tmp_path
    return settings


def test_daily_materialization_preserves_massive_preferred_ticker_case(tmp_path):
    settings = make_settings(tmp_path)
    materializer = MarketDataMaterializer(settings)
    d = date(2026, 8, 14)
    source = materializer.paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, d)
    timestamp = ns(datetime(2026, 8, 14, 4, 0, tzinfo=UTC))

    # Massive uses lowercase p in preferred-share ticker symbols. These are two
    # distinct securities, not conflicting duplicate BCPC rows.
    write_gzip_csv(source, [
        ["BCPC", 89141.4, 177.36, 178.51, 178.56, 174.55, timestamp, 4737],
        ["BCpC", 8972, 24.0, 23.97, 24.0, 23.95, timestamp, 82],
    ])

    result = materializer.materialize(DatasetType.STOCK_DAILY_AGGREGATES, d)
    assert result.quality_status.value == "valid"
    assert result.quarantined_symbols == ()
    assert result.canonical_rows == 2

    con = duckdb.connect(":memory:")
    try:
        symbols = con.execute(
            f"SELECT symbol FROM read_parquet('{result.canonical_path.as_posix()}') ORDER BY symbol"
        ).fetchall()
    finally:
        con.close()
    assert symbols == [("BCPC",), ("BCpC",)]


class CaseSensitiveReferenceProvider:
    def stock_snapshot(self, as_of_date, *, include_inactive=True):
        return [
            {
                "ticker": "TPC",
                "name": "Tutor Perini Corporation",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNYS",
                "type": "CS",
                "active": True,
                "composite_figi": "BBG000BQXHV1",
                "share_class_figi": "BBG001S5V297",
                "cik": "0000077543",
            },
            {
                "ticker": "TpC",
                "name": "AT&T preferred Series C",
                "market": "stocks",
                "locale": "us",
                "primary_exchange": "XNYS",
                "type": "PFD",
                "active": True,
                "cik": "0000732717",
            },
        ]


def test_reference_registry_resolves_common_and_preferred_tickers_separately(tmp_path):
    settings = make_settings(tmp_path)
    store = InstrumentRegistryStore(settings, provider=CaseSensitiveReferenceProvider())
    d = date(2026, 8, 14)
    store.sync_snapshot(d)

    common = store.resolve_ticker("TPC", d)
    preferred = store.resolve_ticker("TpC", d)
    assert len(common) == 1
    assert common[0]["name"] == "Tutor Perini Corporation"
    assert len(preferred) == 1
    assert preferred[0]["name"] == "AT&T preferred Series C"


def test_market_repository_symbol_query_is_case_sensitive(tmp_path):
    settings = make_settings(tmp_path)
    materializer = MarketDataMaterializer(settings)
    d = date(2026, 8, 14)
    source = materializer.paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, d)
    timestamp = ns(datetime(2026, 8, 14, 4, 0, tzinfo=UTC))
    write_gzip_csv(source, [
        ["TPC", 100, 95.53, 96.82, 97.85, 95.53, timestamp, 100],
        ["TpC", 100, 16.97, 16.96, 17.02, 16.845, timestamp, 100],
    ])
    materializer.materialize(DatasetType.STOCK_DAILY_AGGREGATES, d)

    repository = DuckDBMarketRepository(settings, persistent=False)
    try:
        common = repository.query_bars("TPC", Timeframe.DAY_1)
        preferred = repository.query_bars("TpC", Timeframe.DAY_1)
    finally:
        repository.close()

    assert len(common) == 1 and common[0]["symbol"] == "TPC"
    assert len(preferred) == 1 and preferred[0]["symbol"] == "TpC"
