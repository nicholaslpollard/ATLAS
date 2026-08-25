from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


PHASE24_GATE1_CONTRACT_VERSION = (
    "phase24-gate1-v1-preregistered-challenger-search-no-protected-read"
)
PHASE24_GATE1_PRIMARY_COST_BPS = 10.0
PHASE24_GATE1_STRESS_COST_BPS = 25.0
PHASE24_GATE1_OUTCOME_HORIZON_SESSIONS = 3
PHASE24_GATE1_SELECTION_FRACTION = 0.75
PHASE24_GATE1_PURGE_SESSIONS = 3
PHASE24_GATE1_SELECTION_FOLDS = 6
PHASE24_GATE1_INTERNAL_VALIDATION_FOLDS = 3
PHASE24_GATE1_PROTECTED_FOLDS = 3
PHASE24_GATE1_BOOTSTRAP_BLOCK_SESSIONS = 6
PHASE24_GATE1_BOOTSTRAP_REPLICATES = 2000
PHASE24_GATE1_BOOTSTRAP_SEED = 240124
PHASE24_GATE1_SELECTION_CONFIDENCE = 0.95
PHASE24_GATE1_INTERNAL_VALIDATION_CONFIDENCE = 0.90
PHASE24_GATE1_PROTECTED_CONFIDENCE = 0.80
PHASE24_GATE1_MULTIPLE_TESTING_METHOD = "HOLM_BONFERRONI_WITHIN_FAMILY_DIRECTION"
PHASE24_GATE1_MULTIPLE_TESTING_ALPHA = 0.05
PHASE24_GATE1_MAX_FINALISTS_PER_FAMILY_DIRECTION = 1

PHASE24_GATE1_SELECTION_MIN_RAW_ROWS = 1000
PHASE24_GATE1_SELECTION_MIN_SIGNAL_SESSIONS = 250
PHASE24_GATE1_INTERNAL_MIN_RAW_ROWS = 300
PHASE24_GATE1_INTERNAL_MIN_SIGNAL_SESSIONS = 80
PHASE24_GATE1_PROTECTED_MIN_RAW_ROWS = 75
PHASE24_GATE1_PROTECTED_MIN_SIGNAL_SESSIONS = 24
PHASE24_GATE1_SELECTION_MIN_POSITIVE_FOLDS = 5
PHASE24_GATE1_INTERNAL_MIN_POSITIVE_FOLDS = 2
PHASE24_GATE1_PROTECTED_MIN_POSITIVE_FOLDS = 2
PHASE24_GATE1_MIN_POSITIVE_YEAR_FRACTION = 0.60
PHASE24_GATE1_MIN_YEAR_SIGNAL_SESSIONS = 20
PHASE24_GATE1_MIN_POSITIVE_REGIME_FRACTION = 0.50
PHASE24_GATE1_MIN_REGIME_SIGNAL_SESSIONS = 20
PHASE24_GATE1_MAX_SINGLE_SESSION_ROW_FRACTION = 0.10
PHASE24_GATE1_REQUIRE_PRIMARY_MEDIAN_POSITIVE = True
PHASE24_GATE1_REQUIRE_PRIMARY_POSITIVE_RATE_AT_LEAST_HALF = True
PHASE24_GATE1_REQUIRE_STRESS_MEAN_POSITIVE = True
PHASE24_GATE1_REQUIRE_BLOCK_BOOTSTRAP_LCB_POSITIVE = True

PHASE24_GATE1_EXTERNAL_PROVIDER_READS = False
PHASE24_GATE1_EXTERNAL_PROVIDER_WRITES = False
PHASE24_GATE1_BROKER_READS = False
PHASE24_GATE1_BROKER_WRITES = False
PHASE24_GATE1_ORDER_WRITES = False
PHASE24_GATE1_PAPER_SUBMITS = False
PHASE24_GATE1_LIVE_WRITES = False
PHASE24_GATE1_PRODUCTION_ML_WRITES = False
PHASE24_GATE1_PHASE11_SUPPORT_WRITES = False
PHASE24_GATE1_PROTECTED_EVIDENCE_READS = False
PHASE24_GATE1_GATE0_CURRENT_EVIDENCE_USED_FOR_SELECTION = False
PHASE24_GATE1_INCUMBENT_PROTECTED_EVIDENCE_IS_FRESH = False


@dataclass(frozen=True, slots=True)
class RuleMutationSpec:
    kind: str
    reason_code: str
    left: str | None = None
    comparison: str | None = None
    right_value: float | None = None


@dataclass(frozen=True, slots=True)
class ChallengerVariantSpec:
    variant_id: str
    base_strategy_id: str
    family: str
    direction: str
    mutations: tuple[RuleMutationSpec, ...]


