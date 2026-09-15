from __future__ import annotations

from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.strategies.successor_conditioning_contract import (
    ACCEPTED_INPUT_MANIFEST_FINGERPRINT,
    ACCEPTED_RUN_CONTRACT_FINGERPRINT,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
)
from packages.strategies.successor_optionworthiness_contract import SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT
from packages.strategies.successor_selected_daily_path_contract import (
    ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
    MOVE_THRESHOLDS,
)


SUCCESSOR_SELECTED_MINUTE_PATH_CONTRACT = (
    "atlas-successor-selected-minute-path-v1-entry-to-actual-exit-first-touch-descriptive"
)
EXPECTED_SELECTED_MINUTE_COMPARABLE = 259
EXPECTED_POLICY_ID = "orb_15m_close_retest_v2"
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


def successor_selected_minute_path_manifest() -> dict[str, object]:
    return {
        "contract": SUCCESSOR_SELECTED_MINUTE_PATH_CONTRACT,
        "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
        "optionworthiness_fingerprint": SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
        "accepted_optionworthiness_analysis_fingerprint": ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
        "accepted_successor_run_contract_fingerprint": ACCEPTED_RUN_CONTRACT_FINGERPRINT,
        "accepted_successor_input_manifest_fingerprint": ACCEPTED_INPUT_MANIFEST_FINGERPRINT,
        "population": "WALK_FORWARD_SELECTED_COMPARABLE_MINUTE_ONLY",
        "expected_population": EXPECTED_SELECTED_MINUTE_COMPARABLE,
        "expected_policy_id": EXPECTED_POLICY_ID,
        "entry": "RETAINED_ACTUAL_NEXT_OBSERVED_REGULAR_MINUTE_ENTRY",
        "exit": "RETAINED_ACTUAL_FROZEN_SUCCESSOR_EXIT_TIMESTAMP",
        "move_thresholds_fraction": list(MOVE_THRESHOLDS),
        "minute_first_touch_semantics": {
            "favorable_touch": "LONG_HIGH_OR_SHORT_LOW_REACHES_THRESHOLD_FROM_ENTRY",
            "adverse_touch": "LONG_LOW_OR_SHORT_HIGH_REACHES_THRESHOLD_FROM_ENTRY",
            "resolution": "MINUTE_BAR_TIMESTAMP",
            "same_minute_both_sides": "SAME_MINUTE_COLLISION_UNORDERED",
            "exit_bar": "DO_NOT_USE_EXIT_BAR_HIGH_LOW; APPLY_RETAINED_REALIZED_GROSS_RETURN_ONLY",
            "reason": "AVOID_POST_EXIT_EXTREME_LEAKAGE_AND_DO_NOT_INFER_INTRAMINUTE_ORDER",
            "tick_order_inference_permitted": False,
        },
        "source_policy": {
            "source": "ACCEPTED_SUCCESSOR_SERIALIZED_MINUTE_UNIT_BINDINGS",
            "only_selected_symbol_session_units": True,
            "canonical_unit_sha256_reverification_required": True,
            "provider_reread": False,
            "broad_minute_materialization": False,
        },
        "metrics": [
            "actual_holding_minutes",
            "retained_gross_directional_return",
            "pre_exit_plus_terminal_mfe",
            "pre_exit_plus_terminal_adverse_excursion_magnitude",
            "first_favorable_touch_minutes_1_2_3_5pct",
            "first_adverse_touch_minutes_1_2_3_5pct",
            "favorable_vs_adverse_first_touch_classification",
            "same_minute_collision_rate",
            "retained_primary_and_stress_net_return_context",
        ],
        "explicitly_not_claimed": [
            "tick_order_within_a_minute_bar",
            "historical_option_contract_pnl",
            "greeks_or_iv_path",
            "strategy_validation_or_promotion",
            "composite_optionworthiness_score",
            "intraday_confluence",
        ],
        "authority": AUTHORITY,
    }


SUCCESSOR_SELECTED_MINUTE_PATH_FINGERPRINT = canonical_sha256(
    successor_selected_minute_path_manifest()
)
