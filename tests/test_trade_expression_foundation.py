from __future__ import annotations

import pytest

from packages.execution.trade_expression import (
    ActionabilityPolicy,
    EconomicCandidate,
    InstrumentKind,
    SelectionKind,
    TradeExpressionError,
    TradeExpressionMode,
    evaluate_actionability,
    select_trade_expression,
)
from packages.execution.trade_expression_contract import (
    TRADE_EXPRESSION_CONTRACT,
    TRADE_EXPRESSION_CONTRACT_FINGERPRINT,
    contract_fingerprint,
)


def _policy(*, material_superiority_ratio: float = 1.5) -> ActionabilityPolicy:
    return ActionabilityPolicy(
        min_expected_net_value=5.0,
        min_expected_return_on_capital=0.01,
        min_probability_profit=0.52,
        max_expected_loss_to_gain_ratio=1.0,
        max_execution_cost_to_expected_gain_ratio=0.20,
        min_liquidity_score=0.60,
        material_superiority_ratio=material_superiority_ratio,
    )


def _stock(
    *,
    identifier: str = "XYZ-STOCK",
    expected_net_value: float = 20.0,
    preference_score: float = 1.0,
) -> EconomicCandidate:
    return EconomicCandidate(
        identifier=identifier,
        kind=InstrumentKind.STOCK,
        capital_required=1_000.0,
        expected_net_value=expected_net_value,
        expected_return_on_capital=0.02,
        probability_profit=0.60,
        expected_gain_dollars=80.0,
        expected_loss_dollars=50.0,
        execution_cost_dollars=4.0,
        liquidity_score=0.95,
        preference_score=preference_score,
        executable=True,
        risk_budget_ok=True,
        scenario_complete=True,
    )


def _option(
    *,
    identifier: str = "XYZ-20270115-C-100",
    expected_net_value: float = 25.0,
    preference_score: float = 1.1,
    complete: bool = True,
    model_relative_undervalued: bool = False,
) -> EconomicCandidate:
    return EconomicCandidate(
        identifier=identifier,
        kind=InstrumentKind.OPTION,
        capital_required=400.0,
        expected_net_value=expected_net_value,
        expected_return_on_capital=0.0625,
        probability_profit=0.58,
        expected_gain_dollars=100.0,
        expected_loss_dollars=60.0,
        execution_cost_dollars=8.0,
        liquidity_score=0.85,
        preference_score=preference_score,
        executable=True,
        risk_budget_ok=True,
        scenario_complete=True,
        option_contract_complete=complete,
        greeks_complete=complete,
        iv_context_complete=complete,
        liquidity_context_complete=complete,
        event_context_complete=complete,
        model_relative_undervalued=model_relative_undervalued,
    )


def test_contract_fingerprint_and_authority_are_frozen() -> None:
    assert contract_fingerprint() == TRADE_EXPRESSION_CONTRACT_FINGERPRINT
    assert TRADE_EXPRESSION_CONTRACT_FINGERPRINT == (
        "a9341b7c0e6399165403cfa3d2f33e9f3b2749194ce39d41044a260dbd5fef4c"
    )
    assert TRADE_EXPRESSION_CONTRACT["universal_gate_required"] is True
    assert TRADE_EXPRESSION_CONTRACT["uneconomic_trade_can_be_forced_by_mode"] is False
    assert TRADE_EXPRESSION_CONTRACT["model_relative_undervaluation_is_sufficient"] is False
    assert TRADE_EXPRESSION_CONTRACT["broker_reads"] == 0
    assert TRADE_EXPRESSION_CONTRACT["broker_writes"] == 0
    assert TRADE_EXPRESSION_CONTRACT["paper_authority"] is False
    assert TRADE_EXPRESSION_CONTRACT["live_authority"] is False
    assert TRADE_EXPRESSION_CONTRACT["promotion_authority"] is False


def test_universal_gate_accepts_economic_stock() -> None:
    evaluation = evaluate_actionability(_stock(), _policy())
    assert evaluation.eligible is True
    assert evaluation.reason_codes == ("ECONOMIC_GATE_ACCEPTED",)


def test_options_only_cannot_force_bad_option_or_fall_back_to_stock() -> None:
    bad_option = _option(expected_net_value=1.0)
    decision = select_trade_expression(
        mode=TradeExpressionMode.OPTIONS_ONLY,
        policy=_policy(),
        stock_candidate=_stock(),
        option_candidates=(bad_option,),
    )
    assert decision.selection_kind == SelectionKind.ABSTAIN
    assert decision.chosen_candidate is None
    assert decision.stock_evaluation is None
    assert decision.option_evaluations[0].eligible is False
    assert "EXPECTED_NET_VALUE_BELOW_POLICY" in decision.option_evaluations[0].reason_codes


def test_stocks_only_ignores_options_and_abstains_when_stock_fails() -> None:
    bad_stock = _stock(expected_net_value=1.0)
    decision = select_trade_expression(
        mode=TradeExpressionMode.STOCKS_ONLY,
        policy=_policy(),
        stock_candidate=bad_stock,
        option_candidates=(_option(),),
    )
    assert decision.selection_kind == SelectionKind.ABSTAIN
    assert decision.option_evaluations == ()
    assert decision.stock_evaluation is not None
    assert decision.stock_evaluation.eligible is False


