from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, time
from enum import StrEnum
from typing import Final


B35_PREOUTCOME_CONTRACT: Final = (
    "atlas-b35-a36-conditional-evidence-v2-pre-outcome-clock-split-corrected"
)
B35_SUPERSEDED_PREOUTCOME_CONTRACT: Final = (
    "atlas-b35-a36-conditional-evidence-v1-pre-outcome"
)
B35_SUPERSEDED_PREOUTCOME_FINGERPRINT: Final = (
    "7bfd1cfdd65e946d45caa99dd2a35a90d8b424cb82cad5941ad26cac51816c4c"
)
B34_PACK_CONTRACT: Final = "atlas-b34-opening-premarket-pack-v1-pre-outcome"
B34_PACK_FINGERPRINT: Final = (
    "6f7239fcda11ac6c890d2635980d431ec49e346707d9cc549f111bd50daaa4bf"
)
B34_STRATEGY_IDS: Final[tuple[str, ...]] = (
    "b34_gap_continuation_v1",
    "b34_opening_range_breakout_15m_v1",
    "b34_premarket_relvol_consolidation_v1",
    "b34_highest_volume_day_style_v1",
)

DEVELOPMENT_LAST_SCORING_SESSION: Final = date(2026, 4, 30)
CONSUMED_MASTER_START: Final = date(2026, 5, 12)
CONSUMED_MASTER_END: Final = date(2026, 8, 11)
FUTURE_BLIND_START_ON_OR_AFTER: Final = date(2026, 9, 8)
FUTURE_BLIND_MIN_COMPLETE_XNYS_SESSIONS: Final = 63

ROLLING_TRAIN_SESSIONS: Final = 504
WALK_FORWARD_TEST_SESSIONS: Final = 63
WALK_FORWARD_STEP_SESSIONS: Final = 63
WALK_FORWARD_EMBARGO_SESSIONS: Final = 1

ALL_IN_ROUND_TRIP_COST_GRID_BPS: Final[tuple[int, ...]] = (0, 10, 25, 50, 100)
SELECTOR_SCORING_COST_BPS: Final = 50
EXECUTION_STRESS_COST_BPS: Final = 100
TARGET_R_MULTIPLE: Final = 2.0
MAX_ENTRY_DELAY_MINUTES: Final = 5
TIME_EXIT_START_ET: Final = time(15, 55)
TIME_EXIT_END_ET: Final = time(15, 59)

MIN_CELL_OPPORTUNITIES: Final = 60
MIN_CELL_UNIQUE_SESSIONS: Final = 30
MIN_CELL_UNIQUE_INSTRUMENTS: Final = 20
SESSION_CLUSTER_BOOTSTRAP_DRAWS: Final = 1000
SELECTOR_LCB_QUANTILE: Final = 0.05
PRIMARY_FDR_Q: Final = 0.05
PBO_CSCV_PARTITIONS: Final = 16

A34_PORTFOLIO_POLICY_FINGERPRINT: Final = (
    "c6528b5619a0058131347715dae771474a7b37babda282856f5f53a430f792fa"
)


class EvidenceWindow(StrEnum):
    DEVELOPMENT = "DEVELOPMENT"
    CONSUMED_MASTER = "CONSUMED_MASTER"
    NONSCORING_WARMUP = "NONSCORING_WARMUP"
    FUTURE_BLIND = "FUTURE_BLIND"


class RowUse(StrEnum):
    SELECTOR_FIT = "SELECTOR_FIT"
    DEVELOPMENT_OUTCOME = "DEVELOPMENT_OUTCOME"
    FUTURE_SIGNAL_WARMUP = "FUTURE_SIGNAL_WARMUP"
    FUTURE_BLIND_OUTCOME = "FUTURE_BLIND_OUTCOME"


@dataclass(frozen=True, slots=True)
class ConditionDimension:
    condition_id: str
    asof_rule: str
    buckets: tuple[str, ...]
    selector_eligible: bool = True


@dataclass(frozen=True, slots=True)
class ExitPolicy:
    strategy_id: str
    stop_anchor: str
    target_r_multiple: float = TARGET_R_MULTIPLE
    maximum_hold: str = "same_session"
    time_exit_rule: str = (
        "submit fixed time exit at 15:55 ET; use the first observed regular-session "
        "bar stamped 15:55..15:59 and fill at that bar open; otherwise mark unresolved"
    )


