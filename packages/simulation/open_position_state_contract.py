from __future__ import annotations

import hashlib
import json


OPEN_POSITION_ACCOUNT_STATE_CONTRACT = {
    "contract_id": "atlas-simulation-open-position-account-state-v1",
    "scope": "PRODUCT_SIMULATION_ENTRY_BOOK_OPEN_POSITION_ACCOUNT_STATE_ONLY",
    "inputs": [
        "atlas-simulation-account-state-v2-stock-option-reservations",
        "atlas-simulated-entry-fill-evidence-v1",
        "atlas-simulation-funding-collateral-terms-v1",
    ],
    "single_source_reservation_batch_required": True,
    "fill_account_state_must_equal_source_reservation_state": True,
    "funding_account_state_must_equal_source_reservation_state": True,
    "exact_fill_funding_reservation_lineage_required": True,
    "transition_order": "filled_utc_then_fill_fingerprint",
    "duplicate_same_fill_idempotent": True,
    "conflicting_fill_same_decision_fails_closed": True,
    "cash_rechecked_at_transition_time": True,
    "reservation_released_exactly_once": True,
    "entry_book_value_equals_gross_fill_notional": True,
    "entry_fees_reduce_entry_book_equity_immediately": True,
    "stock_long_only": True,
    "stock_short_supported": False,
    "option_long_call_put_supported": True,
    "option_delta_exposure_is_entry_reference_only": True,
    "option_premium_at_risk_equals_entry_book_value": True,
    "no_mark_to_market": True,
    "no_unrealized_pnl": True,
    "no_realized_pnl": True,
    "no_exit_closeout": True,
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
        OPEN_POSITION_ACCOUNT_STATE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT = contract_fingerprint()
