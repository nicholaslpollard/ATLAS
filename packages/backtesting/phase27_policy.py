from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal


PHASE27_POLICY_CONTRACT_VERSION = (
    "phase27-policy-v1-cross-sectional-expected-return-ranking-eight-hypotheses"
)
PHASE27_SOURCE_PHASE26_POLICY_FINGERPRINT = (
    "24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2"
)
PHASE27_RESEARCH_START = "2021-08-16"
PHASE27_DEVELOPMENT_END = "2026-05-06"
PHASE27_PROTECTED_START = "2026-05-12"
PHASE27_PROTECTED_END = "2026-08-11"
PHASE27_OUTCOME_HORIZON_SESSIONS = 3
PHASE27_PURGE_SESSIONS = 3

PHASE27_MIN_DIRECTION_ROWS_PER_SESSION = 5
PHASE27_SIGNAL_TAIL_FRACTION = 0.20

PHASE27_COST_GRID_BPS = (0.0, 5.0, 10.0, 25.0, 50.0)
PHASE27_PRIMARY_COST_BPS = 10.0
PHASE27_STRESS_COST_BPS = 25.0

PHASE27_SELECTION_FRACTION = 0.75
PHASE27_INNER_TUNING_FOLDS = 5
PHASE27_SELECTION_FOLDS = 6
PHASE27_INTERNAL_VALIDATION_FOLDS = 3
PHASE27_PROTECTED_FOLDS = 3

PHASE27_BOOTSTRAP_BLOCK_SESSIONS = 6
PHASE27_BOOTSTRAP_REPLICATES = 2000
PHASE27_BOOTSTRAP_SEED = 270227
PHASE27_SELECTION_CONFIDENCE = 0.95
PHASE27_INTERNAL_CONFIDENCE = 0.90
PHASE27_PROTECTED_CONFIDENCE = 0.80

PHASE27_SELECTION_MIN_RAW_ROWS = 750
PHASE27_SELECTION_MIN_SIGNAL_SESSIONS = 250
PHASE27_INTERNAL_MIN_RAW_ROWS = 250
PHASE27_INTERNAL_MIN_SIGNAL_SESSIONS = 80
PHASE27_PROTECTED_MIN_RAW_ROWS = 75
PHASE27_PROTECTED_MIN_SIGNAL_SESSIONS = 24
PHASE27_SELECTION_MIN_POSITIVE_FOLDS = 5
PHASE27_INTERNAL_MIN_POSITIVE_FOLDS = 2
PHASE27_PROTECTED_MIN_POSITIVE_FOLDS = 2
PHASE27_MIN_POSITIVE_YEAR_FRACTION = 0.60
PHASE27_MIN_YEAR_SIGNAL_SESSIONS = 20
PHASE27_MIN_POSITIVE_REGIME_FRACTION = 0.50
PHASE27_MIN_REGIME_SIGNAL_SESSIONS = 20
PHASE27_MAX_SINGLE_SESSION_ROW_FRACTION = 0.10

PHASE27_MULTIPLE_TESTING_METHOD = "HOLM_BONFERRONI_GLOBAL_8"
PHASE27_MULTIPLE_TESTING_ALPHA = 0.05
PHASE27_MAX_SELECTION_WINNERS_PER_DIRECTION = 1
PHASE27_MAX_FINALISTS_PER_DIRECTION = 1
PHASE27_RUNNER_UP_SUBSTITUTION_ALLOWED = False
PHASE27_WIN_RATE_IS_HARD_GATE = False
PHASE27_MEDIAN_RETURN_IS_HARD_GATE = False
PHASE27_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED = True

PHASE27_RIDGE_ALPHA_GRID = (0.1, 1.0, 10.0, 100.0)
PHASE27_HGB_MAX_LEAF_NODES_GRID = (7, 15)
PHASE27_HGB_LEARNING_RATE_GRID = (0.03, 0.05)
PHASE27_HGB_MAX_ITER_GRID = (100, 200)
PHASE27_HGB_L2_REGULARIZATION_GRID = (1.0, 10.0)
PHASE27_HGB_MIN_SAMPLES_LEAF = 50
PHASE27_PAIRWISE_C_GRID = (0.1, 1.0, 10.0)
PHASE27_PAIRWISE_MAX_UNORDERED_PAIRS_PER_SESSION = 128
PHASE27_PAIRWISE_SEED = 270127

PHASE27_PROVIDER_READS = 0
PHASE27_PROVIDER_WRITES = 0
PHASE27_BROKER_READS = 0
PHASE27_BROKER_WRITES = 0
PHASE27_ORDER_WRITES = 0
PHASE27_PAPER_SUBMITS = 0
PHASE27_LIVE_WRITES = 0
PHASE27_AUTOMATION_WRITES = 0
PHASE27_AUTOMATIC_BROKER_FAILOVER = False
PHASE27_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED = False

