from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from packages.features.engine import compute_core_features, compute_core_features_reference
from packages.features.feature_registry import CORE_FEATURE_REGISTRY


FEATURE_NAMES = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]


def _assert_exact_feature_parity(frame: pd.DataFrame) -> None:
    reference = compute_core_features_reference(frame)
    optimized = compute_core_features(frame)

    assert reference.columns.tolist() == optimized.columns.tolist()
    assert reference.attrs == optimized.attrs
    assert reference[["symbol", "timestamp_utc"]].equals(
        optimized[["symbol", "timestamp_utc"]]
    )
    if "session_segment" in reference.columns:
        assert reference["session_segment"].equals(optimized["session_segment"])

    for name in FEATURE_NAMES:
        np.testing.assert_allclose(
            optimized[name].to_numpy(dtype="float64"),
            reference[name].to_numpy(dtype="float64"),
            rtol=1e-10,
            atol=1e-10,
            equal_nan=True,
        )


def test_optimized_batch_matches_reference_after_full_daily_warmup() -> None:
    rows: list[dict[str, object]] = []
    start = datetime(2025, 1, 2, 21, 0, tzinfo=UTC)
    for offset in range(260):
        for symbol, base in (("ABC", 50.0), ("AbC", 125.0), ("XYZ", 300.0)):
            close = base + offset * 0.17 + ((offset % 11) - 5) * 0.09
            rows.append(
                {
                    "symbol": symbol,
                    "timestamp_utc": start + timedelta(days=offset),
                    "high": close + 1.25,
                    "low": close - 1.10,
                    "close": close,
                    "volume": float(100_000 + offset * 37 + len(symbol) * 100),
                }
            )

    frame = pd.DataFrame.from_records(rows).sample(frac=1.0, random_state=19).reset_index(drop=True)
    _assert_exact_feature_parity(frame)


def test_optimized_batch_matches_reference_for_independent_session_segments() -> None:
    rows: list[dict[str, object]] = []
    start = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
    for segment_index, segment in enumerate(("premarket", "regular", "after_hours")):
        for offset in range(220):
            base = 80.0 + segment_index * 25.0
            close = base + offset * 0.04 + ((offset % 9) - 4) * 0.03
            rows.append(
                {
                    "symbol": "MiXeD",
                    "session_segment": segment,
                    "timestamp_utc": start + timedelta(minutes=offset),
                    "high": close + 0.55,
                    "low": close - 0.45,
                    "close": close,
                    "volume": float(25_000 + segment_index * 5_000 + offset * 13),
                }
            )

    frame = pd.DataFrame.from_records(rows).sample(frac=1.0, random_state=23).reset_index(drop=True)
    _assert_exact_feature_parity(frame)
