from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Final


SUCCESSOR_LAB_CONTRACT: Final[str] = (
    "atlas-successor-practitioner-lab-v1-21-families-pre-outcome-no-promotion"
)
DEVELOPMENT_START: Final[str] = "2016-01-04"
DEVELOPMENT_END: Final[str] = "2026-04-30"
CONSUMED_MASTER_START: Final[str] = "2026-05-12"
CONSUMED_MASTER_END: Final[str] = "2026-08-11"
FUTURE_BLIND_START: Final[str] = "2026-09-08"


@dataclass(frozen=True, slots=True)
class SuccessorFamilySpec:
    family_id: str
    canonical_policy_ids: tuple[str, ...]
    native_timeframes: tuple[str, ...]
    evidence_source: str
    mechanism: str
    role: str
    independent_confluence_family: str
    b35_inspired: bool = False


@dataclass(frozen=True, slots=True)
class SuccessorChallengerSpec:
    policy_id: str
    economic_family_id: str
    evidence_source: str
    mechanism: str
    frozen_research_question: str
    same_family_for_multiplicity: bool = True
    authority: str = "RESEARCH"


RETAINED_FAMILIES: Final[tuple[SuccessorFamilySpec, ...]] = (
    SuccessorFamilySpec(
        "ma_trend_cross_50_200",
        ("ma_trend_cross_50_200_long_v1",),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "slow moving-average trend transition",
        "retained_daily_baseline",
        "trend",
    ),
    SuccessorFamilySpec(
        "ema_pullback_20_50",
        ("ema_pullback_20_50_long_v1",),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "confirmed retracement inside an established trend",
        "retained_daily_baseline",
        "trend",
    ),
    SuccessorFamilySpec(
        "macd_shift_12_26_9",
        ("macd_shift_12_26_9_long_v1", "macd_shift_12_26_9_short_v1"),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "momentum transition around the MACD signal line",
        "retained_daily_baseline",
        "momentum",
    ),
    SuccessorFamilySpec(
        "rsi_recovery_14_trend",
        ("rsi_recovery_14_trend_long_v1",),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "short-horizon reversal after downside momentum inside a long trend",
        "retained_daily_baseline",
        "momentum",
    ),
    SuccessorFamilySpec(
        "donchian_breakout_20_volume",
        ("donchian_breakout_20_volume_long_v1", "donchian_breakout_20_volume_short_v1"),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "range escape confirmed by participation and trend",
        "retained_daily_baseline",
        "price_structure",
    ),
    SuccessorFamilySpec(
        "bollinger_squeeze_breakout_20",
        ("bollinger_squeeze_breakout_20_long_v1", "bollinger_squeeze_breakout_20_short_v1"),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "directional escape from volatility compression",
        "retained_daily_baseline",
        "volatility",
    ),
    SuccessorFamilySpec(
        "gap_continuation",
        ("b34_gap_continuation_v1",),
        ("1m",),
        "PRACTITIONER_BASELINE",
        "opening discontinuity followed by directional continuation",
        "retained_intraday_negative_baseline",
        "price_structure",
        True,
    ),
    SuccessorFamilySpec(
        "opening_range",
        ("b34_opening_range_breakout_15m_v1",),
        ("1m",),
        "PRACTITIONER_BASELINE",
        "regular-session price-discovery range breakout",
        "retained_intraday_negative_baseline",
        "price_structure",
        True,
    ),
    SuccessorFamilySpec(
        "premarket_relvol_consolidation",
        ("b34_premarket_relvol_consolidation_v1",),
        ("1m",),
        "PRACTITIONER_BASELINE",
        "premarket participation plus consolidation breakout",
        "retained_intraday_cost_sensitive_baseline",
        "participation",
        True,
    ),
    SuccessorFamilySpec(
        "highest_volume_day_style",
        ("b34_highest_volume_day_style_v1",),
        ("1m",),
        "PRACTITIONER_BASELINE",
        "abnormal premarket participation relative to prior daily volume",
        "retained_sparse_reference_only",
        "participation",
        True,
    ),
)


