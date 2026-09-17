from __future__ import annotations

import hashlib
import json


EXIT_FILL_EVIDENCE_CONTRACT = {
    "contract_id": "atlas-simulated-exit-fill-evidence-v1",
    "scope": "PRODUCT_SIMULATION_BROKER_NEUTRAL_COMPLETE_EXIT_FILL_EVIDENCE_ONLY",
    "inputs": ["atlas-simulation-open-position-account-state-v1"],
    "exact_open_position_account_state_required": True,
    "exact_active_position_fingerprint_required": True,
    "source_id_and_sha256_required": True,
    "complete_position_close_only": True,
    "partial_exit_supported": False,
    "exit_timestamp_not_before_position_open": True,
    "exit_timestamp_not_before_source_state": True,
    "stock_exit_price_must_be_positive": True,
    "long_option_exit_price_may_be_zero": True,
    "explicit_exit_fees_nonnegative": True,
    "gross_exit_value": "quantity*exit_price_per_unit*contract_multiplier",
    "quantity_and_multiplier_copied_from_position": True,
    "no_position_mutation": True,
    "no_realized_pnl": True,
    "no_mark_to_market": True,
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
        EXIT_FILL_EVIDENCE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


EXIT_FILL_EVIDENCE_CONTRACT_FINGERPRINT = contract_fingerprint()
