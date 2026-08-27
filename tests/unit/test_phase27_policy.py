from __future__ import annotations

from packages.backtesting.phase27_policy import (
    PHASE27_AUTOMATIC_BROKER_FAILOVER,
    PHASE27_CANDIDATES,
    PHASE27_DEVELOPMENT_END,
    PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS,
    PHASE27_HGB_L2_REGULARIZATION_GRID,
    PHASE27_HGB_LEARNING_RATE_GRID,
    PHASE27_HGB_MAX_ITER_GRID,
    PHASE27_HGB_MAX_LEAF_NODES_GRID,
    PHASE27_INNER_TUNING_FOLDS,
    PHASE27_MULTIPLE_TESTING_METHOD,
    PHASE27_OUTCOME_HORIZON_SESSIONS,
    PHASE27_PAIRWISE_C_GRID,
    PHASE27_PREDICTOR_FIELDS,
    PHASE27_PROTECTED_END,
    PHASE27_PROTECTED_START,
    PHASE27_RIDGE_ALPHA_GRID,
    PHASE27_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE27_SIGNAL_TAIL_FRACTION,
    phase27_policy_fingerprint,
    phase27_policy_payload,
)


def test_phase27_policy_is_finite_and_frozen() -> None:
    payload = phase27_policy_payload()
    assert len(PHASE27_CANDIDATES) == 8
    assert {candidate.direction for candidate in PHASE27_CANDIDATES} == {"LONG", "SHORT"}
    assert {candidate.family for candidate in PHASE27_CANDIDATES} == {
        "discovery_priority_baseline",
        "ridge_relative_return",
        "hgb_relative_return",
        "pairwise_logistic_rank",
    }
    assert len(PHASE27_PREDICTOR_FIELDS) == 29
    assert len(set(PHASE27_PREDICTOR_FIELDS)) == 29
    assert PHASE27_SIGNAL_TAIL_FRACTION == 0.20
    assert PHASE27_OUTCOME_HORIZON_SESSIONS == 3
    assert PHASE27_INNER_TUNING_FOLDS == 5
    assert PHASE27_MULTIPLE_TESTING_METHOD == "HOLM_BONFERRONI_GLOBAL_8"
    assert PHASE27_RUNNER_UP_SUBSTITUTION_ALLOWED is False
    assert payload["protected_returns_before_finalists_allowed"] is False
    assert payload["phase26_protected_holdout_one_time_reuse_requires_blindness_audit"] is True
    assert payload["phase26_protected_holdout_consumed_after_any_phase27_return_read"] is True
    assert len(phase27_policy_fingerprint()) == 64


def test_phase27_boundaries_preserve_unopened_phase26_holdout() -> None:
    assert PHASE27_DEVELOPMENT_END == "2026-05-06"
    assert PHASE27_PROTECTED_START == "2026-05-12"
    assert PHASE27_PROTECTED_END == "2026-08-11"
    assert set(PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS) == {
        "future_date",
        "future_close",
        "forward_return",
        "directional_return",
        "relative_directional_return",
    }


def test_phase27_hyperparameter_grids_are_bounded() -> None:
    assert PHASE27_RIDGE_ALPHA_GRID == (0.1, 1.0, 10.0, 100.0)
    assert len(PHASE27_HGB_MAX_LEAF_NODES_GRID) == 2
    assert len(PHASE27_HGB_LEARNING_RATE_GRID) == 2
    assert len(PHASE27_HGB_MAX_ITER_GRID) == 2
    assert len(PHASE27_HGB_L2_REGULARIZATION_GRID) == 2
    assert len(PHASE27_PAIRWISE_C_GRID) == 3
    assert PHASE27_AUTOMATIC_BROKER_FAILOVER is False


def test_phase27_policy_forbids_external_trading_authority() -> None:
    payload = phase27_policy_payload()
    for field in (
        "provider_reads",
        "provider_writes",
        "broker_reads",
        "broker_writes",
        "order_writes",
        "paper_submits",
        "live_writes",
        "automation_writes",
    ):
        assert payload[field] == 0
