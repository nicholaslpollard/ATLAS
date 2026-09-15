from __future__ import annotations

from typing import Final

from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.strategies.successor_conditioning_contract import (
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
)
from packages.strategies.successor_optionworthiness_contract import (
    SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
)


SUCCESSOR_PATH_KINETICS_CONTRACT: Final[str] = (
    "atlas-successor-path-kinetics-v1-selected-daily-development-day-resolution"
)
ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT: Final[str] = (
    "6f82ac0e55be43b8cf95fc362c7f292cb592b41c15ff897b24665470e95410f3"
)
ACCEPTED_SELECTED_COMPARABLE_TOTAL: Final[int] = 36_254
ACCEPTED_SELECTED_DAILY_COMPARABLE: Final[int] = 35_995
ACCEPTED_SELECTED_INTRADAY_COMPARABLE: Final[int] = 259
MOVE_THRESHOLDS: Final[tuple[float, ...]] = (0.01, 0.02, 0.03, 0.05)
SESSION_HORIZONS: Final[tuple[int, ...]] = (1, 2, 3, 5, 10, 20)

AUTHORITY: Final[dict[str, object]] = {
    "strategy_authority": "RESEARCH",
    "development_source_reread_permitted": True,
    "development_source_scope": [DEVELOPMENT_START.isoformat(), DEVELOPMENT_END.isoformat()],
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


def successor_path_kinetics_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": SUCCESSOR_PATH_KINETICS_CONTRACT,
        "purpose": (
            "MEASURE_DAY_RESOLUTION_MOVE_TIMING_AND_PATH_KINETICS_FOR_EXACTLY_THE_ALREADY_SELECTED_"
            "COMPARABLE_DAILY_SUCCESSOR_DEVELOPMENT_OPPORTUNITIES"
        ),
        "accepted_inputs": {
            "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
            "optionworthiness_fingerprint": SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
            "optionworthiness_analysis_fingerprint": ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
            "selected_comparable_total": ACCEPTED_SELECTED_COMPARABLE_TOTAL,
            "selected_daily_comparable": ACCEPTED_SELECTED_DAILY_COMPARABLE,
            "selected_intraday_comparable": ACCEPTED_SELECTED_INTRADAY_COMPARABLE,
        },
        "scope": {
            "timeframe": "1d",
            "selection": "WALK_FORWARD_SELECTED_COMPARABLE_ALREADY_FROZEN_BY_CONDITIONING_V1",
            "development_start": DEVELOPMENT_START.isoformat(),
            "development_end": DEVELOPMENT_END.isoformat(),
            "entry": "NEXT_REGULAR_SESSION_OPEN_AFTER_SIGNAL_SESSION",
            "source": "HASH_BOUND_ALPACA_SIP_V2_RESEARCH_DAILY_DEVELOPMENT_VIEW",
            "intraday_selected_opportunities": (
                "RETAINED_BUT_NOT_REOPENED_IN_V1_PATH_KINETICS_BECAUSE_DAILY_SELECTED_EVIDENCE_IS_99PCT_PLUS_"
                "AND_INTRADAY_REQUIRES_SEPARATE_MINUTE_PATH_CONTRACT"
            ),
        },
        "move_thresholds_fraction": list(MOVE_THRESHOLDS),
        "session_horizons": list(SESSION_HORIZONS),
        "frozen_metrics": {
            "directional_close_return_by_horizon": True,
            "directional_mfe_by_horizon": True,
            "directional_mae_by_horizon": True,
            "favorable_threshold_hit_by_horizon": True,
            "adverse_threshold_hit_by_horizon": True,
            "first_favorable_threshold_session_offset": True,
            "first_adverse_threshold_session_offset": True,
            "symmetric_threshold_first_hit_classification": [
                "FAVORABLE_BEFORE_ADVERSE",
                "ADVERSE_BEFORE_FAVORABLE",
                "SAME_SESSION_AMBIGUOUS",
                "FAVORABLE_ONLY",
                "ADVERSE_ONLY",
                "NEITHER",
            ],
            "same_session_intraday_order_inferred": False,
        },
        "interpretation": {
            "descriptive_only": True,
            "post_result_diagnostic": True,
            "may_motivate_bounded_versioned_research": True,
            "may_validate_strategy_or_option_trade": False,
            "no_composite_optionworthiness_score": True,
            "no_post_result_threshold_tuning": True,
            "daily_ohlc_ordering_limit": (
                "IF_FAVORABLE_AND_ADVERSE_THRESHOLDS_FIRST_OCCUR_IN_THE_SAME_DAILY_BAR_THE_SEQUENCE_IS_AMBIGUOUS"
            ),
            "historical_option_pnl_claimed": False,
        },
        "authority": AUTHORITY,
    }
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


SUCCESSOR_PATH_KINETICS_FINGERPRINT: Final[str] = str(
    successor_path_kinetics_manifest()["fingerprint"]
)
