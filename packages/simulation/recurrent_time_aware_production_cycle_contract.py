from __future__ import annotations

import hashlib
import json

from packages.execution.current_webull_time_aware_stock_close_contract import (
    CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_production_cycle_contract import (
    RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT,
)


RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT = {
    "contract_id": (
        "atlas-simulation-recurrent-time-aware-production-cycle-v1"
    ),
    "scope": (
        "PRODUCT_SIMULATION_TIME_AWARE_CLOSE_EXTENSION_OF_ACCEPTED_PRODUCTION_CYCLE"
    ),
    "base_production_cycle_contract_fingerprint": (
        RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT
    ),
    "time_aware_close_contract_fingerprint": (
        CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT
    ),
    "base_begin_semantics_preserved": True,
    "base_reserve_semantics_preserved": True,
    "base_entry_semantics_preserved": True,
    "base_post_entry_refresh_semantics_preserved": True,
    "base_mark_semantics_preserved": True,
    "base_complete_semantics_preserved": True,
    "generic_runner_stage_order_preserved": [
        "CLOSE",
        "RESERVE",
        "ENTRY",
        "MARK",
    ],
    "close_uses_time_aware_final_bundle": True,
    "close_requires_current_state_on_first_application": True,
    "exact_close_retry_delegated_to_existing_stage_admission": True,
    "restart_restore_inherited_from_base_cycle": True,
    "provider_reads_performed": 0,
    "provider_writes_performed": 0,
    "broker_reads_performed": 0,
    "broker_writes_performed": 0,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
