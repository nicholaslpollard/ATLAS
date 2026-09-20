from __future__ import annotations

from datetime import date
from typing import Final

from packages.backtesting.successor_runner_contract import canonical_sha256


RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT: Final[str] = (
    "atlas-recurrent-successor-dynamic-exit-selector-v1"
)

SOURCE_STATIC_REGIME_RUN_FINGERPRINT: Final[str] = (
    "60989a10985973bff48d3d2a82a633282b62e664f22f5c3fac4c35bfee380ede"
)

DEVELOPMENT_SCOPE: Final[tuple[date, date]] = (
    date(2018, 1, 1),
    date(2026, 4, 30),
)

# Frozen after the static-exit regime map and before Dynamic Exit V1 results.
# Every action has target >= 1.5x stop. The five-session horizon remains fixed
# so V1 isolates dynamic stop/target selection.
DYNAMIC_EXIT_ACTIONS: Final[tuple[tuple[float, float], ...]] = (
    (0.01, 0.02),
    (0.01, 0.03),
    (0.01, 0.05),
    (0.02, 0.03),
    (0.02, 0.05),
    (0.03, 0.05),
)

ABSTAIN_ACTION_ID: Final[str] = "ABSTAIN"
LOOKBACK_COMPLETED_FOLDS: Final[int] = 8
MIN_TRAINING_CASES: Final[int] = 60
MIN_TRAINING_SESSIONS: Final[int] = 30
MIN_TRAINING_INSTRUMENTS: Final[int] = 20
ONE_SIDED_LCB_Z: Final[float] = 1.645
MIN_ACCEPTABLE_LCB: Final[float] = 0.0

# Context is intentionally interpretable and point-in-time. More-specific cells
# own the decision when supported; fallback occurs only for insufficient support.
CONTEXT_FALLBACK_HIERARCHY: Final[tuple[tuple[str, ...], ...]] = (
    (
        "policy_id",
        "market_volatility_state",
        "higher_timeframe_ticker_trend",
        "realized_volatility_bucket",
        "market_direction_alignment",
    ),
    (
        "policy_id",
        "market_volatility_state",
        "higher_timeframe_ticker_trend",
        "realized_volatility_bucket",
    ),
    (
        "policy_id",
        "market_volatility_state",
        "higher_timeframe_ticker_trend",
    ),
    (
        "policy_id",
        "market_volatility_state",
    ),
    ("policy_id",),
)

AUTHORITY: Final[dict[str, object]] = {
    "development_only": True,
    "dynamic_exit_research_only": True,
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
    "exit_policy_promotion": False,
    "portfolio_policy_promotion": False,
}


def dynamic_exit_action_id(stop_fraction: float, target_fraction: float) -> str:
    return (
        f"STOP_{int(round(stop_fraction * 100)):02d}_"
        f"TARGET_{int(round(target_fraction * 100)):02d}"
    )


def recurrent_successor_dynamic_exit_v1_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT,
        "source_static_regime_run_fingerprint": SOURCE_STATIC_REGIME_RUN_FINGERPRINT,
        "development_scope": [
            DEVELOPMENT_SCOPE[0].isoformat(),
            DEVELOPMENT_SCOPE[1].isoformat(),
        ],
        "actions": [
            {
                "action_id": dynamic_exit_action_id(stop, target),
                "stop_fraction": stop,
                "target_fraction": target,
                "time_exit_sessions": 5,
            }
            for stop, target in DYNAMIC_EXIT_ACTIONS
        ],
        "abstain_action_id": ABSTAIN_ACTION_ID,
        "lookback_completed_folds": LOOKBACK_COMPLETED_FOLDS,
        "support": {
            "min_training_cases": MIN_TRAINING_CASES,
            "min_training_sessions": MIN_TRAINING_SESSIONS,
            "min_training_instruments": MIN_TRAINING_INSTRUMENTS,
        },
        "scoring": {
            "unit": "NET_RETURN_AFTER_10BPS_SPLIT_ENTRY_EXIT_COST",
            "session_weighting": "EQUAL_WEIGHT_SESSION_MEANS",
            "one_sided_lcb_z": ONE_SIDED_LCB_Z,
            "minimum_acceptable_lcb": MIN_ACCEPTABLE_LCB,
            "selection": (
                "HIGHEST_POSITIVE_SESSION_MEAN_LCB_THEN_MEAN_NET_"
                "THEN_PROBABILITY_POSITIVE_THEN_ACTION_ID"
            ),
            "no_positive_supported_action": ABSTAIN_ACTION_ID,
        },
        "context_fallback_hierarchy": [list(level) for level in CONTEXT_FALLBACK_HIERARCHY],
        "time_exit_policy": "FIXED_FIVE_ENTRY_SESSIONS_V1",
        "same_session_collision_policy": "STOP_WORST_CASE",
        "gap_stop_policy": "FILL_AT_WORSE_OPEN",
        "gap_target_policy": "FILL_AT_TARGET_NO_POSITIVE_SLIPPAGE",
        "anti_lookahead": {
            "current_case_future_path_may_influence_selection": False,
            "current_fold_outcomes_may_train_current_fold": False,
            "training_folds": (
                "ONLY_COMPLETED_PRIOR_FOLDS_WITHIN_LAST_8_FOLDS"
            ),
            "current_context": "POINT_IN_TIME_NORMALIZED_CONTEXT_ONLY",
        },
        "next_gate": (
            "IF_SELECTOR_DIAGNOSTIC_IS_COHERENT_BUILD_RECURRENT_ACCOUNT_REPLAY_"
            "WITH_DECISION_BOUND_DYNAMIC_EXIT_ACTIONS"
        ),
        "authority": AUTHORITY,
    }
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT: Final[str] = str(
    recurrent_successor_dynamic_exit_v1_manifest()["fingerprint"]
)
