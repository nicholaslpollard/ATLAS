from __future__ import annotations

from packages.ml.historical_backfill_model_benchmark import (
    HISTORICAL_BACKFILL_ACCEPTED_GATE11D_SOURCE_FINGERPRINT,
    HISTORICAL_BACKFILL_FINAL_HOLDOUT_ACCESSED,
    HISTORICAL_BACKFILL_MODEL_NAME,
    HISTORICAL_BACKFILL_MODEL_REPLACEMENT_ALLOWED if False else HISTORICAL_BACKFILL_PRODUCTION_MODEL_REPLACEMENT_ALLOWED,
    HISTORICAL_BACKFILL_NESTED_C_ROLE,
    HISTORICAL_BACKFILL_PRIMARY_B_ROLE,
    HISTORICAL_BACKFILL_PRIMARY_C_ROLE,
    _accepted_spec,
    _aggregate_role,
    primary_selection_decision,
)


def _fold(role: str, log_loss: float, brier: float, rows: int = 100) -> dict[str, object]:
    return {
        "roles": {
            role: {
                "test_rows": rows,
                "test_metrics": {
                    "rows": rows,
                    "log_loss": log_loss,
                    "multiclass_brier": brier,
                    "accuracy": 0.60,
                    "macro_ovr_auc": 0.57,
                    "macro_ece": 0.02,
                },
            }
        }
    }


def test_historical_benchmark_binds_accepted_gate11d_fingerprint() -> None:
    assert HISTORICAL_BACKFILL_ACCEPTED_GATE11D_SOURCE_FINGERPRINT == (
        "798cc974d06863116c02a8b09c46b2935b5e633793bd34288ef27638dd22238e"
    )


def test_historical_benchmark_uses_accepted_hgb_spec() -> None:
    spec = _accepted_spec()
    assert spec.name == HISTORICAL_BACKFILL_MODEL_NAME == "hgb_leaf15_iter100"
    assert spec.max_leaf_nodes == 15
    assert spec.max_iter == 100
    assert spec.learning_rate == 0.05
    assert spec.min_samples_leaf == 100
    assert spec.l2_regularization == 1.0


def test_historical_benchmark_cannot_replace_production_or_read_final_holdout() -> None:
    assert HISTORICAL_BACKFILL_PRODUCTION_MODEL_REPLACEMENT_ALLOWED is False
    assert HISTORICAL_BACKFILL_FINAL_HOLDOUT_ACCESSED is False


def test_primary_selection_requires_both_proper_scores_to_improve() -> None:
    b = {
        "weighted_log_loss": 1.0,
        "weighted_multiclass_brier": 0.60,
    }
    c_both = {
        "weighted_log_loss": 0.99,
        "weighted_multiclass_brier": 0.59,
    }
    c_mixed = {
        "weighted_log_loss": 0.98,
        "weighted_multiclass_brier": 0.61,
    }
    both = primary_selection_decision(
        {HISTORICAL_BACKFILL_PRIMARY_B_ROLE: b, HISTORICAL_BACKFILL_PRIMARY_C_ROLE: c_both}
    )
    mixed = primary_selection_decision(
        {HISTORICAL_BACKFILL_PRIMARY_B_ROLE: b, HISTORICAL_BACKFILL_PRIMARY_C_ROLE: c_mixed}
    )
    assert both["C_improves_both_primary_scores"] is True
    assert both["decision"] == "REGISTER_C_AS_VERSIONED_CHALLENGER_EVIDENCE"
    assert mixed["C_improves_both_primary_scores"] is False
    assert mixed["decision"] == "RETAIN_ACCEPTED_PHASE10_PRODUCTION_MODEL"
    assert both["production_model_replacement_allowed"] is False


def test_role_aggregate_is_test_row_weighted() -> None:
    folds = [
        _fold(HISTORICAL_BACKFILL_PRIMARY_B_ROLE, 1.0, 0.60, rows=100),
        _fold(HISTORICAL_BACKFILL_PRIMARY_B_ROLE, 0.8, 0.50, rows=300),
    ]
    aggregate = _aggregate_role(HISTORICAL_BACKFILL_PRIMARY_B_ROLE, folds)
    assert aggregate["test_rows"] == 400
    assert abs(float(aggregate["weighted_log_loss"]) - 0.85) < 1e-12
    assert abs(float(aggregate["weighted_multiclass_brier"]) - 0.525) < 1e-12


def test_comparison_roles_remain_distinct() -> None:
    assert len(
        {
            HISTORICAL_BACKFILL_PRIMARY_B_ROLE,
            HISTORICAL_BACKFILL_PRIMARY_C_ROLE,
            HISTORICAL_BACKFILL_NESTED_C_ROLE,
        }
    ) == 3
