from __future__ import annotations

import hashlib
import json


LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT = {
    "contract_id": "atlas-simulation-lifecycle-closeout-account-v1",
    "scope": "PRODUCT_SIMULATION_LIFECYCLE_POST_REENTRY_CLOSEOUT_AND_REALIZED_PNL",
    "inputs": [
        "atlas-simulation-lifecycle-position-account-v1",
        "atlas-simulation-lifecycle-exit-fill-evidence-v1",
    ],
    "exact_source_position_state_and_ledger_required": True,
    "exact_active_position_and_exit_lineage_required": True,
    "full_close_only": True,
    "remaining_reservations_unchanged": True,
    "unrelated_open_positions_unchanged": True,
    "prior_closed_trades_immutable": True,
    "matched_open_position_removed_once": True,
    "cash_delta": "net_exit_proceeds",
    "account_realized_pnl_delta": "net_exit_proceeds-entry_book_value",
    "lifetime_trade_net_pnl": (
        "gross_exit_proceeds-entry_book_value-entry_fees-exit_fees"
    ),
    "entry_fees_already_expensed_not_double_counted": True,
    "account_book_equity": (
        "initial_equity-cumulative_entry_fees+cumulative_account_realized_pnl"
    ),
    "balance_reconciliation": (
        "cash+stock_reserved+option_reserved+remaining_open_entry_book_value"
    ),
    "idempotent_same_exit_fill_reuse": True,
    "conflicting_second_close_fails_closed": True,
    "chronological_transition_order_required": True,
    "deterministic_batch_replay_required": True,
    "simulation_account_state_mutation": True,
    "simulation_realized_pnl_computation": True,
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
        LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT = contract_fingerprint()
