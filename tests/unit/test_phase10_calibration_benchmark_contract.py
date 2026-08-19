from __future__ import annotations

import numpy as np

from packages.ml.calibration_benchmark import (
    ML_CALIBRATION_BENCHMARK_CONTRACT_VERSION,
    ML_CALIBRATION_BENCHMARK_STATUS,
    ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED,
    ML_CALIBRATION_METHODS,
    ML_CALIBRATION_TEST_ONLY_SCORE,
    ML_CALIBRATION_VALIDATION_ONLY_FIT,
    MLCalibrationBenchmark,
    _normalize_scores,
)


def test_phase10_gate10_calibration_contract_is_chronological_and_bounded() -> None:
    assert ML_CALIBRATION_BENCHMARK_CONTRACT_VERSION == (
        "ml-calibration-benchmark-v1-raw-platt-isotonic-validation-fit-test-score"
    )
    assert ML_CALIBRATION_BENCHMARK_STATUS == "EVIDENCE_ONLY"
    assert ML_CALIBRATION_METHODS == ("raw", "ovr_platt", "ovr_isotonic")
    assert ML_CALIBRATION_VALIDATION_ONLY_FIT is True
    assert ML_CALIBRATION_TEST_ONLY_SCORE is True
    assert ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED is False


def test_phase10_gate10_score_normalization_returns_valid_probabilities() -> None:
    scores = np.asarray([[2.0, 1.0, 1.0], [0.1, 0.3, 0.6]], dtype=np.float64)
    probabilities = _normalize_scores(scores)
    assert probabilities.shape == (2, 3)
    assert np.all(np.isfinite(probabilities))
    assert np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-12)


def test_phase10_gate10_platt_and_isotonic_transform_without_test_labels() -> None:
    labels = np.asarray((["DOWN", "NEUTRAL", "UP"] * 20), dtype=object)
    validation = np.tile(
        np.asarray(
            [
                [0.55, 0.30, 0.15],
                [0.20, 0.60, 0.20],
                [0.15, 0.30, 0.55],
            ],
            dtype=np.float64,
        ),
        (20, 1),
    )
    test = np.asarray(
        [
            [0.40, 0.40, 0.20],
            [0.20, 0.50, 0.30],
            [0.25, 0.25, 0.50],
        ],
        dtype=np.float64,
    )
    platt, coefficients, intercepts = MLCalibrationBenchmark._platt(labels, validation, test)
    isotonic, knot_counts = MLCalibrationBenchmark._isotonic(labels, validation, test)
    assert platt.shape == test.shape
    assert isotonic.shape == test.shape
    assert np.allclose(platt.sum(axis=1), 1.0, atol=1e-12)
    assert np.allclose(isotonic.sum(axis=1), 1.0, atol=1e-12)
    assert len(coefficients) == len(intercepts) == len(knot_counts) == 3
