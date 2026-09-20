from __future__ import annotations

from datetime import date
from typing import Final

from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.backtesting.recurrent_successor_daily_exit_confirmation_contract import (
    CANDIDATE_EXIT_POLICIES,
    RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT,
    SOURCE_2025_SWEEP_RUN_FINGERPRINT,
)


RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT: Final[str] = (
    "atlas-recurrent-successor-daily-exit-regime-robustness-v1"
)

SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT: Final[str] = (
    "bd8e1fd32d2c34e8699e6e243e851c936c475e0d5b16fc4f6047d5f02e40f210"
)

ANNUAL_REGIME_WINDOWS: Final[tuple[tuple[str, date, date], ...]] = tuple(
    (
        str(year),
        date(year, 1, 1),
        date(year, 12, 31),
    )
    for year in range(2018, 2025)
)

AUTHORITY: Final[dict[str, object]] = {
    "development_only": True,
    "retrospective_regime_robustness_only": True,
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


def recurrent_successor_daily_exit_regime_robustness_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT,
        "source_confirmation_contract_fingerprint": (
            RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT
        ),
        "source_2025_sweep_run_fingerprint": SOURCE_2025_SWEEP_RUN_FINGERPRINT,
        "source_2026_confirmation_run_fingerprint": (
            SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT
        ),
        "candidate_exit_policies": [
            {"stop_fraction": stop, "target_fraction": target}
            for stop, target in CANDIDATE_EXIT_POLICIES
        ],
        "annual_regime_windows": [
            {
                "regime_id": regime_id,
                "start": start.isoformat(),
                "end": end.isoformat(),
            }
            for regime_id, start, end in ANNUAL_REGIME_WINDOWS
        ],
        "account_reset_policy": (
            "RESET_TO_SAME_INITIAL_EQUITY_FOR_EACH_CALENDAR_REGIME_TO_COMPARE_"
            "POLICY_BEHAVIOR_WITHOUT_PRIOR_YEAR_COMPOUNDING"
        ),
        "candidate_policy_mutation_after_2026": False,
        "purpose": (
            "MAP_STATIC_EXIT_POLICY_RETURN_DRAWDOWN_AND_EXIT_MIX_ACROSS_"
            "EARLIER_DEVELOPMENT_REGIMES_BEFORE_DYNAMIC_EXIT_V1"
        ),
        "next_research_package": (
            "DYNAMIC_EXIT_V1_POINT_IN_TIME_REGIME_VOLATILITY_PATH_EVIDENCE"
        ),
        "authority": AUTHORITY,
    }
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT: Final[str] = str(
    recurrent_successor_daily_exit_regime_robustness_manifest()["fingerprint"]
)
