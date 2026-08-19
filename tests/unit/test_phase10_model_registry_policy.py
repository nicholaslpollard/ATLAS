from __future__ import annotations

from packages.ml.model_registry_policy import (
    ML_MODEL_REGISTRY_ACCEPTED_FINGERPRINT,
    ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID,
    ML_MODEL_REGISTRY_ACCEPTED_OOS_FOLDS,
    ML_MODEL_REGISTRY_ACCEPTED_OOS_ROWS,
    ML_MODEL_REGISTRY_ACCEPTED_PREDICTION_ARTIFACT_SHA256,
    ML_MODEL_REGISTRY_FINAL_FIT_DEFERRED_TO_GATE13,
    ML_MODEL_REGISTRY_GATE12_FINAL_HOLDOUT_ACCESSED,
    ML_MODEL_REGISTRY_POLICY_ACCEPTED,
    ML_MODEL_REGISTRY_POLICY_CONTRACT_VERSION,
)


def test_phase10_gate12_registry_policy_is_accepted() -> None:
    assert ML_MODEL_REGISTRY_POLICY_CONTRACT_VERSION == (
        "ml-model-registry-policy-v1-accepted-d485e6c287bacce1"
    )
    assert ML_MODEL_REGISTRY_POLICY_ACCEPTED is True
    assert ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID == "mlmodel-hgb15-2026-08-14-d485e6c287bacce1"
    assert len(ML_MODEL_REGISTRY_ACCEPTED_FINGERPRINT) == 64


def test_phase10_gate12_registry_policy_reconciles_oos_scope() -> None:
    assert ML_MODEL_REGISTRY_ACCEPTED_OOS_FOLDS == 10
    assert ML_MODEL_REGISTRY_ACCEPTED_OOS_ROWS == 3_978_577
    assert tuple(sorted(ML_MODEL_REGISTRY_ACCEPTED_PREDICTION_ARTIFACT_SHA256)) == tuple(range(1, 11))
    assert all(len(value) == 64 for value in ML_MODEL_REGISTRY_ACCEPTED_PREDICTION_ARTIFACT_SHA256.values())


def test_phase10_gate12_registry_policy_preserves_final_holdout_boundary() -> None:
    assert ML_MODEL_REGISTRY_FINAL_FIT_DEFERRED_TO_GATE13 is True
    assert ML_MODEL_REGISTRY_GATE12_FINAL_HOLDOUT_ACCESSED is False


def test_phase10_gate12_prediction_hashes_are_unique() -> None:
    values = tuple(ML_MODEL_REGISTRY_ACCEPTED_PREDICTION_ARTIFACT_SHA256.values())
    assert len(set(values)) == len(values) == 10
