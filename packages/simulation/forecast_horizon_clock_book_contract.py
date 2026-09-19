from __future__ import annotations

import hashlib
import json

from packages.simulation.forecast_horizon_clock_contract import (
    FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_decision_exit_plan_contract import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
)


FORECAST_HORIZON_CLOCK_BOOK_CONTRACT = {
    "contract_id": "atlas-simulation-forecast-horizon-clock-book-v1",
    "scope": "PRODUCT_SIMULATION_DURABLE_OPEN_POSITION_HORIZON_CLOCK_BOOK",
    "source_exit_plan_book_contract_fingerprint": (
        RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ),
    "source_clock_contract_fingerprint": (
        FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
    ),
    "full_source_exit_plan_book_retained": True,
    "exact_open_plan_clock_coverage_required": True,
    "existing_open_position_clocks_immutable": True,
    "new_positions_require_explicit_clock_policy": True,
    "exact_new_position_policy_coverage_required": True,
    "session_counting_policy_cannot_change_after_clock_freeze": True,
    "closed_position_clocks_pruned_on_rebuild": True,
    "book_effective_time_is_source_plan_book_time": True,
    "deterministic_position_order_required": True,
    "atomic_fsync_persistence_required": True,
    "book_self_fingerprint_required": True,
    "evaluation_time_in_book": False,
    "expired_boolean_in_book": False,
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
        FORECAST_HORIZON_CLOCK_BOOK_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
