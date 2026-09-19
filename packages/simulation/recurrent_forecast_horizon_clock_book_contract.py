from __future__ import annotations

import hashlib
import json

from packages.simulation.forecast_horizon_clock_contract import (
    FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_decision_exit_plan_contract import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
)


RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-forecast-horizon-clock-book-v1",
    "scope": (
        "PRODUCT_SIMULATION_DURABLE_OPEN_POSITION_FORECAST_HORIZON_CLOCK_BOOK"
    ),
    "source_clock_contract_fingerprint": (
        FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
    ),
    "source_exit_plan_book_contract_fingerprint": (
        RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ),
    "full_exit_plan_book_retained": True,
    "exact_open_plan_clock_coverage_required": True,
    "existing_open_position_clocks_immutable": True,
    "new_plans_require_explicit_clock_policy": True,
    "policy_coverage_exact_for_new_plans": True,
    "existing_plan_policy_redefinition_forbidden": True,
    "closed_position_clocks_pruned": True,
    "stored_clocks_rederived_from_plan_and_policy": True,
    "atomic_fsync_persistence_required": True,
    "book_self_fingerprint_required": True,
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
        RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
