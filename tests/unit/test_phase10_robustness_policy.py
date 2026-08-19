from __future__ import annotations

from packages.ml.robustness_policy import (
    ML_GATE12_MODEL_REGISTRY_CURRENT,
    ML_ROBUSTNESS_ACCEPTED_FOLDS,
    ML_ROBUSTNESS_ACCEPTED_OOS_ROWS,
    ML_ROBUSTNESS_ARGMAX_IS_PRODUCTION_SIGNAL,
    ML_ROBUSTNESS_ARGMAX_NEUTRAL_FRACTION,
    ML_ROBUSTNESS_FINAL_HOLDOUT_ACCESSED,
    ML_ROBUSTNESS_MARKET_CONTEXT_FRACTION,
    ML_ROBUSTNESS_POLICY_ACCEPTED,
    ML_ROBUSTNESS_POLICY_CONTRACT_VERSION,
    ML_ROBUSTNESS_PROBABILITY_SURFACE_IS_PRODUCTION_EVIDENCE,
    ML_ROBUSTNESS_UNAVAILABLE_SEGMENTS,
    ML_ROBUSTNESS_WEAKEST_SUPPORTED_AUC,
    ML_ROBUSTNESS_WEAKEST_SUPPORTED_AUC_FAMILY,
    ML_ROBUSTNESS_WEAKEST_SUPPORTED_AUC_VALUE,
)


def test_phase10_gate11_robustness_policy_accepts_probability_role() -> None:
    assert ML_ROBUSTNESS_POLICY_CONTRACT_VERSION == (
        "ml-robustness-policy-v1-accepted-probability-role-with-segment-caveats"
    )
    assert ML_ROBUSTNESS_POLICY_ACCEPTED is True
    assert ML_ROBUSTNESS_ACCEPTED_FOLDS == 10
    assert ML_ROBUSTNESS_ACCEPTED_OOS_ROWS == 3_978_577
    assert ML_ROBUSTNESS_MARKET_CONTEXT_FRACTION == 1.0
    assert ML_ROBUSTNESS_FINAL_HOLDOUT_ACCESSED is False


def test_phase10_gate11_argmax_is_diagnostic_not_production_signal() -> None:
    assert ML_ROBUSTNESS_ARGMAX_NEUTRAL_FRACTION > 0.99
    assert ML_ROBUSTNESS_ARGMAX_IS_PRODUCTION_SIGNAL is False
    assert ML_ROBUSTNESS_PROBABILITY_SURFACE_IS_PRODUCTION_EVIDENCE is True


def test_phase10_gate11_locks_weakest_supported_segment_and_missing_metadata() -> None:
    assert ML_ROBUSTNESS_WEAKEST_SUPPORTED_AUC_FAMILY == "volatility_bucket"
    assert ML_ROBUSTNESS_WEAKEST_SUPPORTED_AUC_VALUE == "2_TO_4PCT"
    assert ML_ROBUSTNESS_WEAKEST_SUPPORTED_AUC > 0.50
    assert ML_ROBUSTNESS_UNAVAILABLE_SEGMENTS == (
        "sector_regime",
        "ticker_regime",
        "risk_mode",
        "security_type",
    )
    assert ML_GATE12_MODEL_REGISTRY_CURRENT is True
