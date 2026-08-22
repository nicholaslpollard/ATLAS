from __future__ import annotations

from packages.backtesting.phase11_closeout import phase11_acceptance_checks
from packages.discovery.current_candidates import CURRENT_CANDIDATE_SECTOR_POLICY
from packages.ml.model_registry import accepted_model_id, model_registry_fingerprint
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY


def _passing_payloads():
    registered = [strategy.metadata.strategy_id for strategy in DEFAULT_STRATEGY_REGISTRY.all()]
    study = {
        "pass": True,
        "strategy_count": len(registered),
        "protected_holdout_role": "CONFIRMATION_ONLY_NOT_SUPPORT_SELECTION",
        "production_writes": 0,
        "broker_writes": 0,
    }
    current = {
        "pass": True,
        "sector_context_policy": CURRENT_CANDIDATE_SECTOR_POLICY,
        "lineage": {
            "accepted_ml_model_id": accepted_model_id(),
            "accepted_ml_model_fingerprint": model_registry_fingerprint(),
        },
        "production_ml_writes": 0,
        "broker_writes": 0,
    }
    validation = {
        "pass": True,
        "supported_strategy_ids": registered[:2],
        "checks": {
            "strategy_support_recomputed_exact": True,
            "candidate_promotion_recomputed_valid": True,
            "no_trade_or_order_geometry": True,
        },
        "production_ml_writes": 0,
        "broker_writes": 0,
    }
    return study, current, validation


def test_phase11_acceptance_checks_pass_for_bound_evidence() -> None:
    study, current, validation = _passing_payloads()
    checks = phase11_acceptance_checks(
        study=study,
        current=current,
        validation=validation,
    )
    assert checks
    assert all(checks.values())


def test_phase11_acceptance_checks_reject_nonaccepted_ml_identity() -> None:
    study, current, validation = _passing_payloads()
    current["lineage"]["accepted_ml_model_id"] = "wrong-model"
    checks = phase11_acceptance_checks(
        study=study,
        current=current,
        validation=validation,
    )
    assert checks["accepted_phase10_model_remains_probability_authority"] is False


def test_phase11_acceptance_checks_reject_unknown_supported_strategy() -> None:
    study, current, validation = _passing_payloads()
    validation["supported_strategy_ids"] = ["not-registered"]
    checks = phase11_acceptance_checks(
        study=study,
        current=current,
        validation=validation,
    )
    assert checks["supported_strategies_are_registered"] is False