NEW_FAMILIES: Final[tuple[SuccessorFamilySpec, ...]] = (
    SuccessorFamilySpec(
        "bollinger_mean_reversion",
        ("pract_bollinger_mean_reversion_v1",),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "re-entry toward the distribution center after an outer-band stretch",
        "new_family",
        "momentum",
    ),
    SuccessorFamilySpec(
        "atr_volatility_expansion",
        ("pract_atr_volatility_expansion_v1",),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "directional range escape as realized range expands from compression",
        "new_family",
        "volatility",
    ),
    SuccessorFamilySpec(
        "vwap_reclaim_reject",
        ("pract_vwap_reclaim_reject_v1",),
        ("1m",),
        "PRACTITIONER_BASELINE",
        "objective session-VWAP reclaim or rejection with closed-bar confirmation",
        "new_family",
        "price_structure",
    ),
    SuccessorFamilySpec(
        "pivot_sr_breakout",
        ("pract_pivot_sr_breakout_v1",),
        ("1d", "1m"),
        "PRACTITIONER_BASELINE",
        "continuation through universally observable prior-session structural levels",
        "new_family",
        "price_structure",
    ),
    SuccessorFamilySpec(
        "head_shoulders",
        ("pract_head_shoulders_v1",),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "algorithmic three-pivot reversal with objective neckline break",
        "new_family",
        "chart_pattern",
    ),
    SuccessorFamilySpec(
        "double_top_bottom",
        ("pract_double_top_bottom_v1",),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "two comparable swing extremes separated by a material retracement and neckline break",
        "new_family",
        "chart_pattern",
    ),
    SuccessorFamilySpec(
        "flag_pennant",
        ("pract_flag_pennant_v1",),
        ("1d", "1m"),
        "PRACTITIONER_BASELINE",
        "impulse followed by bounded contraction and continuation breakout",
        "new_family",
        "chart_pattern",
    ),
    SuccessorFamilySpec(
        "triangle_breakout",
        ("pract_triangle_breakout_v1",),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "converging objective swing boundaries followed by directional breakout",
        "new_family",
        "chart_pattern",
    ),
    SuccessorFamilySpec(
        "adx_dmi_continuation",
        ("pract_adx_dmi_continuation_v1",),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "directional continuation when DMI agrees and ADX confirms trend strength",
        "new_family",
        "trend",
    ),
    SuccessorFamilySpec(
        "relative_strength_momentum",
        ("pract_relative_strength_momentum_v1",),
        ("1d",),
        "PRACTITIONER_BASELINE",
        "persistent focal-stock outperformance or underperformance versus SPY",
        "new_family",
        "relative_strength",
    ),
    SuccessorFamilySpec(
        "session_failed_break_reclaim",
        ("pract_session_failed_break_reclaim_v1",),
        ("1m",),
        "PRACTITIONER_BASELINE",
        "objective breach and reclaim of prior-day or premarket structural levels",
        "new_family",
        "price_structure",
    ),
)


B35_CHALLENGERS: Final[tuple[SuccessorChallengerSpec, ...]] = (
    SuccessorChallengerSpec(
        "gap_quality_condition_long_v2",
        "gap_continuation",
        "INTERNAL_CHALLENGER",
        "long-side gap continuation conditioned on preregistered liquidity, volatility, price, and premarket-participation quality",
        "Can a mechanism-level quality/condition gate produce stable after-cost continuation without relying on the failed 1.8/2.0/2.2 percent threshold tuning?",
    ),
    SuccessorChallengerSpec(
        "orb_stocks_in_play_5m_v1",
        "opening_range",
        "LITERATURE_ANCHORED",
        "five-minute opening-range breakout only after abnormal same-time opening participation and executable liquidity qualify the stock as in play",
        "Does activity selection transform broad negative ORB into a viable opening-momentum specialist after realistic costs?",
    ),
    SuccessorChallengerSpec(
        "orb_15m_close_retest_v2",
        "opening_range",
        "INTERNAL_CHALLENGER",
        "closed 15-minute range breakout followed by an objective bounded retest/hold confirmation before entry",
        "Does false-break rejection improve expectancy enough to offset later entry and lost MFE?",
    ),
    SuccessorChallengerSpec(
        "premarket_relvol_quality_v2",
        "premarket_relvol_consolidation",
        "INTERNAL_CHALLENGER",
        "premarket participation breakout restricted by preregistered liquidity, participation quality, and execution quality while retaining immediate information-safe entry",
        "Can quality selection increase the thin gross signal enough to survive binding transaction costs?",
    ),
)


SHARED_PIT_CONTEXT: Final[tuple[str, ...]] = (
    "market_direction_alignment",
    "market_volatility_state",
    "ticker_relative_strength_vs_spy_short_horizon",
    "ticker_relative_strength_vs_spy_medium_horizon",
    "higher_timeframe_ticker_trend",
    "atr_normalized_trend_maturity_extension",
    "opening_same_time_volume_participation",
    "premarket_volume_participation",
    "prior_dollar_volume_liquidity",
    "overnight_gap",
    "price_band",
    "signal_time",
    "realized_volatility",
    "execution_liquidity_quality",
)


