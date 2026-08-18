from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from packages.features.engine import compute_core_features
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.incremental import IncrementalFeatureEngine


def test_incremental_engine_matches_batch_feature_contract_bar_for_bar():
    rng = np.random.default_rng(20260816)
    count = 260
    returns = rng.normal(loc=0.0004, scale=0.012, size=count)
    close = 100.0 * np.exp(np.cumsum(returns))
    upper = rng.uniform(0.001, 0.02, size=count)
    lower = rng.uniform(0.001, 0.02, size=count)
    high = close * (1.0 + upper)
    low = close * (1.0 - lower)
    volume = rng.integers(10_000, 2_000_000, size=count).astype("float64")
    start = datetime(2025, 1, 2, 14, 30, tzinfo=UTC)

    frame = pd.DataFrame(
        {
            "symbol": ["TpC"] * count,
            "timestamp_utc": [start + timedelta(minutes=index) for index in range(count)],
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )
    batch = compute_core_features(frame)

    incremental = IncrementalFeatureEngine()
    rows: list[dict[str, float | None]] = []
    for row in frame.itertuples(index=False):
        rows.append(
            incremental.update(
                symbol=row.symbol,
                timestamp_utc=row.timestamp_utc,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
        )

    streamed = pd.DataFrame(rows, dtype="float64")
    for definition in CORE_FEATURE_REGISTRY.all():
        np.testing.assert_allclose(
            streamed[definition.name].to_numpy(dtype="float64"),
            batch[definition.name].to_numpy(dtype="float64"),
            rtol=1e-12,
            atol=1e-12,
            equal_nan=True,
            err_msg=f"incremental mismatch for {definition.name}",
        )
    assert incremental.symbol_count == 1


def test_incremental_state_is_case_sensitive_and_symbol_local():
    engine = IncrementalFeatureEngine()
    start = datetime(2026, 8, 14, 13, 30, tzinfo=UTC)
    first = engine.update(symbol="TPC", timestamp_utc=start, high=101, low=99, close=100, volume=1000)
    second = engine.update(symbol="TpC", timestamp_utc=start, high=11, low=9, close=10, volume=2000)
    assert first["obv"] == 0.0
    assert second["obv"] == 0.0
    assert engine.symbol_count == 2
