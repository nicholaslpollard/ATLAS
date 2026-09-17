from __future__ import annotations

import hashlib
import json


SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT = {
    "contract_id": "atlas-simulation-funding-collateral-terms-v1",
    "scope": "PRODUCT_SIMULATION_FUNDING_COLLATERAL_TERMS_ONLY",
    "inputs": [
        "atlas-simulation-account-state-v2-stock-option-reservations",
        "atlas-simulated-entry-fill-evidence-v1",
    ],
    "exact_account_state_fingerprint_required": True,
    "exact_active_reservation_fingerprint_required": True,
    "exact_fill_fingerprint_required": True,
    "stock_long_funding_model": "CASH_ONLY_NO_BORROWING",
    "stock_long_required_cash_includes_fill_notional_and_entry_fees": True,
    "stock_long_may_use_existing_reservation_plus_unreserved_cash": True,
    "stock_long_insufficient_unreserved_cash_fails_closed": True,
    "stock_short_supported": False,
    "stock_short_proceeds_inferred": False,
    "stock_margin_inferred": False,
    "stock_collateral_inferred": False,
    "option_funding_model": "EXACT_ACCEPTED_LONG_OPTION_DEBIT",
    "option_supplemental_cash_required": False,
    "option_unspent_reservation_preserved": True,
    "borrowing_authority": False,
    "account_mutation_authority": False,
    "reservation_release_authority": False,
    "open_position_authority": False,
    "mark_to_market_authority": False,
    "realized_pnl_authority": False,
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
        SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_FINGERPRINT = contract_fingerprint()
