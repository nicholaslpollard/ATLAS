from __future__ import annotations

from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.schemas.feature import (
    CORE_FEATURE_STORAGE_COLUMNS,
    CORE_FEATURE_STORAGE_SCHEMA,
    CORE_FEATURE_STORAGE_SCHEMA_VERSION,
    CORE_FEATURE_STORAGE_TYPES,
    core_feature_select_sql,
    core_feature_storage_schema_matches,
)


def test_core_feature_storage_schema_is_symbol_time_plus_frozen_registry() -> None:
    expected_features = tuple(definition.name for definition in CORE_FEATURE_REGISTRY.all())
    assert CORE_FEATURE_STORAGE_SCHEMA_VERSION == "core-feature-storage-v1-symbol-time-33-double"
    assert CORE_FEATURE_STORAGE_COLUMNS == ("symbol", "timestamp_utc", *expected_features)
    assert len(expected_features) == 33
    assert len(CORE_FEATURE_STORAGE_COLUMNS) == 35


def test_core_feature_storage_types_are_explicit_and_stable() -> None:
    assert CORE_FEATURE_STORAGE_TYPES[:2] == ("VARCHAR", "TIMESTAMP WITH TIME ZONE")
    assert CORE_FEATURE_STORAGE_TYPES[2:] == ("DOUBLE",) * 33
    assert CORE_FEATURE_STORAGE_SCHEMA == tuple(
        zip(CORE_FEATURE_STORAGE_COLUMNS, CORE_FEATURE_STORAGE_TYPES)
    )


def test_core_feature_storage_schema_match_rejects_order_type_or_missing_columns() -> None:
    description = [(name, dtype, "YES", None, None, None) for name, dtype in CORE_FEATURE_STORAGE_SCHEMA]
    assert core_feature_storage_schema_matches(description) is True

    wrong_order = list(description)
    wrong_order[2], wrong_order[3] = wrong_order[3], wrong_order[2]
    assert core_feature_storage_schema_matches(wrong_order) is False

    wrong_type = list(description)
    wrong_type[2] = (wrong_type[2][0], "FLOAT", "YES", None, None, None)
    assert core_feature_storage_schema_matches(wrong_type) is False
    assert core_feature_storage_schema_matches(description[:-1]) is False


def test_core_feature_select_sql_casts_every_frozen_column() -> None:
    sql = core_feature_select_sql(table_alias="f")
    assert "CAST(f.symbol AS VARCHAR) AS symbol" in sql
    assert "CAST(f.timestamp_utc AS TIMESTAMPTZ) AS timestamp_utc" in sql
    for definition in CORE_FEATURE_REGISTRY.all():
        assert f'CAST(f."{definition.name}" AS DOUBLE) AS "{definition.name}"' in sql
