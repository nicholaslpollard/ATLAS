from __future__ import annotations

"""One options-native research specification; no execution or outcome authority."""

from copy import deepcopy
from datetime import datetime
from typing import Any

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.schemas.strategy_lab import (
    StrategyTrialDisposition, StrategyTrialDraft, StrategyTrialStage,
)

PILOT_ID = "options-native-spy-long-straddle-v1"
CONTRACT = "atlas-options-native-volatility-pilot-specification-v1"
DATA_CONTRACT = "atlas-options-native-pilot-inputs-v1"
START_DATE = "2018-01-01"
END_DATE = "2025-12-31"
LOOKBACK_RETURNS = 20
MIN_DTE = 30
MAX_DTE = 45
MAX_HOLD_SESSIONS = 5

AUTHORITY = {
    "provider_requests": 0, "broker_requests": 0, "raw_source_scans": 0,
    "option_outcomes_read": 0, "protected_outcomes_read": 0,
    "source_acceptance": False, "historical_replay_authority": False,
    "historical_fill_authority": False, "strategy_promotion": False,
    "paper": False, "live": False,
}

_IMPLIED_INPUT = {
    "model": "LEISEN_REIMER_AMERICAN_BINOMIAL",
    "steps": 101, "version": "1",
    "price_input": "CONTEMPORANEOUS_QUOTE_MID_ANALYTICAL_ONLY",
    "rate": "PIT_SOFR", "dividend": "PIT_REQUIRED_NO_ZERO_DEFAULT",
    "iv_unit": "ANNUAL_DECIMAL_VOLATILITY_365_DAY_YEAR",
    "maturity": "SAME_EXPLICIT_MODEL_MATURITY_FOR_BOTH_LEGS_AND_FORECAST",
    "maturity_is_trading_or_exercise_deadline": False,
    "pair_variance": "(call_iv**2+put_iv**2)/2",
    "model_price_can_replace_quote": False,
}
IMPLIED_INPUT_FINGERPRINT = _fingerprint(_IMPLIED_INPUT)

_DATA = {
    "contract": DATA_CONTRACT,
    "roles": {
        "DECISION_INPUT": "observed by 10:00 ET and available by 10:01 ET decision readiness; independent of outcomes",
        "EXECUTION_EVENT": "reached after order eligibility; never an entry filter in hindsight",
        "OUTCOME": "research labels and performance; never predictor inputs",
    },
    "required_provenance": [
        "raw_body_sha256", "request_and_receipt_fingerprints", "exact_contract_identity",
        "observed_at_utc", "source_available_at_utc_or_explicit_unknown",
        "input_as_of_utc", "offline_computed_at_utc", "source_qualification_fingerprint",
        "availability_model_fingerprint_and_latency_assumptions_if_modeled",
    ],
    "underlying_inputs": {
        "symbol": "SPY", "spot": "last qualified observation by cutoff, available by readiness; age <=60s at cutoff",
        "return_history": "20 contiguous completed close-to-close economic log returns",
        "return_adjustments": "PIT split/dividend treatment and identity lineage required",
        "latest_return": "previous completed XNYS session; no current-day finalized close",
        "warmup": "21 completed closes before the first eligible decision; inputs only",
    },
    "option_pair_inputs": {
        "required": [
            "call_and_put_exact_symbols", "same_underlying_expiration_strike_model_maturity",
            "bid", "ask", "bid_size", "ask_size", "quote_observed_and_available_clocks",
            "multiplier", "deliverable_and_adjustment_proof", "prior_state_open_interest",
            "open_interest_state_and_publication_clocks", "american_model_iv_and_greeks",
            "PIT_rate_and_dividend_inputs", "qualified_option_session_hours",
        ],
        "maximum_quote_age_seconds": 30,
        "maximum_pair_observation_skew_seconds": 1,
        "positive_uncrossed_two_sided_quotes": True,
        "minimum_open_interest_each_leg": 100,
        "maximum_spread_to_mid_each_leg": "0.15",
        "size": "positive bid size and ask size covering one contract each",
        "volume": "retain as context; zero reported volume alone is not a quote rejection",
        "open_interest": "prior-session state with availability by readiness; never midnight by date",
        "implied_input_contract": _IMPLIED_INPUT,
    },
    "failure_semantics": {
        "missing_or_unqualified_decision_input": "ABSTAIN_WITH_REASON_RETAIN_ORIGINAL_CLOCK",
        "unknown_publication_clock": "BLOCK_UNLESS_SEPARATELY_QUALIFIED_BOUNDED_CLOCK_LATENCY_MODEL; retain assumption label",
        "missing_future_fill_or_mark": "UNRESOLVED_ACCOUNT_NOT_RETROACTIVE_ENTRY_REMOVAL",
        "offline_computation_time": "does not establish historical source availability",
        "source_validation_after_collection": "cannot retroactively improve decision eligibility",
    },
    "downstream_outputs": {
        "screen": "dimensionless variance comparison; not a dollar-profit forecast",
        "exact_replay": "actual qualified quotes/events; independent fees and lifecycle",
        "forecast_calibration": "future realized variance is an outcome, never an input",
    },
}
DATA_FINGERPRINT = _fingerprint(_DATA)

