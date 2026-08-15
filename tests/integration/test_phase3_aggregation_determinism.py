from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

from packages.aggregation.bar_builder import SessionBarBuilder
from packages.aggregation.sessionizer import session_boundaries
from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.data.duckdb_connection import connect_utc


def _write_canonical(path: Path, reverse: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(120):
        ts = datetime(2026, 8, 14, 13, 30, tzinfo=UTC).timestamp() + i * 60
        rows.append(("AAPL", datetime.fromtimestamp(ts, UTC), 100+i/10, 101+i/10, 99+i/10, 100.5+i/10, 10.0, i+1))
    if reverse:
        rows.reverse()
    con = connect_utc(":memory:")
    con.execute("CREATE TABLE bars(symbol VARCHAR, timestamp_utc TIMESTAMPTZ, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE, transaction_count BIGINT)")
    con.executemany("INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    out = path.as_posix()
    con.execute(f"COPY (SELECT symbol, timestamp_utc, DATE '2026-08-14' session_date, '1m' timeframe, 'regular' session_segment, open, high, low, close, volume, NULL::DOUBLE vwap, transaction_count, 'massive' provider, 'stock_minute_aggregates' dataset, 'src_x' source_id, NULL::BOOLEAN is_adjusted FROM bars) TO '{out}' (FORMAT PARQUET)")
    con.close()


def test_aggregation_is_independent_of_source_row_order(tmp_path):
    a = tmp_path / "a.parquet"
    b = tmp_path / "b.parquet"
    _write_canonical(a, False)
    _write_canonical(b, True)
    bounds = session_boundaries(date(2026, 8, 14), MarketCalendar())
    builder = SessionBarBuilder()
    out_a = tmp_path / "out_a.parquet"
    out_b = tmp_path / "out_b.parquet"
    builder.build(a, out_a, Timeframe.HOUR_1, date(2026, 8, 14), bounds)
    builder.build(b, out_b, Timeframe.HOUR_1, date(2026, 8, 14), bounds)
    con = connect_utc(":memory:")
    try:
        diff = con.execute(
            f"SELECT count(*) FROM ((SELECT * FROM read_parquet('{out_a.as_posix()}') EXCEPT SELECT * FROM read_parquet('{out_b.as_posix()}')) UNION ALL (SELECT * FROM read_parquet('{out_b.as_posix()}') EXCEPT SELECT * FROM read_parquet('{out_a.as_posix()}')))"
        ).fetchone()[0]
    finally:
        con.close()
    assert diff == 0
