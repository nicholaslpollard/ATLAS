from __future__ import annotations

import hashlib
import json


RECURRENT_GENESIS_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-genesis-v1",
    "scope": "PRODUCT_SIMULATION_EXPLICIT_EMPTY_RECURRENT_ACCOUNT_GENESIS",
    "required_economic_input": "explicit_positive_initial_equity",
    "genesis_timestamp_required": True,
    "accepted_initializer_chain": [
        "atlas-simulation-account-state-v2-stock-option-reservations",
        "atlas-simulation-open-position-account-state-v1",
        "atlas-simulation-closeout-account-state-v1",
        "atlas-simulation-lifecycle-reservation-account-v1",
        "atlas-simulation-lifecycle-position-account-v1",
        "atlas-simulation-lifecycle-closeout-account-v1",
        "atlas-simulation-recurrent-lifecycle-account-v1",
    ],
    "empty_stock_reservations_required": True,
    "empty_option_reservations_required": True,
    "empty_open_positions_required": True,
    "empty_closed_trades_required": True,
    "empty_recurrent_ledger_required": True,
    "cash_equals_initial_equity_required": True,
    "book_equity_equals_initial_equity_required": True,
    "no_fees_or_realized_pnl_at_genesis": True,
    "no_test_fixture_fingerprint_fabrication": True,
    "no_broker_balance_inference": True,
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
        RECURRENT_GENESIS_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_GENESIS_CONTRACT_FINGERPRINT = contract_fingerprint()
