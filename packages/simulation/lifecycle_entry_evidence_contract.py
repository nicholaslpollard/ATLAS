from __future__ import annotations

import hashlib
import json


LIFECYCLE_ENTRY_FILL_CONTRACT = {
    "contract_id": "atlas-simulation-lifecycle-entry-fill-evidence-v1",
    "scope": "PRODUCT_SIMULATION_LIFECYCLE_BROKER_NEUTRAL_COMPLETE_ENTRY_FILL_EVIDENCE_ONLY",
    "inputs": [
        "atlas-simulation-decision-record-v1",
        "atlas-simulation-lifecycle-reservation-account-v1",
        "atlas-long-option-capital-risk-reservation-v1",
    ],
    "exact_lifecycle_reservation_state_fingerprint_required": True,
    "exact_active_reservation_fingerprint_required": True,
    "exact_decision_record_fingerprint_required": True,
    "exact_candidate_fingerprint_required": True,
    "fill_source_id_and_sha256_required": True,
    "complete_entry_only": True,
    "partial_fill_support": False,
    "stock_fill_notional_equals_reserved_economic_notional": True,
    "stock_quantity_derived_from_explicit_fill_price_and_reserved_notional": True,
    "stock_funding_semantics_inferred": False,
    "option_terms_required": True,
    "option_contract_count_equals_reserved_terms": True,
    "option_multiplier_equals_reserved_terms": True,
    "option_cash_debit_includes_explicit_entry_fees": True,
    "option_cash_debit_cannot_exceed_reserved_capital": True,
    "option_unspent_reservation_recorded": True,
    "deterministic_fill_fingerprint": True,
    "account_mutation_authority": False,
    "reservation_release_authority": False,
    "open_position_authority": False,
    "provider_read_authority": False,
    "provider_write_authority": False,
    "broker_read_authority": False,
    "broker_write_authority": False,
    "broker_fill_authority": False,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}

LIFECYCLE_FUNDING_TERMS_CONTRACT = {
    "contract_id": "atlas-simulation-lifecycle-funding-terms-v1",
    "scope": "PRODUCT_SIMULATION_LIFECYCLE_FUNDING_TERMS_ONLY",
    "inputs": [
        "atlas-simulation-lifecycle-reservation-account-v1",
        "atlas-simulation-lifecycle-entry-fill-evidence-v1",
    ],
    "exact_lifecycle_reservation_state_fingerprint_required": True,
    "exact_active_reservation_fingerprint_required": True,
    "exact_fill_fingerprint_required": True,
    "stock_long_funding_model": "CASH_ONLY_NO_BORROWING",
    "stock_required_cash_includes_fill_notional_and_entry_fees": True,
    "stock_may_use_reserved_capital_plus_current_unreserved_cash": True,
    "stock_insufficient_current_cash_fails_closed": True,
    "stock_short_supported": False,
    "option_funding_model": "EXACT_RESERVED_LONG_OPTION_DEBIT",
    "option_supplemental_cash_required": False,
    "option_unspent_reservation_preserved": True,
    "projected_cash_after_entry_required": True,
    "prior_realized_history_not_recomputed": True,
    "borrowing_authority": False,
    "account_mutation_authority": False,
    "reservation_release_authority": False,
    "open_position_authority": False,
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


def _fingerprint(payload: dict[str, object]) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


LIFECYCLE_ENTRY_FILL_CONTRACT_FINGERPRINT = _fingerprint(
    LIFECYCLE_ENTRY_FILL_CONTRACT
)
LIFECYCLE_FUNDING_TERMS_CONTRACT_FINGERPRINT = _fingerprint(
    LIFECYCLE_FUNDING_TERMS_CONTRACT
)
