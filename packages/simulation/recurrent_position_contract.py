from __future__ import annotations

import hashlib
import json


RECURRENT_POSITION_TRANSITION_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-position-transition-v1",
    "scope": "PRODUCT_SIMULATION_RECURRENT_RESERVATION_TO_OPEN_POSITION_MUTATION",
    "input_output_account_contract": "atlas-simulation-recurrent-lifecycle-account-v1",
    "fill_input": "atlas-simulation-recurrent-entry-fill-evidence-v1",
    "funding_input": "atlas-simulation-recurrent-funding-terms-v1",
    "same_account_contract_before_and_after": True,
    "append_only_recurrent_ledger": True,
    "exact_evidence_source_snapshot_required": True,
    "exact_current_active_reservation_required": True,
    "matched_reservation_consumed_once": True,
    "open_position_created_once": True,
    "entry_fee_expensed_once": True,
    "canonical_closed_history_preserved": True,
    "unrelated_open_positions_and_reservations_preserved": True,
    "current_cash_competition_enforced": True,
    "batch_common_source_snapshot_supported": True,
    "deterministic_batch_order": "filled_utc_then_fill_fingerprint",
    "duplicate_fill_idempotent": True,
    "conflicting_second_fill_fails_closed": True,
    "stock_short_supported": False,
    "no_exit_closeout": True,
    "no_mark_to_market": True,
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
        RECURRENT_POSITION_TRANSITION_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_POSITION_TRANSITION_CONTRACT_FINGERPRINT = contract_fingerprint()
