from __future__ import annotations

import pandas as pd

from packages.analogues.policy import (
    PHASE12_ANALOGUE_TOP_K,
    PHASE12_MIN_ANALOGUES_FOR_DISTRIBUTION,
    PHASE12_PER_INSTRUMENT_CAP,
    PHASE12_SIMILARITY_FEATURES,
    phase12_policy_payload,
)
from packages.analogues.statistics import classify_quality, summarize_distribution


def test_phase12_policy_is_promoted_only_scale_stable_and_fixed() -> None:
    assert PHASE12_ANALOGUE_TOP_K == 200
    assert PHASE12_PER_INSTRUMENT_CAP == 3
    assert PHASE12_MIN_ANALOGUES_FOR_DISTRIBUTION == 50
    assert len(PHASE12_SIMILARITY_FEATURES) == 16
    assert "return_1" in PHASE12_SIMILARITY_FEATURES
    assert "natr_14" in PHASE12_SIMILARITY_FEATURES
    assert "directional_efficiency_20" in PHASE12_SIMILARITY_FEATURES
    for nominal_scale_feature in ("sma_20", "ema_20", "ema_50", "ema_200", "dollar_volume", "obv"):
        assert nominal_scale_feature not in PHASE12_SIMILARITY_FEATURES
    payload = phase12_policy_payload()
    assert payload["analogue_top_k"] == 200
    assert payload["production_ml_writes"] == 0
    assert payload["broker_writes"] == 0
    assert payload["trade_geometry_present"] is False


def test_analogue_distribution_uses_direction_adjusted_returns_and_inverse_distance_weights() -> None:
    frame = pd.DataFrame(
        {
            "instrument_id": ["i1", "i2", "i3"],
            "distance": [0.0, 1.0, 3.0],
            "direction_adjusted_return": [0.10, -0.05, 0.02],
        }
    )
    result = summarize_distribution(frame)
    assert result.rows == 3
    assert result.unique_instruments == 3
    assert result.mean_return == (0.10 - 0.05 + 0.02) / 3.0
    expected_weighted = (0.10 * 1.0 + -0.05 * 0.5 + 0.02 * 0.25) / 1.75
    assert abs(float(result.weighted_mean_return) - expected_weighted) < 1e-15
    assert result.positive_rate == 2.0 / 3.0
    assert result.worst_return == -0.05
    assert result.best_return == 0.10


def test_quality_is_insufficient_below_locked_minimum() -> None:
    analogues = pd.DataFrame(
        {
            "instrument_id": [f"i{x}" for x in range(10)],
            "session_date": pd.date_range("2025-01-01", periods=10, freq="D"),
            "distance": [float(x) / 10.0 for x in range(10)],
        }
    )
    paths = pd.DataFrame({"observation_key": [f"k{x}" for x in range(10)]})
    quality = classify_quality(analogues, paths)
    assert quality.status == "INSUFFICIENT"
    assert "ANALOGUE_COUNT_BELOW_PREREGISTERED_MINIMUM" in quality.reason_codes


def test_quality_can_be_robust_without_affecting_any_promotion_threshold() -> None:
    rows = 120
    analogues = pd.DataFrame(
        {
            "instrument_id": [f"i{x % 60}" for x in range(rows)],
            "session_date": pd.date_range("2025-01-01", periods=rows, freq="D"),
            "distance": [0.1 + x / 1000.0 for x in range(rows)],
        }
    )
    paths = pd.DataFrame({"observation_key": [f"k{x}" for x in range(100)]})
    quality = classify_quality(analogues, paths)
    assert quality.status == "ROBUST"
    assert quality.path_coverage == 100 / 120