EVALUATION_CONTRACT: Final[dict[str, object]] = {
    "development_scope": [DEVELOPMENT_START, DEVELOPMENT_END],
    "master_protected_scope": [CONSUMED_MASTER_START, CONSUMED_MASTER_END],
    "master_reuse_permitted": False,
    "future_blind_start": FUTURE_BLIND_START,
    "future_blind_read_permitted": False,
    "walk_forward": {
        "training_sessions": 504,
        "test_sessions": 63,
        "step_sessions": 63,
        "embargo_sessions": 1,
    },
    "minimum_condition_support": {
        "opportunities": 60,
        "sessions": 30,
        "instruments": 20,
    },
    "reporting_cost_grid_bps": [0, 10, 25, 50, 100],
    "daily_decision_costs_bps": {"primary": 10, "stress": 25},
    "intraday_decision_costs_bps": {"primary": 50, "stress": 100},
    "standalone_before_conditioning": True,
    "standalone_before_confluence": True,
    "cash_abstention_valid": True,
    "post_result_slice_self_validates": False,
    "challenger_inspired_by_development_can_validate_on_same_development": False,
    "promotion_from_this_contract": False,
}


CONFLUENCE_CONTRACT: Final[dict[str, object]] = {
    "separate_from_strategy_firing": True,
    "preserve_primary_strategy_and_direction": True,
    "preserve_exact_contributors": True,
    "preserve_opposing_evidence": True,
    "count_distinct_evidence_families": True,
    "correlated_indicator_votes_are_independent": False,
    "evidence_families": [
        "trend",
        "momentum",
        "participation",
        "price_structure",
        "volatility",
        "chart_pattern",
        "relative_strength",
        "context_regime",
    ],
    "declared_comparisons": [
        "standalone",
        "hard_confirmation",
        "confluence_ranking",
    ],
    "arbitrary_subjective_point_score_permitted": False,
}


RUNTIME_CONTRACT: Final[dict[str, object]] = {
    "parallel_by_default": True,
    "process_isolation_for_independent_groups": True,
    "duckdb_thread_budget_per_worker": True,
    "restart_safe_group_receipts": True,
    "atomic_output_publication": True,
    "validated_completed_group_reuse": True,
    "scientific_identity_excludes_execution_profile": True,
    "heartbeat_seconds_max": 60,
    "machine_readable_progress": True,
    "pid_scope_profile_console_banner": True,
    "benchmark_before_long_run": True,
    "golden_output_equivalence_required_for_execution_tuning": True,
    "operator_and_thermal_headroom_required": True,
    "observed_i7_8700k_24gib_targeted_replay_reference": {
        "sustained_choice": "8_workers_x_1_duckdb_thread",
        "approx_units_per_hour": 1702,
        "ten_by_one_rejected_for_sustained_use": "thermal_throttling_observed",
        "not_a_global_hardcoded_default": True,
    },
}


SUCCESSOR_FAMILIES: Final[tuple[SuccessorFamilySpec, ...]] = RETAINED_FAMILIES + NEW_FAMILIES


def _validate() -> None:
    if len(RETAINED_FAMILIES) != 10:
        raise RuntimeError("successor lab must retain exactly 10 economic families")
    if len(NEW_FAMILIES) != 11:
        raise RuntimeError("successor lab must add exactly 11 economic families")
    if len(SUCCESSOR_FAMILIES) != 21:
        raise RuntimeError("successor lab must contain exactly 21 economic families")
    family_ids = [item.family_id for item in SUCCESSOR_FAMILIES]
    if len(family_ids) != len(set(family_ids)):
        raise RuntimeError("successor economic family ids must be unique")
    policy_ids = [policy for family in SUCCESSOR_FAMILIES for policy in family.canonical_policy_ids]
    policy_ids.extend(item.policy_id for item in B35_CHALLENGERS)
    if len(policy_ids) != len(set(policy_ids)):
        raise RuntimeError("successor policy ids must be unique")
    economic_ids = set(family_ids)
    for challenger in B35_CHALLENGERS:
        if challenger.economic_family_id not in economic_ids:
            raise RuntimeError("challenger must belong to a declared economic family")
        if not challenger.same_family_for_multiplicity:
            raise RuntimeError("nearby challenger cannot masquerade as an independent family")
    if EVALUATION_CONTRACT["master_reuse_permitted"] is not False:
        raise RuntimeError("consumed master may never be reused")
    if EVALUATION_CONTRACT["future_blind_read_permitted"] is not False:
        raise RuntimeError("future blind must remain untouched")


_validate()


def frozen_successor_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": SUCCESSOR_LAB_CONTRACT,
        "families": [asdict(item) for item in SUCCESSOR_FAMILIES],
        "b35_challengers": [asdict(item) for item in B35_CHALLENGERS],
        "shared_pit_context": list(SHARED_PIT_CONTEXT),
        "evaluation": EVALUATION_CONTRACT,
        "confluence": CONFLUENCE_CONTRACT,
        "runtime": RUNTIME_CONTRACT,
        "authority": {
            "strategy_authority": "RESEARCH",
            "paper_authority": False,
            "live_authority": False,
            "promotion_authority": False,
            "provider_calls": 0,
            "broker_reads": 0,
            "broker_writes": 0,
        },
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["fingerprint"] = hashlib.sha256(raw).hexdigest()
    return payload


SUCCESSOR_LAB_FINGERPRINT: Final[str] = str(frozen_successor_manifest()["fingerprint"])
