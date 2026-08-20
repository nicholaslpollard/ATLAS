from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from packages.schemas.market import CanonicalBar


CANONICAL_STOCK_DAILY_SCHEMA_VERSION = "canonical-stock-daily-v1"


@dataclass(frozen=True, slots=True)
class CanonicalMarketColumn:
    """One physical column in an ATLAS canonical market-data Parquet row."""

    name: str
    duckdb_type: str


CANONICAL_STOCK_DAILY_SCHEMA = (
    CanonicalMarketColumn("symbol", "VARCHAR"),
    CanonicalMarketColumn("timestamp_utc", "TIMESTAMP WITH TIME ZONE"),
    CanonicalMarketColumn("session_date", "DATE"),
    CanonicalMarketColumn("timeframe", "VARCHAR"),
    CanonicalMarketColumn("session_segment", "VARCHAR"),
    CanonicalMarketColumn("open", "DOUBLE"),
    CanonicalMarketColumn("high", "DOUBLE"),
    CanonicalMarketColumn("low", "DOUBLE"),
    CanonicalMarketColumn("close", "DOUBLE"),
    CanonicalMarketColumn("volume", "DOUBLE"),
    CanonicalMarketColumn("vwap", "DOUBLE"),
    CanonicalMarketColumn("transaction_count", "BIGINT"),
    CanonicalMarketColumn("provider", "VARCHAR"),
    CanonicalMarketColumn("dataset", "VARCHAR"),
    CanonicalMarketColumn("source_id", "VARCHAR"),
    CanonicalMarketColumn("is_adjusted", "BOOLEAN"),
    CanonicalMarketColumn("provider_timestamp_utc", "TIMESTAMP WITH TIME ZONE"),
)

CANONICAL_STOCK_DAILY_COLUMNS = tuple(column.name for column in CANONICAL_STOCK_DAILY_SCHEMA)
CANONICAL_STOCK_DAILY_TYPES = tuple(column.duckdb_type for column in CANONICAL_STOCK_DAILY_SCHEMA)


def canonical_stock_daily_schema_matches(description: Sequence[Sequence[object]]) -> bool:
    """Return whether a DuckDB DESCRIBE result exactly matches canonical 1d storage."""

    columns = tuple(str(row[0]) for row in description)
    types = tuple(str(row[1]) for row in description)
    return columns == CANONICAL_STOCK_DAILY_COLUMNS and types == CANONICAL_STOCK_DAILY_TYPES


# CanonicalBar is the semantic contract; this module is the physical storage
# contract. Keep the two aligned so a schema edit cannot silently create a
# provider-specific field set.
if tuple(CanonicalBar.model_fields) != CANONICAL_STOCK_DAILY_COLUMNS:
    raise RuntimeError(
        "canonical 1d physical schema is not aligned with CanonicalBar fields: "
        f"model={tuple(CanonicalBar.model_fields)!r} storage={CANONICAL_STOCK_DAILY_COLUMNS!r}"
    )
