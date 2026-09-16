from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


class TradeExpressionError(ValueError):
    pass


class InstrumentKind(str, Enum):
    STOCK = "STOCK"
    OPTION = "OPTION"


class TradeExpressionMode(str, Enum):
    OPTIONS_ONLY = "OPTIONS_ONLY"
    STOCKS_ONLY = "STOCKS_ONLY"
    OPTIONS_PREFERRED = "OPTIONS_PREFERRED"
    STOCKS_PREFERRED = "STOCKS_PREFERRED"


class SelectionKind(str, Enum):
    STOCK = "STOCK"
    OPTION = "OPTION"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class ActionabilityPolicy:
    """Explicit product policy for the universal economic gate.

    ATLAS intentionally has no hidden production defaults here. A caller must
    supply the economic thresholds and preference override ratio explicitly.
    """

    min_expected_net_value: float
    min_expected_return_on_capital: float
    min_probability_profit: float
    max_expected_loss_to_gain_ratio: float
    max_execution_cost_to_expected_gain_ratio: float
    min_liquidity_score: float
    material_superiority_ratio: float

    def __post_init__(self) -> None:
        finite = (
            self.min_expected_net_value,
            self.min_expected_return_on_capital,
            self.min_probability_profit,
            self.max_expected_loss_to_gain_ratio,
            self.max_execution_cost_to_expected_gain_ratio,
            self.min_liquidity_score,
            self.material_superiority_ratio,
        )
        if not all(math.isfinite(float(value)) for value in finite):
            raise TradeExpressionError("actionability policy contains non-finite values")
        if self.min_expected_net_value < 0.0:
            raise TradeExpressionError("minimum expected net value cannot be negative")
        if self.min_expected_return_on_capital < 0.0:
            raise TradeExpressionError("minimum expected return on capital cannot be negative")
        if not 0.0 <= self.min_probability_profit <= 1.0:
            raise TradeExpressionError("minimum probability of profit must be in [0, 1]")
        if self.max_expected_loss_to_gain_ratio < 0.0:
            raise TradeExpressionError("maximum expected loss-to-gain ratio cannot be negative")
        if self.max_execution_cost_to_expected_gain_ratio < 0.0:
            raise TradeExpressionError("maximum execution-cost ratio cannot be negative")
        if not 0.0 <= self.min_liquidity_score <= 1.0:
            raise TradeExpressionError("minimum liquidity score must be in [0, 1]")
        if self.material_superiority_ratio < 1.0:
            raise TradeExpressionError("material-superiority ratio must be at least 1.0")


@dataclass(frozen=True)
class EconomicCandidate:
    """Instrument-level economic evidence produced upstream of execution.

    The object carries decision evidence only. It is not an order, execution
    intent, broker instruction, or promotion record.
    """

    identifier: str
    kind: InstrumentKind
    capital_required: float
    expected_net_value: float
    expected_return_on_capital: float
    probability_profit: float
    expected_gain_dollars: float
    expected_loss_dollars: float
    execution_cost_dollars: float
    liquidity_score: float
    preference_score: float
    executable: bool
    risk_budget_ok: bool
    scenario_complete: bool
    option_contract_complete: bool = False
    greeks_complete: bool = False
    iv_context_complete: bool = False
    liquidity_context_complete: bool = False
    event_context_complete: bool = False
    model_relative_undervalued: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", InstrumentKind(self.kind))
        if not self.identifier.strip():
            raise TradeExpressionError("candidate identifier cannot be blank")
        numeric = (
            self.capital_required,
            self.expected_net_value,
            self.expected_return_on_capital,
            self.probability_profit,
            self.expected_gain_dollars,
            self.expected_loss_dollars,
            self.execution_cost_dollars,
            self.liquidity_score,
            self.preference_score,
        )
        if not all(math.isfinite(float(value)) for value in numeric):
            raise TradeExpressionError("candidate contains non-finite economic evidence")
        if self.capital_required <= 0.0:
            raise TradeExpressionError("candidate capital requirement must be positive")
        if not 0.0 <= self.probability_profit <= 1.0:
            raise TradeExpressionError("candidate probability of profit must be in [0, 1]")
        if self.expected_gain_dollars < 0.0 or self.expected_loss_dollars < 0.0:
            raise TradeExpressionError("expected gain/loss magnitudes cannot be negative")
        if self.execution_cost_dollars < 0.0:
            raise TradeExpressionError("execution cost cannot be negative")
        if not 0.0 <= self.liquidity_score <= 1.0:
            raise TradeExpressionError("candidate liquidity score must be in [0, 1]")


