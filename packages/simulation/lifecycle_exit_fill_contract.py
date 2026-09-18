from __future__ import annotations

import hashlib
import json


LIFECYCLE_EXIT_FILL_CONTRACT = {
    "contract_id": "atlas-simulation-lifecycle-exit-fill-evidence-v1",
    "scope": "PRODUCT_SIMULATION_LIFECYCLE_BROKER_NEUTRAL_COMPLETE_EXIT_FILL_EVIDENCE_ONLY",
    "inputs": ["atlas-simulation-lifecycle-position-account-v1"],
    "exact_lifecycle_position_state_fingerprint_required": True,
    "exact_active_open_position_required": True,
    "exact_open_position_fingerprint_required": True,
    "source_id_and_sha256_required": True,
    "timezone_aware_exit_timestamp_required": True,
    "exit_timestamp_not_before_position_state": True,
    "exit_timestamp_not_before_position_open": True,
    "full_position_close_quantity_required": True,
    "quantity_and_multiplier_bound_to_open_position": True,
    "exit_price_must_be_finite_and_nonnegative": True,
    "explicit_exit_fees_must_be_finite_and_nonnegative": True,
    "exit_fees_may_not_exceed_gross_exit_proceeds": True,
    "gross_exit_proceeds": (
        "quantity*exit_price_per_unit*contract_multiplier"
    ),
    "net_exit_proceeds": "gross_exit_proceeds-explicit_exit_fees",
    "zero_price_complete_loss_supported": True,
    "no_partial_exit": True,
    "no_realized_pnl": True,
    "no_position_mutation": True,
    "no_account_mutation": True,
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
        LIFECYCLE_EXIT_FILL_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


LIFECYCLE_EXIT_FILL_CONTRACT_FINGERPRINT = contract_fingerprint()
