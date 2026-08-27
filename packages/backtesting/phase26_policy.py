from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal


PHASE26_POLICY_CONTRACT_VERSION = (
    "phase26-policy-v1-production-path-native-alpha-24-candidates-one-phase-gate"
)
PHASE26_RESEARCH_START = "2021-08-16"
PHASE26_DEVELOPMENT_END = "2026-05-06"
PHASE26_PROTECTED_START = "2026-05-12"
PHASE26_PROTECTED_END = "2026-08-11"
PHASE26_OUTCOME_HORIZON_SESSIONS = 3
PHASE26_PURGE_SESSIONS = 3

PHASE26_COST_GRID_BPS = (0.0, 5.0, 10.0, 25.0)
PHASE26_PRIMARY_COST_BPS = 10.0
PHASE26_STRESS_COST_BPS = 25.0

PHASE26_SELECTION_FRACTION = 0.75
PHASE26_SELECTION_FOLDS = 6
PHASE26_INTERNAL_VALIDATION_FOLDS = 3
PHASE26_PROTECTED_FOLDS = 3

PHASE26_BOOTSTRAP_BLOCK_SESSIONS = 6
PHASE26_BOOTSTRAP_REPLICATES = 2000
PHASE26_BOOTSTRAP_SEED = 260126
PHASE26_SELECTION_CONFIDENCE = 0.95
PHASE26_INTERNAL_CONFIDENCE = 0.90
PHASE26_PROTECTED_CONFIDENCE = 0.80

PHASE26_SELECTION_MIN_RAW_ROWS = 1000
PHASE26_SELECTION_MIN_SIGNAL_SESSIONS = 250
PHASE26_INTERNAL_MIN_RAW_ROWS = 300
PHASE26_INTERNAL_MIN_SIGNAL_SESSIONS = 80
PHASE26_PROTECTED_MIN_RAW_ROWS = 75
PHASE26_PROTECTED_MIN_SIGNAL_SESSIONS = 24
PHASE26_SELECTION_MIN_POSITIVE_FOLDS = 5
PHASE26_INTERNAL_MIN_POSITIVE_FOLDS = 2
PHASE26_PROTECTED_MIN_POSITIVE_FOLDS = 2
PHASE26_MIN_POSITIVE_YEAR_FRACTION = 0.60
PHASE26_MIN_YEAR_SIGNAL_SESSIONS = 20
PHASE26_MIN_POSITIVE_REGIME_FRACTION = 0.50
PHASE26_MIN_REGIME_SIGNAL_SESSIONS = 20
PHASE26_MAX_SINGLE_SESSION_ROW_FRACTION = 0.10

PHASE26_MULTIPLE_TESTING_METHOD = "HOLM_BONFERRONI_GLOBAL_24"
PHASE26_MULTIPLE_TESTING_ALPHA = 0.05
PHASE26_MAX_FINALISTS_PER_FAMILY_DIRECTION = 1
PHASE26_MEDIAN_RETURN_IS_HARD_GATE = False
PHASE26_WIN_RATE_IS_HARD_GATE = False
PHASE26_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED = True

PHASE26_PROVIDER_READS = 0
PHASE26_PROVIDER_WRITES = 0
PHASE26_BROKER_READS = 0
PHASE26_BROKER_WRITES = 0
PHASE26_ORDER_WRITES = 0
PHASE26_PAPER_SUBMITS = 0
PHASE26_LIVE_WRITES = 0
PHASE26_AUTOMATION_WRITES = 0
PHASE26_SECTOR_MAPPING_AUTHORITY = False
PHASE26_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED = False

ConditionOperator = Literal["GT", "GE", "LT", "LE", "BETWEEN"]
StrategyDirection = Literal["LONG", "SHORT"]


@dataclass(frozen=True, slots=True)
class SignalCondition:
    feature: str
    operator: ConditionOperator
    value: float
    upper: float | None = None


@dataclass(frozen=True, slots=True)
class Phase26CandidateSpec:
    candidate_id: str
    family: str
    direction: StrategyDirection
    thesis: str
    conditions: tuple[SignalCondition, ...]


def _c(feature: str, operator: ConditionOperator, value: float, upper: float | None = None) -> SignalCondition:
    return SignalCondition(feature=feature, operator=operator, value=float(value), upper=upper)