@dataclass(frozen=True)
class GateEvaluation:
    candidate: EconomicCandidate
    eligible: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class TradeExpressionDecision:
    mode: TradeExpressionMode
    selection_kind: SelectionKind
    chosen_identifier: str | None
    chosen_candidate: EconomicCandidate | None
    stock_evaluation: GateEvaluation | None
    option_evaluations: tuple[GateEvaluation, ...]
    reason_codes: tuple[str, ...]


_OPTION_COMPLETENESS_FIELDS = (
    ("option_contract_complete", "OPTION_CONTRACT_INCOMPLETE"),
    ("greeks_complete", "OPTION_GREEKS_INCOMPLETE"),
    ("iv_context_complete", "OPTION_IV_CONTEXT_INCOMPLETE"),
    ("liquidity_context_complete", "OPTION_LIQUIDITY_CONTEXT_INCOMPLETE"),
    ("event_context_complete", "OPTION_EVENT_CONTEXT_INCOMPLETE"),
)


def evaluate_actionability(
    candidate: EconomicCandidate,
    policy: ActionabilityPolicy,
) -> GateEvaluation:
    """Apply the universal economic gate to one stock or option expression."""

    reasons: list[str] = []
    if not candidate.executable:
        reasons.append("NOT_EXECUTABLE")
    if not candidate.risk_budget_ok:
        reasons.append("RISK_BUDGET_REJECTED")
    if not candidate.scenario_complete:
        reasons.append("SCENARIO_EVIDENCE_INCOMPLETE")
    if candidate.expected_net_value < policy.min_expected_net_value:
        reasons.append("EXPECTED_NET_VALUE_BELOW_POLICY")
    if candidate.expected_return_on_capital < policy.min_expected_return_on_capital:
        reasons.append("RETURN_ON_CAPITAL_BELOW_POLICY")
    if candidate.probability_profit < policy.min_probability_profit:
        reasons.append("PROBABILITY_OF_PROFIT_BELOW_POLICY")
    if candidate.liquidity_score < policy.min_liquidity_score:
        reasons.append("LIQUIDITY_BELOW_POLICY")
    if candidate.expected_gain_dollars <= 0.0:
        reasons.append("NONPOSITIVE_EXPECTED_GAIN")
    else:
        loss_ratio = candidate.expected_loss_dollars / candidate.expected_gain_dollars
        if loss_ratio > policy.max_expected_loss_to_gain_ratio:
            reasons.append("EXPECTED_LOSS_TO_GAIN_ABOVE_POLICY")
        cost_ratio = candidate.execution_cost_dollars / candidate.expected_gain_dollars
        if cost_ratio > policy.max_execution_cost_to_expected_gain_ratio:
            reasons.append("EXECUTION_COST_TO_GAIN_ABOVE_POLICY")
    if candidate.preference_score <= 0.0:
        reasons.append("NONPOSITIVE_PREFERENCE_SCORE")

    if candidate.kind == InstrumentKind.OPTION:
        for field, reason in _OPTION_COMPLETENESS_FIELDS:
            if not bool(getattr(candidate, field)):
                reasons.append(reason)
        if candidate.model_relative_undervalued:
            reasons.append("MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY")

    blocking = tuple(
        reason
        for reason in reasons
        if reason != "MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY"
    )
    if not blocking:
        reasons.append("ECONOMIC_GATE_ACCEPTED")
    return GateEvaluation(
        candidate=candidate,
        eligible=not blocking,
        reason_codes=tuple(reasons),
    )


def _best_eligible(evaluations: Iterable[GateEvaluation]) -> GateEvaluation | None:
    eligible = [item for item in evaluations if item.eligible]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda item: (-item.candidate.preference_score, item.candidate.identifier),
    )[0]


