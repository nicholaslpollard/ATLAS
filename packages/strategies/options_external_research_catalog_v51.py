from __future__ import annotations

"""V51 externally researched options candidates, NO validated performance.

Immutable IDs separate published rules, independently reproduced backtests,
source claims, and proposed ATLAS adaptations. Source-backed figures are never
used as simulated returns, paper/live authority, or a parameter sweep result.
"""

from copy import deepcopy
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-options-external-research-strategy-candidates-v51"
EVIDENCE_STATUS = "EXTERNAL_REPORTED_OR_REPRODUCED_NOT_ATLAS_VALIDATED"
SOURCE_O = "https://options.cafe/blog/0dte-opening-range-breakout-strategy-spy-backtested-results/"
SOURCE_W = "https://github.com/Javier-Garzo/ern-wo-options-backtester"
SOURCE_W2 = "https://github.com/Javier-Garzo/ern-wo-options-backtester/blob/main/docs/research/strategies-postmortem/wealthy-option.md"
SOURCE_S = "https://www.thetaprofits.com/my-most-profitable-options-trading-strategy-0dte-breakeven-iron-condor/"
SOURCE_M = "https://www.thetaprofits.com/tammy-chambless-explains-her-meic-strategy-for-trading-0dte-options/"
SOURCE_R = "https://www.thetaprofits.com/two-0dte-strategies-for-spx-one-buys-premium-the-other-sells/"
SOURCE_D = "https://www.sandvand.net/2022/11/26/the-results-of-100-trades-with-the-1dte-high-delta-iron-condor-options-strategy/"
CANDIDATES = (
    {
        "id": "external-spy-0dte-opening-range-breakout-published-v1",
        "rank": 1, "priority": "HIGH", "underlying": "SPY", "product": "ETF_OPTION",
        "direction": "LONG_SINGLE_CALL_OR_PUT", "entry_window_et": "AFTER_09:35_FIRST_BREAKOUT",
        "required_observations": ("SPY_09:30_TO_09:35_1MIN_OR_FINER",
          "SPY_TICK_TIME_FOR_FIRST_BREAKOUT", "SPY_ATM_0DTE_OPTION_CHAIN_AT_BREAKOUT",
          "SAME_CONTRACT_INTRADAY_QUOTES_TO_15:30"),
        "published_parameters": {
            "range_minutes": 5, "breakout_buffer_usd": "0.00",
            "weekdays": ("MON","WED","FRI"), "max_daily_entries": 1,
            "premium_allocation_usd": "500", "profit_target_pct": "100",
            "stop_loss_pct": "-50", "time_exit_et": "15:30", "expiration_dte": 0,
        },
        "evidence_type": "ORIGINAL_DEVELOPER_BACKTEST_OPTIMIZED_IN_SAMPLE",
        "claims": {"trades":303,"period":"2024-02..2026-03","total_return_pct":"59.4",
                   "max_drawdown_pct":"7.6","account_start_usd":"25000"},
        "critical_gaps": ("ONE_MINUTE_BARS_CANNOT_PROVE_INTRABAR_FIRST_BREAKOUT_OR_FILL",
           "MWF_AND_FIVE_MINUTE_RANGE_SELECTED_AFTER_TESTING",
           "SOURCE_NOT_NET_OF_FULL_SPREAD_FEES_AND_SLIPPAGE",
           "SOURCE_PROVIDER_1MIN_OPTION_BARS_NOT_RETAINED_IN_ATLAS"),
        "sources": (SOURCE_O,),
    },
    {
        "id": "external-wealthyoption-spxw-six-short-sleeves-published-v1",
        "rank": 2, "priority": "HIGH", "underlying": "SPXW", "product": "INDEX_OPTION",
        "direction": "SIX_INDEPENDENT_SHORT_OPTION_SLEEVES",
        "entry_window_et": "PUT_AFTER_09:34_CALL_BEFORE_15:00",
        "required_observations": ("SPXW_1_TO_4DTE_CHAIN_GREEKS", "SHORT_SIDE_BID_ASK",
          "5MIN_OR_BETTER_GTC_EXIT_QUOTE", "EXPIRATION_SETTLEMENT",
          "REALISTIC_PORTFOLIO_MARGIN_AND_TAIL_RISK"),
        "published_parameters": {
            "put_sleeves": (("0.055","74","25"),("0.065","72","30"),("0.075","69","25")),
            "call_sleeves": (("0.020","78","25"),("0.025","80","30"),("0.030","83","25")),
            "new_0dte_entries": False, "held_to_expiry_if_target_missed": True,
        },
        "evidence_type": "INDEPENDENT_OPEN_SOURCE_RULE_LEVEL_BACKTEST",
        "claims": {"third_party_combined_spxw_cagr_pct":"17.58",
                  "third_party_combined_spxw_drawdown_pct":"21.43",
                  "third_party_combined_spxw_trades":14438,
                  "independent_spy_adaptation_combined_cagr_pct":"14.91",
                  "independent_spy_adaptation_drawdown_pct":"23.64"},
        "critical_gaps": ("GROSS_MODELED_SLEEVE_ALLOCATION_160_PERCENT",
          "REAL_BROKER_MARGIN_NOT_REPLICATED",
          "SPY_AMERICAN_EARLY_ASSIGNMENT_NOT_MODELED_IN_REFERENCE",
          "5MIN_OBSERVATIONS_CANNOT_CERTIFY_GTC_INTRABAR_FILLS",
          "SPY_VARIANT_MUST_BE_SEPARATE_FROM_ORIGINAL_SPXW"),
        "sources": ("https://wealthyoption.com/",SOURCE_W,SOURCE_W2),
    },
    {
        "id": "external-sandvand-spx-0dte-breakeven-condor-reported-v1",
        "rank": 3, "priority": "HIGH", "underlying": "SPXW", "product": "INDEX_OPTION",
        "direction": "SHORT_IRON_CONDOR_SEPARATE_SIDE_STOPS",
        "entry_window_et": "MULTIPLE_INTRADAY_ENTRIES_30MIN_OR_MORE_APART",
        "required_observations": ("SPXW_INTRADAY_GREEKS", "FOUR_LEG_REAL_QUOTES",
          "INDEPENDENT_SHORT_STOP_EVENTS", "WING_CLOSE_OR_REUSE",
          "OCO_STOP_LIMIT_AND_STOP_MARKET_BEHAVIOR","LIVE_BP_AND_RISK_LIMITS"),
        "published_parameters": {"short_delta_band":("0.10","0.15"),
          "put_and_call_side_credits_approximately_equal":True,
          "stop_per_side_based_on_total_condor_credit":True,
          "usual_wing_width_spx_points":"30"},
        "evidence_type": "TRADER_REPORTED_LIVE_RESULTS_UNAUDITED",
        "claims":{"self_reported_trades":9100,"profitable_months":49,"months":57,
                  "winning_trade_pct":"40"},
        "critical_gaps": ("DISCRETIONARY_STOP_TIGHTENING_NOT_FULLY_DETERMINISTIC",
          "SHORT_ONLY_STOP_VS_FULL_SPREAD_EXIT_NEED_SEPARATE_VERSIONS",
          "NO_INDEPENDENT_BROKER_CONFIRMATION_OF_9100_TRADES"),
        "sources":(SOURCE_S,),
    },
    {
        "id":"external-chambless-spx-0dte-meic-reported-v1",
        "rank":4,"priority":"HIGH","underlying":"SPXW","product":"INDEX_OPTION",
        "direction":"SIX_CONCURRENT_SHORT_IRON_CONDORS_SEPARATE_SIDE_STOPS",
        "entry_window_et":"SIX_SCHEDULED_INTRADAY_TIMES_30_TO_60MIN_APART",
        "required_observations":("FOUR_LEG_QUOTES_PER_ENTRY","CONCURRENT_BP",
          "INDIVIDUAL_SPREAD_STOP_QUOTES","EXPIRATION_SETTLEMENT"),
        "published_parameters":{"usual_entries_per_day":6,"credit_each_side_usd":("1.00","1.75"),
          "usual_wing_width_spx_points":("50","60"),
          "wing_width_max_spx_points":100,
          "per_side_stop":"TOTAL_CREDIT_ORIGINAL_CONDOR"},
        "evidence_type":"TRADER_REPORTED_ACCOUNT_RETURNS_UNAUDITED",
        "claims":{"reported_cagr_pct":"20.7","reported_max_drawdown_pct":"4.31",
                   "since":"2023-01"},
        "critical_gaps":("EXACT_SIX_ENTRY_CLOCKS_NOT_CONFIRMED",
          "ORIGINAL_VS_MEIC_PLUS_STOP_OFFSET_MUST_BE_SEPARATE",
          "NO_BROKER_AUDITED_HISTORY"),
        "sources":(SOURCE_M,),
    },
    {
        "id":"external-ruchel-spx-0dte-reverse-iron-condor-backtest-v1",
        "rank":5,"priority":"HIGH","underlying":"SPXW","product":"INDEX_OPTION",
        "direction":"FOUR_LEG_LONG_REVERSE_IRON_CONDOR",
        "entry_window_et":"BEFORE_11:00_ON_QUALIFIED_FALLING_VIX",
        "required_observations":("HISTORICAL_VIX_YESTERDAY_OPEN_CURRENT_ASOF",
          "FOUR_LEG_SPXW_0DTE_QUOTES","EXPIRATION_SETTLEMENT"),
        "published_parameters":{"wing_width_spx_points":30,
          "vix_falling_from_prior_close":True,"vix_falling_from_today_open":True,
          "early_profit_target_optional_pct":"100"},
        "evidence_type":"TRADER_DEVELOPER_PLATFORM_BACKTEST",
        "claims":{"reported_cagr_pct":"36.7","approximate_trades":338,
                  "years_more_than":4},
        "critical_gaps":("ENTRY_SPREAD_STRIKE_AND_VIX_CUTOFF_INCOMPLETE",
          "EXACT_OPTION_OMEGA_RESULTS_NOT_DOWNLOADED_AND_VERIFIED",
          "NO_FILL_RECEIPTS"),
        "sources":(SOURCE_R,),
    },
    {
        "id":"external-ruchel-spx-0dte-late-short-iron-fly-backtest-v1",
        "rank":6,"priority":"MEDIUM_HIGH","underlying":"SPXW","product":"INDEX_OPTION",
        "direction":"FOUR_LEG_SHORT_IRON_FLY_OR_ASYMMETRIC_CONDOR",
        "entry_window_et":"13:45",
        "required_observations":("ASOF_VIX_13:45","FOUR_LEG_0DTE_QUOTES",
          "EXPIRATION_SETTLEMENT_AND_PIN_RISK"),
        "published_parameters":{"short_put_delta":"0.50","short_call_delta":"0.40",
          "protective_wing_points":15,"vix_max":"20","expiry_or_early_profit_variant":True},
        "evidence_type":"TRADER_DEVELOPER_PLATFORM_BACKTEST",
        "claims":{"reported_cagr_pct":"44","approximate_trades":300,
                  "approximate_years":2},
        "critical_gaps":("NOT_A_SYMMETRIC_CLASSIC_IRON_FLY_AT_UNEQUAL_SHORT_DELTAS",
          "EXACT_SETTLEMENT_AND_OPTION_OMEGA_RULES_NOT_IN_SOURCE",
          "PUBLISHED_FAVORABLE_WEEKDAY_SLICE_POSTTEST"),
        "sources":(SOURCE_R,),
    },
    {
        "id":"external-sandvand-spx-1dte-high-delta-condor-100-live-v1",
        "rank":7,"priority":"MEDIUM","underlying":"SPXW","product":"INDEX_OPTION",
        "direction":"FOUR_LEG_SHORT_IRON_CONDOR_WIDE_WINGS",
        "entry_window_et":"09:35_TO_09:40",
        "required_observations":("1DTE_SPXW_22_TO_25_DELTA_QUOTES",
          "FOUR_LEG_INTRADAY_CLOSE_QUOTES","SHORT_ONLY_OCO_STOPS",
          "LIVE_BP_AND_END_OF_DAY_FLATTENING"),
        "published_parameters":{"short_delta":("0.22","0.25"),
          "wing_width_spx_points":100,"profit_capture_pct":("5","7"),
          "max_entries_per_day":1,"exit_before_session_close":True,
          "stop":"SHORT_ONLY_OCO_LIMIT_MARKET_THEN_SEPARATE_LONGS"},
        "evidence_type":"TRADER_REPORTED_100_LIVE_TRADES",
        "claims":{"trades":100,"net_usd":"2577","wins_pct":"78",
                  "average_holding_minutes":22},
        "critical_gaps":("DISCRETIONARY_FINAL_LONG_WING_MANAGEMENT",
          "STOP_PATH_AND_STOP_FILL_NOT_FROZEN_FOR_ALL_100",
          "WIDE_SPREADS_REQUIRE_VALID_BP_AND_MARGIN"),
        "sources":(SOURCE_D,),
    },
    {
        "id":"research-adaptive-spx-0dte-butterfly-lead-v1",
        "rank":8,"priority":"WATCH","underlying":"SPXW","product":"INDEX_OPTION",
        "direction":"ADAPTIVE_MULTI_LEG_DIRECTIONAL_SPREADS",
        "entry_window_et":"RULES_NOT_DETERMINISTIC",
        "required_observations":("INTRADAY_GEX","HISTORICAL_DECISION_PATH"),
        "published_parameters":{},"evidence_type":"SHORT_TRADER_REPORTED_LIVE_EXPERIMENT",
        "claims":{"reported_monthly_pct":"10","months":3},
        "critical_gaps":("DISCRETIONARY_ADAPTATION_PREVENTS_FROZEN_REPRODUCTION",),
        "sources":("https://www.thetaprofits.com/the-0dte-adaptive-butterfly-strategy-how-a-doctor-makes-10-a-month-trading-spx/",),
    },
    {
        "id":"research-reddit-spy-0dte-short-iron-fly-lead-v1",
        "rank":9,"priority":"WATCH","underlying":"SPY","product":"ETF_OPTION",
        "direction":"FOUR_LEG_SHORT_IRON_FLY",
        "entry_window_et":"APPROX_TWO_AND_HALF_HOURS_BEFORE_CLOSE",
        "required_observations":("FOUR_LEG_INTRADAY_QUOTES","CRASH_TAIL_RISK"),
        "published_parameters":{},"evidence_type":"SHORT_REDDIT_ANECDOTE",
        "claims":{"reported_account_growth_pct":"75","approximate_weeks":5},
        "critical_gaps":("EXTREMELY_SHORT_EXPERIMENT","FULL_RULES_UNVERIFIED"),
        "sources":("https://www.reddit.com/r/options/comments/1o9vgbb/spy_0dte_strategy_with_almost_75_return_over_15/",),
    },
    {
        "id":"research-earnings-options-prepost-straddle-lead-v1",
        "rank":10,"priority":"WATCH","underlying":"MULTI_STOCK","product":"EQUITY_OPTION",
        "direction":"LONG_STRADDLE_ACROSS_EARNINGS",
        "entry_window_et":"PRE_EARNINGS_TIME_DEPENDENT",
        "required_observations":("EARNINGS_AS_PUBLISHED_CLOCK",
          "ASOF_VOL_IV_AND_GREEKS","BID_ASK_PRE_AND_POST_EVENT"),
        "published_parameters":{},"evidence_type":"ACADEMIC_HISTORICAL_STUDY",
        "claims":{"reported_portfolio_return_pct":"9.4","annualized":False},
        "critical_gaps":("FULL_PAPER_NOT_YET_REPRODUCED",
          "CORPORATE_ACTION_AND_ANNOUNCEMENT_TIMESTAMPS_REQUIRED"),
        "sources":("https://www.sciencedirect.com/science/article/pii/S0927539816300743",),
    },
)


def registry() -> dict:
    entries=deepcopy(CANDIDATES)
    if (len(entries)!=10 or {x["rank"] for x in entries}!=set(range(1,11))
            or len({x["id"] for x in entries})!=10):
        raise ValueError("V51_RESEARCH_CATALOG_SCOPE_DRIFT")
    for item in entries:
        if (not item["id"] or not item["sources"] or not item["critical_gaps"]
                or "claim_of_validated_atlas_pnl" in item):
            raise ValueError("V51_EVIDENCE_ITEM_INVALID")
        item["atlas_historical_net_pnl"]=None
        item["source_publication_proof_complete"]=False
        item["atlas_historical_execution_verified"]=False
        item["atlas_strategy_promotion_authorized"]=False
    result={
        "contract":CONTRACT,
        "status":EVIDENCE_STATUS,
        "primary_candidate_count":7,
        "watch_candidate_count":3,
        "entries":entries,
        "atlas_live_order_authority":False,
        "candidates_tested_on_workstation":0,
        "prior_2018_2025_spy_and_2026_holdout_are_development_only":True,
    }
    result["fingerprint"]=_fingerprint(result)
    return result
