from packages.ml.label_policy import ML_PREDICTION_LABEL_HORIZON_SESSIONS
from packages.ml.walk_forward_probe import (
    ML_WALK_FORWARD_ADDITIONAL_EMBARGO_SESSIONS,
    ML_WALK_FORWARD_CANDIDATE_SPECS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS,
    ML_WALK_FORWARD_PURGE_SESSIONS,
    ML_WALK_FORWARD_RANDOM_ROW_SPLIT_ALLOWED,
    ML_WALK_FORWARD_SPLIT_UNIT,
    MLWalkForwardProbe,
    SessionClassEvidence,
)


def test_phase10_gate7_split_contract_is_session_level_and_purged() -> None:
    assert ML_WALK_FORWARD_SPLIT_UNIT == "EXCHANGE_SESSION_CROSS_SECTION"
    assert ML_WALK_FORWARD_RANDOM_ROW_SPLIT_ALLOWED is False
    assert ML_WALK_FORWARD_PURGE_SESSIONS == ML_PREDICTION_LABEL_HORIZON_SESSIONS == 3
    assert ML_WALK_FORWARD_ADDITIONAL_EMBARGO_SESSIONS == 0
    assert ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS == 63


def test_phase10_gate7_candidate_grid_is_bounded() -> None:
    assert tuple(spec.name for spec in ML_WALK_FORWARD_CANDIDATE_SPECS) == (
        "quarterly-train252",
        "quarterly-train378",
        "quarterly-train504",
        "halfyear-train252",
    )
    assert all(spec.minimum_train_sessions >= 252 for spec in ML_WALK_FORWARD_CANDIDATE_SPECS)
    assert all(spec.validation_sessions > 0 and spec.test_sessions > 0 for spec in ML_WALK_FORWARD_CANDIDATE_SPECS)


def test_phase10_gate7_fold_builder_keeps_test_sessions_unique() -> None:
    sessions = [
        SessionClassEvidence(
            session_date=f"2024-{1 + (index // 28):02d}-{1 + (index % 28):02d}",
            rows=100,
            down_rows=20,
            neutral_rows=55,
            up_rows=25,
        )
        for index in range(700)
    ]
    evidence = MLWalkForwardProbe._candidate_evidence(sessions, ML_WALK_FORWARD_CANDIDATE_SPECS[0])
    assert evidence.fold_count > 0
    assert evidence.distinct_test_sessions == evidence.fold_count * 63
    assert evidence.minimum_train_rows == 252 * 100
    assert all(fold.test_rows == 63 * 100 for fold in evidence.folds)
