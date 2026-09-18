from __future__ import annotations

import hashlib
import json


SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT = {
    "contract_id": "atlas-simulation-closeout-account-state-v1",
    "scope": "PRODUCT_SIMULATION_DETERMINISTIC_CLOSEOUT_AND_REALIZED_PNL_ACCOUNTING",
    "inputs": [
        "atlas-simulation-open-position-account-state-v1",
        "atlas-simulated-exit-fill-evidence-v1",
    ],
    "exact_source_open_position_state_required": True,
    "exact_active_position_and_exit_fill_lineage_required": True,
    "full_close_only": True,
    "remaining_reservations_unchanged": True,
    "matched_open_position_removed_only": True,
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
        "cash+remaining_reserved_capital+remaining_open_entry_book_value"
    ),
    "closed_trade_hold_seconds_required": True,
    "idempotent_same_exit_fill_reuse": True,
    "conflicting_second_close_fails_closed": True,
    "chronological_transition_order_required": True,
    "deterministic_batch_replay_required": True,
    "simulation_account_state_mutation": True,
    "simulation_realized_pnl_computation": True,
    "no_provider_reads_or_writes": True,
    "no_broker_reads_or_writes": True,
    "no_order_creation": True,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT = contract_fingerprint()
