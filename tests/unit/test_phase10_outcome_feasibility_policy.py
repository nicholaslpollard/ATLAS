from packages.ml.outcome_feasibility_policy import (
    ML_DAILY_PATH_BARRIER_SELECTED,
    ML_ENDPOINT_OUTCOME_FAMILY_FEASIBLE,
    ML_EXACT_PROVIDER_TICKER_REQUIRED,
    ML_EXACT_SESSION_CONTINUITY_REQUIRED,
    ML_FEATURE_PARQUET_UNION_BY_NAME_REQUIRED,
    ML_GATE3_ACCEPTED_CANDIDATE_ROWS,
    ML_GATE3_ACCEPTED_CANDIDATE_SYMBOLS,
    ML_GATE3_PRIMARY_CANDIDATE_IS_PRODUCTION_LOCK,
    ML_GATE3_PRIMARY_CANDIDATE_THRESHOLD_MULTIPLIER,
    ML_OUTCOME_ACCEPTED_HORIZONS,
    ML_OUTCOME_FEASIBILITY_ACCEPTED,
    ML_OUTCOME_FEASIBILITY_POLICY_CONTRACT_VERSION,
    ML_PLAIN_RETURN_SIGN_PRODUCTION_TARGET_ACCEPTED,
    ML_PREDICTION_LABEL_POLICY_LOCKED,
    ML_SPLIT_CROSSING_LABELS_CENSORED,
    ML_TICKER_TEXT_SPLICING_ALLOWED_FOR_LABELS,
    ML_VOLATILITY_FEATURE_INTEGRITY_RECONCILED,
)


def test_phase10_gate3_feasibility_policy_remains_locked_after_gate4_acceptance() -> None:
    assert ML_OUTCOME_FEASIBILITY_POLICY_CONTRACT_VERSION == (
        "ml-outcome-feasibility-policy-v1-split-censored-endpoint-natr-feasible"
    )
    assert ML_OUTCOME_FEASIBILITY_ACCEPTED is True
    # Gate 4 is now accepted. This compatibility flag mirrors that current phase state;
    # the authoritative production label definition lives in packages.ml.label_policy.
    assert ML_PREDICTION_LABEL_POLICY_LOCKED is True
    # Gate 3's 0.5x candidate evidence remains evidence-only and does not itself define
    # the production horizon/label contract.
    assert ML_GATE3_PRIMARY_CANDIDATE_IS_PRODUCTION_LOCK is False


def test_phase10_gate3_feasibility_safety_rules_are_explicit() -> None:
    assert ML_OUTCOME_ACCEPTED_HORIZONS == (1, 3, 5, 10, 20)
    assert ML_SPLIT_CROSSING_LABELS_CENSORED is True
    assert ML_EXACT_SESSION_CONTINUITY_REQUIRED is True
    assert ML_EXACT_PROVIDER_TICKER_REQUIRED is True
    assert ML_TICKER_TEXT_SPLICING_ALLOWED_FOR_LABELS is False
    assert ML_DAILY_PATH_BARRIER_SELECTED is False
    assert ML_ENDPOINT_OUTCOME_FAMILY_FEASIBLE is True


def test_phase10_gate3_feature_integrity_and_population_are_reconciled() -> None:
    assert ML_FEATURE_PARQUET_UNION_BY_NAME_REQUIRED is True
    assert ML_VOLATILITY_FEATURE_INTEGRITY_RECONCILED is True
    assert ML_GATE3_ACCEPTED_CANDIDATE_ROWS == 6_588_579
    assert ML_GATE3_ACCEPTED_CANDIDATE_SYMBOLS == 12_596


def test_phase10_gate3_keeps_target_selection_for_gate4() -> None:
    assert ML_PLAIN_RETURN_SIGN_PRODUCTION_TARGET_ACCEPTED is False
    assert ML_GATE3_PRIMARY_CANDIDATE_THRESHOLD_MULTIPLIER == 0.5
    assert ML_GATE3_PRIMARY_CANDIDATE_IS_PRODUCTION_LOCK is False
