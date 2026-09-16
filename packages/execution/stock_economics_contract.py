from __future__ import annotations

import hashlib
import json


STOCK_ECONOMICS_CONTRACT = {
    "contract_id": "atlas-stock-economics-adapter-v1",
    "scope": "PRODUCT_SIMULATION_DECISION_SUPPORT_ONLY",
    "input_forecast_contract": "atlas-underlying-move-time-forecast-v1",
    "output_candidate_kind": "STOCK",
    "requires_available_directional_forecast": True,
    "neutral_forecast_action": "NO_CANDIDATE",
    "unavailable_forecast_action": "NO_CANDIDATE",
    "position_notional_explicit": True,
    "capital_required_explicit": True,
    "leverage_or_margin_assumption_hidden": False,
    "cost_inputs": [
        "entry_slippage_bps",
        "exit_slippage_bps",
        "round_trip_commission_dollars",
        "round_trip_fees_dollars",
        "horizon_borrow_cost_dollars",
        "horizon_financing_cost_dollars",
    ],
    "risk_inputs": [
        "risk_budget_ok",
        "executable",
        "liquidity_score",
        "net_probability_profit",
        "shortable_if_bearish",
    ],
    "expected_gross_pnl_source": (
        "direction_adjusted_mean_signed_underlying_return_x_position_notional"
    ),
    "expected_gain_dollars_source": "mean_mfe_x_position_notional",
    "expected_loss_dollars_source": "mean_mae_x_position_notional",
    "probability_profit_source": "explicit_net_probability_profit_input",
    "net_profit_probability_cannot_exceed_gross_directional_sign_probability": True,
    "preference_score_source": "expected_return_on_capital",
    "execution_cost_is_all_in_expression_cost": True,
    "execution_cost_is_nonnegative": True,
    "historical_option_pnl_claimed": False,
    "option_candidate_created": False,
    "broker_reads": 0,
    "broker_writes": 0,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
}


def contract_payload() -> dict[str, object]:
    return json.loads(json.dumps(STOCK_ECONOMICS_CONTRACT))


def contract_fingerprint() -> str:
    raw = json.dumps(
        STOCK_ECONOMICS_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


STOCK_ECONOMICS_CONTRACT_FINGERPRINT = (
    "68f4b7ca0e4f86f07bf20afa1c7e6e5aa9708c081db44cc3c18f8123e711f924"
)
