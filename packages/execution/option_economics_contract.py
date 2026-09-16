from __future__ import annotations

import hashlib
import json


OPTION_ECONOMICS_CONTRACT = {
    "contract_id": "atlas-option-scenario-economics-adapter-v1",
    "scope": "PRODUCT_SIMULATION_DECISION_SUPPORT_ONLY",
    "input_forecast_contract": "atlas-underlying-move-time-forecast-v1",
    "input_option_evidence": "OptionCandidateEvidence",
    "option_evidence_fingerprint_required": True,
    "candidate_identifier_includes_option_evidence_fingerprint": True,
    "output_candidate_kind": "OPTION",
    "supported_structure": "LONG_SINGLE_LEG_CALL_OR_PUT_ONLY",
    "requires_available_directional_forecast": True,
    "neutral_forecast_action": "NO_CANDIDATE",
    "unavailable_forecast_action": "NO_CANDIDATE",
    "direction_alignment": {
        "BULLISH": "call",
        "BEARISH": "put",
    },
    "entry_reference": "CURRENT_QUOTE_MID",
    "entry_execution": "ASK_DEBIT",
    "entry_cash_debit_source": "ask*contract_multiplier*contracts",
    "entry_spread_cost_source": "(ask-mid)*contract_multiplier*contracts",
    "scenario_outputs_are_explicit": True,
    "scenario_output_fields": [
        "expected_terminal_premium_per_share",
        "favorable_terminal_premium_per_share",
        "adverse_terminal_premium_per_share",
        "model_probability_profit",
        "scenario_model_id",
        "scenario_model_fingerprint",
        "scenario_forecast_fingerprint",
    ],
    "scenario_price_order": "adverse<=expected<=favorable",
    "greek_context": [
        "delta_from_option_evidence",
        "gamma",
        "theta_per_calendar_day",
        "vega_per_one_iv_fraction",
    ],
    "iv_context": [
        "current_implied_volatility_from_option_evidence",
        "iv_percentile",
        "skew_signal",
        "term_structure_signal",
    ],
    "macro_context": [
        "risk_free_rate",
        "dividend_yield",
    ],
    "event_context": [
        "event_within_horizon",
        "event_risk_acceptable",
        "event_context_fingerprint",
    ],
    "liquidity_context": [
        "bid",
        "ask",
        "spread_to_mid",
        "open_interest",
        "volume",
        "liquidity_score",
    ],
    "position_inputs": [
        "contracts",
        "contract_multiplier",
        "capital_required_dollars",
    ],
    "cost_inputs": [
        "entry_spread_cost_derived_from_quote",
        "exit_slippage_dollars",
        "round_trip_commission_dollars",
        "round_trip_fees_dollars",
    ],
    "expected_gross_pnl_source": (
        "(expected_terminal_premium-current_mid)*contract_multiplier*contracts"
    ),
    "expected_net_value_source": "expected_gross_pnl-all_in_expression_cost",
    "expected_gain_source": (
        "max((favorable_terminal_premium-current_mid)*multiplier*contracts,0)"
    ),
    "expected_loss_source": (
        "max((current_mid-adverse_terminal_premium)*multiplier*contracts,0)"
    ),
    "probability_profit_source": "explicit_model_probability_profit_input",
    "preference_score_source": "expected_return_on_capital",
    "capital_required_is_economic_denominator_only": True,
    "capital_required_floor": "entry_cash_debit",
    "capital_required_is_simulator_reservation_authority": False,
    "model_reference_premium_optional": True,
    "model_relative_undervalued_rule": "model_reference_premium_per_share>ask",
    "model_relative_undervalued_is_evidence_only": True,
    "historical_option_pnl_claimed": False,
    "historical_option_source_required_for_historical_pnl": True,
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
    return json.loads(json.dumps(OPTION_ECONOMICS_CONTRACT))


def contract_fingerprint() -> str:
    raw = json.dumps(
        OPTION_ECONOMICS_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


OPTION_ECONOMICS_CONTRACT_FINGERPRINT = (
    "798b05ab3867058865301c35a52491ee9a8cde82c6f1b019b8d27bae34e88178"
)
