from __future__ import annotations

import numpy as np
import pytest

from packages.ml.evaluation import (
    ML_MULTICLASS_BRIER_NORMALIZATION,
    ML_PROBABILITY_ECE_BINS,
    ML_PROBABILITY_EVALUATION_CONTRACT_VERSION,
    ML_PROBABILITY_ROW_SUM_TOLERANCE,
    class_indices,
    probability_metrics,
    validate_probabilities,
)


def test_phase10_probability_evaluation_contract_is_locked() -> None:
    assert ML_PROBABILITY_EVALUATION_CONTRACT_VERSION == (
        "ml-probability-evaluation-v1-logloss-brier-auc-ece-accuracy"
    )
    assert ML_PROBABILITY_ECE_BINS == 15
    assert ML_MULTICLASS_BRIER_NORMALIZATION == "SUM_OVER_CLASSES_MEAN_OVER_ROWS"
    assert ML_PROBABILITY_ROW_SUM_TOLERANCE == 1e-6


def test_phase10_probability_metrics_reward_perfect_predictions() -> None:
    labels = np.asarray(["DOWN", "NEUTRAL", "UP", "DOWN", "UP"], dtype=object)
    probabilities = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    metrics = probability_metrics(labels, probabilities)
    assert metrics.rows == 5
    assert metrics.log_loss == pytest.approx(0.0, abs=1e-12)
    assert metrics.multiclass_brier == pytest.approx(0.0, abs=1e-12)
    assert metrics.accuracy == 1.0
    assert metrics.macro_ovr_auc == 1.0
    assert metrics.macro_ece == pytest.approx(0.0, abs=1e-12)


def test_phase10_probability_validation_normalizes_valid_float_roundoff() -> None:
    probabilities = np.asarray(
        [
            [0.20000002, 0.30000001, 0.49999999],
            [0.10000000, 0.20000000, 0.69999997],
        ],
        dtype=np.float64,
    )
    validated = validate_probabilities(probabilities)
    assert np.allclose(validated.sum(axis=1), 1.0, atol=1e-15, rtol=1e-15)
    assert np.all(validated >= 0.0)
    assert np.all(validated <= 1.0)


def test_phase10_probability_validation_rejects_bad_rows_and_labels() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        validate_probabilities(np.asarray([[0.2, 0.2, 0.2]], dtype=np.float64))
    with pytest.raises(ValueError, match="unknown prediction labels"):
        class_indices(np.asarray(["UP", "OTHER"], dtype=object))
