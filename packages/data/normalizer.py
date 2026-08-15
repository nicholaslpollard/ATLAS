from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.aggregation.sessionizer import SessionBoundaries
from packages.core.enums import DatasetType, Timeframe
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None


class MassiveStockNormalizer:
    def __init__(self, *, compression: str = "zstd", row_group_size: int = 122_880) -> None:
        self.compression = compression.upper()
        self.row_group_size = row_group_size

    @staticmethod
    def _read_csv(path: Path) -> str:
        return (
            "read_csv("
            f"{sql_string(path)}, header=true, auto_detect=false, "
            "columns={'ticker':'VARCHAR','volume':'DOUBLE','open':'DOUBLE','close':'DOUBLE',"
            "'high':'DOUBLE','low':'DOUBLE','window_start':'BIGINT','transactions':'BIGINT'})"
        )

    def normalize(
        self,
        source_path: Path,
        target_path: Path,
        dataset: DatasetType,
        trading_date: date,
        source_id: str,
        boundaries: SessionBoundaries,
    ) -> int:
        if duckdb is None:
            raise RuntimeError("duckdb is required for Phase 3. Run: pip install -r requirements.lock")
        target_path = Path(target_path)
        temp = atomic_target(target_path)
        temp.unlink(missing_ok=True)
        src = self._read_csv(Path(source_path))
        source_id_sql = source_id.replace("'", "''")

        if dataset == DatasetType.STOCK_MINUTE_AGGREGATES:
            ns = boundaries.as_epoch_ns()
            query = f"""
                SELECT
                    upper(trim(ticker)) AS symbol,
                    to_timestamp(window_start / 1000000000.0) AS timestamp_utc,
                    DATE '{trading_date}' AS session_date,
                    '{Timeframe.MINUTE_1.value}' AS timeframe,
                    CASE
                        WHEN window_start >= {ns['premarket_start_ns']} AND window_start < {ns['regular_open_ns']} THEN 'premarket'
                        WHEN window_start >= {ns['regular_open_ns']} AND window_start < {ns['regular_close_ns']} THEN 'regular'
                        WHEN window_start >= {ns['regular_close_ns']} AND window_start < {ns['after_hours_end_ns']} THEN 'after_hours'
                        ELSE 'closed'
                    END AS session_segment,
                    open::DOUBLE AS open,
                    high::DOUBLE AS high,
                    low::DOUBLE AS low,
                    close::DOUBLE AS close,
                    volume::DOUBLE AS volume,
                    NULL::DOUBLE AS vwap,
                    transactions::BIGINT AS transaction_count,
                    'massive' AS provider,
                    '{dataset.value}' AS dataset,
                    '{source_id_sql}' AS source_id,
                    NULL::BOOLEAN AS is_adjusted
                FROM {src}
                ORDER BY symbol, timestamp_utc
            """
        elif dataset == DatasetType.STOCK_DAILY_AGGREGATES:
            provider_ts = "to_timestamp(window_start / 1000000000.0)"
            semantic_ts = boundaries.regular_open_utc.isoformat()
            query = f"""
                SELECT
                    upper(trim(ticker)) AS symbol,
                    TIMESTAMPTZ '{semantic_ts}' AS timestamp_utc,
                    DATE '{trading_date}' AS session_date,
                    '{Timeframe.DAY_1.value}' AS timeframe,
                    'regular' AS session_segment,
                    open::DOUBLE AS open,
                    high::DOUBLE AS high,
                    low::DOUBLE AS low,
                    close::DOUBLE AS close,
                    volume::DOUBLE AS volume,
                    NULL::DOUBLE AS vwap,
                    transactions::BIGINT AS transaction_count,
                    'massive' AS provider,
                    '{dataset.value}' AS dataset,
                    '{source_id_sql}' AS source_id,
                    NULL::BOOLEAN AS is_adjusted,
                    {provider_ts} AS provider_timestamp_utc
                FROM {src}
                ORDER BY symbol
            """
        else:
            raise ValueError(f"Unsupported normalization dataset: {dataset}")

        con = connect_utc(":memory:")
        try:
            out = sql_string(temp)
            con.execute(
                f"COPY ({query}) TO {out} "
                f"(FORMAT PARQUET, COMPRESSION {self.compression}, ROW_GROUP_SIZE {self.row_group_size})"
            )
            count = int(con.execute(f"SELECT count(*) FROM read_parquet({out})").fetchone()[0])
        finally:
            con.close()
        promote(temp, target_path)
        return count
