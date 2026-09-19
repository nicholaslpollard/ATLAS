from __future__ import annotations

import hashlib
import json

from packages.execution.current_webull_decision_stock_close_contract import (
    CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT,
)
from packages.simulation.forecast_horizon_time_disposition_contract import (
    FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT,
)


CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT = {
    "contract_id": (
        "atlas-simulation-current-webull-time-aware-stock-close-v1"
    ),
    "scope": (
        "PRODUCT_SIMULATION_PRICE_FIRST_STOP_TARGET_TIME_CLOSE_DECISION"
    ),
    "source_price_close_contract_fingerprint": (
        CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
    ),
    "source_time_disposition_contract_fingerprint": (
        FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT
    ),
    "full_source_price_close_bundle_retained": True,
    "full_source_time_disposition_bundle_retained": True,
    "exact_exit_plan_book_match_required": True,
    "time_evaluation_must_equal_price_close_build_time": True,
    "price_trigger_precedence_over_time": True,
    "stop_precedence_over_time": True,
    "target_precedence_over_time": True,
    "time_only_when_price_no_trigger": True,
    "time_exit_requires_time_expired": True,
    "time_exit_quote_received_at_or_after_deadline": True,
    "time_exit_uses_existing_webull_bid": True,
    "explicit_time_exit_fee_source_required": True,
    "exact_time_exit_fee_coverage_required": True,
    "combined_close_batch_dry_run_required": True,
    "deterministic_position_order_required": True,
    "atomic_fsync_persistence_required": True,
    "bundle_self_fingerprint_required": True,
    "provider_calls_performed": 0,
    "broker_calls_performed": 0,
    "provider_read_authority": False,
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
        CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
