from __future__ import annotations

from packages.ml.final_acceptance import (
    ML_FINAL_ACCEPTANCE_CONTRACT_VERSION,
    ML_FINAL_ACCEPTANCE_HOLDOUT_ROLE,
    ML_FINAL_ACCEPTANCE_MIN_MACRO_AUC,
    ML_FINAL_ACCEPTANCE_REPLAY_MAX_ABS_DIFF,
    ML_FINAL_ACCEPTANCE_REQUIRE_BRIER_WIN_VS_PRIOR,
    ML_FINAL_ACCEPTANCE_REQUIRE_LOGLOSS_WIN_VS_PRIOR,
    ML_FINAL_ACCEPTANCE_TRAINING_SAMPLE_RULE,
    MLFinalAcceptance,
)
from packages.ml.model_registry import ML_MODEL_REGISTRY_SPEC
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS,
    ML_WALK_FORWARD_PURGE_SESSIONS,
)


def test_phase10_gate13_final_acceptance_contract_is_locked() -> None:
    assert ML_FINAL_ACCEPTANCE_CONTRACT_VERSION == (
        "ml-final-acceptance-v1-purged-finalfit-replay-prior-untouched-holdout"
    )
    assert ML_FINAL_ACCEPTANCE_HOLDOUT_ROLE == "FINAL_UNTOUCHED_HOLDOUT"
    assert ML_FINAL_ACCEPTANCE_TRAINING_SAMPLE_RULE == "DETERMINISTIC_OBSERVATION_KEY_HASH_CAP"


def test_phase10_gate13_acceptance_thresholds_are_fixed_before_holdout() -> None:
    assert ML_FINAL_ACCEPTANCE_REQUIRE_LOGLOSS_WIN_VS_PRIOR is True
    assert ML_FINAL_ACCEPTANCE_REQUIRE_BRIER_WIN_VS_PRIOR is True
    assert ML_FINAL_ACCEPTANCE_MIN_MACRO_AUC == 0.52
    assert ML_FINAL_ACCEPTANCE_REPLAY_MAX_ABS_DIFF == 1e-12


def test_phase10_gate13_preserves_locked_holdout_geometry() -> None:
    assert ML_WALK_FORWARD_PURGE_SESSIONS == 3
    assert ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS == 63
    assert ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS == 454_773


def test_phase10_gate13_final_model_matches_gate12_spec() -> None:
    model = MLFinalAcceptance._model()
    assert model.max_leaf_nodes == ML_MODEL_REGISTRY_SPEC["max_leaf_nodes"] == 15
    assert model.max_iter == ML_MODEL_REGISTRY_SPEC["max_iter"] == 100
    assert model.learning_rate == ML_MODEL_REGISTRY_SPEC["learning_rate"] == 0.05
    assert model.random_state == ML_MODEL_REGISTRY_SPEC["random_state"] == 42
    assert MLFinalAcceptance._sample_threshold(5_000_000) == 200_000
