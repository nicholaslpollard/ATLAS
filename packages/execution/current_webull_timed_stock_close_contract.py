from __future__ import annotations

import hashlib
import json

from packages.execution.current_webull_decision_stock_close_contract import (
    CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT,
)
from packages.simulation.forecast_horizon_clock_contract import (
    FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
)


CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT = {
    "contract_id": "atlas-simulation-current-webull-timed-stock-close-v2",
    "scope": "PRODUCT_SIMULATION_PRICE_AND_FORECAST_HORIZON_STOCK_CLOSE",
    "base_price_close_contract_fingerprint": (
        CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
    ),
    "horizon_clock_contract_fingerprint": (
        FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
    ),
    "base_price_evidence_retained_complete": True,
    "clock_evidence_retained_complete_per_position": True,
    "clock_evaluation_time_is_quote_receipt_time": True,
    "final_dispositions": ["NO_TRIGGER", "STOP", "TARGET", "TIME"],
    "time_precedence_after_expiry": True,
    "pre_expiry_price_disposition_preserved": True,
    "final_trigger_fill_uses_executable_bid": True,
    "exact_final_trigger_fee_coverage_required": True,
    "aggregate_final_close_batch_dry_run_required": True,
    "atomic_fsync_persistence_required": True,
    "bundle_self_fingerprint_required": True,
    "provider_calls_performed": 0,
    "broker_calls_performed": 0,
    "provider_write_authority": False,
    "broker_read_authority": False,
    "broker_write_authority": False,
    "broker_fill_authority": False,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