_SPEC = {
    "contract": CONTRACT, "pilot_id": PILOT_ID,
    "status": "SPECIFIED_NOT_PERFORMANCE_TESTED",
    "hypothesis": (
        "A fixed prior-only volatility estimate greater than same-maturity ATM implied "
        "variance identifies long-straddle entries with useful net economics. "
        "This is an unproven predictor hypothesis, not a variance-arbitrage claim."
    ),
    "universe": {
        "symbols": ["SPY"], "entry_clock_et": "10:00:00.000",
        "entry_cadence": "FIRST_XNYS_SESSION_OF_ISO_WEEK",
        "calendar_is_option_hours_authority": False,
        "stock_signal_required": False,
        "development_start": START_DATE, "development_end": END_DATE,
        "end_buffer_calendar_days": MAX_DTE,
        "buffer_reason": "all potential maturities/outcomes stay before 2026",
        "protected_2026_outcomes_permitted": 0,
        "qualification": "NEW_PROSPECTIVE_INTERVAL_REQUIRES_SEPARATE_REGISTRATION_AND_AUTHORITY",
        "earlier_years_not_new_independent_holdout": True,
    },
    "forecast": {
        "id": "trailing-20-economic-log-return-calendar-variance-rate-v1",
        "lookback_returns": LOOKBACK_RETURNS,
        "formula": "sum(log_return_i**2)/sum(interval_calendar_seconds_i)",
        "projection": "variance_rate * seconds(decision_readiness, explicit_model_maturity)",
        "assumptions": "constant calendar-time variance rate; no weekend/intraday seasonality model",
        "fit_or_parameter_search": False,
        "future_realized_volatility_role": "OUTCOME_ONLY",
    },
    "construction": {
        "structure": "LONG_ATM_STRADDLE", "legs": ["BUY_ONE_CALL", "BUY_ONE_PUT"],
        "same_strike_expiration_underlying": True, "multiplier": 100,
        "deliverable": "independently verified standard contract; adjusted contracts abstain",
        "dte_calendar_days": [MIN_DTE, MAX_DTE],
        "selection_order": ["earliest expiration in DTE band", "common strike closest to causal spot",
                            "lower strike breaks equal-distance tie"],
        "selection_before_liquidity_filter": True,
        "failed_selected_pair": "ABSTAIN_NO_NEXT_STRIKE_OR_EXPIRATION_FALLBACK",
        "entry_signal": "forecast_total_variance > pair_implied_total_variance",
        "equal_variance_action": "ABSTAIN",
        "implied_input_fingerprint": IMPLIED_INPUT_FINGERPRINT,
        "hedging": "NONE; changing delta exposure and IV repricing remain economic risks",
        "premium_spread_theta_and_vega_are_in_net_outcome": True,
    },
    "management": {
        "evaluation_clock_et": "10:00:00.000", "first_check": "NEXT_XNYS_SESSION_AFTER_ENTRY",
        "dynamic_exit": "forecast_total_variance <= current_original_pair_implied_total_variance",
        "maximum_holding_sessions": MAX_HOLD_SESSIONS,
        "dte_guard": "request close if calendar DTE <=14",
        "missing_feature": "cannot establish thesis exit; clock/dte guards still request close",
        "exit_quote_missing": "keep original contracts/reserves/slot; unresolved equity",
        "stock_percent_stop_or_target": None,
        "tick_or_intraminute_stop_protection_claimed": False,
        "contract_roll_or_replacement": False,
    },
    "execution_and_account": {
        "initial_research_cash": "100000.00", "maximum_open_pairs": 1,
        "pairs_per_entry": 1, "maximum_total_debit_and_reserved_fees_fraction": "0.05",
        "cash_interest_baseline": "0.00; explicit accounting assumption, benchmark separately",
        "order_eligible_clock_et": "10:01:00.000",
        "decision_readiness": "one minute after observation cutoff; source/model/compute latency must qualify",
        "entry_observed_price_reference": "ASK_EACH_LEG", "exit_observed_price_reference": "BID_EACH_LEG",
        "quotes_are_fills": False, "midpoint_is_execution": False,
        "multi_leg_requirement": "qualified paired-order model or explicit legging timeline/exposure",
        "atomic_fill_from_two_snapshots_permitted": False,
        "fees": "qualified broker/account/date/channel profile required; zero commission != zero all-in cost",
        "stress": "one extra contemporary full spread per leg per side and 60s extra execution latency; no executable price means no fill",
        "entry_failure": "NO_FILL_OR_PARTIAL_LEG_EXPOSURE_RETAINED; never silently complete a pair",
        "exercise_expiry_settlement": "explicit effective-date evidence; no automatic intrinsic settlement",
        "integration_status": "SINGLE_LEG_ENGINES_NOT_YET_QUALIFIED_FOR_THIS_PAIR",
    },
    "research_protocol": {
        "maximum_strategy_variants": 1, "cost_scenarios": ["QUALIFIED_PRIMARY", "FROZEN_SPREAD_STRESS"],
        "controls": ["NO_TRADE_CASH", "SAME_WINDOW_SPY_TOTAL_RETURN_CONTEXT_NOT_RISK_MATCHED"],
        "revision_requires_new_trial": ["universe", "clock", "forecast", "DTE", "strike_rule",
                                        "entry_threshold", "exit_rule", "sizing"],
        "trial_ledger_required_before_any_historical_outcome_read": True,
        "development": "chronological replay; all specified versions/failures retained",
        "rolling_account_windows_sessions": [5, 21, 252],
        "calendar_windows": ["ISO_WEEK", "CALENDAR_MONTH", "CALENDAR_YEAR"],
        "rolling_anchors": "every eligible session; report counts and unresolved coverage",
        "metrics": ["net equity", "realized/unrealized P&L", "drawdown", "tail loss",
                    "cost sensitivity", "capital usage", "coverage", "concentration"],
        "greeks_attribution": "model-based approximation separate from observed net economics",
        "positive_every_window_required": False,
        "post_result_regime_pruning": False,
        "fast_screen_authority": "fixture mechanics only until historical source/adapter acceptance",
        "promotion": "independent prospective evidence, cost/capacity/risk and PAPER execution acceptance",
    },
    "data_contract_fingerprint": DATA_FINGERPRINT,
    "authority": AUTHORITY,
    "references": [
        "https://www.optionseducation.org/strategies/all-strategies/long-straddle",
        "https://doi.org/10.1093/rfs/hhag061",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts",
        "https://docs.thetadata.us/operations/option_at_time_quote.html",
    ],
}


