from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.ml.calibration_benchmark import (
    ML_CALIBRATION_BENCHMARK_CONTRACT_VERSION,
    ML_CALIBRATION_BENCHMARK_STATUS,
    ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED,
    ML_CALIBRATION_METHODS,
    ML_CALIBRATION_TEST_ONLY_SCORE,
    ML_CALIBRATION_VALIDATION_ONLY_FIT,
)
from packages.ml.candidate_model_policy import (
    ML_CANDIDATE_MODEL_ACCEPTED_FOLDS,
    ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
    ML_CANDIDATE_MODEL_ACCEPTED_OOS_ROWS,
    ML_CANDIDATE_MODEL_POLICY_ACCEPTED,
    ML_CANDIDATE_MODEL_POLICY_CONTRACT_VERSION,
)
from packages.ml.walk_forward_policy import ML_WALK_FORWARD_FINAL_HOLDOUT_START


def main() -> int:
    assert ML_CANDIDATE_MODEL_POLICY_ACCEPTED is True
    assert ML_CANDIDATE_MODEL_POLICY_CONTRACT_VERSION == (
        "ml-candidate-model-policy-v1-hgb-leaf15-probability-quality-winner"
    )
    assert ML_CANDIDATE_MODEL_ACCEPTED_MODEL == "hgb_leaf15_iter100"
    assert ML_CANDIDATE_MODEL_ACCEPTED_FOLDS == 10
    assert ML_CANDIDATE_MODEL_ACCEPTED_OOS_ROWS == 3_978_577
    assert ML_CALIBRATION_BENCHMARK_CONTRACT_VERSION == (
        "ml-calibration-benchmark-v1-raw-platt-isotonic-validation-fit-test-score"
    )
    assert ML_CALIBRATION_BENCHMARK_STATUS == "EVIDENCE_ONLY"
    assert ML_CALIBRATION_METHODS == ("raw", "ovr_platt", "ovr_isotonic")
    assert ML_CALIBRATION_VALIDATION_ONLY_FIT is True
    assert ML_CALIBRATION_TEST_ONLY_SCORE is True
    assert ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED is False

    print(f"ML Gate 9 candidate policy: {ML_CANDIDATE_MODEL_POLICY_CONTRACT_VERSION}")
    print(f"ML Gate 9 accepted model: {ML_CANDIDATE_MODEL_ACCEPTED_MODEL}")
    print(
        "ML Gate 9 accepted OOS scope: "
        f"folds={ML_CANDIDATE_MODEL_ACCEPTED_FOLDS} / rows={ML_CANDIDATE_MODEL_ACCEPTED_OOS_ROWS:,}"
    )
    print(f"ML Gate 10 calibration benchmark: {ML_CALIBRATION_BENCHMARK_CONTRACT_VERSION}")
    print(f"ML Gate 10 methods: {ML_CALIBRATION_METHODS}")
    print("ML Gate 10 chronology: fit=VALIDATION_ONLY / score=FROZEN_TEST_ONLY")
    print(
        "ML Gate 10 final holdout: "
        f"start={ML_WALK_FORWARD_FINAL_HOLDOUT_START} / accessed={ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED}"
    )
    print("ML Gate 9 candidate model benchmark: ACCEPTED")
    print("ML Gate 10 probability calibration policy: CURRENT; target-machine benchmark not yet run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
