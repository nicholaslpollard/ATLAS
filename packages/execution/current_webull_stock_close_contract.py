from __future__ import annotations

import hashlib
import json


CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT = {
    "contract_id": (
        "atlas-simulation-current-webull-stock-close-evidence-bundle-v1"
    ),
    "scope": (
        "PRODUCT_SIMULATION_WEBULL_L1_EXIT_PLAN_TRIGGER_TO_RECURRENT_CLOSE_EVIDENCE"
    ),
    "source_exit_plan_contract_required": True,
    "source_quote_bundle_contract_required": True,
    "source_recurrent_state_binding_required": True,
    "stock_long_only_v1": True,
    "complete_current_position_plan_coverage_required": True,
    "complete_current_ticker_quote_coverage_required": True,
    "bid_price_used_for_long_stock_exit": True,
    "provider_quote_age_cap_seconds": 30,
    "stop_trigger_bid_le_stop": True,
    "target_trigger_bid_ge_target": True,
    "no_trigger_preserved_explicitly": True,
    "time_exit_evaluated_v1": False,
    "explicit_exit_fee_source_required": True,
    "exact_triggered_fee_coverage_required": True,
    "aggregate_close_batch_dry_run_required": True,
    "deterministic_trigger_order_required": True,
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
        CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
