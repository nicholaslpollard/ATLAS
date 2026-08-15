from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from packages.core.enums import SessionSegment, Timeframe
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None


class DuckDBMarketRepository:
    """DuckDB analytical facade over partitioned ATLAS Parquet files."""

    def __init__(self, settings: AtlasSettings, *, persistent: bool = True) -> None:
        if duckdb is None:
            raise RuntimeError("duckdb is required for Phase 3. Run: pip install -r requirements.lock")
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        db_path = self.paths.duckdb_file() if persistent else Path(":memory:")
        if persistent:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = connect_utc(db_path)

    def close(self) -> None:
        self.connection.close()

    def refresh_views(self) -> None:
        for timeframe in (Timeframe.MINUTE_1, Timeframe.MINUTE_15, Timeframe.HOUR_1, Timeframe.HOUR_4, Timeframe.DAY_1):
            glob = self.paths.glob_for_timeframe(timeframe)
            view = f"bars_{timeframe.value.replace('m','min').replace('h','hour').replace('d','day')}"
            # DuckDB rejects an empty glob. Create a typed empty view until data exists.
            if not any(Path(glob.split("**")[0]).rglob("*.parquet")):
                self.connection.execute(
                    f"CREATE OR REPLACE VIEW {view} AS SELECT "
                    "NULL::VARCHAR symbol, NULL::TIMESTAMPTZ timestamp_utc, NULL::DATE session_date, "
                    "NULL::VARCHAR timeframe, NULL::VARCHAR session_segment, NULL::DOUBLE open, NULL::DOUBLE high, "
                    "NULL::DOUBLE low, NULL::DOUBLE close, NULL::DOUBLE volume WHERE FALSE"
                )
            else:
                self.connection.execute(
                    f"CREATE OR REPLACE VIEW {view} AS SELECT * FROM read_parquet({sql_string(glob)}, union_by_name=true, hive_partitioning=true)"
                )

    def query_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: datetime | date | None = None,
        end: datetime | date | None = None,
        session_segment: SessionSegment | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        glob = self.paths.glob_for_timeframe(timeframe)
        root = Path(glob.split("**")[0])
        if not root.exists() or not any(root.rglob("*.parquet")):
            return []
        clauses = ["upper(symbol) = upper(?)"]
        params: list[Any] = [symbol]
        if start is not None:
            clauses.append("timestamp_utc >= ?")
            params.append(start)
        if end is not None:
            clauses.append("timestamp_utc <= ?")
            params.append(end)
        if session_segment is not None:
            clauses.append("session_segment = ?")
            params.append(session_segment.value)
        lim = f" LIMIT {int(limit)}" if limit is not None else ""
        rel = self.connection.execute(
            f"SELECT * FROM read_parquet({sql_string(glob)}, union_by_name=true, hive_partitioning=true) "
            f"WHERE {' AND '.join(clauses)} ORDER BY timestamp_utc{lim}",
            params,
        )
        names = [col[0] for col in rel.description]
        return [dict(zip(names, row, strict=True)) for row in rel.fetchall()]
