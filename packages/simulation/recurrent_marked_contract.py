from __future__ import annotations

import hashlib
import json


RECURRENT_MARKED_ACCOUNT_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-marked-account-v1",
    "scope": "PRODUCT_SIMULATION_RECURRENT_CURRENT_MARKED_ACCOUNT_PROJECTION",
    "input_account": "atlas-simulation-recurrent-lifecycle-account-v1",
    "mark_input": "atlas-simulation-market-mark-evidence-v1",
    "exact_recurrent_state_fingerprint_required": True,
    "exact_current_open_position_fingerprint_per_mark_required": True,
    "complete_current_open_position_mark_coverage_required": True,
    "one_mark_per_current_open_position_required": True,
    "common_valuation_timestamp_required": True,
    "valuation_not_before_account_state": True,
    "fresh_valuation_eligible_marks_only": True,
    "missing_duplicate_stale_or_extra_mark_fails_closed": True,
    "marked_position_value": (
        "quantity*selected_mark_price_per_unit*contract_multiplier"
    ),
    "position_unrealized_pnl": "marked_position_value-entry_book_value",
    "account_unrealized_pnl": "sum_current_open_position_unrealized_pnl",
    "marked_equity": "account_book_equity+account_unrealized_pnl",
    "balance_reconciliation": (
        "cash+stock_reserved+option_reserved+marked_open_position_value"
    ),
    "canonical_closed_history_not_revalued": True,
    "recurrent_ledger_mutation": False,
    "account_mutation_authority": False,
    "new_realized_pnl_authority": False,
    "exit_closeout_authority": False,
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
        RECURRENT_MARKED_ACCOUNT_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_MARKED_ACCOUNT_CONTRACT_FINGERPRINT = contract_fingerprint()
