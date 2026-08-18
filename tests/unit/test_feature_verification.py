from __future__ import annotations

import pandas as pd

from packages.features.verification import first_market_key_difference, market_key_series_equal


def test_market_key_comparison_ignores_equivalent_string_storage_dtypes():
    pandas_string = pd.Series(["AAPL", "TpC"], dtype="string")
    duckdb_like_object = pd.Series(["AAPL", "TpC"], dtype="object")

    assert market_key_series_equal(pandas_string, duckdb_like_object, "symbol")
    assert market_key_series_equal(pandas_string, duckdb_like_object, "session_segment")


def test_market_key_comparison_canonicalizes_utc_timestamps():
    timestamps = pd.Series(
        pd.to_datetime(
            ["2021-09-13T13:30:00Z", "2021-09-13T17:30:00Z"],
            utc=True,
        )
    )
    equivalent_text = pd.Series(
        ["2021-09-13 13:30:00+00:00", "2021-09-13 17:30:00+00:00"],
        dtype="object",
    )

    assert market_key_series_equal(timestamps, equivalent_text, "timestamp_utc")


def test_market_key_comparison_reports_real_value_difference():
    expected = pd.Series(["AAPL", "MSFT"], dtype="string")
    persisted = pd.Series(["AAPL", "META"], dtype="object")

    assert not market_key_series_equal(expected, persisted, "symbol")
    assert first_market_key_difference(expected, persisted, "symbol") == (1, "MSFT", "META")