def _choose_preferred(
    *,
    preferred: GateEvaluation | None,
    alternate: GateEvaluation | None,
    policy: ActionabilityPolicy,
) -> tuple[GateEvaluation | None, tuple[str, ...]]:
    if preferred is None and alternate is None:
        return None, ("NO_ECONOMICALLY_ACTIONABLE_EXPRESSION",)
    if preferred is None:
        return alternate, ("PREFERRED_EXPRESSION_UNAVAILABLE_USE_ACCEPTABLE_ALTERNATE",)
    if alternate is None:
        return preferred, ("PREFERRED_EXPRESSION_ACCEPTED",)

    preferred_score = preferred.candidate.preference_score
    alternate_score = alternate.candidate.preference_score
    if alternate_score >= preferred_score * policy.material_superiority_ratio:
        return alternate, ("ALTERNATE_EXPRESSION_MATERIALLY_SUPERIOR",)
    return preferred, ("PREFERRED_EXPRESSION_ACCEPTED_WITHIN_MATERIALITY_BAND",)


def select_trade_expression(
    *,
    mode: TradeExpressionMode,
    policy: ActionabilityPolicy,
    stock_candidate: EconomicCandidate | None,
    option_candidates: Sequence[EconomicCandidate] = (),
) -> TradeExpressionDecision:
    """Choose stock, option, or abstention without creating execution authority."""

    mode = TradeExpressionMode(mode)
    if stock_candidate is not None and stock_candidate.kind != InstrumentKind.STOCK:
        raise TradeExpressionError("stock_candidate must be a STOCK candidate")
    if any(candidate.kind != InstrumentKind.OPTION for candidate in option_candidates):
        raise TradeExpressionError("option_candidates must contain only OPTION candidates")

    stock_eval: GateEvaluation | None = None
    option_evals: tuple[GateEvaluation, ...] = ()

    if mode != TradeExpressionMode.OPTIONS_ONLY and stock_candidate is not None:
        stock_eval = evaluate_actionability(stock_candidate, policy)
    if mode != TradeExpressionMode.STOCKS_ONLY:
        option_evals = tuple(
            evaluate_actionability(candidate, policy)
            for candidate in option_candidates
        )

    best_stock = stock_eval if stock_eval is not None and stock_eval.eligible else None
    best_option = _best_eligible(option_evals)

    chosen: GateEvaluation | None
    decision_reasons: tuple[str, ...]
    if mode == TradeExpressionMode.STOCKS_ONLY:
        chosen = best_stock
        decision_reasons = (
            "STOCKS_ONLY_ACCEPTED" if chosen else "STOCKS_ONLY_NO_ACCEPTABLE_STOCK",
        )
    elif mode == TradeExpressionMode.OPTIONS_ONLY:
        chosen = best_option
        decision_reasons = (
            "OPTIONS_ONLY_ACCEPTED" if chosen else "OPTIONS_ONLY_NO_ACCEPTABLE_OPTION",
        )
    elif mode == TradeExpressionMode.OPTIONS_PREFERRED:
        chosen, decision_reasons = _choose_preferred(
            preferred=best_option,
            alternate=best_stock,
            policy=policy,
        )
    elif mode == TradeExpressionMode.STOCKS_PREFERRED:
        chosen, decision_reasons = _choose_preferred(
            preferred=best_stock,
            alternate=best_option,
            policy=policy,
        )
    else:  # pragma: no cover - exhaustive enum guard
        raise TradeExpressionError(f"unsupported trade-expression mode: {mode}")

    if chosen is None:
        return TradeExpressionDecision(
            mode=mode,
            selection_kind=SelectionKind.ABSTAIN,
            chosen_identifier=None,
            chosen_candidate=None,
            stock_evaluation=stock_eval,
            option_evaluations=option_evals,
            reason_codes=decision_reasons + ("ABSTAIN",),
        )

    kind = (
        SelectionKind.STOCK
        if chosen.candidate.kind == InstrumentKind.STOCK
        else SelectionKind.OPTION
    )
    return TradeExpressionDecision(
        mode=mode,
        selection_kind=kind,
        chosen_identifier=chosen.candidate.identifier,
        chosen_candidate=chosen.candidate,
        stock_evaluation=stock_eval,
        option_evaluations=option_evals,
        reason_codes=decision_reasons + ("NO_BROKER_OR_EXECUTION_AUTHORITY_GRANTED",),
    )
