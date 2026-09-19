from __future__ import annotations

from itertools import product
from typing import Final

from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.backtesting.recurrent_successor_outcome_replay_contract import (
    INITIAL_POSITION_FRACTION,
    MAX_OPEN_POSITIONS,
    MAX_POSITIONS_PER_FAMILY,
    ONE_ACTIVE_POSITION_PER_TICKER,
)
from packages.strategies.successor_conditioning_contract import (
    DAILY_PRIMARY_COST_BPS,
    DAILY_PRIMARY_HORIZON_SESSIONS,
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
)
from packages.strategies.successor_selected_daily_path_contract import (
    MOVE_THRESHOLDS,
    SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT,
)


RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT: Final[str] = (
    "atlas-recurrent-successor-daily-exit-policy-sweep-v1"
)

# Frozen accepted daily-path analysis recorded in the Strategy Evidence Register.
ACCEPTED_SELECTED_DAILY_PATH_ANALYSIS_FINGERPRINT: Final[str] = (
    "e89d1d61b7fe6875353816a11727f7ad4a0797917eac0ef4b2d437812a053e20"
)

STOP_TARGET_POLICY_PAIRS: Final[tuple[tuple[float, float], ...]] = tuple(
    (float(stop), float(target))
    for stop, target in product(MOVE_THRESHOLDS, MOVE_THRESHOLDS)
)

MIN_PRIOR_SELECTED_PATH_CASES: Final[int] = 30
SAME_SESSION_COLLISION_POLICY: Final[str] = "STOP_WORST_CASE"
GAP_THROUGH_STOP_POLICY: Final[str] = "SESSION_OPEN_IF_WORSE_THAN_STOP"
GAP_THROUGH_TARGET_POLICY: Final[str] = "TARGET_PRICE_NO_POSITIVE_SLIPPAGE"
TIME_EXIT_POLICY: Final[str] = "FIFTH_ENTRY_SESSION_REGULAR_CLOSE"

AUTHORITY: Final[dict[str, object]] = {
    "development_only": True,
    "post_result_exit_research": True,
    "consumed_master_rows_permitted": 0,
    "future_blind_rows_permitted": 0,
    "provider_calls_permitted": 0,
    "broker_reads_permitted": 0,
    "broker_writes_permitted": 0,
    "order_actions_permitted": 0,
    "paper_authority": False,
    "live_authority": False,
    "strategy_promotion": False,
    "selector_promotion": False,
    "portfolio_policy_promotion": False,
    "confluence_authority": False,
}


def recurrent_successor_daily_exit_sweep_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT,
        "scope": [DEVELOPMENT_START, DEVELOPMENT_END],
        "population": {
            "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
            "research_eligible_required": True,
            "comparable_required": True,
            "native_timeframe": "1d",
            "direction": "LONG",
            "short_disposition": "DEFER_TO_SEPARATE_SHORT_FUNDING_CONTRACT",
        },
        "historical_price_source": {
            "selected_daily_path_fingerprint": SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT,
            "accepted_selected_daily_path_analysis_fingerprint": (
                ACCEPTED_SELECTED_DAILY_PATH_ANALYSIS_FINGERPRINT
            ),
            "execution_bars": "HASH_BOUND_ALPACA_SIP_V2_DAILY_DEVELOPMENT",
            "selected_instrument_projection_only": True,
            "provider_reread": False,
            "protected_master_rows": 0,
        },
        "forecast_threshold_evidence": {
            "source": "STRICTLY_PRIOR_FOLD_SELECTED_DAILY_PATH_RESULTS",
            "minimum_prior_cases": MIN_PRIOR_SELECTED_PATH_CASES,
            "thresholds_fraction": [float(value) for value in MOVE_THRESHOLDS],
            "current_fold_outcome_used": False,
        },
        "portfolio": {
            "position_fraction_of_current_book_equity": INITIAL_POSITION_FRACTION,
            "max_open_positions": MAX_OPEN_POSITIONS,
            "max_positions_per_family": MAX_POSITIONS_PER_FAMILY,
            "one_active_position_per_ticker": ONE_ACTIVE_POSITION_PER_TICKER,
            "reinvestment": "CURRENT_BOOK_EQUITY_COMPOUNDING",
        },
        "exit_policy_grid": {
            "pairs": [
                {"stop_fraction": stop, "target_fraction": target}
                for stop, target in STOP_TARGET_POLICY_PAIRS
            ],
            "horizon_sessions": DAILY_PRIMARY_HORIZON_SESSIONS,
            "round_trip_cost_bps": DAILY_PRIMARY_COST_BPS,
            "same_session_collision": SAME_SESSION_COLLISION_POLICY,
            "gap_through_stop": GAP_THROUGH_STOP_POLICY,
            "gap_through_target": GAP_THROUGH_TARGET_POLICY,
            "time_exit": TIME_EXIT_POLICY,
        },
        "valuation": {
            "daily_close_mark_to_market": True,
            "historical_close_as_zero_spread_replay_mark": True,
            "recurrent_marked_account_is_valuation_truth": True,
        },
        "selection": {
            "automatic_winner_promotion": False,
            "purpose": (
                "DEVELOPMENT_DIAGNOSTIC_COMPARE_BOUNDED_EXIT_POLICIES_FOR_"
                "PORTFOLIO_RETURN_DRAWDOWN_AND_CAPITAL_RECYCLING"
            ),
        },
        "authority": AUTHORITY,
    }
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT: Final[str] = str(
    recurrent_successor_daily_exit_sweep_manifest()["fingerprint"]
)
