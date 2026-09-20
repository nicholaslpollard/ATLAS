from __future__ import annotations

from datetime import date
from typing import Final

from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.backtesting.recurrent_successor_daily_exit_sweep_contract import (
    RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
)


RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT: Final[str] = (
    "atlas-recurrent-successor-daily-exit-candidate-confirmation-v1"
)

SOURCE_2025_SWEEP_RUN_FINGERPRINT: Final[str] = (
    "2726c3a644ac22ed3238adf5b03e978152eaa50a5d0e91fc937716309f0db9f4"
)
TUNING_WINDOW: Final[tuple[date, date]] = (
    date(2025, 1, 1),
    date(2025, 12, 31),
)
FORWARD_CONFIRMATION_WINDOW: Final[tuple[date, date]] = (
    date(2026, 1, 1),
    date(2026, 4, 30),
)

# Frozen before any 2026 confirmation result is observed.
CANDIDATE_EXIT_POLICIES: Final[tuple[tuple[float, float], ...]] = (
    (0.02, 0.05),
    (0.03, 0.05),
)

AUTHORITY: Final[dict[str, object]] = {
    "development_only": True,
    "chronologically_after_tuning_window": True,
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


def recurrent_successor_daily_exit_confirmation_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT,
        "source_exit_sweep_contract_fingerprint": (
            RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT
        ),
        "source_2025_sweep_run_fingerprint": SOURCE_2025_SWEEP_RUN_FINGERPRINT,
        "tuning_window": [item.isoformat() for item in TUNING_WINDOW],
        "confirmation_window": [
            item.isoformat() for item in FORWARD_CONFIRMATION_WINDOW
        ],
        "candidate_exit_policies": [
            {"stop_fraction": stop, "target_fraction": target}
            for stop, target in CANDIDATE_EXIT_POLICIES
        ],
        "candidate_freeze_reason": (
            "ONLY_2025_GRID_POLICIES_WITH_POSITIVE_ENDPOINT_RETURN; "
            "2PCT_STOP_5PCT_TARGET_PRIMARY_DIAGNOSTIC_CANDIDATE; "
            "3PCT_STOP_5PCT_TARGET_SECONDARY_DIAGNOSTIC_CANDIDATE"
        ),
        "portfolio_mechanics": "UNCHANGED_FROM_DAILY_EXIT_SWEEP_V1",
        "selection_policy": {
            "automatic_promotion": False,
            "automatic_winner_selection": False,
            "2026_result_may_not_change_candidate_set": True,
            "next_step": (
                "REPORT_FORWARD_CONFIRMATION_FIRST; THEN RUN_BACKWARD_REGIME_"
                "ROBUSTNESS_WITH_CANDIDATES_UNCHANGED"
            ),
        },
        "authority": AUTHORITY,
    }
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT: Final[str] = str(
    recurrent_successor_daily_exit_confirmation_manifest()["fingerprint"]
)
