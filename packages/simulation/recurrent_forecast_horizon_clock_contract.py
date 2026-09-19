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


RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-forecast-horizon-clock-v1",
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
    "sessions_semantics": "ENTRY_SESSION_COUNTS_AS_SESSION_ONE",
    "sessions_deadline_basis": "NTH_INCLUDED_EXCHANGE_SESSION_CLOSE",
    "holidays_from_exchange_calendar": True,
    "early_closes_from_exchange_calendar": True,
    "non_session_days_do_not_count": True,
    "deadline_may_equal_regular_close": True,
    "deadline_deterministic": True,
    "deadline_trace_required": True,
    "time_exit_trigger_authority": False,
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
        RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