def pilot_manifest() -> dict[str, Any]:
    body = deepcopy(_SPEC)
    body["specification_fingerprint"] = _fingerprint(body)
    return body


def pilot_data_contract() -> dict[str, Any]:
    body = deepcopy(_DATA)
    body["data_contract_fingerprint"] = DATA_FINGERPRINT
    return body


SPECIFICATION_FINGERPRINT = str(pilot_manifest()["specification_fingerprint"])


def specification_trial_draft(registered_at_utc: datetime) -> StrategyTrialDraft:
    """Use the existing append-only ledger before an eventual authorized replay.

    Returning a draft does not append a workstation ledger or grant a read gate.
    """
    return StrategyTrialDraft(
        trial_id="options-native.spy-long-straddle.v1.specification",
        registered_at_utc=registered_at_utc, stage=StrategyTrialStage.SPECIFICATION,
        disposition=StrategyTrialDisposition.REGISTERED,
        family_ids=("options_native_underpriced_movement",), strategy_ids=(PILOT_ID,),
        strategy_policy_fingerprint=SPECIFICATION_FINGERPRINT,
        feature_fingerprint=DATA_FINGERPRINT,
        hypotheses=(_SPEC["hypothesis"],),
        notes=("One frozen strategy variant; no outcomes opened.",
               "Prior negative experiments and consumed holdout remain unchanged.",
               "Historical execution and source integration remain unqualified."),
    )
