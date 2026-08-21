from __future__ import annotations

import numpy as np

from packages.features.historical_backfill_replay_validation_v2 import (
    GATE9_SENTINEL_ACCEPTANCE_ATOL,
    GATE9_SENTINEL_ACCEPTANCE_RTOL,
    feature_numeric_equivalence_diagnostics,
)


def _diagnostics(expected: np.ndarray, actual: np.ndarray) -> dict[str, object]:
    return feature_numeric_equivalence_diagnostics(
        expected,
        actual,
        [f"f{index}" for index in range(expected.shape[1])],
    )


def test_gate9_numeric_policy_accepts_machine_scale_rolling_path_variance() -> None:
    expected = np.array([[1.0, 100.0], [0.0, -2.0]], dtype="float64")
    actual = expected.copy()
    actual[0, 0] += 8.1e-9

    report = _diagnostics(expected, actual)

    assert GATE9_SENTINEL_ACCEPTANCE_ATOL == 1e-8
    assert GATE9_SENTINEL_ACCEPTANCE_RTOL == 1e-12
    assert report["strict_mismatches"] == 1
    assert report["acceptance_mismatches"] == 0
    assert report["nan_mask_mismatches"] == 0


def test_gate9_numeric_policy_rejects_difference_outside_locked_tolerance() -> None:
    expected = np.array([[1.0]], dtype="float64")
    actual = np.array([[1.0 + 2.0e-8]], dtype="float64")

    report = _diagnostics(expected, actual)

    assert report["acceptance_mismatches"] == 1
    assert float(report["max_abs_error"]) > GATE9_SENTINEL_ACCEPTANCE_ATOL


def test_gate9_numeric_policy_requires_exact_nan_mask() -> None:
    expected = np.array([[np.nan, 1.0], [2.0, np.nan]], dtype="float64")
    actual = np.array([[0.0, 1.0], [2.0, np.nan]], dtype="float64")

    report = _diagnostics(expected, actual)

    assert report["nan_mask_mismatches"] == 1
    assert report["acceptance_mismatches"] == 1


def test_gate9_numeric_policy_forbids_infinities_even_when_matching() -> None:
    expected = np.array([[np.inf]], dtype="float64")
    actual = np.array([[np.inf]], dtype="float64")

    report = _diagnostics(expected, actual)

    assert report["expected_infinite_values"] == 1
    assert report["actual_infinite_values"] == 1
