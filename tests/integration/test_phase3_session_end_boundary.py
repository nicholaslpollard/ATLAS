from __future__ import annotations

import csv
import gzip
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

from packages.core.enums import DatasetType, Timeframe
from packages.core.settings import load_settings
from packages.data.duckdb_connection import connect_utc
from packages.data.materializer import MarketDataMaterializer


def _ns(ts: datetime) -> int:
    return int(ts.timestamp() * 1_000_000_000)


def _write_gzip_csv(path: Path, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ticker", "volume", "open", "close", "high", "low", "window_start", "transactions"])
        writer.writerows(rows)


def test_exact_20_et_bar_is_preserved_but_excluded_from_derived_bars(tmp_path):
    settings = load_settings()
    settings.project_root = tmp_path
    materializer = MarketDataMaterializer(settings)
    trading_date = date(2026, 8, 14)  # EDT; 20:00 ET == 2026-08-15 00:00 UTC.

    source = materializer.paths.provider_file(DatasetType.STOCK_MINUTE_AGGREGATES, trading_date)
    _write_gzip_csv(
        source,
        [
            ["TEST", 100, 10, 10, 10, 10, _ns(datetime(2026, 8, 14, 23, 59, tzinfo=UTC)), 1],
            ["TEST", 200, 11, 11, 11, 11, _ns(datetime(2026, 8, 15, 0, 0, tzinfo=UTC)), 2],
        ],
    )

    result = materializer.materialize(DatasetType.STOCK_MINUTE_AGGREGATES, trading_date)

    assert result.canonical_rows == 2
    assert result.quality_status.value == "warning"

    con = connect_utc(":memory:")
    try:
        canonical = con.execute(
            f"SELECT timestamp_utc, session_segment FROM read_parquet('{result.canonical_path.as_posix()}') ORDER BY timestamp_utc"
        ).fetchall()
        derived_15m = materializer.paths.derived_file(Timeframe.MINUTE_15, trading_date).as_posix()
        derived_rows = con.execute(
            f"SELECT timestamp_utc, input_bar_count FROM read_parquet('{derived_15m}') WHERE symbol='TEST' ORDER BY timestamp_utc"
        ).fetchall()
    finally:
        con.close()

    assert canonical[0][1] == "after_hours"
    assert canonical[1][1] == "closed"
    assert len(derived_rows) == 1
    assert derived_rows[0][1] == 1
