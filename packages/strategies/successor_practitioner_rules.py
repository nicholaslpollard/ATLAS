from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from packages.strategies.successor_practitioner_lab import B35_CHALLENGERS, NEW_FAMILIES


SUCCESSOR_POLICY_IMPLEMENTATION_CONTRACT = (
    "successor-policy-implementation-v1-exact-preoutcome-rules-no-authority"
)


@dataclass(frozen=True, slots=True)
class SuccessorPolicyImplementation:
    policy_id: str
    economic_family_id: str
    native_timeframe: str
    directions: tuple[str, ...]
    evidence_family: str
    minimum_history_sessions: int
    trigger_features: tuple[str, ...]
    parameters: tuple[tuple[str, object], ...]
    exact_rule: str
    information_clock: str
    same_family_for_multiplicity: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


NEW_POLICY_IMPLEMENTATIONS: tuple[SuccessorPolicyImplementation, ...] = (
    SuccessorPolicyImplementation(
        policy_id="pract_bollinger_mean_reversion_v1",
        economic_family_id="bollinger_mean_reversion",
        native_timeframe="1d",
        directions=("LONG", "SHORT"),
        evidence_family="price_structure",
        minimum_history_sessions=21,
        trigger_features=("bollinger_mean_reversion_long", "bollinger_mean_reversion_short"),
        parameters=(("bollinger_period", 20), ("standard_deviations", 2.0), ("long_rsi_max", 45.0), ("short_rsi_min", 55.0)),
        exact_rule=("LONG when prior close was below prior BB20 lower band and current finalized close re-enters at/above the current lower band with RSI14<=45. SHORT is symmetric at the upper band with RSI14>=55. Decision is after the finalized daily close."),
        information_clock="FINALIZED_DAILY_CLOSE_NEXT_REGULAR_OPEN",
    ),
    SuccessorPolicyImplementation(
        policy_id="pract_atr_volatility_expansion_v1",
        economic_family_id="atr_volatility_expansion",
        native_timeframe="1d",
        directions=("LONG", "SHORT"),
        evidence_family="volatility",
        minimum_history_sessions=16,
        trigger_features=("atr_volatility_expansion_long", "atr_volatility_expansion_short"),
        parameters=(("atr_period", 14), ("true_range_multiple_of_prior_atr", 1.5), ("long_close_location_min", 0.75), ("short_close_location_max", 0.25)),
        exact_rule=("Require current true range >=1.5x prior-session ATR14. LONG additionally requires close in the top quartile of the bar and above the prior close; SHORT requires the bottom quartile and below the prior close."),
        information_clock="FINALIZED_DAILY_CLOSE_NEXT_REGULAR_OPEN",
    ),
    SuccessorPolicyImplementation(
        policy_id="pract_vwap_reclaim_reject_v1",
        economic_family_id="vwap_reclaim_reject",
        native_timeframe="1m",
        directions=("LONG", "SHORT"),
        evidence_family="price_structure",
        minimum_history_sessions=1,
        trigger_features=("session_vwap_reclaim_long", "session_vwap_reject_short"),
        parameters=(("session", "XNYS_REGULAR"), ("vwap_price", "HLC3"), ("decision_bar", "LATEST_FULLY_CLOSED_1M"), ("entry_cutoff_et", "15:30:00")),
        exact_rule=("Compute cumulative regular-session VWAP from observed closed one-minute bars using HLC3*volume. LONG when the prior closed bar was at/below its cumulative VWAP and the latest closed bar finishes above current cumulative VWAP; SHORT is symmetric. Zero-volume cumulative state is unavailable rather than fabricated."),
        information_clock="LEFT_EDGE_1M_AVAILABLE_AT_TIMESTAMP_PLUS_1M",
    ),
    SuccessorPolicyImplementation(
        policy_id="pract_pivot_sr_breakout_v1",
        economic_family_id="pivot_sr_breakout",
        native_timeframe="1d",
        directions=("LONG", "SHORT"),
        evidence_family="price_structure",
        minimum_history_sessions=25,
        trigger_features=("pivot_sr_breakout_long", "pivot_sr_breakout_short"),
        parameters=(("pivot_radius_sessions", 2), ("relative_volume_20_min", 1.25)),
        exact_rule=("A swing high/low is strict versus two bars on each side and becomes usable only after both right-side bars close. LONG/SHORT requires a close crossing a previously-known confirmed pivot resistance/support with relative volume20>=1.25."),
        information_clock="CONFIRMED_PIVOT_AVAILABLE_AFTER_SECOND_RIGHT_BAR_CLOSE",
    ),
    SuccessorPolicyImplementation(
        policy_id="pract_head_shoulders_v1",
        economic_family_id="head_shoulders",
        native_timeframe="1d",
        directions=("LONG", "SHORT"),
        evidence_family="chart_pattern",
        minimum_history_sessions=20,
        trigger_features=("inverse_head_shoulders_breakout_long", "head_shoulders_breakdown_short"),
        parameters=(("pivot_radius_sessions", 2), ("shoulder_similarity_fraction", 0.03), ("head_prominence_fraction", 0.03)),
        exact_rule=("Use only previously-confirmed radius-2 pivots. Bearish H&S requires three pivot highs with shoulders within 3% and the middle high >=3% above both shoulders, plus confirmed intervening pivot lows defining a linear neckline; fire only on a finalized close cross below that neckline. Inverse H&S is symmetric."),
        information_clock="PATTERN_GEOMETRY_KNOWN_BEFORE_BREAKOUT_BAR",
    ),
    SuccessorPolicyImplementation(
        policy_id="pract_double_top_bottom_v1",
        economic_family_id="double_top_bottom",
        native_timeframe="1d",
        directions=("LONG", "SHORT"),
        evidence_family="chart_pattern",
        minimum_history_sessions=15,
        trigger_features=("double_bottom_breakout_long", "double_top_breakdown_short"),
        parameters=(("pivot_radius_sessions", 2), ("peak_trough_similarity_fraction", 0.02), ("minimum_pivot_separation_sessions", 5), ("maximum_pivot_separation_sessions", 40)),
        exact_rule=("Use the last two previously-confirmed same-type radius-2 pivots 5..40 sessions apart. They must be within 2%. A double top fires SHORT only when close crosses below the confirmed intervening pivot-low valley; a double bottom fires LONG on the symmetric intervening pivot-high break."),
        information_clock="PATTERN_GEOMETRY_KNOWN_BEFORE_BREAKOUT_BAR",
    ),
    SuccessorPolicyImplementation(
        policy_id="pract_flag_pennant_v1",
        economic_family_id="flag_pennant",
        native_timeframe="1d",
        directions=("LONG", "SHORT"),
        evidence_family="chart_pattern",
        minimum_history_sessions=17,
        trigger_features=("flag_pennant_breakout_long", "flag_pennant_breakout_short"),
        parameters=(("impulse_span_sessions", 10), ("consolidation_sessions", 5), ("minimum_abs_impulse_return", 0.08), ("maximum_consolidation_range_as_impulse_fraction", 0.50), ("maximum_retracement_as_impulse_fraction", 0.50)),
        exact_rule=("Measure a completed 10-session impulse ending six sessions before the signal and the five completed sessions immediately before the signal as consolidation. Require >=8% absolute impulse, consolidation range <=50% of impulse price move, <=50% retracement, then a current finalized close beyond the prior consolidation high/low in impulse direction."),
        information_clock="ALL_IMPULSE_AND_CONSOLIDATION_BARS_PRECEDE_BREAKOUT_BAR",
    ),
    SuccessorPolicyImplementation(
        policy_id="pract_triangle_breakout_v1",
        economic_family_id="triangle_breakout",
        native_timeframe="1d",
        directions=("LONG", "SHORT"),
        evidence_family="chart_pattern",
        minimum_history_sessions=11,
        trigger_features=("triangle_breakout_long", "triangle_breakout_short"),
        parameters=(("formation_sessions", 10), ("minimum_normalized_upper_abs_slope_per_bar", 0.001), ("minimum_normalized_lower_slope_per_bar", 0.001), ("maximum_end_width_as_start_width_fraction", 0.70)),
        exact_rule=("Fit separate least-squares lines to highs and lows of the ten completed sessions before the signal. Require normalized high slope<=-0.001/bar, low slope>=+0.001/bar and fitted end width <=70% of fitted start width. Fire on current close beyond the projected next-session upper/lower boundary."),
        information_clock="FORMATION_EXCLUDES_CURRENT_BREAKOUT_BAR",
    ),
    SuccessorPolicyImplementation(
        policy_id="pract_adx_dmi_continuation_v1",
        economic_family_id="adx_dmi_continuation",
        native_timeframe="1d",
        directions=("LONG", "SHORT"),
        evidence_family="trend",
        minimum_history_sessions=30,
        trigger_features=("adx_dmi_continuation_long", "adx_dmi_continuation_short"),
        parameters=(("adx_period", 14), ("minimum_adx", 25.0), ("trend_average", "EMA20")),
        exact_rule=("Wilder ADX/DMI14. LONG when +DI crosses above -DI while ADX>=25 and close>EMA20; SHORT when -DI crosses above +DI while ADX>=25 and close<EMA20."),
        information_clock="FINALIZED_DAILY_CLOSE_NEXT_REGULAR_OPEN",
    ),
    SuccessorPolicyImplementation(
        policy_id="pract_relative_strength_momentum_v1",
        economic_family_id="relative_strength_momentum",
        native_timeframe="1d",
        directions=("LONG", "SHORT"),
        evidence_family="relative_strength",
        minimum_history_sessions=64,
        trigger_features=("relative_strength_momentum_long", "relative_strength_momentum_short"),
        parameters=(("short_horizon_sessions", 20), ("medium_horizon_sessions", 63), ("benchmark", "SPY"), ("trend_average", "EMA50")),
        exact_rule=("Relative strength is ticker simple return minus same-session SPY simple return. LONG when RS20 crosses from <=0 to >0, RS63>0 and close>EMA50; SHORT is symmetric."),
        information_clock="SAME_SESSION_FINALIZED_TICKER_AND_SPY_CLOSE_NEXT_OPEN",
    ),
    SuccessorPolicyImplementation(
        policy_id="pract_session_failed_break_reclaim_v1",
        economic_family_id="session_failed_break_reclaim",
        native_timeframe="1m",
        directions=("LONG", "SHORT"),
        evidence_family="price_structure",
        minimum_history_sessions=2,
        trigger_features=("session_failed_break_reclaim_long", "session_failed_break_reject_short"),
        parameters=(("support_levels", "PRIOR_REGULAR_LOW|PREMARKET_LOW"), ("resistance_levels", "PRIOR_REGULAR_HIGH|PREMARKET_HIGH"), ("decision_bar", "LATEST_FULLY_CLOSED_1M"), ("entry_cutoff_et", "15:30:00")),
        exact_rule=("LONG when the latest fully closed regular one-minute bar trades below a previously-known support level but closes back above it; SHORT when it trades above a known resistance level but closes back below it. If both directions qualify on one bar, abstain as ambiguous."),
        information_clock="LEVELS_FIXED_BEFORE_OR_AT_0930_AND_SIGNAL_BAR_FULLY_CLOSED",
    ),
)

