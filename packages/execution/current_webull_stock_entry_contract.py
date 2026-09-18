from __future__ import annotations

import hashlib
import json


CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT = {
    "contract_id": (
        "atlas-simulation-current-webull-stock-entry-evidence-bundle-v1"
    ),
    "scope": (
        "PRODUCT_SIMULATION_WEBULL_L1_TO_RECURRENT_STOCK_ENTRY_EVIDENCE"
    ),
    "source_quote_bundle_contract_required": True,
    "source_reserve_bundle_contract_required": True,
    "source_recurrent_state_binding_required": True,
    "stock_selections_only_v1": True,
    "abstentions_omitted_from_entry_actions": True,
    "option_selection_fails_closed_v1": True,
    "exact_case_quote_coverage_required": True,
    "ask_price_used_for_stock_entry": True,
    "quote_received_after_reserve_state_required": True,
    "provider_quote_age_cap_seconds": 30,
    "explicit_entry_fee_source_required": True,
    "exact_fee_coverage_required": True,
    "aggregate_batch_funding_dry_run_required": True,
    "deterministic_fill_order_required": True,
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
        CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
