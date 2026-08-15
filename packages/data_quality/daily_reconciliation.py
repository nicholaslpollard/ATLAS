from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from packages.data.sql import sql_string

from packages.data.duckdb_connection import connect_utc

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None


@dataclass(frozen=True, slots=True)
class DailyReconciliationSummary:
    trading_date: date
    compared_symbols: int
    exact_ohlc_matches: int
    ohlc_mismatches: int
    volume_mismatches: int
    minute_only_symbols: int
    daily_only_symbols: int


class DailyMinuteReconciler:
    """Compare regular-session canonical minute facts to provider daily bars.

    This is an audit/reconciliation signal, not a hard equivalence assumption.
    Provider daily definitions or late corrections can legitimately differ.
    """

    def compare(self, minute_path: Path, daily_path: Path, trading_date: date, *, price_tolerance: float = 1e-9) -> DailyReconciliationSummary:
        if duckdb is None:
            raise RuntimeError("duckdb is required for Phase 3. Run: pip install -r requirements.lock")
        con = connect_utc(":memory:")
        try:
            row = con.execute(
                f"""
                WITH minute_daily AS (
                    SELECT symbol,
                           first(open ORDER BY timestamp_utc) open,
                           max(high) high,
                           min(low) low,
                           last(close ORDER BY timestamp_utc) close,
                           sum(volume) volume
                    FROM read_parquet({sql_string(minute_path)})
                    WHERE session_segment = 'regular'
                    GROUP BY symbol
                ), provider_daily AS (
                    SELECT symbol, open, high, low, close, volume
                    FROM read_parquet({sql_string(daily_path)})
                ), joined AS (
                    SELECT coalesce(m.symbol, d.symbol) symbol,
                           m.symbol IS NOT NULL has_minute,
                           d.symbol IS NOT NULL has_daily,
                           m.open mo, d.open do_, m.high mh, d.high dh,
                           m.low ml, d.low dl, m.close mc, d.close dc,
                           m.volume mv, d.volume dv
                    FROM minute_daily m FULL OUTER JOIN provider_daily d USING(symbol)
                )
                SELECT
                    count(*) FILTER (WHERE has_minute AND has_daily),
                    count(*) FILTER (WHERE has_minute AND has_daily
                        AND abs(mo-do_) <= {price_tolerance}
                        AND abs(mh-dh) <= {price_tolerance}
                        AND abs(ml-dl) <= {price_tolerance}
                        AND abs(mc-dc) <= {price_tolerance}),
                    count(*) FILTER (WHERE has_minute AND has_daily
                        AND NOT (abs(mo-do_) <= {price_tolerance}
                        AND abs(mh-dh) <= {price_tolerance}
                        AND abs(ml-dl) <= {price_tolerance}
                        AND abs(mc-dc) <= {price_tolerance})),
                    count(*) FILTER (WHERE has_minute AND has_daily AND mv <> dv),
                    count(*) FILTER (WHERE has_minute AND NOT has_daily),
                    count(*) FILTER (WHERE has_daily AND NOT has_minute)
                FROM joined
                """
            ).fetchone()
        finally:
            con.close()
        return DailyReconciliationSummary(trading_date, *(int(x) for x in row))
