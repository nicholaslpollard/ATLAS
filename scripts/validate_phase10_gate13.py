from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.ml.final_acceptance import (
    ML_FINAL_ACCEPTANCE_CONTRACT_VERSION,
    ML_FINAL_ACCEPTANCE_MIN_MACRO_AUC,
    ML_FINAL_ACCEPTANCE_REPLAY_MAX_ABS_DIFF,
    ML_FINAL_ACCEPTANCE_TRAINING_SAMPLE_RULE,
)
from packages.ml.model_registry_policy import (
    ML_MODEL_REGISTRY_ACCEPTED_FINGERPRINT,
    ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID,
    ML_MODEL_REGISTRY_ACCEPTED_OOS_FOLDS,
    ML_MODEL_REGISTRY_ACCEPTED_OOS_ROWS,
    ML_MODEL_REGISTRY_POLICY_ACCEPTED,
    ML_MODEL_REGISTRY_POLICY_CONTRACT_VERSION,
)
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_FINAL_HOLDOUT_END,
    ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_START,
    ML_WALK_FORWARD_PURGE_SESSIONS,
)


def main() -> int:
    print(f"ML Gate 12 registry policy: {ML_MODEL_REGISTRY_POLICY_CONTRACT_VERSION}")
    print(f"ML Gate 12 accepted model id: {ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID}")
    print(f"ML Gate 12 accepted fingerprint: {ML_MODEL_REGISTRY_ACCEPTED_FINGERPRINT}")
    print(
        "ML Gate 12 immutable OOS evidence: "
        f"folds={ML_MODEL_REGISTRY_ACCEPTED_OOS_FOLDS} / rows={ML_MODEL_REGISTRY_ACCEPTED_OOS_ROWS:,}"
    )
    print(f"ML Gate 13 final acceptance: {ML_FINAL_ACCEPTANCE_CONTRACT_VERSION}")
    print(
        "ML Gate 13 chronology: "
        f"purge={ML_WALK_FORWARD_PURGE_SESSIONS} sessions / "
        f"holdout={ML_WALK_FORWARD_FINAL_HOLDOUT_START}->{ML_WALK_FORWARD_FINAL_HOLDOUT_END} / "
        f"{ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS} sessions / {ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS:,} rows"
    )
    print(
        "ML Gate 13 training: "
        f"rule={ML_FINAL_ACCEPTANCE_TRAINING_SAMPLE_RULE} / accepted_cap=1,000,000 rows"
    )
    print(
        "ML Gate 13 locked acceptance criteria: "
        f"logloss<train_prior / brier<train_prior / macro_auc>={ML_FINAL_ACCEPTANCE_MIN_MACRO_AUC:.2f} / "
        f"replay_max_abs_diff<={ML_FINAL_ACCEPTANCE_REPLAY_MAX_ABS_DIFF:.0e}"
    )
    if not ML_MODEL_REGISTRY_POLICY_ACCEPTED:
        raise RuntimeError("Gate 12 model registry policy is not accepted")
    print("ML Gate 12 model registry + immutable prediction contract: ACCEPTED")
    print("ML Gate 13 final reproducibility/leakage/OOS validation: CURRENT; protected holdout not yet run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
