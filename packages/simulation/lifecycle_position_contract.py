from __future__ import annotations

import hashlib
import json


LIFECYCLE_POSITION_ACCOUNT_CONTRACT = {
    "contract_id": "atlas-simulation-lifecycle-position-account-v1",
    "scope": "PRODUCT_SIMULATION_LIFECYCLE_RESERVATION_TO_OPEN_POSITION_STATE",
    "inputs": [
        "atlas-simulation-lifecycle-reservation-account-v1",
        "atlas-simulation-lifecycle-entry-fill-evidence-v1",
        "atlas-simulation-lifecycle-funding-terms-v1",
    ],
    "exact_source_reservation_state_and_ledger_required": True,
    "entry_evidence_must_bind_source_reservation_state": True,
    "exact_current_active_reservation_required": True,
    "matched_reservation_removed_once": True,
    "new_open_position_created_once": True,
    "entry_fee_expensed_once": True,
    "prior_open_positions_immutable": True,
    "prior_closed_trades_immutable": True,
    "prior_realized_pnl_immutable": True,
    "current_cash_competition_enforced": True,
    "deterministic_entry_batch_order": "filled_utc_then_fill_fingerprint",
    "idempotent_duplicate_fill_reuse": True,
    "conflicting_second_fill_fails_closed": True,
    "account_book_equity": (
        "initial_equity-cumulative_entry_fees+cumulative_account_realized_pnl"
    ),
    "balance_reconciliation": (
        "cash+stock_reserved+option_reserved+open_entry_book_value"
    ),
    "stock_short_supported": False,
    "exit_closeout_supported": False,
    "mark_to_market_supported": False,
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
        LIFECYCLE_POSITION_ACCOUNT_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT = contract_fingerprint()