def _replace(reason_code: str, value: float) -> RuleMutationSpec:
    return RuleMutationSpec(kind="replace_right_value", reason_code=reason_code, right_value=value)


def _add(feature: str, comparison: str, value: float, reason_code: str) -> RuleMutationSpec:
    return RuleMutationSpec(
        kind="add_condition",
        reason_code=reason_code,
        left=feature,
        comparison=comparison,
        right_value=value,
    )


def _variant(
    variant_id: str,
    base_strategy_id: str,
    family: str,
    direction: str,
    *mutations: RuleMutationSpec,
) -> ChallengerVariantSpec:
    return ChallengerVariantSpec(
        variant_id=variant_id,
        base_strategy_id=base_strategy_id,
        family=family,
        direction=direction,
        mutations=tuple(mutations),
    )


PHASE24_GATE1_CHALLENGER_VARIANTS: tuple[ChallengerVariantSpec, ...] = (
    _variant(
        "trend_following_long_v2_rsi55",
        "trend_following_long_v1",
        "trend_following",
        "LONG",
        _add("rsi_14", "GT", 55.0, "phase24_rsi_above_55"),
    ),
    _variant(
        "trend_following_long_v2_rvol1",
        "trend_following_long_v1",
        "trend_following",
        "LONG",
        _add("relative_volume_20", "GT", 1.0, "phase24_rvol_above_1"),
    ),
    _variant(
        "trend_following_long_v2_rsi55_rvol1",
        "trend_following_long_v1",
        "trend_following",
        "LONG",
        _add("rsi_14", "GT", 55.0, "phase24_rsi_above_55"),
        _add("relative_volume_20", "GT", 1.0, "phase24_rvol_above_1"),
    ),
    _variant(
        "trend_following_short_v2_rsi45",
        "trend_following_short_v1",
        "trend_following",
        "SHORT",
        _add("rsi_14", "LT", 45.0, "phase24_rsi_below_45"),
    ),
    _variant(
        "trend_following_short_v2_rvol1",
        "trend_following_short_v1",
        "trend_following",
        "SHORT",
        _add("relative_volume_20", "GT", 1.0, "phase24_rvol_above_1"),
    ),
    _variant(
        "trend_following_short_v2_rsi45_rvol1",
        "trend_following_short_v1",
        "trend_following",
        "SHORT",
        _add("rsi_14", "LT", 45.0, "phase24_rsi_below_45"),
        _add("relative_volume_20", "GT", 1.0, "phase24_rvol_above_1"),
    ),
    _variant(
        "momentum_long_v2_rsi55",
        "momentum_long_v1",
        "momentum",
        "LONG",
        _replace("rsi_above_midline", 55.0),
    ),
    _variant(
        "momentum_long_v2_rsi60",
        "momentum_long_v1",
        "momentum",
        "LONG",
        _replace("rsi_above_midline", 60.0),
    ),
    _variant(
        "momentum_long_v2_rsi55_rvol1",
        "momentum_long_v1",
        "momentum",
        "LONG",
        _replace("rsi_above_midline", 55.0),
        _add("relative_volume_20", "GT", 1.0, "phase24_rvol_above_1"),
    ),
    _variant(
        "momentum_long_v2_rsi60_rvol1",
        "momentum_long_v1",
        "momentum",
        "LONG",
        _replace("rsi_above_midline", 60.0),
        _add("relative_volume_20", "GT", 1.0, "phase24_rvol_above_1"),
    ),
    _variant(
        "momentum_short_v2_rsi45",
        "momentum_short_v1",
        "momentum",
        "SHORT",
        _replace("rsi_below_midline", 45.0),
    ),
    _variant(
        "momentum_short_v2_rsi40",
        "momentum_short_v1",
        "momentum",
        "SHORT",
        _replace("rsi_below_midline", 40.0),
    ),
    _variant(
        "momentum_short_v2_rsi45_rvol1",
        "momentum_short_v1",
        "momentum",
        "SHORT",
        _replace("rsi_below_midline", 45.0),
        _add("relative_volume_20", "GT", 1.0, "phase24_rvol_above_1"),
    ),
    _variant(
        "momentum_short_v2_rsi40_rvol1",
        "momentum_short_v1",
        "momentum",
        "SHORT",
        _replace("rsi_below_midline", 40.0),
        _add("relative_volume_20", "GT", 1.0, "phase24_rvol_above_1"),
    ),
    _variant(
        "breakout_long_v2_rvol125",
        "breakout_long_v1",
        "breakout",
        "LONG",
        _replace("volume_above_20_average", 1.25),
    ),
    _variant(
        "breakout_long_v2_rvol150",
        "breakout_long_v1",
        "breakout",
        "LONG",
        _replace("volume_above_20_average", 1.50),
    ),
    _variant(
        "breakout_long_v2_rvol125_rsi55",
        "breakout_long_v1",
        "breakout",
        "LONG",
        _replace("volume_above_20_average", 1.25),
        _add("rsi_14", "GT", 55.0, "phase24_rsi_above_55"),
    ),
    _variant(
        "breakout_long_v2_rvol150_rsi55",
        "breakout_long_v1",
        "breakout",
        "LONG",
        _replace("volume_above_20_average", 1.50),
        _add("rsi_14", "GT", 55.0, "phase24_rsi_above_55"),
    ),
    _variant(
        "breakdown_short_v2_rvol125",
        "breakdown_short_v1",
        "breakout",
        "SHORT",
        _replace("volume_above_20_average", 1.25),
    ),
    _variant(
        "breakdown_short_v2_rvol150",
        "breakdown_short_v1",
        "breakout",
        "SHORT",
        _replace("volume_above_20_average", 1.50),
    ),
    _variant(
        "breakdown_short_v2_rvol125_rsi45",
        "breakdown_short_v1",
        "breakout",
        "SHORT",
        _replace("volume_above_20_average", 1.25),
        _add("rsi_14", "LT", 45.0, "phase24_rsi_below_45"),
    ),
    _variant(
        "breakdown_short_v2_rvol150_rsi45",
        "breakdown_short_v1",
        "breakout",
        "SHORT",
        _replace("volume_above_20_average", 1.50),
        _add("rsi_14", "LT", 45.0, "phase24_rsi_below_45"),
    ),
    _variant(
        "pullback_long_v2_rsi55",
        "pullback_long_v1",
        "pullback",
        "LONG",
        _add("rsi_14", "GT", 55.0, "phase24_rsi_above_55"),
    ),
    _variant(
        "pullback_long_v2_macdpos",
        "pullback_long_v1",
        "pullback",
        "LONG",
        _add("macd_hist_12_26_9", "GT", 0.0, "phase24_macd_positive"),
    ),
    _variant(
        "pullback_long_v2_rsi55_macdpos",
        "pullback_long_v1",
        "pullback",
        "LONG",
        _add("rsi_14", "GT", 55.0, "phase24_rsi_above_55"),
        _add("macd_hist_12_26_9", "GT", 0.0, "phase24_macd_positive"),
    ),
    _variant(
        "pullback_short_v2_rsi45",
        "pullback_short_v1",
        "pullback",
        "SHORT",
        _add("rsi_14", "LT", 45.0, "phase24_rsi_below_45"),
    ),
    _variant(
        "pullback_short_v2_macdneg",
        "pullback_short_v1",
        "pullback",
        "SHORT",
        _add("macd_hist_12_26_9", "LT", 0.0, "phase24_macd_negative"),
    ),
    _variant(
        "pullback_short_v2_rsi45_macdneg",
        "pullback_short_v1",
        "pullback",
        "SHORT",
        _add("rsi_14", "LT", 45.0, "phase24_rsi_below_45"),
        _add("macd_hist_12_26_9", "LT", 0.0, "phase24_macd_negative"),
    ),
)


