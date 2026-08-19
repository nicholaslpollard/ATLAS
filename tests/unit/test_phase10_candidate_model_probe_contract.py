from __future__ import annotations

from packages.ml.candidate_model_probe import (
    ML_CANDIDATE_MODEL_FAMILY,
    ML_CANDIDATE_MODEL_FINAL_HOLDOUT_ACCESSED,
    ML_CANDIDATE_MODEL_HASH_BUCKETS,
    ML_CANDIDATE_MODEL_PROBE_CONTRACT_VERSION,
    ML_CANDIDATE_MODEL_PROBE_FOLD,
    ML_CANDIDATE_MODEL_SPECS,
    ML_CANDIDATE_MODEL_TEST_ACCESSED,
    ML_CANDIDATE_MODEL_TRAIN_SAMPLE_TARGET,
)


def test_phase10_gate9_probe_is_bounded_to_training_and_validation() -> None:
    assert ML_CANDIDATE_MODEL_PROBE_CONTRACT_VERSION == (
        "ml-candidate-model-probe-v1-hgb-fold1-train-validation-sampled"
    )
    assert ML_CANDIDATE_MODEL_PROBE_FOLD == 1
    assert ML_CANDIDATE_MODEL_TEST_ACCESSED is False
    assert ML_CANDIDATE_MODEL_FINAL_HOLDOUT_ACCESSED is False
    assert ML_CANDIDATE_MODEL_TRAIN_SAMPLE_TARGET == 500_000
    assert ML_CANDIDATE_MODEL_HASH_BUCKETS == 1_000_000


def test_phase10_gate9_probe_uses_small_fixed_hist_gradient_boosting_grid() -> None:
    assert ML_CANDIDATE_MODEL_FAMILY == "sklearn_hist_gradient_boosting"
    assert tuple(spec.name for spec in ML_CANDIDATE_MODEL_SPECS) == (
        "hgb_leaf15_iter100",
        "hgb_leaf31_iter100",
        "hgb_leaf31_iter200",
    )
    assert all(spec.learning_rate == 0.05 for spec in ML_CANDIDATE_MODEL_SPECS)
    assert all(spec.min_samples_leaf == 100 for spec in ML_CANDIDATE_MODEL_SPECS)
    assert all(spec.l2_regularization == 1.0 for spec in ML_CANDIDATE_MODEL_SPECS)


def test_phase10_gate9_probe_increases_capacity_without_family_sprawl() -> None:
    capacities = [(spec.max_leaf_nodes, spec.max_iter) for spec in ML_CANDIDATE_MODEL_SPECS]
    assert capacities == [(15, 100), (31, 100), (31, 200)]
    assert len(ML_CANDIDATE_MODEL_SPECS) == 3
