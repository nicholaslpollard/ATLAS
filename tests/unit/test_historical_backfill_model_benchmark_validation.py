from __future__ import annotations

import numpy as np

from packages.ml.historical_backfill_model_benchmark_validation import (
    HISTORICAL_BACKFILL_ECE_BINS,
    HISTORICAL_BACKFILL_VALIDATION_TOLERANCE,
    _close,
    _independent_metrics,
    _key_hash,
)


def test_independent_metrics_match_simple_three_class_case() -> None:
    labels = np.asarray(["DOWN", "NEUTRAL", "UP"], dtype=object)
    probabilities = np.asarray(
        [
            [0.8, 0.1, 0.1],
            [0.1, 0.8, 0.1],
            [0.1, 0.1, 0.8],
        ],
        dtype=np.float64,
    )
    metrics = _independent_metrics(labels, probabilities)
    assert metrics["rows"] == 3
    assert abs(float(metrics["log_loss"]) - (-np.log(0.8))) < 1e-12
    assert abs(float(metrics["multiclass_brier"]) - 0.06) < 1e-12
    assert metrics["accuracy"] == 1.0
    assert metrics["macro_ovr_auc"] == 1.0
    assert 0.0 <= float(metrics["macro_ece"]) <= 1.0


def test_independent_key_hash_is_order_sensitive_and_deterministic() -> None:
    first = _key_hash(["a", "b", "c"])
    assert first == _key_hash(["a", "b", "c"])
    assert first != _key_hash(["c", "b", "a"])
    assert len(first) == 64
    int(first, 16)


def test_validation_tolerance_is_strict() -> None:
    assert HISTORICAL_BACKFILL_VALIDATION_TOLERANCE == 1e-12
    assert _close(1.0, 1.0 + 5e-13)
    assert not _close(1.0, 1.0 + 2e-12)
    assert HISTORICAL_BACKFILL_ECE_BINS == 15
