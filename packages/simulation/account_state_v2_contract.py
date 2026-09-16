from __future__ import annotations

import hashlib
import json


SIMULATION_ACCOUNT_STATE_V2_CONTRACT = {
    "contract_id": "atlas-simulation-account-state-v2-stock-option-reservations",
    "scope": "PRODUCT_SIMULATION_ACCOUNT_STATE_STOCK_AND_LONG_OPTION_RESERVATION_ONLY",
    "input_contracts": [
        "atlas-simulation-decision-record-v1",
        "atlas-long-option-capital-risk-reservation-v1",
    ],
    "accounting_model": "SEPARATE_STOCK_OPTION_RESERVED_CAPITAL_NO_FILL_NO_PNL_V2",
    "tracks_cash": True,
    "tracks_equity": True,
    "tracks_stock_reserved_capital": True,
    "tracks_option_reserved_capital": True,
    "tracks_stock_gross_notional": True,
    "tracks_option_signed_delta_equivalent_notional": True,
    "tracks_option_abs_delta_equivalent_notional": True,
    "tracks_option_max_loss_cash": True,
    "tracks_option_premium_at_risk": True,
    "cash_plus_stock_reserved_plus_option_reserved_equals_equity": True,
    "equity_invariant": True,
    "stock_accounting_arithmetic_reuses_v1": True,
    "stock_candidate_fingerprint_lineage_required": True,
    "option_reservation_uses_accepted_terms_exact": True,
    "option_terms_require_exact_decision_lineage": True,
    "option_terms_require_exact_candidate_lineage": True,
    "option_release_restores_exact_reserved_cash": True,
    "insufficient_unreserved_cash_fail_closed": True,
    "missing_option_terms_fail_closed": True,
    "duplicate_decision_application_is_idempotent": True,
    "duplicate_release_is_idempotent": True,
    "competition_order": ["decision_created_utc", "record_fingerprint"],
    "replayable_ledger": True,
    "deterministic_state_fingerprint": True,
    "deterministic_event_fingerprint": True,
    "deterministic_ledger_fingerprint": True,
    "stock_gross_notional_never_includes_option_exposure": True,
    "option_delta_exposure_never_reinterpreted_as_stock_notional": True,
    "margin_inference": False,
    "collateral_inference": False,
    "leverage_inference": False,
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
    return json.loads(json.dumps(SIMULATION_ACCOUNT_STATE_V2_CONTRACT))


def contract_fingerprint() -> str:
    raw = json.dumps(
        SIMULATION_ACCOUNT_STATE_V2_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT = (
    "1e9da000571d02eb8fe4d317d770fdef25fb35a527ad177d1a87a6794c9592e5"
)
