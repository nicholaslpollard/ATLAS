from __future__ import annotations

from pathlib import Path

import duckdb

from packages.data.alpaca_backfill_seam import AlpacaBackfillSeamProbe
from packages.schemas.canonical_market import canonical_stock_daily_schema_matches


def _sql_string(value: str | Path) -> str:
    text = str(value).replace("\\", "/").replace("'", "''")
    return f"'{text}'"


def canonical_daily_physical_schema_exact(path: Path) -> bool:
    """Validate only the Parquet file's physical canonical columns.

    Gate 7 inspects individual files stored beneath Hive-style year=/date=
    directories. DuckDB can infer those path components as virtual columns when
    read_parquet() is used directly, which would make an otherwise correct
    canonical file appear to have extra year/date fields. Disable Hive partition
    inference explicitly here so the shared schema contract remains an exact
    physical-file check rather than being weakened to tolerate virtual columns.
    """

    if not path.is_file():
        return False
    con = duckdb.connect(":memory:")
    try:
        description = con.execute(
            f"DESCRIBE SELECT * FROM read_parquet({_sql_string(path)}, hive_partitioning=false)"
        ).fetchall()
    finally:
        con.close()
    return canonical_stock_daily_schema_matches(description)


class AlpacaBackfillSeamRuntimeProbe(AlpacaBackfillSeamProbe):
    """Gate 7-A probe with physical-file schema introspection semantics."""

    @staticmethod
    def _schema_exact(path: Path) -> bool:
        return canonical_daily_physical_schema_exact(path)
