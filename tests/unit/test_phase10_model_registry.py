from __future__ import annotations

from packages.ml.model_registry import (
    ML_IMMUTABLE_PREDICTION_CONTRACT_VERSION,
    ML_MODEL_REGISTRY_CONTRACT_VERSION,
    ML_MODEL_REGISTRY_EVALUATION_ROLE,
    ML_MODEL_REGISTRY_FINAL_FIT_ARTIFACT_PRESENT,
    ML_MODEL_REGISTRY_FINAL_HOLDOUT_ACCESSED,
    ML_MODEL_REGISTRY_MODEL_FAMILY,
    ML_MODEL_REGISTRY_OUTCOME_STATUS,
    ML_MODEL_REGISTRY_SPEC,
    ML_MODEL_REGISTRY_STATUS,
    accepted_model_id,
    model_registry_fingerprint,
)


def test_phase10_gate12_registry_contract_is_locked() -> None:
    assert ML_MODEL_REGISTRY_CONTRACT_VERSION == (
        "ml-model-registry-v1-policy-lineage-oos-artifacts-finalfit-deferred"
    )
    assert ML_IMMUTABLE_PREDICTION_CONTRACT_VERSION == (
        "ml-prediction-record-v1-stable-id-raw-threeclass-oos-outcome-known"
    )
    assert ML_MODEL_REGISTRY_STATUS == "ACCEPTED_CANDIDATE_AWAITING_GATE13_FINAL_FIT"
    assert ML_MODEL_REGISTRY_EVALUATION_ROLE == "OOS_TEST"
    assert ML_MODEL_REGISTRY_OUTCOME_STATUS == "KNOWN_HISTORICAL_OOS"


def test_phase10_gate12_registry_model_spec_matches_accepted_hgb_capacity() -> None:
    assert ML_MODEL_REGISTRY_MODEL_FAMILY == "sklearn_hist_gradient_boosting"
    assert ML_MODEL_REGISTRY_SPEC["max_leaf_nodes"] == 15
    assert ML_MODEL_REGISTRY_SPEC["max_iter"] == 100
    assert ML_MODEL_REGISTRY_SPEC["training_cap_rows"] == 1_000_000
    assert ML_MODEL_REGISTRY_SPEC["random_state"] == 42


def test_phase10_gate12_model_identity_is_deterministic() -> None:
    first_fingerprint = model_registry_fingerprint()
    second_fingerprint = model_registry_fingerprint()
    first_id = accepted_model_id()
    second_id = accepted_model_id()
    assert len(first_fingerprint) == 64
    assert first_fingerprint == second_fingerprint
    assert first_id == second_id
    assert first_id.startswith("mlmodel-hgb15-2026-08-14-")


def test_phase10_gate12_does_not_preempt_gate13_final_fit_or_holdout() -> None:
    assert ML_MODEL_REGISTRY_FINAL_FIT_ARTIFACT_PRESENT is False
    assert ML_MODEL_REGISTRY_FINAL_HOLDOUT_ACCESSED is False