CONDITION_DIMENSIONS: Final[tuple[ConditionDimension, ...]] = (
    ConditionDimension(
        "prior_market_regime",
        "exact accepted market-regime value finalized no later than the PRIOR regular-session close; never same-day close",
        ("EXACT_ACCEPTED_LABEL", "UNAVAILABLE"),
    ),
    ConditionDimension(
        "prior_close_price",
        "prior regular-session close",
        ("LT_5", "5_TO_20", "20_TO_100", "GE_100"),
    ),
    ConditionDimension(
        "median_dollar_volume_20",
        "median of the prior 20 eligible regular sessions using only data available by the prior close",
        ("LT_1M", "1M_TO_10M", "10M_TO_50M", "50M_TO_250M", "GE_250M", "UNAVAILABLE"),
    ),
    ConditionDimension(
        "realized_volatility_20",
        "annualized close-to-close realized volatility over the prior 20 eligible sessions, through prior close only; requires 21 completed closes in one split epoch",
        ("LT_25PCT", "25_TO_50PCT", "50_TO_100PCT", "GE_100PCT", "UNAVAILABLE"),
    ),
    ConditionDimension(
        "prior_trend_20_50",
        "prior close versus prior-close SMA20/SMA50; no current-session bars",
        ("UP", "MIXED", "DOWN", "UNAVAILABLE"),
    ),
    ConditionDimension(
        "absolute_gap_pct",
        "current regular open versus prior regular close; unavailable when raw prices cross a split between those sessions",
        ("LT_2PCT", "2_TO_5PCT", "5_TO_10PCT", "GE_10PCT", "UNAVAILABLE"),
    ),
    ConditionDimension(
        "premarket_relvol_20",
        "frozen at 09:30 ET from observed 04:00..09:29 bars and exactly 20 prior eligible premarkets",
        ("LT_2", "2_TO_4", "4_TO_8", "GE_8", "UNAVAILABLE"),
    ),
    ConditionDimension(
        "premarket_dollar_volume",
        "frozen at 09:30 ET from observed premarket bars only",
        ("LT_250K", "250K_TO_1M", "1M_TO_5M", "5M_TO_25M", "GE_25M", "UNAVAILABLE"),
    ),
    ConditionDimension(
        "opening_range_width_pct",
        "available only from 09:45 ET after bars stamped 09:30..09:44 are closed",
        ("LT_1PCT", "1_TO_2PCT", "2_TO_4PCT", "GE_4PCT", "UNAVAILABLE"),
    ),
    ConditionDimension(
        "signal_time_et",
        "information-safe signal decision time, never the underlying bar stamp or future entry/exit time",
        ("0931_TO_0944", "0945_TO_1000", "1001_TO_1030", "1031_TO_1131"),
    ),
    ConditionDimension(
        "hvd_volume_ratio",
        "current observed premarket volume / maximum regular daily volume of exactly 252 prior eligible sessions",
        ("LT_1", "1_TO_1_5", "1_5_TO_2", "GE_2", "UNAVAILABLE"),
    ),
)


EXIT_POLICIES: Final[tuple[ExitPolicy, ...]] = (
    ExitPolicy("b34_gap_continuation_v1", "prior_regular_close"),
    ExitPolicy("b34_opening_range_breakout_15m_v1", "opposite_opening_range_boundary"),
    ExitPolicy("b34_premarket_relvol_consolidation_v1", "premarket_consolidation_low"),
    ExitPolicy("b34_highest_volume_day_style_v1", "premarket_consolidation_low"),
)

SETUP_INTENSITY_BY_STRATEGY: Final[dict[str, str]] = {
    "b34_gap_continuation_v1": "absolute_gap_pct",
    "b34_opening_range_breakout_15m_v1": "opening_range_width_pct",
    "b34_premarket_relvol_consolidation_v1": "premarket_relvol_20",
    "b34_highest_volume_day_style_v1": "hvd_volume_ratio",
}

SELECTOR_FALLBACK_HIERARCHY: Final[tuple[tuple[str, ...], ...]] = (
    ("strategy_id", "prior_market_regime", "realized_volatility_20", "median_dollar_volume_20", "setup_intensity"),
    ("strategy_id", "prior_market_regime", "realized_volatility_20", "setup_intensity"),
    ("strategy_id", "prior_market_regime", "setup_intensity"),
    ("strategy_id", "setup_intensity"),
    ("strategy_id",),
)

PRIMARY_CONDITION_INTERACTIONS: Final[tuple[tuple[str, ...], ...]] = (
    ("prior_market_regime", "realized_volatility_20"),
    ("prior_close_price", "median_dollar_volume_20"),
    ("absolute_gap_pct", "premarket_relvol_20"),
    ("absolute_gap_pct", "opening_range_width_pct"),
)

