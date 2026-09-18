from __future__ import annotations

import hashlib
import json


RECURRENT_RESERVATION_TRANSITION_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-reservation-transitions-v1",
    "scope": "PRODUCT_SIMULATION_RECURRENT_ACCOUNT_RESERVATION_MUTATION",
    "input": "atlas-simulation-recurrent-lifecycle-account-v1",
    "current_unreserved_cash_only": True,
    "existing_open_positions_preserved": True,
    "canonical_closed_history_preserved": True,
    "prior_fee_and_realized_pnl_history_preserved": True,
    "stock_long_reservation_supported": True,
    "stock_short_reservation_supported": False,
    "long_option_reservation_supported": True,
    "option_terms_required": True,
    "option_reservation_exposure_separate_from_open_position_exposure": True,
    "duplicate_decision_idempotent": True,
    "conflicting_duplicate_option_terms_fail_closed": True,
    "deterministic_batch_order": "decision_created_utc_then_record_fingerprint",
    "append_only_recurrent_ledger": True,
    "entry_fill_authority": False,
    "open_position_authority": False,
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
        RECURRENT_RESERVATION_TRANSITION_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_RESERVATION_TRANSITION_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
