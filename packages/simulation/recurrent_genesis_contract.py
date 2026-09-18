from __future__ import annotations

import hashlib
import json


RECURRENT_GENESIS_BOOTSTRAP_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-genesis-bootstrap-v1",
    "scope": "PRODUCT_SIMULATION_ONE_TIME_EMPTY_RECURRENT_ACCOUNT_BOOTSTRAP",
    "input_initial_equity_explicit_positive": True,
    "input_as_of_utc_timezone_aware": True,
    "source_chain": [
        "atlas-simulation-account-state-v2-stock-option-reservations",
        "atlas-simulation-open-position-account-state-v1",
        "atlas-simulation-closeout-account-state-v1",
        "atlas-simulation-lifecycle-reservation-account-v1",
        "atlas-simulation-lifecycle-position-account-v1",
        "atlas-simulation-lifecycle-closeout-account-v1",
        "atlas-simulation-recurrent-lifecycle-account-v1",
    ],
    "all_source_reservations_empty_required": True,
    "all_open_positions_empty_required": True,
    "all_closed_trade_history_empty_required": True,
    "all_ledgers_empty_required": True,
    "cash_equals_initial_equity_required": True,
    "account_book_equity_equals_initial_equity_required": True,
    "one_time_checkpoint_creation_only": True,
    "existing_current_checkpoint_fails_closed": True,
    "existing_checkpoint_history_fails_closed": True,
    "durable_runtime_bootstrap_required": True,
    "research_artifact_source_forbidden": True,
    "broker_account_source_forbidden": True,
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
        RECURRENT_GENESIS_BOOTSTRAP_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_GENESIS_BOOTSTRAP_CONTRACT_FINGERPRINT = contract_fingerprint()