ROBUSTNESS_PERTURBATIONS: Final[dict[str, tuple[object, ...]]] = {
    "entry_delay_minutes": (0, 1, 2),
    "all_in_round_trip_cost_bps": ALL_IN_ROUND_TRIP_COST_GRID_BPS,
    "gap_threshold_multiplier": (0.9, 1.0, 1.1),
    "opening_range_minutes": (14, 15, 16),
    "premarket_relvol_threshold_multiplier": (0.9, 1.0, 1.1),
    "premarket_consolidation_range_multiplier": (0.9, 1.0, 1.1),
}


def classify_session(session_date: date) -> EvidenceWindow:
    if session_date <= DEVELOPMENT_LAST_SCORING_SESSION:
        return EvidenceWindow.DEVELOPMENT
    if CONSUMED_MASTER_START <= session_date <= CONSUMED_MASTER_END:
        return EvidenceWindow.CONSUMED_MASTER
    if session_date >= FUTURE_BLIND_START_ON_OR_AFTER:
        return EvidenceWindow.FUTURE_BLIND
    return EvidenceWindow.NONSCORING_WARMUP


def validate_row_use(
    session_date: date,
    use: RowUse,
    *,
    blind_signal_session: date | None = None,
) -> None:
    window = classify_session(session_date)
    if use in {RowUse.SELECTOR_FIT, RowUse.DEVELOPMENT_OUTCOME}:
        if window != EvidenceWindow.DEVELOPMENT:
            raise ValueError("development fitting/outcomes are restricted to sessions through 2026-04-30")
        return
    if use == RowUse.FUTURE_BLIND_OUTCOME:
        if window != EvidenceWindow.FUTURE_BLIND:
            raise ValueError("future blind outcomes must start on/after the frozen 2026-09-08 boundary")
        return
    if use == RowUse.FUTURE_SIGNAL_WARMUP:
        if blind_signal_session is None or blind_signal_session < FUTURE_BLIND_START_ON_OR_AFTER:
            raise ValueError("future warm-up requires a future-blind signal session")
        if session_date >= blind_signal_session:
            raise ValueError("future warm-up rows must precede the signal session")
        return
    raise ValueError(f"unsupported row use: {use}")


def future_blind_unblind_permitted(
    *,
    complete_xnys_sessions: int,
    consumption_receipt_absent: bool,
    contract_fingerprint_matches: bool,
    strategy_pack_fingerprint_matches: bool,
) -> bool:
    return (
        complete_xnys_sessions >= FUTURE_BLIND_MIN_COMPLETE_XNYS_SESSIONS
        and consumption_receipt_absent
        and contract_fingerprint_matches
        and strategy_pack_fingerprint_matches
    )


def bucket_prior_close_price(value: float) -> str:
    if value < 5.0:
        return "LT_5"
    if value < 20.0:
        return "5_TO_20"
    if value < 100.0:
        return "20_TO_100"
    return "GE_100"


