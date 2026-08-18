from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def _canonical_key_values(values: pd.Series, column: str) -> list[object]:
    """Return dtype-independent canonical values for persisted market-key checks.

    DuckDB and pandas can represent the same textual/timestamp values with different
    dtypes (for example object versus pandas StringDtype, or different datetime
    resolutions). Verification is about key value identity, not dataframe storage
    dtype identity.
    """

    if column == "timestamp_utc":
        timestamps = pd.to_datetime(values, utc=True, errors="raise")
        return [timestamp.isoformat() for timestamp in timestamps]
    if column in {"symbol", "session_segment"}:
        normalized = values.astype("string")
        if normalized.isna().any():
            raise ValueError(f"market key {column} contains null values")
        return normalized.tolist()
    return values.tolist()


def market_key_series_equal(left: pd.Series, right: pd.Series, column: str) -> bool:
    if len(left) != len(right):
        return False
    return _canonical_key_values(left, column) == _canonical_key_values(right, column)


def first_market_key_difference(
    left: pd.Series,
    right: pd.Series,
    column: str,
) -> tuple[int, object | None, object | None] | None:
    left_values = _canonical_key_values(left, column)
    right_values = _canonical_key_values(right, column)
    limit = min(len(left_values), len(right_values))
    for index in range(limit):
        if left_values[index] != right_values[index]:
            return index, left_values[index], right_values[index]
    if len(left_values) != len(right_values):
        left_value = left_values[limit] if limit < len(left_values) else None
        right_value = right_values[limit] if limit < len(right_values) else None
        return limit, left_value, right_value
    return None
