from __future__ import annotations

import hashlib
import json


MARKED_ACCOUNT_STATE_CONTRACT = {
    "contract_id": "atlas-simulation-marked-account-state-v1",
    "scope": "PRODUCT_SIMULATION_FRESH_MARKED_ACCOUNT_AND_UNREALIZED_PNL_ONLY",
    "inputs": [
        "atlas-simulation-open-position-account-state-v1",
        "atlas-simulation-market-mark-evidence-v1",
    ],
    "exact_open_position_account_state_required": True,
    "exact_open_position_fingerprint_per_mark_required": True,
    "complete_active_position_mark_coverage_required": True,
    "one_mark_per_active_position_required": True,
    "common_valuation_timestamp_required": True,
    "valuation_timestamp_not_before_open_position_state": True,
    "mark_market_timestamp_not_before_position_open": True,
    "fresh_valuation_eligible_marks_only": True,
    "stale_missing_or_extra_mark_fails_closed": True,
    "marked_position_value": "quantity*selected_mark_price_per_unit*contract_multiplier",
    "position_unrealized_pnl": "marked_position_value-entry_book_value",
    "position_unrealized_return": "position_unrealized_pnl/entry_book_value",
    "account_unrealized_pnl": "sum_position_unrealized_pnl",
    "marked_equity": "entry_book_equity+account_unrealized_pnl",
    "balance_reconciliation": "cash+remaining_reserved_capital+marked_open_position_value",
    "entry_fees_already_expensed_not_double_counted": True,
    "option_entry_delta_reference_not_current_greek": True,
    "no_current_greek_inference": True,
    "no_realized_pnl": True,
    "no_exit_closeout": True,
    "no_account_mutation": True,
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
        MARKED_ACCOUNT_STATE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT = contract_fingerprint()
