from __future__ import annotations

import hashlib
import json

from packages.core.constants import DEFAULT_EXCHANGE_CALENDAR
from packages.schemas.move_time_forecast_contract import (
    MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_decision_exit_plan_contract import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
)


FORECAST_HORIZON_CLOCK_CONTRACT = {
    "contract_id": "atlas-simulation-forecast-horizon-clock-v1",
    "scope": "PRODUCT_SIMULATION_DESCRIPTIVE_FORECAST_HORIZON_DEADLINE",
    "source_exit_plan_contract_fingerprint": (
        RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ),
    "source_forecast_contract_fingerprint": (
        MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
    ),
    "exchange_calendar": DEFAULT_EXCHANGE_CALENDAR,
    "clock_start_basis": "ACTUAL_SIMULATED_POSITION_OPENED_UTC",
    "minutes_semantics": "REGULAR_SESSION_ELAPSED_MINUTES",
    "minutes_pause_outside_regular_session": True,
    "holidays_from_exchange_calendar": True,
    "early_closes_from_exchange_calendar": True,
    "session_horizon_requires_explicit_counting_policy": True,
    "session_counting_policies": [
        "ENTRY_SESSION_INCLUDED",
        "FULL_SESSIONS_AFTER_ENTRY",
    ],
    "entry_session_included_semantics": (
        "horizon=1 expires at official close of entry session"
    ),
    "full_sessions_after_entry_semantics": (
        "horizon=1 expires at official close of first session after entry session"
    ),
    "minutes_horizon_rejects_session_counting_policy": True,
    "deadline_deterministic_from_plan_calendar_policy": True,
    "deadline_session_trace_required": True,
    "evaluation_time_in_clock_evidence": False,
    "expired_boolean_in_clock_evidence": False,
    "time_exit_disposition_authority": False,
    "price_trigger_authority": False,
    "close_fill_authority": False,
    "account_mutation_authority": False,
    "provider_reads": 0,
    "provider_writes": 0,
    "broker_reads": 0,
    "broker_writes": 0,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        FORECAST_HORIZON_CLOCK_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT = contract_fingerprint()
