from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from packages.schemas.market import CanonicalBar


CANONICAL_STOCK_BAR_SCHEMA_VERSION = "canonical-stock-bar-v1"


@dataclass(frozen=True, slots=True)
class CanonicalMarketColumn:
    """One physical column in an ATLAS canonical market-data Parquet row."""

    name: str
    duckdb_type: str


CANONICAL_STOCK_BAR_SCHEMA = (
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

CANONICAL_STOCK_BAR_COLUMNS = tuple(column.name for column in CANONICAL_STOCK_BAR_SCHEMA)
CANONICAL_STOCK_BAR_TYPES = tuple(column.duckdb_type for column in CANONICAL_STOCK_BAR_SCHEMA)


def canonical_stock_bar_schema_matches(description: Sequence[Sequence[object]]) -> bool:
    """Return whether a DuckDB DESCRIBE result matches canonical stock-bar storage."""

    columns = tuple(str(row[0]) for row in description)
    types = tuple(str(row[1]) for row in description)
    return columns == CANONICAL_STOCK_BAR_COLUMNS and types == CANONICAL_STOCK_BAR_TYPES


# Compatibility aliases. The original physical contract was named "daily"
# even though the exact same CanonicalBar layout is used by native 1m V2
# partitions. Keep old imports stable while making the timeframe-neutral
# storage contract explicit for B34 and later intraday materialization.
CANONICAL_STOCK_DAILY_SCHEMA_VERSION = "canonical-stock-daily-v1"
CANONICAL_STOCK_DAILY_SCHEMA = CANONICAL_STOCK_BAR_SCHEMA
CANONICAL_STOCK_DAILY_COLUMNS = CANONICAL_STOCK_BAR_COLUMNS
CANONICAL_STOCK_DAILY_TYPES = CANONICAL_STOCK_BAR_TYPES


def canonical_stock_daily_schema_matches(description: Sequence[Sequence[object]]) -> bool:
    return canonical_stock_bar_schema_matches(description)


# CanonicalBar is the semantic contract; this module is the physical storage
# contract. Keep the two aligned so a schema edit cannot silently create a
# provider-specific field set.
if tuple(CanonicalBar.model_fields) != CANONICAL_STOCK_BAR_COLUMNS:
    raise RuntimeError(
        "canonical stock-bar physical schema is not aligned with CanonicalBar fields: "
        f"model={tuple(CanonicalBar.model_fields)!r} storage={CANONICAL_STOCK_BAR_COLUMNS!r}"
    )
