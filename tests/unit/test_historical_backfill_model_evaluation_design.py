from __future__ import annotations

from packages.ml.candidate_model_policy import ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS
from packages.ml.candidate_model_probe import ML_CANDIDATE_MODEL_HASH_BUCKETS
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.historical_backfill_model_evaluation_design import (
    GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT,
    GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT,
    GATE11D_DIAGNOSTIC_METRICS,
    GATE11D_FIXED_BUDGET_ROWS,
    GATE11D_MODEL_TRAINING_ALLOWED,
    GATE11D_NESTED_EXTENSION_CAP_ROWS,
    GATE11D_PRIMARY_COMPARISON,
    GATE11D_PRIMARY_SELECTION_METRICS,
    GATE11D_PRODUCTION_MODEL_REPLACEMENT_ALLOWED,
    GATE11D_SENSITIVITY_COMPARISON,
    _sample_threshold,
    _stable_hash,
)
from packages.ml.model_registry import ML_MODEL_REGISTRY_SPEC
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT,
    ML_WALK_FORWARD_ADDITIONAL_EMBARGO_SESSIONS,
    ML_WALK_FORWARD_PURGE_SESSIONS,
)


def test_gate11d_parent_fingerprints_are_sha256() -> None:
    for value in (
        GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT,
        GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT,
    ):
        assert len(value) == 64
        int(value, 16)


def test_gate11d_primary_budget_retains_accepted_registry_cap() -> None:
    assert GATE11D_FIXED_BUDGET_ROWS == ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS
    assert GATE11D_FIXED_BUDGET_ROWS == int(ML_MODEL_REGISTRY_SPEC["training_cap_rows"])
    assert GATE11D_NESTED_EXTENSION_CAP_ROWS == ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS


def test_gate11d_sampling_threshold_is_bounded_and_monotone() -> None:
    assert _sample_threshold(500_000, 1_000_000) == ML_CANDIDATE_MODEL_HASH_BUCKETS
    assert _sample_threshold(1_000_000, 1_000_000) == ML_CANDIDATE_MODEL_HASH_BUCKETS
    assert _sample_threshold(2_000_000, 1_000_000) == 500_000
    assert _sample_threshold(10_000_000, 1_000_000) == 100_000
    assert 1 <= _sample_threshold(10**12, 1_000_000) <= ML_CANDIDATE_MODEL_HASH_BUCKETS


def test_gate11d_roles_keep_practical_selection_separate_from_attribution() -> None:
    assert GATE11D_PRIMARY_COMPARISON == "FIXED_1M_TRAIN_BUDGET_PAIRED_POST2021_OOS"
    assert GATE11D_SENSITIVITY_COMPARISON == "NESTED_B_SAMPLE_PLUS_UP_TO_1M_PRESEAM_EXTENSION"
    assert GATE11D_PRIMARY_SELECTION_METRICS == ("log_loss", "multiclass_brier")
    assert GATE11D_DIAGNOSTIC_METRICS == ("accuracy", "macro_ovr_auc", "macro_ece")


def test_gate11d_design_gate_cannot_fit_or_promote_model() -> None:
    assert GATE11D_MODEL_TRAINING_ALLOWED is False
    assert GATE11D_PRODUCTION_MODEL_REPLACEMENT_ALLOWED is False


def test_gate11d_reuses_core33_and_accepted_purge_policy() -> None:
    assert len(ML_PRODUCTION_CORE_FEATURE_NAMES) == 33
    assert ML_WALK_FORWARD_PURGE_SESSIONS == 3
    assert ML_WALK_FORWARD_ADDITIONAL_EMBARGO_SESSIONS == 0
    assert ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT == 10


def test_gate11d_stable_hash_binds_policy_payload() -> None:
    first = _stable_hash({"role": GATE11D_PRIMARY_COMPARISON, "budget": GATE11D_FIXED_BUDGET_ROWS})
    assert first == _stable_hash({"budget": GATE11D_FIXED_BUDGET_ROWS, "role": GATE11D_PRIMARY_COMPARISON})
    assert first != _stable_hash({"role": GATE11D_PRIMARY_COMPARISON, "budget": GATE11D_FIXED_BUDGET_ROWS + 1})
