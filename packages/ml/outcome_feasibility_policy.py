from __future__ import annotations


ML_OUTCOME_FEASIBILITY_POLICY_CONTRACT_VERSION = (
    "ml-outcome-feasibility-policy-v1-split-censored-endpoint-natr-feasible"
)

# Gate 3 accepts feasibility and data-safety conclusions only. Gate 4 still owns the
# production prediction-label choice (exact horizon, threshold, and neutral handling).
ML_OUTCOME_FEASIBILITY_ACCEPTED = True
ML_OUTCOME_ACCEPTED_HORIZONS = (1, 3, 5, 10, 20)
ML_SPLIT_CROSSING_LABELS_CENSORED = True
ML_EXACT_SESSION_CONTINUITY_REQUIRED = True
ML_EXACT_PROVIDER_TICKER_REQUIRED = True
ML_TICKER_TEXT_SPLICING_ALLOWED_FOR_LABELS = False
ML_ENDPOINT_OUTCOME_FAMILY_FEASIBLE = True
ML_DAILY_PATH_BARRIER_SELECTED = False
ML_VOLATILITY_FEATURE_INTEGRITY_RECONCILED = True
ML_FEATURE_PARQUET_UNION_BY_NAME_REQUIRED = True
ML_FEASIBLE_VOLATILITY_THRESHOLD_GRID = (0.5, 1.0, 1.5, 2.0)
ML_PLAIN_RETURN_SIGN_PRODUCTION_TARGET_ACCEPTED = False
ML_PREDICTION_LABEL_POLICY_LOCKED = False

# Evidence summary captured on the target machine for 2026-08-14. These are
# documentary acceptance anchors, not runtime filters.
ML_GATE3_ACCEPTED_CANDIDATE_ROWS = 6_588_579
ML_GATE3_ACCEPTED_CANDIDATE_SYMBOLS = 12_596
ML_GATE3_SPLIT_EVIDENCE_SHA256 = (
    "4c67e22d8e611ce805640dddb31f335ecefec97c955d08a6284319ee034c179c"
)

# The 0.5x NATR family remained large and roughly direction-balanced across all five
# tested horizons (~41-46% directional). The 1.0x family remained feasible but much
# sparser (~14-16% directional); 1.5x/2.0x are diagnostic tails. Gate 4 chooses the
# production target from this evidence and must not infer that 0.5x is already locked.
ML_GATE3_PRIMARY_CANDIDATE_THRESHOLD_MULTIPLIER = 0.5
ML_GATE3_PRIMARY_CANDIDATE_IS_PRODUCTION_LOCK = False
