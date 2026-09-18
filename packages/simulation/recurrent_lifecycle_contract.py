from __future__ import annotations

import hashlib
import json


RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-lifecycle-account-v1",
    "scope": "PRODUCT_SIMULATION_STABLE_MULTI_CYCLE_ACCOUNT_STATE_FOUNDATION",
    "bootstrap_input": "atlas-simulation-lifecycle-closeout-account-v1",
    "canonical_closed_trade_history_required": True,
    "legacy_closed_trade_provenance_preserved": True,
    "lifecycle_closed_trade_provenance_preserved": True,
    "source_record_fingerprint_required": True,
    "source_state_contract_and_fingerprint_required": True,
    "active_reservations_preserved": True,
    "open_positions_preserved": True,
    "fee_history_preserved": True,
    "realized_pnl_history_preserved": True,
    "account_book_equity": (
        "initial_equity-cumulative_entry_fees+cumulative_account_realized_pnl"
    ),
    "balance_reconciliation": (
        "cash+stock_reserved+option_reserved+open_entry_book_value"
    ),
    "immutable_snapshot_fingerprints": True,
    "append_only_event_ledger": True,
    "stable_repeated_cycle_contract": True,
    "mark_to_market_is_read_only_projection": True,
    "provider_read_authority": False,
    "provider_write_authority": False,
    "broker_read_authority": False,
    "broker_write_authority": False,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT = contract_fingerprint()
