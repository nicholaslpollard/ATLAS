from __future__ import annotations

import hashlib
import json


SIMULATED_ENTRY_FILL_CONTRACT = {
    "contract_id": "atlas-simulated-entry-fill-evidence-v1",
    "scope": "PRODUCT_SIMULATION_BROKER_NEUTRAL_COMPLETE_ENTRY_FILL_EVIDENCE_ONLY",
    "input_contracts": [
        "atlas-simulation-decision-record-v1",
        "atlas-simulation-account-state-v2-stock-option-reservations",
        "atlas-long-option-capital-risk-reservation-v1",
    ],
    "requires_active_reservation": True,
    "requires_exact_account_state_fingerprint": True,
    "requires_exact_decision_record_fingerprint": True,
    "requires_exact_candidate_fingerprint": True,
    "fill_source_id_required": True,
    "fill_source_fingerprint_required": True,
    "complete_entry_only": True,
    "partial_fill_support": False,
    "stock_fill_notional_equals_reserved_economic_notional": True,
    "stock_quantity_derived_from_explicit_fill_price_and_reserved_notional": True,
    "stock_quantity_may_be_fractional": True,
    "stock_funding_semantics_inferred": False,
    "stock_short_proceeds_semantics_inferred": False,
    "option_terms_required": True,
    "option_contract_count_equals_reserved_terms": True,
    "option_multiplier_equals_reserved_terms": True,
    "option_cash_debit_includes_explicit_entry_fees": True,
    "option_premium_debit_cannot_exceed_reserved_ask_debit": True,
    "option_entry_fees_cannot_exceed_cash_fee_reserve": True,
    "option_cash_debit_cannot_exceed_reserved_capital": True,
    "option_unspent_reservation_recorded": True,
    "deterministic_fill_fingerprint": True,
    "account_mutation_authority": False,
    "reservation_release_authority": False,
    "open_position_authority": False,
    "mark_to_market_authority": False,
    "realized_pnl_authority": False,
    "provider_reads": 0,
    "provider_writes": 0,
    "broker_reads": 0,
    "broker_writes": 0,
    "broker_fill_authority": False,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_payload() -> dict[str, object]:
    return json.loads(json.dumps(SIMULATED_ENTRY_FILL_CONTRACT))


def contract_fingerprint() -> str:
    raw = json.dumps(
        SIMULATED_ENTRY_FILL_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT = (
    "e271ba5c66fe9bc41b7f81945a1ef8152a2eeae091b27f6efd4859bacd2d8668"
)
