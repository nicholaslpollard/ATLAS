from __future__ import annotations

from typing import Final

from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.strategies.successor_conditioning_contract import (
    ACCEPTED_GROUP_COUNT,
    ACCEPTED_RUN_CONTRACT_FINGERPRINT,
    ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT,
    ACCEPTED_STANDALONE_RECORD_COUNT,
    ACCEPTED_STANDALONE_RUN_FINGERPRINT,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
)


SUCCESSOR_OPTIONWORTHINESS_CONTRACT: Final[str] = (
    "atlas-successor-optionworthiness-v1-retained-conditioning-artifacts-descriptive-no-option-pnl"
)
MOVE_THRESHOLDS: Final[tuple[float, ...]] = (0.01, 0.02, 0.03, 0.05)
ANALYSIS_SUBSETS: Final[tuple[str, ...]] = (
    "DEVELOPMENT_ALL_COMPARABLE",
    "WALK_FORWARD_TEST_COMPARABLE",
    "WALK_FORWARD_SELECTED_COMPARABLE",
)

AUTHORITY: Final[dict[str, object]] = {
    "strategy_authority": "RESEARCH",
    "consumed_master_rows_permitted": 0,
    "future_blind_rows_permitted": 0,
    "provider_calls_permitted": 0,
    "broker_reads_permitted": 0,
    "broker_writes_permitted": 0,
    "paper_authority": False,
    "live_authority": False,
    "strategy_promotion": False,
    "selector_promotion": False,
    "option_trading_authority": False,
    "confluence_opened": False,
}


def successor_optionworthiness_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": SUCCESSOR_OPTIONWORTHINESS_CONTRACT,
        "purpose": (
            "DESCRIBE_UNDERLYING_MOVE_MAGNITUDE_EXCURSION_AND_AVAILABLE_TIME_CHARACTERISTICS_"
            "FROM_ALREADY_ACCEPTED_SUCCESSOR_DEVELOPMENT_AND_CONDITIONING_ARTIFACTS"
        ),
        "accepted_inputs": {
            "successor_run_contract_fingerprint": ACCEPTED_RUN_CONTRACT_FINGERPRINT,
            "standalone_run_fingerprint": ACCEPTED_STANDALONE_RUN_FINGERPRINT,
            "standalone_artifact_set_fingerprint": ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT,
            "standalone_group_count": ACCEPTED_GROUP_COUNT,
            "standalone_record_count": ACCEPTED_STANDALONE_RECORD_COUNT,
            "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
        },
        "subsets": list(ANALYSIS_SUBSETS),
        "move_thresholds_fraction": list(MOVE_THRESHOLDS),
        "supported_metrics": {
            "directional_mfe_percent_threshold_frequency": True,
            "directional_mae_percent_threshold_frequency": True,
            "excursion_window_semantics": {
                "daily": "THROUGH_20_SESSIONS",
                "intraday": "ENTRY_TO_ACTUAL_EXIT",
            },
            "mfe_mae_distribution_quantiles": True,
            "daily_5_session_gross_directional_return": True,
            "daily_1_and_20_session_primary_net_return": True,
            "intraday_gross_and_primary_stress_return": True,
            "intraday_holding_minutes": True,
            "walk_forward_selected_vs_test_vs_all_comparison": True,
            "route_direction_fold_selected_stability": True,
        },
        "explicitly_unavailable_from_retained_artifacts": {
            "exact_time_to_1_2_3_5_percent_favorable_move": (
                "MFE_PERSISTS_MAGNITUDE_BUT_NOT_TIMESTAMP_OF_THRESHOLD_CROSSING"
            ),
            "daily_5_session_mfe_mae_threshold_frequency": (
                "DAILY_RETAINED_MFE_MAE_COVERS_THE_20_SESSION_WINDOW_NOT_THE_PRIMARY_5_SESSION_WINDOW"
            ),
            "exact_mfe_before_mae_path_sequence": (
                "EXTREMA_ARE_PERSISTED_WITHOUT_COMPLETE_PATH_ORDER"
            ),
            "atr_normalized_1atr_2atr_favorable_move_frequency": (
                "ENTRY_ATR_MAGNITUDE_IS_NOT_PERSISTED_IN_CONDITIONING_NORMALIZED_ARTIFACTS"
            ),
            "realized_volatility_during_hold": (
                "CONTEXT_HAS_PRE_SIGNAL_OR_SIGNAL_STATE_NOT_A_COMPLETE_HOLD_PERIOD_VOLATILITY_PATH"
            ),
            "historical_option_pnl": (
                "NO_ACCEPTED_PIT_HISTORICAL_OPTION_CHAIN_QUOTE_IV_REPLAY_SOURCE"
            ),
            "contract_level_greeks_iv_skew_term_structure": (
                "REQUIRES_SEPARATE_OPTION_SOURCE_AND_CONSTRUCTION_PACKAGE"
            ),
        },
        "interpretation": {
            "descriptive_only": True,
            "post_result_diagnostic": True,
            "may_motivate_bounded_versioned_research": True,
            "may_validate_strategy_or_option_trade": False,
            "no_composite_optionworthiness_score": True,
            "reason": (
                "WEIGHTS_OR_THRESHOLDS_FOR_A_COMPOSITE_SCORE_HAVE_NOT_BEEN_PROSPECTIVELY_FROZEN_OR_VALIDATED"
            ),
        },
        "authority": AUTHORITY,
    }
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT: Final[str] = str(
    successor_optionworthiness_manifest()["fingerprint"]
)
