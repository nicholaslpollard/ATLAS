from __future__ import annotations

import numpy as np
import pandas as pd

from packages.ml.robustness_audit import (
    ML_ROBUSTNESS_AUDIT_CONTRACT_VERSION,
    ML_ROBUSTNESS_CONFIDENCE_BUCKETS,
    ML_ROBUSTNESS_FINAL_HOLDOUT_ACCESSED,
    ML_ROBUSTNESS_LIQUIDITY_BUCKETS,
    ML_ROBUSTNESS_SEGMENT_FAMILIES,
    ML_ROBUSTNESS_SOURCE_PROBABILITIES,
    ML_ROBUSTNESS_UNAVAILABLE_SEGMENTS,
    ML_ROBUSTNESS_VOLATILITY_BUCKETS,
    _confidence_bucket,
    _liquidity_bucket,
    _volatility_bucket,
)


def test_phase10_gate11_uses_only_accepted_point_in_time_segment_families() -> None:
    assert ML_ROBUSTNESS_AUDIT_CONTRACT_VERSION == (
        "ml-robustness-audit-v1-raw-hgb-oos-market-liquidity-volatility-direction-time"
    )
    assert ML_ROBUSTNESS_SOURCE_PROBABILITIES == "GATE9_RAW_TEST_ARTIFACTS"
    assert "market_regime_composite" in ML_ROBUSTNESS_SEGMENT_FAMILIES
    assert "liquidity_bucket" in ML_ROBUSTNESS_SEGMENT_FAMILIES
    assert "volatility_bucket" in ML_ROBUSTNESS_SEGMENT_FAMILIES
    assert ML_ROBUSTNESS_UNAVAILABLE_SEGMENTS == (
        "sector_regime",
        "ticker_regime",
        "risk_mode",
        "security_type",
    )
    assert ML_ROBUSTNESS_FINAL_HOLDOUT_ACCESSED is False


def test_phase10_gate11_fixed_liquidity_and_volatility_buckets_are_deterministic() -> None:
    liquidity = _liquidity_bucket(pd.Series([250_000.0, 1_000_000.0, 5_000_000.0, 25_000_000.0]))
    volatility = _volatility_bucket(pd.Series([0.005, 0.01, 0.02, 0.04]))
    assert tuple(liquidity) == ML_ROBUSTNESS_LIQUIDITY_BUCKETS
    assert tuple(volatility) == ML_ROBUSTNESS_VOLATILITY_BUCKETS


def test_phase10_gate11_confidence_buckets_are_fixed_before_evidence() -> None:
    probabilities = np.asarray(
        [
            [0.34, 0.33, 0.33],
            [0.20, 0.55, 0.25],
            [0.15, 0.20, 0.65],
            [0.10, 0.15, 0.75],
        ],
        dtype=np.float64,
    )
    assert tuple(_confidence_bucket(probabilities)) == ML_ROBUSTNESS_CONFIDENCE_BUCKETS
