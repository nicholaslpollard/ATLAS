from __future__ import annotations

from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.strategies.successor_conditioning_contract import SUCCESSOR_CONDITIONING_FINGERPRINT
from packages.strategies.successor_optionworthiness_contract import SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT


SUCCESSOR_SELECTED_DAILY_PATH_CONTRACT = (
    "atlas-successor-selected-daily-path-v1-five-session-first-touch-descriptive"
)
ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT = (
    "6f82ac0e55be43b8cf95fc362c7f292cb592b41c15ff897b24665470e95410f3"
)
MOVE_THRESHOLDS = (0.01, 0.02, 0.03, 0.05)
PATH_HORIZON_SESSIONS = 5
AUTHORITY = {
    "strategy_authority": "RESEARCH_DIAGNOSTIC_ONLY",
    "development_only": True,
    "post_result_diagnostic": True,
    "consumed_master_rows_permitted": 0,
    "future_blind_rows_permitted": 0,
    "provider_calls_permitted": 0,
    "broker_reads_permitted": 0,
    "broker_writes_permitted": 0,
    "paper_authority": False,
    "live_authority": False,
    "strategy_promotion_authority": False,
    "selector_promotion_authority": False,
    "confluence_authority": False,
    "option_trading_authority": False,
}


def successor_selected_daily_path_manifest() -> dict[str, object]:
    return {
        "contract": SUCCESSOR_SELECTED_DAILY_PATH_CONTRACT,
        "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
        "optionworthiness_fingerprint": SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
        "accepted_optionworthiness_analysis_fingerprint": ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
        "population": "WALK_FORWARD_SELECTED_COMPARABLE_DAILY_ONLY",
        "entry": "NEXT_REGULAR_SESSION_OPEN",
        "path_horizon_sessions": PATH_HORIZON_SESSIONS,
        "move_thresholds_fraction": list(MOVE_THRESHOLDS),
        "daily_bar_first_touch_semantics": {
            "favorable_touch": "LONG_HIGH_OR_SHORT_LOW_REACHES_THRESHOLD_FROM_ENTRY",
            "adverse_touch": "LONG_LOW_OR_SHORT_HIGH_REACHES_THRESHOLD_FROM_ENTRY",
            "first_touch_resolution": "SESSION_INDEX_ONLY",
            "same_session_both_sides": "SAME_SESSION_COLLISION_UNORDERED",
            "intraday_order_inference_permitted": False,
        },
        "metrics": [
            "five_session_directional_close_return",
            "five_session_mfe",
            "five_session_adverse_excursion_magnitude",
            "first_favorable_touch_session_1_2_3_5pct",
            "first_adverse_touch_session_1_2_3_5pct",
            "favorable_vs_adverse_first_touch_classification",
            "five_session_exit_capture_ratio_vs_mfe",
            "five_session_peak_giveback",
            "route_direction_fold_stability_context",
        ],
        "explicitly_not_claimed": [
            "intraday_order_within_a_daily_bar",
            "minute_level_time_to_threshold",
            "historical_option_contract_pnl",
            "greeks_or_iv_path",
            "atr_normalized_threshold_frequency",
            "strategy_validation_or_promotion",
            "composite_optionworthiness_score",
        ],
        "intraday_routes": "DEFERRED_TO_SEPARATE_MINUTE_PATH_DIAGNOSTIC",
        "authority": AUTHORITY,
    }


SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT = canonical_sha256(
    successor_selected_daily_path_manifest()
)
