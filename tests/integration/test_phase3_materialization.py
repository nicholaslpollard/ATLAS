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


def minute_rows():
    # 2026-08-14 is EDT: regular open is 13:30 UTC.
    return [
        ["AAPL", 10, 100, 101, 102, 99, ns(datetime(2026, 8, 14, 12, 0, tzinfo=UTC)), 2],  # pre
        ["AAPL", 20, 101, 102, 103, 100, ns(datetime(2026, 8, 14, 13, 30, tzinfo=UTC)), 3],
        ["AAPL", 30, 102, 104, 105, 101, ns(datetime(2026, 8, 14, 13, 31, tzinfo=UTC)), 4],
        ["AAPL", 40, 104, 103, 106, 102, ns(datetime(2026, 8, 14, 14, 29, tzinfo=UTC)), 5],
        ["AAPL", 50, 103, 107, 108, 103, ns(datetime(2026, 8, 14, 14, 30, tzinfo=UTC)), 6],
        ["AAPL", 60, 107, 109, 110, 106, ns(datetime(2026, 8, 14, 20, 0, tzinfo=UTC)), 7],  # after
    ]


def test_minute_materialization_is_idempotent_and_session_anchored(tmp_path):
    settings = make_settings(tmp_path)
    m = MarketDataMaterializer(settings)
    d = date(2026, 8, 14)
    src = m.paths.provider_file(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    write_gzip_csv(src, minute_rows())

    result = m.materialize(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    assert result.canonical_rows == 6
    assert result.quality_status.value == "valid"
    assert result.derived_rows[Timeframe.HOUR_1] >= 4  # pre + regular buckets + after

    con = connect_utc(":memory:")
    try:
        one_hour = m.paths.derived_file(Timeframe.HOUR_1, d).as_posix()
        rows = con.execute(
            f"SELECT timestamp_utc, open, close, volume, input_bar_count "
            f"FROM read_parquet('{one_hour}') WHERE symbol='AAPL' AND session_segment='regular' ORDER BY timestamp_utc"
        ).fetchall()
    finally:
        con.close()
    assert rows[0][0].astimezone(UTC).hour == 13 and rows[0][0].astimezone(UTC).minute == 30
    assert rows[0][1:5] == (101.0, 103.0, 90.0, 3)
    assert rows[1][0].astimezone(UTC).hour == 14 and rows[1][0].astimezone(UTC).minute == 30

    second = m.materialize(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    assert second.skipped is True


def test_source_hash_change_rebuilds_only_session(tmp_path):
    settings = make_settings(tmp_path)
    m = MarketDataMaterializer(settings)
    d = date(2026, 8, 14)
    src = m.paths.provider_file(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    rows = minute_rows()
    write_gzip_csv(src, rows)
    first = m.materialize(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    assert first.skipped is False

    rows.append(["MSFT", 1, 50, 50, 50, 50, ns(datetime(2026, 8, 14, 13, 30, tzinfo=UTC)), 1])
    write_gzip_csv(src, rows)
    second = m.materialize(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    assert second.skipped is False
    assert second.canonical_rows == first.canonical_rows + 1


def test_daily_materialization_preserves_provider_timestamp(tmp_path):
    settings = make_settings(tmp_path)
    m = MarketDataMaterializer(settings)
    d = date(2026, 8, 14)
    src = m.paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, d)
    write_gzip_csv(src, [["AAPL", 1000, 100, 105, 106, 99, ns(datetime(2026, 8, 14, 4, 0, tzinfo=UTC)), 100]])
    result = m.materialize(DatasetType.STOCK_DAILY_AGGREGATES, d)
    assert result.canonical_rows == 1
    con = connect_utc(":memory:")
    try:
        path = result.canonical_path.as_posix()
        row = con.execute(f"SELECT timestamp_utc, provider_timestamp_utc FROM read_parquet('{path}')").fetchone()
    finally:
        con.close()
    assert row[0].astimezone(UTC).hour == 13 and row[0].astimezone(UTC).minute == 30
    assert row[1] is not None


def test_conflicting_daily_symbol_rows_are_quarantined_not_guessed(tmp_path):
    settings = make_settings(tmp_path)
    m = MarketDataMaterializer(settings)
    d = date(2026, 8, 14)
    src = m.paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, d)
    t = ns(datetime(2026, 8, 14, 4, 0, tzinfo=UTC))
    write_gzip_csv(src, [
        ["AAPL", 1000, 100, 105, 106, 99, t, 100],
        ["BCPC", 8972, 24.0, 23.97, 24.0, 23.95, t, 82],
        ["BCPC", 89141.4, 177.36, 178.51, 178.56, 174.55, t, 4737],
    ])

    result = m.materialize(DatasetType.STOCK_DAILY_AGGREGATES, d)
    assert result.quality_status.value == "warning"
    assert result.quarantined_symbols == ("BCPC",)
    assert result.canonical_rows == 1

    con = connect_utc(":memory:")
    try:
        canonical_symbols = con.execute(
            f"SELECT symbol FROM read_parquet('{result.canonical_path.as_posix()}') ORDER BY symbol"
        ).fetchall()
        quarantine = m.paths.quarantine_file(Timeframe.DAY_1, d)
        quarantined_rows = con.execute(
            f"SELECT count(*) FROM read_parquet('{quarantine.as_posix()}') WHERE symbol='BCPC'"
        ).fetchone()[0]
    finally:
        con.close()
    assert canonical_symbols == [("AAPL",)]
    assert quarantined_rows == 2


def test_minute_materialization_applies_daily_symbol_quarantine(tmp_path):
    settings = make_settings(tmp_path)
    m = MarketDataMaterializer(settings)
    d = date(2026, 8, 14)
    t = ns(datetime(2026, 8, 14, 4, 0, tzinfo=UTC))
    daily = m.paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, d)
    write_gzip_csv(daily, [
        ["BCPC", 8972, 24.0, 23.97, 24.0, 23.95, t, 82],
        ["BCPC", 89141.4, 177.36, 178.51, 178.56, 174.55, t, 4737],
        ["AAPL", 1000, 100, 105, 106, 99, t, 100],
    ])
    m.materialize(DatasetType.STOCK_DAILY_AGGREGATES, d)

    minute = m.paths.provider_file(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    write_gzip_csv(minute, [
        ["AAPL", 10, 100, 101, 102, 99, ns(datetime(2026, 8, 14, 13, 30, tzinfo=UTC)), 2],
        ["BCPC", 10, 24.0, 23.97, 24.0, 23.95, ns(datetime(2026, 8, 14, 13, 30, tzinfo=UTC)), 2],
        ["BCPC", 10, 177.0, 178.0, 178.5, 176.5, ns(datetime(2026, 8, 14, 13, 31, tzinfo=UTC)), 2],
    ])

    result = m.materialize(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    assert result.quality_status.value == "warning"
    assert result.quarantined_symbols == ("BCPC",)
    assert result.canonical_rows == 1

    con = connect_utc(":memory:")
    try:
        symbols = con.execute(
            f"SELECT DISTINCT symbol FROM read_parquet('{result.canonical_path.as_posix()}') ORDER BY symbol"
        ).fetchall()
    finally:
        con.close()
    assert symbols == [("AAPL",)]


def test_exact_duplicate_daily_rows_are_deduplicated_with_warning(tmp_path):
    settings = make_settings(tmp_path)
    m = MarketDataMaterializer(settings)
    d = date(2026, 8, 14)
    src = m.paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, d)
    row = ["AAPL", 1000, 100, 105, 106, 99, ns(datetime(2026, 8, 14, 4, 0, tzinfo=UTC)), 100]
    write_gzip_csv(src, [row, row])

    result = m.materialize(DatasetType.STOCK_DAILY_AGGREGATES, d)
    assert result.quality_status.value == "warning"
    assert result.quarantined_symbols == ()
    assert result.canonical_rows == 1


def test_minute_rebuilds_when_quarantine_dependency_changes(tmp_path):
    settings = make_settings(tmp_path)
    m = MarketDataMaterializer(settings)
    d = date(2026, 8, 14)
    minute = m.paths.provider_file(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    write_gzip_csv(minute, [
        ["AAPL", 10, 100, 101, 102, 99, ns(datetime(2026, 8, 14, 13, 30, tzinfo=UTC)), 2],
        ["BCPC", 10, 177, 178, 179, 176, ns(datetime(2026, 8, 14, 13, 30, tzinfo=UTC)), 2],
    ])

    first = m.materialize(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    assert first.canonical_rows == 2
    assert first.skipped is False
    assert m.materialize(DatasetType.STOCK_MINUTE_AGGREGATES, d).skipped is True

    registry = m.paths.symbol_quarantine_registry(d)
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        '{"trading_date":"2026-08-14","reason":"test","symbols":["BCPC"]}\n',
        encoding="utf-8",
    )

    rebuilt = m.materialize(DatasetType.STOCK_MINUTE_AGGREGATES, d)
    assert rebuilt.skipped is False
    assert rebuilt.canonical_rows == 1
    assert rebuilt.quarantined_symbols == ("BCPC",)
