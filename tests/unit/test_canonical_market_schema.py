from packages.data.alpaca_backfill_candidate_canonical import (
    CANONICAL_DAILY_COLUMNS,
    CANONICAL_DAILY_TYPES,
)
from packages.schemas.canonical_market import (
    CANONICAL_STOCK_DAILY_COLUMNS,
    CANONICAL_STOCK_DAILY_SCHEMA,
    CANONICAL_STOCK_DAILY_SCHEMA_VERSION,
    CANONICAL_STOCK_DAILY_TYPES,
    canonical_stock_daily_schema_matches,
)
from packages.schemas.market import CanonicalBar


def test_canonical_daily_storage_contract_matches_semantic_bar_fields() -> None:
    assert CANONICAL_STOCK_DAILY_SCHEMA_VERSION == "canonical-stock-daily-v1"
    assert tuple(CanonicalBar.model_fields) == CANONICAL_STOCK_DAILY_COLUMNS
    assert tuple(column.name for column in CANONICAL_STOCK_DAILY_SCHEMA) == CANONICAL_STOCK_DAILY_COLUMNS
    assert tuple(column.duckdb_type for column in CANONICAL_STOCK_DAILY_SCHEMA) == CANONICAL_STOCK_DAILY_TYPES


def test_gate6_uses_central_daily_schema_objects_not_provider_local_copies() -> None:
    assert CANONICAL_DAILY_COLUMNS is CANONICAL_STOCK_DAILY_COLUMNS
    assert CANONICAL_DAILY_TYPES is CANONICAL_STOCK_DAILY_TYPES


def test_canonical_daily_schema_matcher_rejects_column_or_type_drift() -> None:
    exact = list(zip(CANONICAL_STOCK_DAILY_COLUMNS, CANONICAL_STOCK_DAILY_TYPES, strict=True))
    assert canonical_stock_daily_schema_matches(exact) is True

    wrong_type = list(exact)
    wrong_type[11] = (wrong_type[11][0], "DOUBLE")
    assert canonical_stock_daily_schema_matches(wrong_type) is False

    missing_column = exact[:-1]
    assert canonical_stock_daily_schema_matches(missing_column) is False