B35_CHALLENGER_IMPLEMENTATIONS: tuple[SuccessorPolicyImplementation, ...] = (
    SuccessorPolicyImplementation(
        policy_id="gap_quality_condition_long_v2", economic_family_id="gap_continuation", native_timeframe="1m", directions=("LONG",), evidence_family="context_regime", minimum_history_sessions=21, trigger_features=("gap_quality_condition_long",),
        parameters=(("minimum_gap_fraction", 0.02), ("minimum_price", 5.0), ("minimum_prior_median_dollar_volume_20", 20_000_000.0), ("minimum_natr_14", 0.01), ("maximum_natr_14", 0.08), ("minimum_premarket_relvol_20", 1.5)),
        exact_rule="Retain the frozen >=2% long gap definition but admit only price>=5, prior 20-session median dollar volume>=20M, NATR14 in [1%,8%], and premarket relvol20>=1.5. This is a quality gate, not a neighboring gap-threshold search.", information_clock="QUALITY_STATE_KNOWN_BY_FIRST_POST_OPEN_DECISION_0931_ET", same_family_for_multiplicity=True,
    ),
    SuccessorPolicyImplementation(
        policy_id="orb_stocks_in_play_5m_v1", economic_family_id="opening_range", native_timeframe="1m", directions=("LONG", "SHORT"), evidence_family="participation", minimum_history_sessions=21, trigger_features=("orb_stocks_in_play_5m_long", "orb_stocks_in_play_5m_short"),
        parameters=(("opening_range_minutes", 5), ("minimum_observed_range_bars", 5), ("minimum_same_time_opening_relvol", 2.0), ("minimum_prior_median_dollar_volume_20", 20_000_000.0), ("minimum_price", 5.0), ("entry_cutoff_et", "11:30:00")),
        exact_rule="Freeze the 09:30..09:34 observed five-minute opening range and require all five one-minute bars, same-time opening activity relvol>=2, prior median dollar volume>=20M, price>=5, then fire on the first fully closed bar through 11:30 closing outside the range.", information_clock="5M_RANGE_AVAILABLE_0935_ET; BREAKOUT_BAR_FULLY_CLOSED", same_family_for_multiplicity=True,
    ),
    SuccessorPolicyImplementation(
        policy_id="orb_15m_close_retest_v2", economic_family_id="opening_range", native_timeframe="1m", directions=("LONG", "SHORT"), evidence_family="price_structure", minimum_history_sessions=15, trigger_features=("orb_15m_close_retest_long", "orb_15m_close_retest_short"),
        parameters=(("opening_range_minutes", 15), ("minimum_observed_range_bars", 15), ("retest_window_observed_bars", 5), ("retest_distance_atr_fraction", 0.25), ("confirmation_distance_atr_fraction", 0.10), ("breakout_search_cutoff_et", "11:00:00")),
        exact_rule="Require a fully observed 09:30..09:44 range and a later fully closed breakout. Within the next five observed regular bars price must retest within 0.25 ATR of the broken boundary without closing back inside; the next observed bar must confirm at least 0.10 ATR beyond the boundary in breakout direction.", information_clock="EVERY_BREAKOUT_RETEST_CONFIRMATION_BAR_FULLY_CLOSED", same_family_for_multiplicity=True,
    ),
    SuccessorPolicyImplementation(
        policy_id="premarket_relvol_quality_v2", economic_family_id="premarket_relvol_consolidation", native_timeframe="1m", directions=("LONG",), evidence_family="participation", minimum_history_sessions=21, trigger_features=("premarket_relvol_quality_long",),
        parameters=(("minimum_premarket_relvol_20", 2.0), ("consolidation_start_et", "09:00:00"), ("consolidation_end_et", "09:30:00"), ("maximum_consolidation_range_fraction", 0.03), ("minimum_consolidation_bars", 5), ("minimum_prior_median_dollar_volume_20", 20_000_000.0), ("minimum_price", 5.0), ("minimum_premarket_dollar_volume", 2_000_000.0), ("minimum_breakout_same_time_relvol", 1.5), ("entry_cutoff_et", "11:30:00")),
        exact_rule="Keep the frozen relvol>=2 and <=3% 09:00..09:29 consolidation, but require price>=5, prior median dollar volume>=20M, observed premarket dollar volume>=2M and the first closed regular breakout bar to have same-time relvol>=1.5.", information_clock="PREMARKET_FREEZES_0930_ET; BREAKOUT_BAR_FULLY_CLOSED", same_family_for_multiplicity=True,
    ),
)

