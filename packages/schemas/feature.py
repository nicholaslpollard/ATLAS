from __future__ import annotations

from collections.abc import Iterable

from packages.features.feature_registry import CORE_FEATURE_REGISTRY


CORE_FEATURE_STORAGE_SCHEMA_VERSION = "core-feature-storage-v1-symbol-time-33-double"
CORE_FEATURE_STORAGE_COLUMNS = (
    "symbol",
    "timestamp_utc",
    *(definition.name for definition in CORE_FEATURE_REGISTRY.all()),
)
CORE_FEATURE_STORAGE_TYPES = (
    "VARCHAR",
    "TIMESTAMP WITH TIME ZONE",
    *("DOUBLE" for _definition in CORE_FEATURE_REGISTRY.all()),
)
CORE_FEATURE_STORAGE_SCHEMA = tuple(zip(CORE_FEATURE_STORAGE_COLUMNS, CORE_FEATURE_STORAGE_TYPES))


def _normalized_description(
    description: Iterable[tuple[object, ...]],
) -> tuple[tuple[str, str], ...]:
    return tuple((str(row[0]), str(row[1]).upper()) for row in description)


def core_feature_storage_schema_matches(description: Iterable[tuple[object, ...]]) -> bool:
    """Return whether a DuckDB DESCRIBE result matches the frozen 1d feature contract."""

    return _normalized_description(description) == CORE_FEATURE_STORAGE_SCHEMA


def core_feature_select_sql(*, table_alias: str | None = None) -> str:
    """Return an explicit cast/order projection for deterministic Parquet writes."""

    prefix = "" if table_alias is None else f"{table_alias}."
    expressions = [
        f"CAST({prefix}symbol AS VARCHAR) AS symbol",
        f"CAST({prefix}timestamp_utc AS TIMESTAMPTZ) AS timestamp_utc",
    ]
    expressions.extend(
        f'CAST({prefix}"{definition.name}" AS DOUBLE) AS "{definition.name}"'
        for definition in CORE_FEATURE_REGISTRY.all()
    )
    return ",\n                    ".join(expressions)


if len(CORE_FEATURE_STORAGE_COLUMNS) != 35:
    raise RuntimeError("core feature storage contract must contain symbol/time plus 33 features")
if len(set(CORE_FEATURE_STORAGE_COLUMNS)) != len(CORE_FEATURE_STORAGE_COLUMNS):
    raise RuntimeError("core feature storage contract contains duplicate columns")
