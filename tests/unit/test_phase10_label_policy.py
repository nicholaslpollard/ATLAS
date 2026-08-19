import math

import pytest

from packages.ml.label_policy import (
    ML_PREDICTION_LABEL_ADJACENT_OVERLAP_SESSIONS,
    ML_PREDICTION_LABEL_CLASSES,
    ML_PREDICTION_LABEL_HORIZON_SESSIONS,
    ML_PREDICTION_LABEL_NEUTRAL_RETAINED,
    ML_PREDICTION_LABEL_POLICY_ACCEPTED,
    ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION,
    ML_PREDICTION_LABEL_PROBABILITY_FIELDS,
    ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER,
    classify_prediction_label,
    prediction_label_threshold,
)


def test_phase10_gate4_prediction_label_policy_is_locked() -> None:
    assert ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION == (
        "ml-prediction-label-policy-v1-3session-0.5natr-three-class-endpoint"
    )
    assert ML_PREDICTION_LABEL_POLICY_ACCEPTED is True
    assert ML_PREDICTION_LABEL_HORIZON_SESSIONS == 3
    assert ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER == 0.5
    assert ML_PREDICTION_LABEL_CLASSES == ("DOWN", "NEUTRAL", "UP")
    assert ML_PREDICTION_LABEL_PROBABILITY_FIELDS == ("p_down", "p_neutral", "p_up")
    assert ML_PREDICTION_LABEL_NEUTRAL_RETAINED is True
    assert ML_PREDICTION_LABEL_ADJACENT_OVERLAP_SESSIONS == 2


def test_phase10_gate4_threshold_uses_observation_natr_and_sqrt_three() -> None:
    assert prediction_label_threshold(0.02) == pytest.approx(0.02 * math.sqrt(3.0) * 0.5)


def test_phase10_gate4_three_class_boundaries_are_symmetric() -> None:
    threshold = prediction_label_threshold(0.02)
    assert classify_prediction_label(forward_return=threshold, natr_14=0.02) == "UP"
    assert classify_prediction_label(forward_return=-threshold, natr_14=0.02) == "DOWN"
    assert classify_prediction_label(forward_return=0.0, natr_14=0.02) == "NEUTRAL"
