from __future__ import annotations

from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.ml.feature_leakage_audit import (
    ML_MARKET_REGIME_CANDIDATE_FIELDS,
    ML_OBSERVATION_AVAILABILITY_RULE,
    ML_PROHIBITED_MODEL_INPUT_FIELDS,
)


ML_FEATURE_POLICY_CONTRACT_VERSION = (
    "ml-feature-policy-v1-core33-postclose-regime-context-not-predictor"
)
ML_FEATURE_POLICY_ACCEPTED = True
ML_PRODUCTION_CORE_FEATURE_NAMES = tuple(
    definition.name for definition in CORE_FEATURE_REGISTRY.all()
)
ML_PRODUCTION_CORE_FEATURE_COUNT = len(ML_PRODUCTION_CORE_FEATURE_NAMES)
ML_PRODUCTION_OBSERVATION_AVAILABILITY_RULE = ML_OBSERVATION_AVAILABILITY_RULE
ML_PRODUCTION_FEATURE_PARQUET_UNION_BY_NAME_REQUIRED = True
ML_PRODUCTION_PROHIBITED_INPUT_FIELDS = ML_PROHIBITED_MODEL_INPUT_FIELDS

# Phase 9 market regime can be replayed point-in-time, but it begins materially later
# than the accepted ML observation history. Gate 5 therefore preserves it as optional
# evaluation/segmentation metadata rather than forcing it into the predictor matrix or
# shrinking the training history. An UNKNOWN predictor would otherwise be nearly a
# calendar-era proxy for the pre-regime-history observations.
ML_MARKET_REGIME_EVALUATION_CONTEXT_ACCEPTED = True
ML_MARKET_REGIME_MODEL_INPUT_ACCEPTED = False
ML_MARKET_REGIME_CONTEXT_FIELDS = ML_MARKET_REGIME_CANDIDATE_FIELDS
ML_GATE5_MARKET_REGIME_COVERED_ROWS = 5_136_676
ML_GATE5_MARKET_REGIME_COVERAGE_FRACTION = 0.7796348734827609
ML_GATE5_MARKET_REGIME_FIRST_DATE = "2023-06-01"
ML_GATE5_MARKET_REGIME_LAST_DATE = "2026-08-14"

# Sector and ticker regime attachment were not accepted because the historical stock
# observation -> sector/ticker context joins are not yet proven date-safe across the
# Gate 2 observation-driven population. Current route/current state may never be
# projected backward to fill that gap.
ML_SECTOR_REGIME_MODEL_INPUT_ACCEPTED = False
ML_SECTOR_REGIME_EVALUATION_CONTEXT_ACCEPTED = False
ML_TICKER_REGIME_MODEL_INPUT_ACCEPTED = False
ML_TICKER_REGIME_EVALUATION_CONTEXT_ACCEPTED = False

# Documentary Gate 5 target-machine anchors.
ML_GATE5_ACCEPTED_CANDIDATE_ROWS = 6_588_579
ML_GATE5_ACCEPTED_CANDIDATE_SYMBOLS = 12_596
ML_GATE5_FEATURE_JOIN_ROWS = 6_588_579
ML_GATE5_BAD_FEATURE_ROWS = 0
ML_GATE5_NON_NUMERIC_FEATURE_COUNT = 0