# Field naming is frozen for the Phase26 observation builder:
# d1_* = finalized daily feature, h4_* / h1_* = final regular-session feature row.
# cs_*_pct = same-session production-candidate percentile in [0, 1].
# gap_return/intraday_return/return_5d/return_20d are exact-interval derived fields.
# bull_block_score/bear_block_score are independent five-block deterministic composites.
PHASE26_CANDIDATES: tuple[Phase26CandidateSpec, ...] = (
    # 1) Cross-sectional relative strength / weakness.
    Phase26CandidateSpec(
        "cs_rs_long_quality",
        "cross_sectional_relative_strength",
        "LONG",
        "Buy unusually strong production candidates when trend quality and liquidity confirm the cross-sectional lead.",
        (
            _c("cs_vol_scaled_return_20d_pct", "GE", 0.80),
            _c("d1_price_distance_ema_20", "GT", 0.0),
            _c("h4_price_distance_ema_20", "GT", 0.0),
            _c("d1_directional_efficiency_20", "GE", 0.20),
            _c("d1_relative_dollar_volume_20", "GE", 0.75),
        ),
    ),
    Phase26CandidateSpec(
        "cs_rs_long_acceleration",
        "cross_sectional_relative_strength",
        "LONG",
        "Buy top-ranked medium-term strength only when the finalized session and short horizons are still accelerating.",
        (
            _c("cs_return_20d_pct", "GE", 0.85),
            _c("d1_return_1", "GT", 0.0),
            _c("h1_macd_hist_12_26_9", "GT", 0.0),
            _c("h4_rsi_14", "GE", 50.0),
            _c("d1_natr_14", "BETWEEN", 0.005, 0.08),
        ),
    ),
    Phase26CandidateSpec(
        "cs_weak_short_break",
        "cross_sectional_relative_strength",
        "SHORT",
        "Short bottom-ranked names only when weakness is accompanied by an actual breakdown, participation, and weak intraday momentum.",
        (
            _c("cs_return_20d_pct", "LE", 0.20),
            _c("d1_breakdown_distance_20", "LE", 0.0),
            _c("cs_realized_volatility_20_pct", "GE", 0.50),
            _c("h4_rsi_14", "LT", 45.0),
            _c("d1_relative_dollar_volume_20", "GE", 1.0),
        ),
    ),
    Phase26CandidateSpec(
        "cs_weak_short_failed_bounce",
        "cross_sectional_relative_strength",
        "SHORT",
        "Short persistent cross-sectional laggards after a weak bounce fails on the shortest horizon.",
        (
            _c("cs_vol_scaled_return_20d_pct", "LE", 0.15),
            _c("h1_price_distance_ema_20", "LT", 0.0),
            _c("h1_macd_hist_12_26_9", "LT", 0.0),
            _c("d1_bb_position_20", "LE", 0.45),
            _c("d1_directional_efficiency_20", "GE", 0.15),
        ),
    ),

    # 2) Volatility/liquidity-conditioned mean reversion.
    Phase26CandidateSpec(
        "mr_long_oversold_liquid",
        "volatility_liquidity_mean_reversion",
        "LONG",
        "Buy deeply oversold but liquid candidates only after the final intraday horizon turns upward.",
        (
            _c("d1_bb_position_20", "LE", 0.15),
            _c("d1_rsi_14", "LE", 35.0),
            _c("d1_price_distance_ema_20", "LT", 0.0),
            _c("cs_dollar_volume_pct", "GE", 0.40),
            _c("d1_natr_14", "BETWEEN", 0.01, 0.08),
            _c("h1_macd_hist_12_26_9", "GT", 0.0),
        ),
    ),
    Phase26CandidateSpec(
        "mr_long_drawdown_reclaim",
        "volatility_liquidity_mean_reversion",
        "LONG",
        "Buy a substantial rolling drawdown only when the session and final hourly bar show a reclaim with participation.",
        (
            _c("d1_drawdown_20", "LE", -0.08),
            _c("d1_return_1", "GT", 0.0),
            _c("h1_price_distance_ema_20", "GT", 0.0),
            _c("h1_rsi_14", "GT", 45.0),
            _c("d1_relative_volume_20", "GE", 1.0),
        ),
    ),
    Phase26CandidateSpec(
        "mr_short_exhaustion",
        "volatility_liquidity_mean_reversion",
        "SHORT",
        "Fade extreme upside extension only after the final hourly momentum has rolled over and liquidity remains adequate.",
        (
            _c("d1_bb_position_20", "GE", 0.90),
            _c("d1_rsi_14", "GE", 72.0),
            _c("d1_price_distance_ema_20", "GE", 0.06),
            _c("h1_macd_hist_12_26_9", "LT", 0.0),
            _c("cs_dollar_volume_pct", "GE", 0.40),
        ),
    ),
    Phase26CandidateSpec(
        "mr_short_spike_fade",
        "volatility_liquidity_mean_reversion",
        "SHORT",
        "Fade a high-participation upside spike that closes below its open and loses the hourly trend.",
        (
            _c("gap_return", "GE", 0.03),
            _c("intraday_return", "LT", 0.0),
            _c("d1_rsi_14", "GE", 60.0),
            _c("h1_price_distance_ema_20", "LT", 0.0),
            _c("d1_relative_volume_20", "GE", 1.25),
        ),
    ),

    # 3) Volatility-normalized breakout / breakdown.
    Phase26CandidateSpec(
        "breakout_long_participation",
        "volatility_normalized_breakout",
        "LONG",
        "Buy a real rolling-range breakout only with directional efficiency, participation, and positive lower-timeframe momentum.",
        (
            _c("d1_breakout_distance_20", "GE", 0.0),
            _c("d1_directional_efficiency_20", "GE", 0.30),
            _c("d1_relative_volume_20", "GE", 1.25),
            _c("h4_macd_hist_12_26_9", "GT", 0.0),
            _c("h1_rsi_14", "GT", 50.0),
            _c("d1_natr_14", "LE", 0.08),
        ),
    ),
    Phase26CandidateSpec(
        "breakout_long_squeeze_release",
        "volatility_normalized_breakout",
        "LONG",
        "Buy a breakout from relatively compressed volatility when volume expands and the 4h trend is positive.",
        (
            _c("d1_breakout_distance_20", "GE", 0.0),
            _c("cs_bb_width_20_pct", "LE", 0.35),
            _c("d1_volume_zscore_20", "GE", 1.0),
            _c("h4_price_distance_ema_20", "GT", 0.0),
        ),
    ),
    Phase26CandidateSpec(
        "breakdown_short_participation",
        "volatility_normalized_breakout",
        "SHORT",
        "Short a confirmed range breakdown only when efficiency, volume expansion, and shorter-horizon momentum agree.",
        (
            _c("d1_breakdown_distance_20", "LE", 0.0),
            _c("d1_directional_efficiency_20", "GE", 0.35),
            _c("d1_volume_zscore_20", "GE", 1.0),
            _c("h4_macd_hist_12_26_9", "LT", 0.0),
            _c("h1_rsi_14", "LT", 45.0),
            _c("d1_natr_14", "LE", 0.10),
        ),
    ),
    Phase26CandidateSpec(
        "breakdown_short_high_vol_liquid",
        "volatility_normalized_breakout",
        "SHORT",
        "Short high-volatility breakdowns only when dollar participation is elevated and the final hourly trend remains weak.",
        (
            _c("d1_breakdown_distance_20", "LE", 0.0),
            _c("cs_realized_volatility_20_pct", "GE", 0.65),
            _c("d1_relative_dollar_volume_20", "GE", 1.25),
            _c("h1_price_distance_ema_20", "LT", 0.0),
            _c("h1_macd_hist_12_26_9", "LT", 0.0),
        ),
    ),

    # 4) Multi-timeframe state transitions.
    Phase26CandidateSpec(
        "mtf_long_full_alignment",
        "multi_timeframe_state_transition",
        "LONG",
        "Buy when daily, 4h, and 1h trends are aligned without an already-extreme hourly RSI.",
        (
            _c("d1_price_distance_ema_20", "GT", 0.0),
            _c("h4_price_distance_ema_20", "GT", 0.0),
            _c("h1_price_distance_ema_20", "GT", 0.0),
            _c("d1_macd_hist_12_26_9", "GT", 0.0),
            _c("h4_macd_hist_12_26_9", "GT", 0.0),
            _c("h1_rsi_14", "BETWEEN", 50.0, 70.0),
            _c("d1_directional_efficiency_20", "GE", 0.20),
        ),
    ),
    Phase26CandidateSpec(
        "mtf_long_pullback_resume",
        "multi_timeframe_state_transition",
        "LONG",
        "Buy a daily uptrend after a 4h pullback when the final hourly bar has already resumed upward.",
        (
            _c("d1_price_distance_ema_20", "GT", 0.0),
            _c("d1_ema_20_slope_1", "GT", 0.0),
            _c("h4_price_distance_ema_20", "LT", 0.0),
            _c("h1_price_distance_ema_20", "GT", 0.0),
            _c("h1_macd_hist_12_26_9", "GT", 0.0),
        ),
    ),
    Phase26CandidateSpec(
        "mtf_short_cascade",
        "multi_timeframe_state_transition",
        "SHORT",
        "Short sustained weakness when all three horizons remain below their EMA and lower-timeframe momentum confirms.",
        (
            _c("d1_price_distance_ema_20", "LT", 0.0),
            _c("h4_price_distance_ema_20", "LT", 0.0),
            _c("h1_price_distance_ema_20", "LT", 0.0),
            _c("h4_macd_hist_12_26_9", "LT", 0.0),
            _c("h1_macd_hist_12_26_9", "LT", 0.0),
            _c("d1_rsi_14", "LT", 50.0),
        ),
    ),
    Phase26CandidateSpec(
        "mtf_short_bounce_failure",
        "multi_timeframe_state_transition",
        "SHORT",
        "Short a bounce inside a daily downtrend after the 4h recovery fails on the final hourly bar.",
        (
            _c("d1_price_distance_ema_20", "LT", 0.0),
            _c("d1_ema_20_slope_1", "LT", 0.0),
            _c("h4_rsi_14", "GT", 50.0),
            _c("h1_rsi_14", "LT", 45.0),
            _c("h1_macd_hist_12_26_9", "LT", 0.0),
            _c("d1_bb_position_20", "LT", 0.50),
        ),
    ),

    # 5) Gap continuation / reversal.
    Phase26CandidateSpec(
        "gap_long_hold",
        "gap_behavior",
        "LONG",
        "Buy a moderate positive gap that holds and closes strong with above-average participation.",
        (
            _c("gap_return", "BETWEEN", 0.01, 0.05),
            _c("intraday_return", "GT", 0.0),
            _c("d1_range_position_20", "GE", 0.75),
            _c("d1_relative_volume_20", "GE", 1.0),
        ),
    ),
    Phase26CandidateSpec(
        "gap_long_reclaim",
        "gap_behavior",
        "LONG",
        "Buy a negative gap only when the stock fully reclaims the prior close and the final hourly momentum is positive.",
        (
            _c("gap_return", "BETWEEN", -0.05, -0.01),
            _c("intraday_return", "GE", 0.02),
            _c("d1_return_1", "GT", 0.0),
            _c("h1_macd_hist_12_26_9", "GT", 0.0),
        ),
    ),
    Phase26CandidateSpec(
        "gap_short_break",
        "gap_behavior",
        "SHORT",
        "Short a moderate negative gap that continues lower and closes near the bottom of its recent range with participation.",
        (
            _c("gap_return", "BETWEEN", -0.05, -0.01),
            _c("intraday_return", "LT", 0.0),
            _c("d1_range_position_20", "LE", 0.25),
            _c("d1_relative_volume_20", "GE", 1.0),
        ),
    ),
    Phase26CandidateSpec(
        "gap_short_fade",
        "gap_behavior",
        "SHORT",
        "Fade a positive gap that reverses sharply during the session while momentum remains extended and hourly momentum turns down.",
        (
            _c("gap_return", "GE", 0.02),
            _c("intraday_return", "LE", -0.02),
            _c("d1_rsi_14", "GE", 60.0),
            _c("h1_macd_hist_12_26_9", "LT", 0.0),
        ),
    ),

    # 6) Independent feature-block composites.
    Phase26CandidateSpec(
        "composite_long_quality4",
        "independent_feature_block_composite",
        "LONG",
        "Buy candidates with at least four of five independent bullish evidence blocks plus above-median cross-sectional strength.",
        (
            _c("bull_block_score", "GE", 4.0),
            _c("cs_return_20d_pct", "GE", 0.60),
        ),
    ),
    Phase26CandidateSpec(
        "composite_long_quality5_lowvol",
        "independent_feature_block_composite",
        "LONG",
        "Require all five bullish blocks when realized volatility is not extreme.",
        (
            _c("bull_block_score", "GE", 5.0),
            _c("d1_natr_14", "LE", 0.08),
        ),
    ),
    Phase26CandidateSpec(
        "composite_short_deterioration4",
        "independent_feature_block_composite",
        "SHORT",
        "Short candidates with at least four independently defined bearish deterioration blocks and below-median medium-term strength.",
        (
            _c("bear_block_score", "GE", 4.0),
            _c("cs_return_20d_pct", "LE", 0.40),
        ),
    ),
    Phase26CandidateSpec(
        "composite_short_break5_highvol",
        "independent_feature_block_composite",
        "SHORT",
        "Require all five bearish blocks when realized volatility is at or above the session median.",
        (
            _c("bear_block_score", "GE", 5.0),
            _c("cs_realized_volatility_20_pct", "GE", 0.50),
        ),
    ),
)