def phase24_gate1_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE24_GATE1_CONTRACT_VERSION,
        "costs_bps": {
            "primary": PHASE24_GATE1_PRIMARY_COST_BPS,
            "stress": PHASE24_GATE1_STRESS_COST_BPS,
        },
        "outcome_horizon_sessions": PHASE24_GATE1_OUTCOME_HORIZON_SESSIONS,
        "development_design": {
            "selection_fraction": PHASE24_GATE1_SELECTION_FRACTION,
            "purge_sessions": PHASE24_GATE1_PURGE_SESSIONS,
            "selection_folds": PHASE24_GATE1_SELECTION_FOLDS,
            "internal_validation_folds": PHASE24_GATE1_INTERNAL_VALIDATION_FOLDS,
            "selection_min_raw_rows": PHASE24_GATE1_SELECTION_MIN_RAW_ROWS,
            "selection_min_signal_sessions": PHASE24_GATE1_SELECTION_MIN_SIGNAL_SESSIONS,
            "internal_min_raw_rows": PHASE24_GATE1_INTERNAL_MIN_RAW_ROWS,
            "internal_min_signal_sessions": PHASE24_GATE1_INTERNAL_MIN_SIGNAL_SESSIONS,
            "selection_min_positive_folds": PHASE24_GATE1_SELECTION_MIN_POSITIVE_FOLDS,
            "internal_min_positive_folds": PHASE24_GATE1_INTERNAL_MIN_POSITIVE_FOLDS,
        },
        "dependence_control": {
            "bootstrap_block_sessions": PHASE24_GATE1_BOOTSTRAP_BLOCK_SESSIONS,
            "bootstrap_replicates": PHASE24_GATE1_BOOTSTRAP_REPLICATES,
            "bootstrap_seed": PHASE24_GATE1_BOOTSTRAP_SEED,
            "selection_confidence": PHASE24_GATE1_SELECTION_CONFIDENCE,
            "internal_validation_confidence": PHASE24_GATE1_INTERNAL_VALIDATION_CONFIDENCE,
            "max_single_session_row_fraction": PHASE24_GATE1_MAX_SINGLE_SESSION_ROW_FRACTION,
        },
        "robustness": {
            "min_positive_year_fraction": PHASE24_GATE1_MIN_POSITIVE_YEAR_FRACTION,
            "min_year_signal_sessions": PHASE24_GATE1_MIN_YEAR_SIGNAL_SESSIONS,
            "min_positive_regime_fraction": PHASE24_GATE1_MIN_POSITIVE_REGIME_FRACTION,
            "min_regime_signal_sessions": PHASE24_GATE1_MIN_REGIME_SIGNAL_SESSIONS,
            "require_primary_median_positive": PHASE24_GATE1_REQUIRE_PRIMARY_MEDIAN_POSITIVE,
            "require_primary_positive_rate_at_least_half": PHASE24_GATE1_REQUIRE_PRIMARY_POSITIVE_RATE_AT_LEAST_HALF,
            "require_stress_mean_positive": PHASE24_GATE1_REQUIRE_STRESS_MEAN_POSITIVE,
            "require_block_bootstrap_lcb_positive": PHASE24_GATE1_REQUIRE_BLOCK_BOOTSTRAP_LCB_POSITIVE,
        },
        "multiple_testing": {
            "method": PHASE24_GATE1_MULTIPLE_TESTING_METHOD,
            "alpha": PHASE24_GATE1_MULTIPLE_TESTING_ALPHA,
            "max_finalists_per_family_direction": PHASE24_GATE1_MAX_FINALISTS_PER_FAMILY_DIRECTION,
        },
        "protected_final_confirmation": {
            "reads_enabled_in_gate1": PHASE24_GATE1_PROTECTED_EVIDENCE_READS,
            "confidence": PHASE24_GATE1_PROTECTED_CONFIDENCE,
            "folds": PHASE24_GATE1_PROTECTED_FOLDS,
            "min_positive_folds": PHASE24_GATE1_PROTECTED_MIN_POSITIVE_FOLDS,
            "min_raw_rows": PHASE24_GATE1_PROTECTED_MIN_RAW_ROWS,
            "min_signal_sessions": PHASE24_GATE1_PROTECTED_MIN_SIGNAL_SESSIONS,
            "require_primary_mean_positive": True,
            "require_primary_median_positive": True,
            "require_stress_mean_positive": PHASE24_GATE1_REQUIRE_STRESS_MEAN_POSITIVE,
            "require_block_bootstrap_lcb_positive": PHASE24_GATE1_REQUIRE_BLOCK_BOOTSTRAP_LCB_POSITIVE,
            "fresh_new_challengers_only": True,
        },
        "selection_exclusions": {
            "gate0_current_evidence_used_for_selection": PHASE24_GATE1_GATE0_CURRENT_EVIDENCE_USED_FOR_SELECTION,
            "incumbent_protected_evidence_is_fresh": PHASE24_GATE1_INCUMBENT_PROTECTED_EVIDENCE_IS_FRESH,
        },
        "authority": {
            "external_provider_reads": PHASE24_GATE1_EXTERNAL_PROVIDER_READS,
            "external_provider_writes": PHASE24_GATE1_EXTERNAL_PROVIDER_WRITES,
            "broker_reads": PHASE24_GATE1_BROKER_READS,
            "broker_writes": PHASE24_GATE1_BROKER_WRITES,
            "order_writes": PHASE24_GATE1_ORDER_WRITES,
            "paper_submits": PHASE24_GATE1_PAPER_SUBMITS,
            "live_writes": PHASE24_GATE1_LIVE_WRITES,
            "production_ml_writes": PHASE24_GATE1_PRODUCTION_ML_WRITES,
            "phase11_support_writes": PHASE24_GATE1_PHASE11_SUPPORT_WRITES,
        },
        "challenger_variants": [asdict(item) for item in PHASE24_GATE1_CHALLENGER_VARIANTS],
    }


def phase24_gate1_policy_fingerprint() -> str:
    raw = json.dumps(
        phase24_gate1_policy_payload(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
