from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from packages.data.duckdb_connection import connect_utc
from packages.features.engine import compute_core_features
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.validation.cumulative_foundation import _deterministic_take, _partition_date
from packages.validation.cumulative_integrity import _daily_integrity_sql
from packages.validation.cumulative_policy import (
    CUMULATIVE_ALPACA_AUTHORITY_END,
    CUMULATIVE_AUDIT_BROKER_WRITES,
    CUMULATIVE_AUDIT_CANONICAL_WRITES,
    CUMULATIVE_AUDIT_EXTERNAL_PROVIDER_CALLS,
    CUMULATIVE_AUDIT_FEATURE_WRITES,
    CUMULATIVE_AUDIT_MODEL_WRITES,
    CUMULATIVE_AUDIT_REGIME_WRITES,
    CUMULATIVE_HISTORY_START,
    CUMULATIVE_INTRADAY_POLICY,
    CUMULATIVE_MARKET_SECTOR_REGIME_ORIGIN,
    CUMULATIVE_MASSIVE_AUTHORITY_START,
    CUMULATIVE_TICKER_REGIME_ORIGIN,
    cumulative_policy_fingerprint,
    validate_cumulative_policy,
)
from packages.validation.independent_features import replay_core_features


def _bars(rows: int = 360) -> pd.DataFrame:
    start = datetime(2024, 1, 2, 14, 30, tzinfo=UTC)
    data = []
    close = 100.0
    for i in range(rows):
        # deterministic, nontrivial path with both up/down moves and changing volume
        move = 0.45 * np.sin(i / 7.0) + 0.18 * np.cos(i / 13.0) + 0.02
        close = max(5.0, close + float(move))
        spread = 0.8 + 0.2 * abs(np.sin(i / 5.0))
        data.append(
            {
                "symbol": "TEST",
                "timestamp_utc": start + timedelta(days=i),
                "open": close - 0.1,
                "high": close + spread,
                "low": close - spread,
                "close": close,
                "volume": float(100_000 + (i % 37) * 1_337),
            }
        )
    return pd.DataFrame(data)


def test_cumulative_policy_locks_split_provider_and_regime_origins() -> None:
    validate_cumulative_policy()
    assert str(CUMULATIVE_HISTORY_START) == "2016-01-04"
    assert str(CUMULATIVE_ALPACA_AUTHORITY_END) == "2021-08-15"
    assert str(CUMULATIVE_MASSIVE_AUTHORITY_START) == "2021-08-16"
    assert CUMULATIVE_MARKET_SECTOR_REGIME_ORIGIN == CUMULATIVE_HISTORY_START
    assert CUMULATIVE_TICKER_REGIME_ORIGIN == CUMULATIVE_MASSIVE_AUTHORITY_START
    assert CUMULATIVE_INTRADAY_POLICY == "NO_SYNTHETIC_PRE2021_4H_OR_1H_FROM_DAILY_BACKFILL"
    assert len(cumulative_policy_fingerprint()) == 64


def test_cumulative_audit_is_read_only_and_offline() -> None:
    assert CUMULATIVE_AUDIT_CANONICAL_WRITES == 0
    assert CUMULATIVE_AUDIT_FEATURE_WRITES == 0
    assert CUMULATIVE_AUDIT_REGIME_WRITES == 0
    assert CUMULATIVE_AUDIT_MODEL_WRITES == 0
    assert CUMULATIVE_AUDIT_BROKER_WRITES == 0
    assert CUMULATIVE_AUDIT_EXTERNAL_PROVIDER_CALLS == 0


def test_deterministic_sampling_is_order_independent() -> None:
    values = ["A", "B", "C", "D", "E", "F"]
    assert _deterministic_take(values, 3, "x") == _deterministic_take(reversed(values), 3, "x")
    assert len(_deterministic_take(values, 3, "x")) == 3


def test_partition_date_parses_both_daily_and_intraday_layouts() -> None:
    assert _partition_date(Path("stocks/1d/year=2021/date=2021-08-16/part-000.parquet")).isoformat() == "2021-08-16"
    assert _partition_date(Path("bars/4h/year=2026/month=08/date=2026-08-14/part-000.parquet")).isoformat() == "2026-08-14"


def test_daily_integrity_sql_executes_against_canonical_transaction_count_schema() -> None:
    con = connect_utc(":memory:")
    try:
        con.execute(
            """
            CREATE TEMP VIEW daily AS
            SELECT
                'TEST'::VARCHAR AS symbol,
                TIMESTAMPTZ '2026-08-14 20:00:00+00' AS timestamp_utc,
                100.0::DOUBLE AS open,
                101.0::DOUBLE AS high,
                99.0::DOUBLE AS low,
                100.5::DOUBLE AS close,
                100000.0::DOUBLE AS volume,
                123::BIGINT AS transaction_count,
                'stocks/1d/year=2026/date=2026-08-14/part-000.parquet'::VARCHAR AS filename
            """
        )
        row = con.execute(_daily_integrity_sql()).fetchone()
    finally:
        con.close()
    assert row is not None
    assert int(row[0]) == 1
    assert int(row[7]) == 0
    assert int(row[8]) == 0


def test_independent_replay_matches_production_core33_on_synthetic_stream() -> None:
    source = _bars()
    production = compute_core_features(source.copy())
    replay = replay_core_features(source[["timestamp_utc", "high", "low", "close", "volume"]])
    names = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]
    assert len(names) == 33
    assert list(replay.columns) == ["timestamp_utc", *names]
    for name in names:
        np.testing.assert_allclose(
            production[name].to_numpy(dtype="float64", na_value=np.nan),
            replay[name].to_numpy(dtype="float64", na_value=np.nan),
            rtol=1e-10,
            atol=1e-12,
            equal_nan=True,
            err_msg=name,
        )
