from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.aggregation.sessionizer import SessionBoundaries
from packages.core.enums import Timeframe
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None


_INTERVAL_MINUTES = {
    Timeframe.MINUTE_15: 15,
    Timeframe.HOUR_1: 60,
    Timeframe.HOUR_4: 240,
}


class SessionBarBuilder:
    """Aggregate a complete canonical 1m session partition.

    Buckets are anchored independently at 04:00 local (premarket), the official
    exchange regular open (normally 09:30 ET), and the official close
    (normally 16:00 ET). This explicitly prevents the old wall-clock 09:00/12:00
    flooring bug and there is no arbitrary source-row chunk aggregation.
    """

    def __init__(self, *, compression: str = "zstd", row_group_size: int = 122_880) -> None:
        self.compression = compression.upper()
        self.row_group_size = row_group_size

    def build(
        self,
        source_1m: Path,
        target: Path,
        timeframe: Timeframe,
        trading_date: date,
        boundaries: SessionBoundaries,
    ) -> int:
        if duckdb is None:
            raise RuntimeError("duckdb is required for Phase 3. Run: pip install -r requirements.lock")
        if timeframe not in _INTERVAL_MINUTES:
            raise ValueError(f"Unsupported materialized timeframe: {timeframe}")
        minutes = _INTERVAL_MINUTES[timeframe]
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)

        pre = boundaries.premarket_start_utc.isoformat()
        opn = boundaries.regular_open_utc.isoformat()
        cls = boundaries.regular_close_utc.isoformat()
        aft = boundaries.after_hours_end_utc.isoformat()

        source = sql_string(Path(source_1m))
        out = sql_string(temp)
        query = f"""
            WITH base AS (
                SELECT *,
                    CASE session_segment
                        WHEN 'premarket' THEN TIMESTAMPTZ '{pre}'
                        WHEN 'regular' THEN TIMESTAMPTZ '{opn}'
                        WHEN 'after_hours' THEN TIMESTAMPTZ '{cls}'
                    END AS anchor_utc,
                    CASE session_segment
                        WHEN 'premarket' THEN TIMESTAMPTZ '{opn}'
                        WHEN 'regular' THEN TIMESTAMPTZ '{cls}'
                        WHEN 'after_hours' THEN TIMESTAMPTZ '{aft}'
                    END AS segment_end_utc
                FROM read_parquet({source})
                WHERE session_segment IN ('premarket', 'regular', 'after_hours')
            ), bucketed AS (
                SELECT *, floor(date_diff('minute', anchor_utc, timestamp_utc) / {minutes})::BIGINT AS bucket_no
                FROM base
                WHERE timestamp_utc >= anchor_utc AND timestamp_utc < segment_end_utc
            )
            SELECT
                symbol,
                anchor_utc + INTERVAL (bucket_no * {minutes}) MINUTE AS timestamp_utc,
                DATE '{trading_date}' AS session_date,
                '{timeframe.value}' AS timeframe,
                session_segment,
                first(open ORDER BY timestamp_utc) AS open,
                max(high) AS high,
                min(low) AS low,
                last(close ORDER BY timestamp_utc) AS close,
                sum(volume)::DOUBLE AS volume,
                CASE WHEN sum(CASE WHEN vwap IS NOT NULL THEN volume ELSE 0 END) > 0
                     THEN sum(CASE WHEN vwap IS NOT NULL THEN vwap * volume ELSE 0 END)
                          / sum(CASE WHEN vwap IS NOT NULL THEN volume ELSE 0 END)
                     ELSE NULL END::DOUBLE AS vwap,
                CASE WHEN count(transaction_count) = 0 THEN NULL ELSE sum(transaction_count)::BIGINT END AS transaction_count,
                'internal' AS provider,
                'derived_stock_bars' AS dataset,
                max(source_id) || ':{timeframe.value}' AS source_id,
                NULL::BOOLEAN AS is_adjusted,
                least(
                    anchor_utc + INTERVAL ((bucket_no + 1) * {minutes}) MINUTE,
                    max(segment_end_utc)
                ) AS bar_end_utc,
                count(*)::INTEGER AS input_bar_count
            FROM bucketed
            GROUP BY symbol, session_segment, anchor_utc, bucket_no
            ORDER BY symbol, timestamp_utc, session_segment
        """
        con = connect_utc(":memory:")
        try:
            # DuckDB RETURN_STATS reports the exact row count written by COPY.
            # Re-reading the just-created Parquet solely for count(*) duplicated
            # file I/O on every derived timeframe/session materialization.
            stats = con.execute(
                f"COPY ({query}) TO {out} "
                f"(FORMAT PARQUET, COMPRESSION {self.compression}, ROW_GROUP_SIZE {self.row_group_size}, RETURN_STATS)"
            ).fetchone()
            if stats is None:
                raise RuntimeError("DuckDB COPY returned no write statistics")
            count = int(stats[1])
        finally:
            con.close()
        promote(temp, target)
        return count
