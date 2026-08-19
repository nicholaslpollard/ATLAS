from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
from packages.ml.evaluation import (
    ML_MULTICLASS_BRIER_NORMALIZATION,
    ML_PROBABILITY_ECE_BINS,
    ML_PROBABILITY_EVALUATION_CONTRACT_VERSION,
)
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_COUNT
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT,
    ML_WALK_FORWARD_ACCEPTED_TOTAL_TEST_ROWS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_START,
    ML_WALK_FORWARD_POLICY_ACCEPTED,
    ML_WALK_FORWARD_POLICY_CONTRACT_VERSION,
)


def main() -> int:
    assert ML_WALK_FORWARD_POLICY_ACCEPTED is True
    assert ML_BASELINE_BENCHMARK_CONTRACT_VERSION == (
        "ml-baseline-benchmark-v1-train-prior-sgd-l2-streaming-oos"
    )
    assert ML_BASELINE_BENCHMARK_STATUS == "EVIDENCE_ONLY"
    assert ML_PROBABILITY_EVALUATION_CONTRACT_VERSION == (
        "ml-probability-evaluation-v1-logloss-brier-auc-ece-accuracy"
    )
    assert ML_PROBABILITY_ECE_BINS == 15
    assert ML_MULTICLASS_BRIER_NORMALIZATION == "SUM_OVER_CLASSES_MEAN_OVER_ROWS"
    assert ML_PRODUCTION_CORE_FEATURE_COUNT == 33
    assert ML_BASELINE_MODELS == (ML_BASELINE_PRIOR_MODEL, ML_BASELINE_LINEAR_MODEL)
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
    assert ML_BASELINE_FINAL_HOLDOUT_ACCESSED is False
    assert ML_WALK_FORWARD_FINAL_HOLDOUT_START == "2026-05-12"

    print(f"ML Gate 8 baseline benchmark: {ML_BASELINE_BENCHMARK_CONTRACT_VERSION}")
    print(f"ML Gate 8 probability evaluation: {ML_PROBABILITY_EVALUATION_CONTRACT_VERSION}")
    print(f"ML Gate 8 walk-forward policy: {ML_WALK_FORWARD_POLICY_CONTRACT_VERSION}")
    print(f"ML Gate 8 models: {ML_BASELINE_MODELS}")
    print(
        "ML Gate 8 linear baseline: "
        f"loss={ML_BASELINE_LINEAR_LOSS} / penalty={ML_BASELINE_LINEAR_PENALTY} / "
        f"alpha={ML_BASELINE_LINEAR_ALPHA} / average={ML_BASELINE_LINEAR_AVERAGE}"
    )
    print(
        "ML Gate 8 training semantics: "
        f"epochs={ML_BASELINE_LINEAR_TRAINING_EPOCHS} / chunk_sessions={ML_BASELINE_LINEAR_CHUNK_SESSIONS} / "
        f"class_weight={ML_BASELINE_LINEAR_CLASS_WEIGHT} / resampling={ML_BASELINE_LINEAR_RESAMPLING}"
    )
    print(
        "ML Gate 8 OOS scope: "
        f"folds={ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT} / test_rows={ML_WALK_FORWARD_ACCEPTED_TOTAL_TEST_ROWS:,}"
    )
    print(
        "ML Gate 8 final holdout: "
        f"start={ML_WALK_FORWARD_FINAL_HOLDOUT_START} / rows={ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS:,} / accessed=False"
    )
    print("ML Gate 8 baseline benchmark foundation: PASS")
    print("ML Gate 8 baseline probability models: CURRENT; target-machine benchmark not yet run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
