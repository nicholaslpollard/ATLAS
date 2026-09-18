from __future__ import annotations

import hashlib
import json


LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT = {
    "contract_id": "atlas-simulation-lifecycle-reservation-account-v1",
    "scope": "PRODUCT_SIMULATION_POST_CLOSE_REENTRY_RESERVATION_ONLY",
    "source": "atlas-simulation-closeout-account-state-v1",
    "source_closeout_history_immutable": True,
    "source_open_positions_immutable": True,
    "source_closed_trades_immutable": True,
    "source_entry_and_exit_fees_immutable": True,
    "source_realized_pnl_immutable": True,
    "new_decisions_supported": True,
    "new_stock_reservations_supported": True,
    "new_long_option_reservations_supported": True,
    "abstain_and_rejection_events_supported": True,
    "cash_reduced_by_new_reserved_capital": True,
    "account_book_equity_unchanged_by_reservation": True,
    "balance_reconciliation": (
        "cash+stock_reserved+option_reserved+open_entry_book_value"
    ),
    "stock_reserved_gross_notional_separate_from_open_stock_exposure": True,
    "option_reserved_delta_separate_from_open_option_entry_reference": True,
    "option_reserved_max_loss_equals_reserved_capital": True,
    "decision_idempotency_required": True,
    "conflicting_option_terms_fail_closed": True,
    "chronological_events_required": True,
    "deterministic_replay_required": True,
    "entry_fill_supported": False,
    "new_open_position_supported": False,
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
        LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT = contract_fingerprint()
