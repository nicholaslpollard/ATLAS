from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.ml.calibration_policy import (
    ML_CALIBRATION_ACCEPTED_METHOD,
    ML_CALIBRATION_POLICY_ACCEPTED,
)
from packages.ml.candidate_model_policy import (
    ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
    ML_CANDIDATE_MODEL_POLICY_ACCEPTED,
)
from packages.ml.model_registry import (
    ML_IMMUTABLE_PREDICTION_CONTRACT_VERSION,
    ML_MODEL_REGISTRY_CONTRACT_VERSION,
    ML_MODEL_REGISTRY_FINAL_FIT_ARTIFACT_PRESENT,
    ML_MODEL_REGISTRY_FINAL_HOLDOUT_ACCESSED,
    ML_MODEL_REGISTRY_STATUS,
    accepted_model_id,
    model_registry_fingerprint,
)
from packages.ml.robustness_policy import (
    ML_ROBUSTNESS_ARGMAX_IS_PRODUCTION_SIGNAL,
    ML_ROBUSTNESS_POLICY_ACCEPTED,
    ML_ROBUSTNESS_POLICY_CONTRACT_VERSION,
)
from packages.ml.walk_forward_policy import ML_WALK_FORWARD_FINAL_HOLDOUT_START


def main() -> int:
    assert ML_CANDIDATE_MODEL_POLICY_ACCEPTED is True
    assert ML_CALIBRATION_POLICY_ACCEPTED is True
    assert ML_ROBUSTNESS_POLICY_ACCEPTED is True
    assert ML_CALIBRATION_ACCEPTED_METHOD == "raw"
    assert ML_ROBUSTNESS_ARGMAX_IS_PRODUCTION_SIGNAL is False
    assert ML_MODEL_REGISTRY_CONTRACT_VERSION == (
        "ml-model-registry-v1-policy-lineage-oos-artifacts-finalfit-deferred"
    )
    assert ML_IMMUTABLE_PREDICTION_CONTRACT_VERSION == (
        "ml-prediction-record-v1-stable-id-raw-threeclass-oos-outcome-known"
    )
    assert ML_MODEL_REGISTRY_STATUS == "ACCEPTED_CANDIDATE_AWAITING_GATE13_FINAL_FIT"
    assert ML_MODEL_REGISTRY_FINAL_FIT_ARTIFACT_PRESENT is False
    assert ML_MODEL_REGISTRY_FINAL_HOLDOUT_ACCESSED is False

    print(f"ML Gate 11 robustness policy: {ML_ROBUSTNESS_POLICY_CONTRACT_VERSION}")
    print(f"ML Gate 11 accepted model role: probability_surface / argmax_signal={ML_ROBUSTNESS_ARGMAX_IS_PRODUCTION_SIGNAL}")
    print(f"ML Gate 12 model registry: {ML_MODEL_REGISTRY_CONTRACT_VERSION}")
    print(f"ML Gate 12 prediction contract: {ML_IMMUTABLE_PREDICTION_CONTRACT_VERSION}")
    print(f"ML Gate 12 model id: {accepted_model_id()}")
    print(f"ML Gate 12 model fingerprint: {model_registry_fingerprint()}")
    print(f"ML Gate 12 accepted candidate: {ML_CANDIDATE_MODEL_ACCEPTED_MODEL} / calibration={ML_CALIBRATION_ACCEPTED_METHOD}")
    print(f"ML Gate 12 status: {ML_MODEL_REGISTRY_STATUS}")
    print(
        "ML Gate 12 final boundary: "
        f"holdout_start={ML_WALK_FORWARD_FINAL_HOLDOUT_START} / "
        "final_fit_artifact=False / holdout_accessed=False"
    )
    print("ML Gate 11 regime/segment robustness: ACCEPTED with explicit probability-role caveats")
    print("ML Gate 12 model registry + immutable prediction contract: CURRENT; target-machine materialization not yet run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