PHASE26_BULL_BLOCKS: tuple[tuple[SignalCondition, ...], ...] = (
    (_c("d1_price_distance_ema_20", "GT", 0.0), _c("d1_ema_20_slope_1", "GT", 0.0)),
    (_c("d1_rsi_14", "GE", 50.0), _c("d1_macd_hist_12_26_9", "GT", 0.0)),
    (_c("d1_range_position_20", "GE", 0.60), _c("d1_directional_efficiency_20", "GE", 0.20)),
    (_c("d1_relative_dollar_volume_20", "GE", 1.0),),
    (_c("h4_price_distance_ema_20", "GT", 0.0), _c("h1_price_distance_ema_20", "GT", 0.0)),
)

PHASE26_BEAR_BLOCKS: tuple[tuple[SignalCondition, ...], ...] = (
    (_c("d1_price_distance_ema_20", "LT", 0.0), _c("d1_ema_20_slope_1", "LT", 0.0)),
    (_c("d1_rsi_14", "LE", 45.0), _c("d1_macd_hist_12_26_9", "LT", 0.0)),
    (_c("d1_range_position_20", "LE", 0.30),),
    (_c("d1_relative_volume_20", "GE", 1.0),),
    (_c("h4_price_distance_ema_20", "LT", 0.0), _c("h1_macd_hist_12_26_9", "LT", 0.0)),
)


