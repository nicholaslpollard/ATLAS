from __future__ import annotations

import hashlib
import json


SIMULATION_ACCOUNT_STATE_CONTRACT = {
    "contract_id": "atlas-simulation-account-state-v1",
    "scope": "PRODUCT_SIMULATION_ACCOUNT_STATE_STOCK_RESERVATION_ONLY",
    "input_contracts": [
        "atlas-simulation-decision-record-v1",
    ],
    "accounting_model": "RESERVED_CAPITAL_NO_FILL_NO_PNL_V1",
    "tracks_cash": True,
    "tracks_equity": True,
    "tracks_reserved_capital": True,
    "tracks_gross_exposure": True,
    "tracks_simulated_stock_reservations": True,
    "cash_plus_reserved_capital_equals_equity": True,
    "gross_exposure_equals_active_reservation_notional": True,
    "stock_reservation_uses_decision_candidate_capital": True,
    "stock_gross_exposure_uses_stock_position_notional": True,
    "reservation_release_restores_capital": True,
    "abstentions_are_ledgered": True,
    "unsupported_option_selections_fail_closed": True,
    "insufficient_capital_fail_closed": True,
    "duplicate_decision_application_is_idempotent": True,
    "competition_order": ["decision_created_utc", "record_fingerprint"],
    "replayable_ledger": True,
    "deterministic_state_fingerprint": True,
    "deterministic_event_fingerprint": True,
    "deterministic_ledger_fingerprint": True,
    "realized_pnl_authority": False,
    "mark_to_market_authority": False,
    "fill_simulation_authority": False,
    "provider_reads": 0,
    "provider_writes": 0,
    "broker_reads": 0,
    "broker_writes": 0,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_payload() -> dict[str, object]:
    return json.loads(json.dumps(SIMULATION_ACCOUNT_STATE_CONTRACT))


def contract_fingerprint() -> str:
    raw = json.dumps(
        SIMULATION_ACCOUNT_STATE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


SIMULATION_ACCOUNT_STATE_CONTRACT_FINGERPRINT = (
    "2460956a47dfa3f73c157b5e2f60aa710b10dabb0c1a7115309056d06c1a588b"
)