PHASE27_PREDICTOR_FIELDS: tuple[str, ...] = (
    "d1_return_1",
    "d1_rsi_14",
    "d1_macd_hist_12_26_9",
    "d1_natr_14",
    "d1_price_distance_ema_20",
    "d1_directional_efficiency_20",
    "d1_relative_dollar_volume_20",
    "d1_bb_position_20",
    "d1_drawdown_20",
    "d1_relative_volume_20",
    "d1_breakout_distance_20",
    "d1_bb_width_20",
    "d1_volume_zscore_20",
    "d1_breakdown_distance_20",
    "d1_range_position_20",
    "d1_ema_20_slope_1",
    "d1_realized_volatility_20",
    "d1_dollar_volume",
    "h4_rsi_14",
    "h4_macd_hist_12_26_9",
    "h4_price_distance_ema_20",
    "h1_rsi_14",
    "h1_macd_hist_12_26_9",
    "h1_price_distance_ema_20",
    "gap_return",
    "intraday_return",
    "return_5d",
    "return_20d",
    "vol_scaled_return_20d",
)
PHASE27_BASELINE_SCORE_FIELD = "priority_score"
PHASE27_MODEL_INPUT_REGIME_FIELDS: tuple[str, ...] = ()
PHASE27_ROBUSTNESS_STATE_FIELDS = ("market_state", "effective_ticker_state")
PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS = (
    "future_date",
    "future_close",
    "forward_return",
    "directional_return",
    "relative_directional_return",
)

StrategyDirection = Literal["LONG", "SHORT"]
ModelFamily = Literal[
    "discovery_priority_baseline",
    "ridge_relative_return",
    "hgb_relative_return",
    "pairwise_logistic_rank",
]


@dataclass(frozen=True, slots=True)
class Phase27CandidateSpec:
    candidate_id: str
    family: ModelFamily
    direction: StrategyDirection
    learned: bool
    score_semantics: str


PHASE27_CANDIDATES: tuple[Phase27CandidateSpec, ...] = (
    Phase27CandidateSpec(
        "priority_tail_long",
        "discovery_priority_baseline",
        "LONG",
        False,
        "existing observation-time discovery priority score",
    ),
    Phase27CandidateSpec(
        "priority_tail_short",
        "discovery_priority_baseline",
        "SHORT",
        False,
        "existing observation-time discovery priority score",
    ),
    Phase27CandidateSpec(
        "ridge_relative_long",
        "ridge_relative_return",
        "LONG",
        True,
        "ridge forecast of same-session median-residualized directional return",
    ),
    Phase27CandidateSpec(
        "ridge_relative_short",
        "ridge_relative_return",
        "SHORT",
        True,
        "ridge forecast of same-session median-residualized directional return",
    ),
    Phase27CandidateSpec(
        "hgb_relative_long",
        "hgb_relative_return",
        "LONG",
        True,
        "histogram gradient boosting forecast of same-session median-residualized directional return",
    ),
    Phase27CandidateSpec(
        "hgb_relative_short",
        "hgb_relative_return",
        "SHORT",
        True,
        "histogram gradient boosting forecast of same-session median-residualized directional return",
    ),
    Phase27CandidateSpec(
        "pairwise_rank_long",
        "pairwise_logistic_rank",
        "LONG",
        True,
        "pairwise logistic utility score trained on within-session directional-return ordering",
    ),
    Phase27CandidateSpec(
        "pairwise_rank_short",
        "pairwise_logistic_rank",
        "SHORT",
        True,
        "pairwise logistic utility score trained on within-session directional-return ordering",
    ),
)


def phase27_hyperparameter_grid_payload() -> dict[str, object]:
    return {
        "ridge": {"alpha": list(PHASE27_RIDGE_ALPHA_GRID)},
        "hgb": {
            "max_leaf_nodes": list(PHASE27_HGB_MAX_LEAF_NODES_GRID),
            "learning_rate": list(PHASE27_HGB_LEARNING_RATE_GRID),
            "max_iter": list(PHASE27_HGB_MAX_ITER_GRID),
            "l2_regularization": list(PHASE27_HGB_L2_REGULARIZATION_GRID),
            "min_samples_leaf": PHASE27_HGB_MIN_SAMPLES_LEAF,
        },
        "pairwise_logistic": {
            "C": list(PHASE27_PAIRWISE_C_GRID),
            "max_unordered_pairs_per_session": PHASE27_PAIRWISE_MAX_UNORDERED_PAIRS_PER_SESSION,
            "pair_seed": PHASE27_PAIRWISE_SEED,
        },
    }