def test_options_preferred_uses_option_inside_materiality_band() -> None:
    decision = select_trade_expression(
        mode=TradeExpressionMode.OPTIONS_PREFERRED,
        policy=_policy(material_superiority_ratio=1.5),
        stock_candidate=_stock(preference_score=1.4),
        option_candidates=(_option(preference_score=1.0),),
    )
    assert decision.selection_kind == SelectionKind.OPTION
    assert decision.chosen_identifier == "XYZ-20270115-C-100"
    assert "PREFERRED_EXPRESSION_ACCEPTED_WITHIN_MATERIALITY_BAND" in decision.reason_codes


def test_options_preferred_allows_materially_superior_stock_override() -> None:
    decision = select_trade_expression(
        mode=TradeExpressionMode.OPTIONS_PREFERRED,
        policy=_policy(material_superiority_ratio=1.5),
        stock_candidate=_stock(preference_score=1.6),
        option_candidates=(_option(preference_score=1.0),),
    )
    assert decision.selection_kind == SelectionKind.STOCK
    assert "ALTERNATE_EXPRESSION_MATERIALLY_SUPERIOR" in decision.reason_codes


def test_stocks_preferred_allows_materially_superior_option_override() -> None:
    decision = select_trade_expression(
        mode=TradeExpressionMode.STOCKS_PREFERRED,
        policy=_policy(material_superiority_ratio=1.5),
        stock_candidate=_stock(preference_score=1.0),
        option_candidates=(_option(preference_score=1.6),),
    )
    assert decision.selection_kind == SelectionKind.OPTION
    assert "ALTERNATE_EXPRESSION_MATERIALLY_SUPERIOR" in decision.reason_codes


def test_model_relative_undervaluation_cannot_rescue_incomplete_option() -> None:
    option = _option(complete=False, model_relative_undervalued=True)
    evaluation = evaluate_actionability(option, _policy())
    assert evaluation.eligible is False
    assert "MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY" in evaluation.reason_codes
    assert "OPTION_CONTRACT_INCOMPLETE" in evaluation.reason_codes
    assert "OPTION_GREEKS_INCOMPLETE" in evaluation.reason_codes
    assert "OPTION_IV_CONTEXT_INCOMPLETE" in evaluation.reason_codes


def test_model_relative_undervaluation_is_nonblocking_when_full_economics_pass() -> None:
    option = _option(complete=True, model_relative_undervalued=True)
    evaluation = evaluate_actionability(option, _policy())
    assert evaluation.eligible is True
    assert "MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY" in evaluation.reason_codes
    assert "ECONOMIC_GATE_ACCEPTED" in evaluation.reason_codes


def test_best_option_is_deterministic_by_score_then_identifier() -> None:
    high_b = _option(identifier="B", preference_score=2.0)
    high_a = _option(identifier="A", preference_score=2.0)
    lower = _option(identifier="C", preference_score=1.5)
    decision = select_trade_expression(
        mode=TradeExpressionMode.OPTIONS_ONLY,
        policy=_policy(),
        stock_candidate=None,
        option_candidates=(high_b, lower, high_a),
    )
    assert decision.selection_kind == SelectionKind.OPTION
    assert decision.chosen_identifier == "A"


def test_execution_cost_can_fail_economic_gate_even_with_positive_expected_value() -> None:
    stock = EconomicCandidate(
        identifier="COSTLY",
        kind=InstrumentKind.STOCK,
        capital_required=1_000.0,
        expected_net_value=20.0,
        expected_return_on_capital=0.02,
        probability_profit=0.60,
        expected_gain_dollars=40.0,
        expected_loss_dollars=20.0,
        execution_cost_dollars=20.0,
        liquidity_score=0.95,
        preference_score=1.0,
        executable=True,
        risk_budget_ok=True,
        scenario_complete=True,
    )
    evaluation = evaluate_actionability(stock, _policy())
    assert evaluation.eligible is False
    assert "EXECUTION_COST_TO_GAIN_ABOVE_POLICY" in evaluation.reason_codes


def test_preferred_mode_falls_back_only_to_economically_accepted_alternate() -> None:
    incomplete_option = _option(complete=False)
    decision = select_trade_expression(
        mode=TradeExpressionMode.OPTIONS_PREFERRED,
        policy=_policy(),
        stock_candidate=_stock(),
        option_candidates=(incomplete_option,),
    )
    assert decision.selection_kind == SelectionKind.STOCK
    assert "PREFERRED_EXPRESSION_UNAVAILABLE_USE_ACCEPTABLE_ALTERNATE" in decision.reason_codes


def test_no_candidates_means_abstain() -> None:
    decision = select_trade_expression(
        mode=TradeExpressionMode.STOCKS_PREFERRED,
        policy=_policy(),
        stock_candidate=None,
        option_candidates=(),
    )
    assert decision.selection_kind == SelectionKind.ABSTAIN
    assert decision.reason_codes[-1] == "ABSTAIN"


def test_material_superiority_ratio_requires_explicit_valid_value() -> None:
    with pytest.raises(TradeExpressionError):
        _policy(material_superiority_ratio=0.99)