ALL_SUCCESSOR_POLICY_IMPLEMENTATIONS = NEW_POLICY_IMPLEMENTATIONS + B35_CHALLENGER_IMPLEMENTATIONS


def _validate() -> None:
    new_expected = {item.policy_id for item in NEW_FAMILIES}
    new_actual = {item.policy_id for item in NEW_POLICY_IMPLEMENTATIONS}
    if new_actual != new_expected:
        raise RuntimeError(f"successor new-policy implementation drift: expected={sorted(new_expected)} actual={sorted(new_actual)}")
    challenger_expected = {item.policy_id for item in B35_CHALLENGERS}
    challenger_actual = {item.policy_id for item in B35_CHALLENGER_IMPLEMENTATIONS}
    if challenger_actual != challenger_expected:
        raise RuntimeError("B35 challenger implementation roster drifted")
    if len({item.policy_id for item in ALL_SUCCESSOR_POLICY_IMPLEMENTATIONS}) != len(ALL_SUCCESSOR_POLICY_IMPLEMENTATIONS):
        raise RuntimeError("successor policy implementation ids must be unique")
    for implementation in B35_CHALLENGER_IMPLEMENTATIONS:
        if not implementation.same_family_for_multiplicity:
            raise RuntimeError("B35 challengers must remain same-family for multiplicity")


_validate()


def frozen_successor_implementation_manifest() -> dict[str, object]:
    payload = {
        "contract": SUCCESSOR_POLICY_IMPLEMENTATION_CONTRACT,
        "new_policies": [item.as_dict() for item in NEW_POLICY_IMPLEMENTATIONS],
        "b35_challengers": [item.as_dict() for item in B35_CHALLENGER_IMPLEMENTATIONS],
        "authority": {"strategy_authority": "RESEARCH", "paper_authority": False, "live_authority": False, "promotion_authority": False, "outcome_access_authorized_by_this_manifest": False, "provider_calls": 0, "broker_reads": 0, "broker_writes": 0},
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    payload["fingerprint"] = hashlib.sha256(raw).hexdigest()
    return payload


SUCCESSOR_POLICY_IMPLEMENTATION_FINGERPRINT = frozen_successor_implementation_manifest()["fingerprint"]
