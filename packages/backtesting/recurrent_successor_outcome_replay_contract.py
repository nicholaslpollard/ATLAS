from __future__ import annotations

import hashlib
import json
from typing import Final

from packages.strategies.successor_conditioning_contract import (
    ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT,
    DAILY_PRIMARY_COST_BPS,
    DAILY_PRIMARY_HORIZON_SESSIONS,
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    INTRADAY_PRIMARY_COST_BPS,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
)


RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT: Final[str] = (
    "atlas-recurrent-successor-outcome-replay-v1-walk-forward-selector-long-only"
)

# Portfolio mechanics intentionally preserve the already accepted A34 reference
# account constraints while moving the accounting onto the current recurrent
# lifecycle. This first mode is an outcome replay, not a bar-level exit retest.
INITIAL_POSITION_FRACTION: Final[float] = 0.10
MAX_OPEN_POSITIONS: Final[int] = 10
MAX_POSITIONS_PER_FAMILY: Final[int] = 3
ONE_ACTIVE_POSITION_PER_TICKER: Final[bool] = True
NORMALIZED_ENTRY_PRICE: Final[float] = 100.0

AUTHORITY: Final[dict[str, object]] = {
    "development_only": True,
    "accepted_successor_conditioning_required": True,
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
    "confluence_authority": False,
}


def _stable_hash(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def recurrent_successor_outcome_replay_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT,
        "scope": [DEVELOPMENT_START, DEVELOPMENT_END],
        "upstream": {
            "successor_conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
            "accepted_standalone_artifact_set_fingerprint": (
                ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT
            ),
            "admission_source": "conditioning_v1/eligibility_assignments.parquet",
            "research_eligible_required": True,
            "comparable_required": True,
        },
        "portfolio": {
            "position_fraction_of_current_book_equity": INITIAL_POSITION_FRACTION,
            "max_open_positions": MAX_OPEN_POSITIONS,
            "max_positions_per_family": MAX_POSITIONS_PER_FAMILY,
            "one_active_position_per_ticker": ONE_ACTIVE_POSITION_PER_TICKER,
            "stock_direction_supported": "LONG_ONLY",
            "short_disposition": "UNSUPPORTED_CURRENT_RECURRENT_FUNDING_V1",
        },
        "outcome_replay": {
            "price_basis": NORMALIZED_ENTRY_PRICE,
            "gross_return_source": "accepted_successor_normalized_gross_return",
            "daily_exit": {
                "horizon_sessions": DAILY_PRIMARY_HORIZON_SESSIONS,
                "round_trip_cost_bps": DAILY_PRIMARY_COST_BPS,
            },
            "intraday_exit": {
                "timestamp_source": "accepted_successor_normalized_entry_exit_time",
                "round_trip_cost_bps": INTRADAY_PRIMARY_COST_BPS,
            },
            "gross_return_used_only_at_exit_event": True,
            "future_outcome_used_for_admission": False,
            "decision_record_adapter": (
                "training_selector_score_product_fixture_not_forecast_evidence"
            ),
            "bar_level_stop_target_time_retest": False,
            "realized_equity_curve_only": True,
        },
        "authority": AUTHORITY,
    }
    payload["fingerprint"] = _stable_hash(payload)
    return payload


RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT_FINGERPRINT: Final[str] = str(
    recurrent_successor_outcome_replay_manifest()["fingerprint"]
)
