from __future__ import annotations


PHASE12_RESEARCH_POLICY_CONTRACT_VERSION = (
    "phase12-research-policy-v1-promoted-only-regime-matched-standardized-analogues"
)
PHASE12_SCENARIO_POLICY_CONTRACT_VERSION = (
    "phase12-scenario-policy-v1-deterministic-empirical-three-session-path-bootstrap"
)

# Locked before any Phase 12 analogue results are observed. These are intentionally
# scale-stable technical-state features. Raw price/volume level features are excluded
# so cross-sectional similarity is not dominated by nominal security scale.
PHASE12_SIMILARITY_FEATURES = (
    "return_1",
    "rsi_14",
    "natr_14",
    "bb_width_20",
    "bb_position_20",
    "realized_volatility_20",
    "relative_volume_20",
    "volume_zscore_20",
    "relative_dollar_volume_20",
    "range_position_20",
    "breakout_distance_20",
    "breakdown_distance_20",
    "drawdown_20",
    "ema_20_slope_1",
    "price_distance_ema_20",
    "directional_efficiency_20",
)

PHASE12_ANALOGUE_TOP_K = 200
PHASE12_PER_INSTRUMENT_CAP = 3
PHASE12_MIN_ANALOGUES_FOR_DISTRIBUTION = 50
PHASE12_MIN_UNIQUE_INSTRUMENTS = 20
PHASE12_ROBUST_ANALOGUE_COUNT = 100
PHASE12_ROBUST_UNIQUE_INSTRUMENTS = 50
PHASE12_ROBUST_PATH_COVERAGE = 0.80
PHASE12_BOOTSTRAP_DRAWS = 10_000
PHASE12_PATH_HORIZON_SESSIONS = 3
PHASE12_DISTANCE_METRIC = "EQUAL_WEIGHT_RMS_Z_DISTANCE"
PHASE12_NORMALIZATION = "ELIGIBLE_POOL_MEAN_STDDEV_POP"
PHASE12_WEIGHTING = "INVERSE_ONE_PLUS_DISTANCE"
PHASE12_REGIME_POLICY = "EXACT_CURRENT_MARKET_COMPOSITE_WHEN_AVAILABLE"
PHASE12_OUTCOME_ROLE = "THREE_SESSION_DIRECTION_ADJUSTED_RESEARCH_EVIDENCE_ONLY"
PHASE12_TICKER_REGIME_HISTORY_POLICY = (
    "CURRENT_TICKER_STATE_CONTEXT_ONLY_NOT_HISTORICAL_FILTER_PRE2021_UNAVAILABLE"
)
PHASE12_SECTOR_POLICY = "UNAVAILABLE_NO_AUTHORITATIVE_TICKER_TO_SECTOR_MAPPING"
PHASE12_PRODUCTION_ML_WRITES = 0
PHASE12_BROKER_WRITES = 0
PHASE12_TRADE_GEOMETRY_PRESENT = False


def phase12_policy_payload() -> dict[str, object]:
    return {
        "research_policy_contract_version": PHASE12_RESEARCH_POLICY_CONTRACT_VERSION,
        "scenario_policy_contract_version": PHASE12_SCENARIO_POLICY_CONTRACT_VERSION,
        "similarity_features": list(PHASE12_SIMILARITY_FEATURES),
        "analogue_top_k": PHASE12_ANALOGUE_TOP_K,
        "per_instrument_cap": PHASE12_PER_INSTRUMENT_CAP,
        "minimum_analogues_for_distribution": PHASE12_MIN_ANALOGUES_FOR_DISTRIBUTION,
        "minimum_unique_instruments": PHASE12_MIN_UNIQUE_INSTRUMENTS,
        "robust_analogue_count": PHASE12_ROBUST_ANALOGUE_COUNT,
        "robust_unique_instruments": PHASE12_ROBUST_UNIQUE_INSTRUMENTS,
        "robust_path_coverage": PHASE12_ROBUST_PATH_COVERAGE,
        "bootstrap_draws": PHASE12_BOOTSTRAP_DRAWS,
        "path_horizon_sessions": PHASE12_PATH_HORIZON_SESSIONS,
        "distance_metric": PHASE12_DISTANCE_METRIC,
        "normalization": PHASE12_NORMALIZATION,
        "weighting": PHASE12_WEIGHTING,
        "regime_policy": PHASE12_REGIME_POLICY,
        "outcome_role": PHASE12_OUTCOME_ROLE,
        "ticker_regime_history_policy": PHASE12_TICKER_REGIME_HISTORY_POLICY,
        "sector_policy": PHASE12_SECTOR_POLICY,
        "production_ml_writes": PHASE12_PRODUCTION_ML_WRITES,
        "broker_writes": PHASE12_BROKER_WRITES,
        "trade_geometry_present": PHASE12_TRADE_GEOMETRY_PRESENT,
    }
