import math

import pytest

from packages.ml.outcome_family_audit import (
    ML_FEATURE_PARQUET_READ_MODE,
    ML_OUTCOME_FAMILY_AUDIT_CONTRACT_VERSION,
    ML_VOLATILITY_FEATURE,
    ML_VOLATILITY_HORIZON_SCALING,
    ML_VOLATILITY_THRESHOLD_GRID,
    classify_scaled_return,
    natr_values_match,
    scaled_move_threshold,
)


def test_phase10_outcome_family_audit_contract_is_explicit() -> None:
    assert ML_OUTCOME_FAMILY_AUDIT_CONTRACT_VERSION == (
        "ml-outcome-family-audit-v2-natr14-schema-reconciled-split-censored-grid"
    )
    assert ML_VOLATILITY_FEATURE == "natr_14"
    assert ML_VOLATILITY_HORIZON_SCALING == "sqrt_sessions"
    assert ML_FEATURE_PARQUET_READ_MODE == "union_by_name"


def test_phase10_outcome_family_threshold_grid_is_evidence_only() -> None:
    assert ML_VOLATILITY_THRESHOLD_GRID == (0.5, 1.0, 1.5, 2.0)


def test_phase10_scaled_move_threshold_uses_sqrt_horizon() -> None:
    assert scaled_move_threshold(
        natr_14=0.02,
        horizon_sessions=4,
        multiplier=1.5,
    ) == pytest.approx(0.02 * math.sqrt(4.0) * 1.5)


def test_phase10_scaled_return_classification_is_symmetric() -> None:
    kwargs = {"natr_14": 0.02, "horizon_sessions": 4, "multiplier": 1.0}
    assert classify_scaled_return(forward_return=0.05, **kwargs) == "UP"
    assert classify_scaled_return(forward_return=-0.05, **kwargs) == "DOWN"
    assert classify_scaled_return(forward_return=0.01, **kwargs) == "NEUTRAL"


def test_phase10_natr_integrity_tolerance_accepts_float_noise_only() -> None:
    assert natr_values_match(0.02000000001, 0.02)
    assert not natr_values_match(0.0, 0.02)
    assert not natr_values_match(1.0, 0.02)
