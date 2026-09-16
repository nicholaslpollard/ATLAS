from __future__ import annotations

import hashlib
import json


LONG_OPTION_RESERVATION_CONTRACT = {
    "contract_id": "atlas-long-option-capital-risk-reservation-v1",
    "scope": "PRODUCT_SIMULATION_LONG_OPTION_RESERVATION_TERMS_ONLY",
    "input_contracts": [
        "atlas-simulation-decision-record-v1",
        "atlas-option-scenario-economics-adapter-v1",
        "OptionCandidateEvidence",
    ],
    "supported_structure": "LONG_SINGLE_LEG_CALL_OR_PUT_ONLY",
    "requires_selected_option_decision": True,
    "requires_exact_decision_candidate_lineage": True,
    "requires_exact_option_economics_lineage": True,
    "requires_exact_forecast_lineage": True,
    "requires_option_quote_lineage": True,
    "requires_complete_delta": True,
    "entry_cash_debit_source": "accepted_option_economics.entry_cash_debit_dollars",
    "cash_fee_reserve_source": "explicit_nonnegative_input",
    "reserved_capital_source": "entry_cash_debit+cash_fee_reserve",
    "max_loss_cash_source": "reserved_capital",
    "economic_capital_must_cover_reserved_capital": True,
    "premium_at_risk_source": "entry_cash_debit",
    "delta_equivalent_notional_source": (
        "delta*underlying_reference_price*contract_multiplier*contracts"
    ),
    "stock_gross_exposure_mutation": 0,
    "account_mutation_authority": False,
    "fill_simulation_authority": False,
    "realized_pnl_authority": False,
    "mark_to_market_authority": False,
    "provider_reads": 0,
    "provider_writes": 0,
    "broker_reads": 0,
    "broker_writes": 0,
    "order_writes": 0,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_payload() -> dict[str, object]:
    return json.loads(json.dumps(LONG_OPTION_RESERVATION_CONTRACT))


def contract_fingerprint() -> str:
    raw = json.dumps(
        LONG_OPTION_RESERVATION_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT = (
    "26835cbab3e551f0f7514e8537d823cb23d5db1f440362d20b1ba7493ff6aa64"
)