def phase26_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE26_POLICY_CONTRACT_VERSION,
        "dates": {
            "research_start": PHASE26_RESEARCH_START,
            "development_end": PHASE26_DEVELOPMENT_END,
            "protected_start": PHASE26_PROTECTED_START,
            "protected_end": PHASE26_PROTECTED_END,
        },
        "outcome": {
            "horizon_sessions": PHASE26_OUTCOME_HORIZON_SESSIONS,
            "purge_sessions": PHASE26_PURGE_SESSIONS,
            "endpoint_only": True,
            "observation_exact_interval_required": True,
            "future_endpoint_same_provider_native_ticker_required": True,
            "future_endpoint_must_remain_inside_observation_interval": False,
            "split_crossings_censored": True,
        },
        "economics": {
            "cost_grid_bps": PHASE26_COST_GRID_BPS,
            "primary_cost_bps": PHASE26_PRIMARY_COST_BPS,
            "stress_cost_bps": PHASE26_STRESS_COST_BPS,
        },
        "chronology": {
            "selection_fraction": PHASE26_SELECTION_FRACTION,
            "selection_folds": PHASE26_SELECTION_FOLDS,
            "internal_validation_folds": PHASE26_INTERNAL_VALIDATION_FOLDS,
            "protected_folds": PHASE26_PROTECTED_FOLDS,
            "random_row_split_allowed": False,
        },
        "bootstrap": {
            "block_sessions": PHASE26_BOOTSTRAP_BLOCK_SESSIONS,
            "replicates": PHASE26_BOOTSTRAP_REPLICATES,
            "seed": PHASE26_BOOTSTRAP_SEED,
            "selection_confidence": PHASE26_SELECTION_CONFIDENCE,
            "internal_confidence": PHASE26_INTERNAL_CONFIDENCE,
            "protected_confidence": PHASE26_PROTECTED_CONFIDENCE,
        },
        "minimum_evidence": {
            "selection_rows": PHASE26_SELECTION_MIN_RAW_ROWS,
            "selection_sessions": PHASE26_SELECTION_MIN_SIGNAL_SESSIONS,
            "internal_rows": PHASE26_INTERNAL_MIN_RAW_ROWS,
            "internal_sessions": PHASE26_INTERNAL_MIN_SIGNAL_SESSIONS,
            "protected_rows": PHASE26_PROTECTED_MIN_RAW_ROWS,
            "protected_sessions": PHASE26_PROTECTED_MIN_SIGNAL_SESSIONS,
            "selection_positive_folds": PHASE26_SELECTION_MIN_POSITIVE_FOLDS,
            "internal_positive_folds": PHASE26_INTERNAL_MIN_POSITIVE_FOLDS,
            "protected_positive_folds": PHASE26_PROTECTED_MIN_POSITIVE_FOLDS,
        },
        "robustness": {
            "min_positive_year_fraction": PHASE26_MIN_POSITIVE_YEAR_FRACTION,
            "min_year_signal_sessions": PHASE26_MIN_YEAR_SIGNAL_SESSIONS,
            "min_positive_regime_fraction": PHASE26_MIN_POSITIVE_REGIME_FRACTION,
            "min_regime_signal_sessions": PHASE26_MIN_REGIME_SIGNAL_SESSIONS,
            "max_single_session_row_fraction": PHASE26_MAX_SINGLE_SESSION_ROW_FRACTION,
            "primary_mean_must_be_positive": True,
            "stress_mean_must_be_positive": True,
            "block_bootstrap_lcb_must_be_positive": True,
            "median_return_is_hard_gate": PHASE26_MEDIAN_RETURN_IS_HARD_GATE,
            "win_rate_is_hard_gate": PHASE26_WIN_RATE_IS_HARD_GATE,
        },
        "multiple_testing": {
            "method": PHASE26_MULTIPLE_TESTING_METHOD,
            "alpha": PHASE26_MULTIPLE_TESTING_ALPHA,
            "max_finalists_per_family_direction": PHASE26_MAX_FINALISTS_PER_FAMILY_DIRECTION,
            "deflated_performance_diagnostic_required": PHASE26_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED,
        },
        "authority": {
            "provider_reads": PHASE26_PROVIDER_READS,
            "provider_writes": PHASE26_PROVIDER_WRITES,
            "broker_reads": PHASE26_BROKER_READS,
            "broker_writes": PHASE26_BROKER_WRITES,
            "order_writes": PHASE26_ORDER_WRITES,
            "paper_submits": PHASE26_PAPER_SUBMITS,
            "live_writes": PHASE26_LIVE_WRITES,
            "automation_writes": PHASE26_AUTOMATION_WRITES,
            "sector_mapping_authority": PHASE26_SECTOR_MAPPING_AUTHORITY,
            "protected_returns_before_finalists_allowed": PHASE26_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        },
        "bull_blocks": [[asdict(condition) for condition in block] for block in PHASE26_BULL_BLOCKS],
        "bear_blocks": [[asdict(condition) for condition in block] for block in PHASE26_BEAR_BLOCKS],
        "candidates": [asdict(candidate) for candidate in PHASE26_CANDIDATES],
    }


def phase26_policy_fingerprint() -> str:
    raw = json.dumps(phase26_policy_payload(), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


assert len(PHASE26_CANDIDATES) == 24
assert len({candidate.candidate_id for candidate in PHASE26_CANDIDATES}) == 24
assert PHASE26_PURGE_SESSIONS == PHASE26_OUTCOME_HORIZON_SESSIONS
assert PHASE26_PRIMARY_COST_BPS in PHASE26_COST_GRID_BPS
assert PHASE26_STRESS_COST_BPS in PHASE26_COST_GRID_BPS
assert PHASE26_MEDIAN_RETURN_IS_HARD_GATE is False
assert PHASE26_WIN_RATE_IS_HARD_GATE is False
assert PHASE26_SECTOR_MAPPING_AUTHORITY is False
assert PHASE26_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED is False