def bucket_median_dollar_volume_20(value: float | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    if value < 1_000_000:
        return "LT_1M"
    if value < 10_000_000:
        return "1M_TO_10M"
    if value < 50_000_000:
        return "10M_TO_50M"
    if value < 250_000_000:
        return "50M_TO_250M"
    return "GE_250M"


def bucket_realized_volatility_20(value: float | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    if value < 0.25:
        return "LT_25PCT"
    if value < 0.50:
        return "25_TO_50PCT"
    if value < 1.00:
        return "50_TO_100PCT"
    return "GE_100PCT"


def bucket_absolute_gap_pct(value: float | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    value = abs(value)
    if value < 0.02:
        return "LT_2PCT"
    if value < 0.05:
        return "2_TO_5PCT"
    if value < 0.10:
        return "5_TO_10PCT"
    return "GE_10PCT"


def bucket_premarket_relvol_20(value: float | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    if value < 2.0:
        return "LT_2"
    if value < 4.0:
        return "2_TO_4"
    if value < 8.0:
        return "4_TO_8"
    return "GE_8"


def bucket_premarket_dollar_volume(value: float | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    if value < 250_000:
        return "LT_250K"
    if value < 1_000_000:
        return "250K_TO_1M"
    if value < 5_000_000:
        return "1M_TO_5M"
    if value < 25_000_000:
        return "5M_TO_25M"
    return "GE_25M"


def bucket_opening_range_width_pct(value: float | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    if value < 0.01:
        return "LT_1PCT"
    if value < 0.02:
        return "1_TO_2PCT"
    if value < 0.04:
        return "2_TO_4PCT"
    return "GE_4PCT"


def bucket_hvd_volume_ratio(value: float | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    if value < 1.0:
        return "LT_1"
    if value < 1.5:
        return "1_TO_1_5"
    if value < 2.0:
        return "1_5_TO_2"
    return "GE_2"


def bucket_signal_time_et(value: time) -> str:
    if value < time(9, 31) or value > time(11, 31):
        raise ValueError("B35 signal-time bucket is restricted to 09:31..11:31 ET")
    if value <= time(9, 44):
        return "0931_TO_0944"
    if value <= time(10, 0):
        return "0945_TO_1000"
    if value <= time(10, 30):
        return "1001_TO_1030"
    return "1031_TO_1131"


def _payload() -> dict[str, object]:
    return {
        "contract": B35_PREOUTCOME_CONTRACT,
        "supersedes_preoutcome": {
            "contract": B35_SUPERSEDED_PREOUTCOME_CONTRACT,
            "fingerprint": B35_SUPERSEDED_PREOUTCOME_FINGERPRINT,
            "outcomes_opened": False,
            "reason": (
                "pre-outcome correction aligns 11:30 bar stamps with 11:31 information-safe "
                "decisions and marks raw cross-split gap context unavailable without changing B34 signals"
            ),
        },
        "bound_b34_pack": {
            "contract": B34_PACK_CONTRACT,
            "fingerprint": B34_PACK_FINGERPRINT,
            "strategy_ids": B34_STRATEGY_IDS,
        },
        "evidence_windows": {
            "development_last_scoring_session": DEVELOPMENT_LAST_SCORING_SESSION.isoformat(),
            "consumed_master": [CONSUMED_MASTER_START.isoformat(), CONSUMED_MASTER_END.isoformat()],
            "future_blind_start_on_or_after": FUTURE_BLIND_START_ON_OR_AFTER.isoformat(),
            "future_blind_min_complete_xnys_sessions": FUTURE_BLIND_MIN_COMPLETE_XNYS_SESSIONS,
            "policy": (
                "Development fitting and scored outcomes end 2026-04-30. The consumed master interval may "
                "never supply fitting labels or scored outcomes. Rows after development and before the future "
                "blind may be used only as fixed-feature warm-up for a future signal. Such warm-up is counted "
                "separately and cannot fit the selector, change a strategy, or contribute a return label."
            ),
        },
        "walk_forward": {
            "rolling_train_sessions": ROLLING_TRAIN_SESSIONS,
            "test_sessions": WALK_FORWARD_TEST_SESSIONS,
            "step_sessions": WALK_FORWARD_STEP_SESSIONS,
            "embargo_sessions": WALK_FORWARD_EMBARGO_SESSIONS,
            "strategy_parameters_refit": False,
            "condition_selector_fit_training_only": True,
        },
        "entry_exit": {
            "entry": (
                "After the frozen signal decision, submit at the next eligible regular-session minute. Fill at "
                "the first observed bar open within 5 minutes; if none, retain the fired opportunity as a no-entry "
                "liquidity/data outcome. Entry must preserve valid stop/target geometry. Only the first entry "
                "attempt per strategy/instrument/session is eligible."
            ),
            "exit_policies": [asdict(policy) for policy in EXIT_POLICIES],
            "target_r_multiple": TARGET_R_MULTIPLE,
            "same_bar_stop_target_collision": "adverse_stop_first",
            "stop_gap_rule": "if an observed bar opens beyond the stop, exit at that worse open",
            "target_gap_rule": "target fills no better than the target price",
            "unresolved_policy": (
                "never silently drop; preserve attempted-entry evidence, report explicitly, and exclude "
                "from completed-return claims"
            ),
        },
        "costs": {
            "all_in_round_trip_grid_bps": ALL_IN_ROUND_TRIP_COST_GRID_BPS,
            "selector_scoring_cost_bps": SELECTOR_SCORING_COST_BPS,
            "execution_stress_cost_bps": EXECUTION_STRESS_COST_BPS,
            "application": "split equally across entry and exit and applied adversely by direction",
            "interpretation": (
                "bar-only all-in spread/slippage/fee proxy; not a quote-level execution claim. Positive results "
                "must be shown across the full frozen cost grid."
            ),
        },
        "conditions": [asdict(dimension) for dimension in CONDITION_DIMENSIONS],
        "primary_condition_interactions": PRIMARY_CONDITION_INTERACTIONS,
        "selector": {
            "setup_intensity_by_strategy": SETUP_INTENSITY_BY_STRATEGY,
            "fallback_hierarchy": SELECTOR_FALLBACK_HIERARCHY,
            "minimum_cell": {
                "opportunities": MIN_CELL_OPPORTUNITIES,
                "unique_sessions": MIN_CELL_UNIQUE_SESSIONS,
                "unique_instruments": MIN_CELL_UNIQUE_INSTRUMENTS,
            },
            "score": (
                "5th percentile of 1000 deterministic session-cluster bootstrap means of net risk-multiple at "
                "50 bps all-in round trip cost, using training-fold outcomes only"
            ),
            "eligible_score": "strictly greater than zero; otherwise abstain/cash",
            "ranking": "descending score, then stable strategy_id and instrument_id tie-breaks",
            "same_session_outcomes_forbidden": True,
            "learning_may_recommend_never_self_promote": True,
        },
        "portfolio": {
            "bound_a34_policy_fingerprint": A34_PORTFOLIO_POLICY_FINGERPRINT,
            "starting_equity_usd": 100_000,
            "risk_fraction_of_equity_per_position": 0.0025,
            "max_single_position_notional_fraction": 0.10,
            "max_gross_exposure_fraction": 1.0,
            "max_open_positions": 10,
            "max_active_family_positions": 3,
            "one_position_per_instrument": True,
            "short_signal_profiles": "research-only after separate outcome authorization",
            "short_portfolio_admission": False,
            "short_blocker": "borrow/locate/recall economics remain unavailable",
            "event_order": "exits before new admissions at the same timestamp; stable tie-breaks",
        },
        "multiplicity": {
            "session_cluster_bootstrap_draws": SESSION_CLUSTER_BOOTSTRAP_DRAWS,
            "selector_lcb_quantile": SELECTOR_LCB_QUANTILE,
            "benjamini_hochberg_primary_fdr_q": PRIMARY_FDR_Q,
            "pbo_cscv_partitions": PBO_CSCV_PARTITIONS,
            "deflated_sharpe_required_as_diagnostic": True,
            "pbo_required_as_diagnostic_when_evaluable": True,
            "all_primary_trials_ledgered": True,
            "unadjusted_condition_p_values_cannot_promote": True,
        },
        "robustness": {
            "perturbations": ROBUSTNESS_PERTURBATIONS,
            "perturbations_are_diagnostic_only": True,
            "perturbation_cannot_replace_primary_frozen_strategy": True,
            "session_bootstrap_draws_for_tail_and_drawdown": 10_000,
            "report_losing_streak_and_pnl_concentration": True,
        },
        "blind_release": {
            "minimum_complete_xnys_sessions": FUTURE_BLIND_MIN_COMPLETE_XNYS_SESSIONS,
            "one_time_consumption_receipt_required": True,
            "no_selector_refit_on_blind_window": True,
            "no_performance_ui_before_unblind": True,
            "blind_rows_may_not_become_development_after_a_bad_result": True,
        },
        "baselines": (
            "independent_strategy_signal_profiles",
            "a34_stable_nonlearned_long_only_portfolio",
            "cash_abstention",
        ),
        "reporting": (
            "opportunities",
            "unique_sessions",
            "unique_instruments",
            "win_rate",
            "mean_and_median_net_return",
            "mean_and_median_net_r",
            "session_level_sharpe_and_deflated_sharpe",
            "profit_factor",
            "mfe_mae",
            "holding_time",
            "cost_drag",
            "max_drawdown",
            "turnover",
            "gross_exposure",
            "worst_day",
            "loss_streak",
            "pnl_concentration",
            "abstention_rate",
            "unresolved_rate",
            "fold_stability",
        ),
        "authority": {
            "performance_outcomes_opened": False,
            "development_outcome_access_permitted": False,
            "future_blind_outcome_access_permitted": False,
            "minute_replay_read_authority": False,
            "provider_calls": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "paper_authority": False,
            "live_authority": False,
            "broad_minute_materialization_authority": False,
            "promotion_authority": False,
            "next_gate": (
                "exact-head acceptance of this v2 contract and finite replay implementation, followed by a "
                "source-only workstation preflight and a separate hash-bound DEVELOPMENT outcome authorization "
                "that still excludes the consumed master and future blind windows"
            ),
        },
    }


def frozen_contract_manifest() -> dict[str, object]:
    payload = _payload()
    payload["fingerprint"] = B35_PREOUTCOME_FINGERPRINT
    return payload


B35_PREOUTCOME_FINGERPRINT: Final = hashlib.sha256(
    json.dumps(_payload(), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
).hexdigest()