def phase27_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE27_POLICY_CONTRACT_VERSION,
        "source_phase26_policy_fingerprint": PHASE27_SOURCE_PHASE26_POLICY_FINGERPRINT,
        "research_start": PHASE27_RESEARCH_START,
        "development_end": PHASE27_DEVELOPMENT_END,
        "protected_start": PHASE27_PROTECTED_START,
        "protected_end": PHASE27_PROTECTED_END,
        "outcome_horizon_sessions": PHASE27_OUTCOME_HORIZON_SESSIONS,
        "purge_sessions": PHASE27_PURGE_SESSIONS,
        "min_direction_rows_per_session": PHASE27_MIN_DIRECTION_ROWS_PER_SESSION,
        "signal_tail_fraction": PHASE27_SIGNAL_TAIL_FRACTION,
        "predictor_fields": list(PHASE27_PREDICTOR_FIELDS),
        "baseline_score_field": PHASE27_BASELINE_SCORE_FIELD,
        "model_input_regime_fields": list(PHASE27_MODEL_INPUT_REGIME_FIELDS),
        "robustness_state_fields": list(PHASE27_ROBUSTNESS_STATE_FIELDS),
        "forbidden_protected_outcome_fields": list(PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS),
        "candidates": [asdict(candidate) for candidate in PHASE27_CANDIDATES],
        "hyperparameter_grids": phase27_hyperparameter_grid_payload(),
        "inner_tuning_folds": PHASE27_INNER_TUNING_FOLDS,
        "inner_tuning_objective": "MEAN_SESSION_SPEARMAN_IC",
        "selection_fraction": PHASE27_SELECTION_FRACTION,
        "selection_folds": PHASE27_SELECTION_FOLDS,
        "internal_validation_folds": PHASE27_INTERNAL_VALIDATION_FOLDS,
        "protected_folds": PHASE27_PROTECTED_FOLDS,
        "cost_grid_bps": list(PHASE27_COST_GRID_BPS),
        "primary_cost_bps": PHASE27_PRIMARY_COST_BPS,
        "stress_cost_bps": PHASE27_STRESS_COST_BPS,
        "bootstrap_block_sessions": PHASE27_BOOTSTRAP_BLOCK_SESSIONS,
        "bootstrap_replicates": PHASE27_BOOTSTRAP_REPLICATES,
        "bootstrap_seed": PHASE27_BOOTSTRAP_SEED,
        "selection_confidence": PHASE27_SELECTION_CONFIDENCE,
        "internal_confidence": PHASE27_INTERNAL_CONFIDENCE,
        "protected_confidence": PHASE27_PROTECTED_CONFIDENCE,
        "selection_min_raw_rows": PHASE27_SELECTION_MIN_RAW_ROWS,
        "selection_min_signal_sessions": PHASE27_SELECTION_MIN_SIGNAL_SESSIONS,
        "internal_min_raw_rows": PHASE27_INTERNAL_MIN_RAW_ROWS,
        "internal_min_signal_sessions": PHASE27_INTERNAL_MIN_SIGNAL_SESSIONS,
        "protected_min_raw_rows": PHASE27_PROTECTED_MIN_RAW_ROWS,
        "protected_min_signal_sessions": PHASE27_PROTECTED_MIN_SIGNAL_SESSIONS,
        "selection_min_positive_folds": PHASE27_SELECTION_MIN_POSITIVE_FOLDS,
        "internal_min_positive_folds": PHASE27_INTERNAL_MIN_POSITIVE_FOLDS,
        "protected_min_positive_folds": PHASE27_PROTECTED_MIN_POSITIVE_FOLDS,
        "min_positive_year_fraction": PHASE27_MIN_POSITIVE_YEAR_FRACTION,
        "min_year_signal_sessions": PHASE27_MIN_YEAR_SIGNAL_SESSIONS,
        "min_positive_regime_fraction": PHASE27_MIN_POSITIVE_REGIME_FRACTION,
        "min_regime_signal_sessions": PHASE27_MIN_REGIME_SIGNAL_SESSIONS,
        "max_single_session_row_fraction": PHASE27_MAX_SINGLE_SESSION_ROW_FRACTION,
        "multiple_testing_method": PHASE27_MULTIPLE_TESTING_METHOD,
        "multiple_testing_alpha": PHASE27_MULTIPLE_TESTING_ALPHA,
        "max_selection_winners_per_direction": PHASE27_MAX_SELECTION_WINNERS_PER_DIRECTION,
        "max_finalists_per_direction": PHASE27_MAX_FINALISTS_PER_DIRECTION,
        "runner_up_substitution_allowed": PHASE27_RUNNER_UP_SUBSTITUTION_ALLOWED,
        "win_rate_is_hard_gate": PHASE27_WIN_RATE_IS_HARD_GATE,
        "median_return_is_hard_gate": PHASE27_MEDIAN_RETURN_IS_HARD_GATE,
        "deflated_performance_diagnostic_required": PHASE27_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED,
        "protected_returns_before_finalists_allowed": PHASE27_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        "phase26_protected_holdout_one_time_reuse_requires_blindness_audit": True,
        "phase26_protected_holdout_consumed_after_any_phase27_return_read": True,
        "provider_reads": PHASE27_PROVIDER_READS,
        "provider_writes": PHASE27_PROVIDER_WRITES,
        "broker_reads": PHASE27_BROKER_READS,
        "broker_writes": PHASE27_BROKER_WRITES,
        "order_writes": PHASE27_ORDER_WRITES,
        "paper_submits": PHASE27_PAPER_SUBMITS,
        "live_writes": PHASE27_LIVE_WRITES,
        "automation_writes": PHASE27_AUTOMATION_WRITES,
        "automatic_broker_failover": PHASE27_AUTOMATIC_BROKER_FAILOVER,
    }


def phase27_policy_fingerprint() -> str:
    raw = json.dumps(
        phase27_policy_payload(), sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
