from __future__ import annotations

import hashlib
import json

from packages.execution.current_webull_decision_stock_close_contract import (
    CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT,
)
from packages.execution.current_webull_stock_entry_contract import (
    CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT,
)
from packages.execution.current_webull_stock_mark_adapter_contract import (
    CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_cycle_runner_contract import (
    RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_decision_exit_plan_contract import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_exit_plan_refresh_contract import (
    RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_reserve_evidence_contract import (
    RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT,
)


RECURRENT_PRODUCTION_CYCLE_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-production-cycle-v1",
    "scope": "PRODUCT_SIMULATION_PLAN_AWARE_RECURRENT_CYCLE_FACADE",
    "recurrent_cycle_runner_contract_fingerprint": (
        RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT
    ),
    "recurrent_reserve_bundle_contract_fingerprint": (
        RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT
    ),
    "current_webull_stock_entry_contract_fingerprint": (
        CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT
    ),
    "recurrent_exit_plan_refresh_contract_fingerprint": (
        RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT
    ),
    "recurrent_decision_stock_exit_plan_contract_fingerprint": (
        RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ),
    "current_webull_decision_stock_close_contract_fingerprint": (
        CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
    ),
    "current_webull_stock_mark_contract_fingerprint": (
        CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT
    ),
    "generic_runner_stage_order_preserved": [
        "CLOSE",
        "RESERVE",
        "ENTRY",
        "MARK",
    ],
    "begin_delegates_to_generic_runner": True,
    "close_requires_current_state_on_first_application": True,
    "reserve_uses_accepted_reserve_bundle": True,
    "entry_requires_current_state_on_first_application": True,
    "entry_must_bind_admitted_reserve_bundle": True,
    "post_entry_exit_plan_refresh_required_before_mark": True,
    "mark_may_recover_interrupted_refresh_before_admission": True,
    "recorded_mark_retry_requires_existing_refresh_lineage": True,
    "open_position_mark_requires_webull_stock_mark_batch": True,
    "zero_position_mark_is_provider_inert": True,
    "complete_delegates_to_generic_runner": True,
    "restart_restore_supported": True,
    "exact_stage_retry_delegated_to_admission_receipts": True,
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
        RECURRENT_PRODUCTION_CYCLE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT = contract_fingerprint()
