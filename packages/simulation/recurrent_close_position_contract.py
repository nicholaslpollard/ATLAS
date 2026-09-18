from __future__ import annotations

import hashlib
import json


RECURRENT_CLOSE_POSITION_TRANSITION_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-close-position-transition-v1",
    "scope": "PRODUCT_SIMULATION_RECURRENT_CLOSE_POSITION_AND_REALIZED_PNL",
    "input_output_account_contract": "atlas-simulation-recurrent-lifecycle-account-v1",
    "exit_fill_input": "atlas-simulation-recurrent-exit-fill-evidence-v1",
    "same_account_contract_before_and_after": True,
    "append_only_recurrent_ledger": True,
    "exact_evidence_source_snapshot_required": True,
    "exact_current_active_position_required": True,
    "matched_position_removed_once": True,
    "remaining_reservations_unchanged": True,
    "unrelated_open_positions_unchanged": True,
    "canonical_closed_history_append_only": True,
    "native_recurrent_closed_trade_origin_required": True,
    "native_source_record_is_exit_fill_fingerprint": True,
    "cash_delta": "net_exit_proceeds",
    "account_realized_pnl_delta": "net_exit_proceeds-entry_book_value",
    "lifetime_trade_net_pnl": (
        "account_realized_pnl_delta-entry_fee_already_expensed"
    ),
    "entry_fee_not_double_counted": True,
    "exit_fee_added_once": True,
    "account_book_equity": (
        "initial_equity-cumulative_entry_fees+cumulative_account_realized_pnl"
    ),
    "balance_reconciliation": (
        "cash+stock_reserved+option_reserved+open_entry_book_value"
    ),
    "batch_common_source_snapshot_supported": True,
    "deterministic_batch_order": "exited_utc_then_exit_fill_fingerprint",
    "duplicate_exit_fill_idempotent": True,
    "conflicting_second_close_fails_closed": True,
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
        RECURRENT_CLOSE_POSITION_TRANSITION_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_CLOSE_POSITION_TRANSITION_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
