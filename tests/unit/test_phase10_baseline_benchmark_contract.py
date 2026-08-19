from __future__ import annotations

from packages.ml.baseline_benchmark import (
    ML_BASELINE_BENCHMARK_CONTRACT_VERSION,
    ML_BASELINE_BENCHMARK_STATUS,
    ML_BASELINE_FINAL_HOLDOUT_ACCESSED,
    ML_BASELINE_LINEAR_ALPHA,
    ML_BASELINE_LINEAR_AVERAGE,
    ML_BASELINE_LINEAR_CHUNK_SESSIONS,
    ML_BASELINE_LINEAR_CLASS_WEIGHT,
    ML_BASELINE_LINEAR_FEATURE_SCALING,
    ML_BASELINE_LINEAR_LOSS,
    ML_BASELINE_LINEAR_MODEL,
    ML_BASELINE_LINEAR_PENALTY,
    ML_BASELINE_LINEAR_RANDOM_STATE,
    ML_BASELINE_LINEAR_RESAMPLING,
    ML_BASELINE_LINEAR_TRAINING_EPOCHS,
    ML_BASELINE_MODELS,
    ML_BASELINE_PRIOR_MODEL,
)
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_ACCEPTED_CANDIDATE,
    ML_WALK_FORWARD_FINAL_HOLDOUT_START,
    ML_WALK_FORWARD_POLICY_ACCEPTED,
)


def test_phase10_gate8_baseline_contract_uses_simple_probability_floors() -> None:
    assert ML_BASELINE_BENCHMARK_CONTRACT_VERSION == (
        "ml-baseline-benchmark-v1-train-prior-sgd-l2-streaming-oos"
    )
    assert ML_BASELINE_BENCHMARK_STATUS == "EVIDENCE_ONLY"
    assert ML_BASELINE_MODELS == (ML_BASELINE_PRIOR_MODEL, ML_BASELINE_LINEAR_MODEL)
    assert ML_BASELINE_PRIOR_MODEL == "train_class_prior"
    assert ML_BASELINE_LINEAR_MODEL == "sgd_logistic_l2"
    assert len(ML_PRODUCTION_CORE_FEATURE_NAMES) == 33


def test_phase10_gate8_linear_baseline_is_fixed_regularized_and_unweighted() -> None:
    assert ML_BASELINE_LINEAR_LOSS == "log_loss"
    assert ML_BASELINE_LINEAR_PENALTY == "l2"
    assert ML_BASELINE_LINEAR_ALPHA == 1e-4
    assert ML_BASELINE_LINEAR_AVERAGE is True
    assert ML_BASELINE_LINEAR_RANDOM_STATE == 42
    assert ML_BASELINE_LINEAR_TRAINING_EPOCHS == 1
    assert ML_BASELINE_LINEAR_CHUNK_SESSIONS == 21
    assert ML_BASELINE_LINEAR_CLASS_WEIGHT is None
    assert ML_BASELINE_LINEAR_RESAMPLING == "NONE"
    assert ML_BASELINE_LINEAR_FEATURE_SCALING == "TRAIN_ONLY_MEAN_STD"


def test_phase10_gate8_respects_gate7_and_blocks_final_holdout() -> None:
    assert ML_WALK_FORWARD_POLICY_ACCEPTED is True
    assert ML_WALK_FORWARD_ACCEPTED_CANDIDATE == "quarterly-train252"
    assert ML_WALK_FORWARD_FINAL_HOLDOUT_START == "2026-05-12"
    assert ML_BASELINE_FINAL_HOLDOUT_ACCESSED is False
