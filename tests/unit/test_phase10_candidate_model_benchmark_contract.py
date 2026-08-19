from __future__ import annotations

from packages.ml.baseline_policy import ML_BASELINE_POLICY_ACCEPTED
from packages.ml.candidate_model_benchmark import (
    ML_CANDIDATE_MODEL_BENCHMARK_CONTRACT_VERSION,
    ML_CANDIDATE_MODEL_BENCHMARK_FINAL_HOLDOUT_ACCESSED,
    ML_CANDIDATE_MODEL_BENCHMARK_FOLD_TEST_ACCESSED,
    ML_CANDIDATE_MODEL_BENCHMARK_MODEL_NAMES,
    ML_CANDIDATE_MODEL_BENCHMARK_SPECS,
    ML_CANDIDATE_MODEL_BENCHMARK_STATUS,
    ML_CANDIDATE_MODEL_BENCHMARK_TRAIN_CAP_ROWS,
)
from packages.ml.candidate_model_probe import ML_CANDIDATE_MODEL_SPECS
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT,
    ML_WALK_FORWARD_FINAL_HOLDOUT_START,
)


def test_phase10_gate9_full_benchmark_is_bounded_and_oos() -> None:
    assert ML_BASELINE_POLICY_ACCEPTED is True
    assert ML_CANDIDATE_MODEL_BENCHMARK_CONTRACT_VERSION == (
        "ml-candidate-model-benchmark-v1-hgb-two-capacities-1m-sampled-10fold-oos"
    )
    assert ML_CANDIDATE_MODEL_BENCHMARK_STATUS == "EVIDENCE_ONLY"
    assert ML_CANDIDATE_MODEL_BENCHMARK_TRAIN_CAP_ROWS == 1_000_000
    assert ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT == 10


def test_phase10_gate9_promotes_only_defensible_feasibility_candidates() -> None:
    assert ML_CANDIDATE_MODEL_BENCHMARK_MODEL_NAMES == (
        "hgb_leaf15_iter100",
        "hgb_leaf31_iter100",
    )
    assert tuple(spec.name for spec in ML_CANDIDATE_MODEL_BENCHMARK_SPECS) == (
        "hgb_leaf15_iter100",
        "hgb_leaf31_iter100",
    )
    assert "hgb_leaf31_iter200" in tuple(spec.name for spec in ML_CANDIDATE_MODEL_SPECS)
    assert "hgb_leaf31_iter200" not in ML_CANDIDATE_MODEL_BENCHMARK_MODEL_NAMES


def test_phase10_gate9_keeps_final_holdout_protected() -> None:
    assert ML_CANDIDATE_MODEL_BENCHMARK_FOLD_TEST_ACCESSED is True
    assert ML_CANDIDATE_MODEL_BENCHMARK_FINAL_HOLDOUT_ACCESSED is False
    assert ML_WALK_FORWARD_FINAL_HOLDOUT_START == "2026-05-12"


def test_phase10_gate9_candidates_keep_probe_regularization_semantics() -> None:
    assert all(spec.learning_rate == 0.05 for spec in ML_CANDIDATE_MODEL_BENCHMARK_SPECS)
    assert all(spec.min_samples_leaf == 100 for spec in ML_CANDIDATE_MODEL_BENCHMARK_SPECS)
    assert all(spec.l2_regularization == 1.0 for spec in ML_CANDIDATE_MODEL_BENCHMARK_SPECS)
    assert all(spec.max_iter == 100 for spec in ML_CANDIDATE_MODEL_BENCHMARK_SPECS)
