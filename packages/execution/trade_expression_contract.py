from __future__ import annotations

import hashlib
import json


TRADE_EXPRESSION_CONTRACT = {
    "contract_id": "atlas-trade-expression-foundation-v1",
    "scope": "PRODUCT_DECISION_SUPPORT_ONLY",
    "modes": [
        "OPTIONS_ONLY",
        "STOCKS_ONLY",
        "OPTIONS_PREFERRED",
        "STOCKS_PREFERRED",
    ],
    "universal_gate_required": True,
    "uneconomic_trade_can_be_forced_by_mode": False,
    "preferred_mode_allows_materially_superior_alternate": True,
    "material_superiority_ratio_requires_explicit_policy": True,
    "stock_required_evidence": [
        "capital_required",
        "expected_net_value",
        "expected_return_on_capital",
        "probability_profit",
        "expected_gain_dollars",
        "expected_loss_dollars",
        "execution_cost_dollars",
        "liquidity_score",
        "preference_score",
        "executable",
        "risk_budget_ok",
        "scenario_complete",
    ],
    "option_additional_required_evidence": [
        "option_contract_complete",
        "greeks_complete",
        "iv_context_complete",
        "liquidity_context_complete",
        "event_context_complete",
    ],
    "option_factors": [
        "strike",
        "expiration_dte",
        "moneyness",
        "premium",
        "bid_ask",
        "delta",
        "gamma",
        "theta",
        "vega",
        "implied_volatility",
        "iv_change_scenarios",
        "skew_smile",
        "term_structure",
        "rates",
        "dividends",
        "american_early_exercise",
        "volume",
        "open_interest",
        "known_events",
        "break_even",
        "max_loss",
        "scenario_expected_pnl",
    ],
    "model_relative_undervaluation_is_sufficient": False,
    "historical_option_pnl_claimed": False,
    "broker_reads": 0,
    "broker_writes": 0,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
}


def contract_payload() -> dict[str, object]:
    """Return a detached copy of the frozen product-side contract."""

    return json.loads(json.dumps(TRADE_EXPRESSION_CONTRACT))


def contract_fingerprint() -> str:
    raw = json.dumps(
        TRADE_EXPRESSION_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


TRADE_EXPRESSION_CONTRACT_FINGERPRINT = (
    "a9341b7c0e6399165403cfa3d2f33e9f3b2749194ce39d41044a260dbd5fef4c"
)
