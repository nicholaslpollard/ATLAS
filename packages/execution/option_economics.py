from __future__ import annotations

import math
import re
from dataclasses import dataclass

from packages.execution.option_economics_contract import (
    OPTION_ECONOMICS_CONTRACT,
    OPTION_ECONOMICS_CONTRACT_FINGERPRINT,
)
from packages.execution.trade_expression import EconomicCandidate, InstrumentKind
from packages.schemas.case_file import OptionCandidateEvidence
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    UnderlyingMoveTimeForecast,
    forecast_fingerprint,
)


OPTION_ECONOMICS_CONTRACT_VERSION = str(OPTION_ECONOMICS_CONTRACT["contract_id"])
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class OptionEconomicsError(ValueError):
    pass


@dataclass(frozen=True)
class OptionEconomicsInputs:
    """Explicit scenario-model evidence and economics for one long option expression.

    Scenario terminal premiums are outputs of an upstream, versioned option scenario
    model bound to the supplied underlying forecast. This adapter does not invent
    an option-return history or infer a pricing distribution from sparse Greeks.
    """

    contracts: int
    contract_multiplier: float
    capital_required_dollars: float
    holding_period_calendar_days: float

    expected_terminal_premium_per_share: float
    favorable_terminal_premium_per_share: float
    adverse_terminal_premium_per_share: float
    model_probability_profit: float
    scenario_model_id: str
    scenario_model_fingerprint: str
    scenario_forecast_fingerprint: str

    gamma: float | None
    theta_per_calendar_day: float | None
    vega_per_one_iv_fraction: float | None
    iv_percentile: float | None
    skew_signal: float | None
    term_structure_signal: float | None
    risk_free_rate: float | None
    dividend_yield: float | None

    event_within_horizon: bool
    event_risk_acceptable: bool
    event_context_fingerprint: str

    liquidity_score: float
    exit_slippage_dollars: float
    round_trip_commission_dollars: float
    round_trip_fees_dollars: float
    executable: bool
    risk_budget_ok: bool

    model_reference_premium_per_share: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.contracts, bool) or not isinstance(self.contracts, int) or self.contracts < 1:
            raise OptionEconomicsError("contracts must be a positive integer")

        required_numeric = (
            self.contract_multiplier,
            self.capital_required_dollars,
            self.holding_period_calendar_days,
            self.expected_terminal_premium_per_share,
            self.favorable_terminal_premium_per_share,
            self.adverse_terminal_premium_per_share,
            self.model_probability_profit,
            self.liquidity_score,
            self.exit_slippage_dollars,
            self.round_trip_commission_dollars,
            self.round_trip_fees_dollars,
        )
        if not all(math.isfinite(float(value)) for value in required_numeric):
            raise OptionEconomicsError("option economics inputs contain non-finite required values")
        if self.contract_multiplier <= 0.0:
            raise OptionEconomicsError("contract multiplier must be positive")
        if self.capital_required_dollars <= 0.0:
            raise OptionEconomicsError("capital required must be positive")
        if self.holding_period_calendar_days <= 0.0:
            raise OptionEconomicsError("holding period must be positive")

        premiums = (
            self.expected_terminal_premium_per_share,
            self.favorable_terminal_premium_per_share,
            self.adverse_terminal_premium_per_share,
        )
        if any(value < 0.0 for value in premiums):
            raise OptionEconomicsError("scenario terminal premiums cannot be negative")
        if not (
            self.adverse_terminal_premium_per_share
            <= self.expected_terminal_premium_per_share
            <= self.favorable_terminal_premium_per_share
        ):
            raise OptionEconomicsError(
                "scenario terminal premiums must satisfy adverse <= expected <= favorable"
            )

        if not 0.0 <= self.model_probability_profit <= 1.0:
            raise OptionEconomicsError("model probability of profit must be in [0, 1]")
        if not 0.0 <= self.liquidity_score <= 1.0:
            raise OptionEconomicsError("liquidity score must be in [0, 1]")

        costs = (
            self.exit_slippage_dollars,
            self.round_trip_commission_dollars,
            self.round_trip_fees_dollars,
        )
        if any(value < 0.0 for value in costs):
            raise OptionEconomicsError("option expression costs cannot be negative")

        optional_finite = (
            self.gamma,
            self.theta_per_calendar_day,
            self.vega_per_one_iv_fraction,
            self.iv_percentile,
            self.skew_signal,
            self.term_structure_signal,
            self.risk_free_rate,
            self.dividend_yield,
            self.model_reference_premium_per_share,
        )
        if any(value is not None and not math.isfinite(float(value)) for value in optional_finite):
            raise OptionEconomicsError("option context contains non-finite values")
        if self.gamma is not None and self.gamma < 0.0:
            raise OptionEconomicsError("long-option gamma cannot be negative")
        if self.vega_per_one_iv_fraction is not None and self.vega_per_one_iv_fraction < 0.0:
            raise OptionEconomicsError("long-option vega cannot be negative")
        if self.iv_percentile is not None and not 0.0 <= self.iv_percentile <= 1.0:
            raise OptionEconomicsError("IV percentile must be in [0, 1]")
        if self.dividend_yield is not None and self.dividend_yield < 0.0:
            raise OptionEconomicsError("dividend yield cannot be negative")
        if (
            self.model_reference_premium_per_share is not None
            and self.model_reference_premium_per_share < 0.0
        ):
            raise OptionEconomicsError("model reference premium cannot be negative")

        if not str(self.scenario_model_id).strip():
            raise OptionEconomicsError("scenario model id cannot be blank")
        for name in (
            "scenario_model_fingerprint",
            "scenario_forecast_fingerprint",
            "event_context_fingerprint",
        ):
            value = str(getattr(self, name))
            if _HEX64.fullmatch(value) is None:
                raise OptionEconomicsError(f"{name} must be a lowercase SHA-256 hex digest")

        for name in (
            "event_within_horizon",
            "event_risk_acceptable",
            "executable",
            "risk_budget_ok",
        ):
            if not isinstance(getattr(self, name), bool):
                raise OptionEconomicsError(f"{name} must be boolean")


@dataclass(frozen=True)
class OptionEconomicsResult:
    contract_version: str
    contract_fingerprint: str
    source_forecast_fingerprint: str
    option_contract_ticker: str
    direction: DiscoveryDirection
    candidate: EconomicCandidate | None

    contracts: int
    contract_multiplier: float
    capital_required_dollars: float
    entry_mid_per_share: float
    entry_ask_per_share: float
    entry_spread_cost_dollars: float | None
    expected_terminal_premium_per_share: float
    favorable_terminal_premium_per_share: float
    adverse_terminal_premium_per_share: float
    expected_gross_pnl_dollars: float | None
    all_in_expression_cost_dollars: float | None
    expected_net_value_dollars: float | None
    expected_return_on_capital: float | None
    expected_gain_dollars: float | None
    expected_loss_dollars: float | None

    option_contract_complete: bool
    greeks_complete: bool
    iv_context_complete: bool
    liquidity_context_complete: bool
    event_context_complete: bool
    macro_context_complete: bool
    scenario_complete: bool
    model_relative_undervalued: bool
    reason_codes: tuple[str, ...]


def _empty_result(
    *,
    forecast: UnderlyingMoveTimeForecast,
    option: OptionCandidateEvidence,
    inputs: OptionEconomicsInputs,
    reason: str,
) -> OptionEconomicsResult:
    return OptionEconomicsResult(
        contract_version=OPTION_ECONOMICS_CONTRACT_VERSION,
        contract_fingerprint=OPTION_ECONOMICS_CONTRACT_FINGERPRINT,
        source_forecast_fingerprint=forecast_fingerprint(forecast),
        option_contract_ticker=option.contract_ticker,
        direction=forecast.direction,
        candidate=None,
        contracts=inputs.contracts,
        contract_multiplier=inputs.contract_multiplier,
        capital_required_dollars=inputs.capital_required_dollars,
        entry_mid_per_share=option.mid,
        entry_ask_per_share=option.ask,
        entry_spread_cost_dollars=None,
        expected_terminal_premium_per_share=inputs.expected_terminal_premium_per_share,
        favorable_terminal_premium_per_share=inputs.favorable_terminal_premium_per_share,
        adverse_terminal_premium_per_share=inputs.adverse_terminal_premium_per_share,
        expected_gross_pnl_dollars=None,
        all_in_expression_cost_dollars=None,
        expected_net_value_dollars=None,
        expected_return_on_capital=None,
        expected_gain_dollars=None,
        expected_loss_dollars=None,
        option_contract_complete=True,
        greeks_complete=False,
        iv_context_complete=False,
        liquidity_context_complete=False,
        event_context_complete=True,
        macro_context_complete=False,
        scenario_complete=False,
        model_relative_undervalued=False,
        reason_codes=(reason, "NO_OPTION_ECONOMIC_CANDIDATE"),
    )


def build_option_economic_candidate(
    *,
    forecast: UnderlyingMoveTimeForecast,
    option: OptionCandidateEvidence,
    inputs: OptionEconomicsInputs,
) -> OptionEconomicsResult:
    """Translate explicit option scenario outputs into one EconomicCandidate.

    The adapter binds model outputs to the exact underlying forecast and current
    contract evidence. It performs deterministic economics only. It does not read
    providers/brokers, create orders, claim historical option P&L, reserve option
    capital in the simulator, or grant PAPER/LIVE/promotion authority.
    """

    source_forecast_fingerprint = forecast_fingerprint(forecast)
    if inputs.scenario_forecast_fingerprint != source_forecast_fingerprint:
        raise OptionEconomicsError(
            "scenario forecast fingerprint does not match the supplied underlying forecast"
        )
    if inputs.holding_period_calendar_days > float(option.dte):
        raise OptionEconomicsError("holding period cannot exceed option DTE")

    if forecast.availability != ForecastAvailability.AVAILABLE:
        return _empty_result(
            forecast=forecast,
            option=option,
            inputs=inputs,
            reason="FORECAST_UNAVAILABLE",
        )
    if forecast.direction == DiscoveryDirection.NEUTRAL:
        return _empty_result(
            forecast=forecast,
            option=option,
            inputs=inputs,
            reason="FORECAST_DIRECTION_NEUTRAL",
        )

    desired_type = "call" if forecast.direction == DiscoveryDirection.BULLISH else "put"
    if option.contract_type != desired_type:
        return _empty_result(
            forecast=forecast,
            option=option,
            inputs=inputs,
            reason="OPTION_DIRECTION_MISMATCH",
        )

    option_contract_complete = True
    greeks_complete = (
        option.delta is not None
        and inputs.gamma is not None
        and inputs.theta_per_calendar_day is not None
        and inputs.vega_per_one_iv_fraction is not None
    )
    iv_context_complete = (
        option.implied_volatility is not None
        and inputs.iv_percentile is not None
        and inputs.skew_signal is not None
        and inputs.term_structure_signal is not None
    )
    liquidity_context_complete = option.volume is not None
    event_context_complete = True
    macro_context_complete = (
        inputs.risk_free_rate is not None
        and inputs.dividend_yield is not None
    )
    scenario_complete = all(
        (
            option_contract_complete,
            greeks_complete,
            iv_context_complete,
            liquidity_context_complete,
            event_context_complete,
            macro_context_complete,
        )
    )

    quantity_multiplier = inputs.contract_multiplier * float(inputs.contracts)
    entry_spread_cost = max(0.0, option.ask - option.mid) * quantity_multiplier
    expected_gross_pnl = (
        inputs.expected_terminal_premium_per_share - option.mid
    ) * quantity_multiplier
    all_in_expression_cost = (
        entry_spread_cost
        + inputs.exit_slippage_dollars
        + inputs.round_trip_commission_dollars
        + inputs.round_trip_fees_dollars
    )
    expected_net_value = expected_gross_pnl - all_in_expression_cost
    expected_return_on_capital = expected_net_value / inputs.capital_required_dollars
    expected_gain_dollars = max(
        0.0,
        (inputs.favorable_terminal_premium_per_share - option.mid) * quantity_multiplier,
    )
    expected_loss_dollars = max(
        0.0,
        (option.mid - inputs.adverse_terminal_premium_per_share) * quantity_multiplier,
    )

    model_relative_undervalued = (
        inputs.model_reference_premium_per_share is not None
        and inputs.model_reference_premium_per_share > option.ask
    )

    event_executable = (
        not inputs.event_within_horizon or inputs.event_risk_acceptable
    )
    effective_executable = inputs.executable and option.eligible and event_executable

    reasons: list[str] = [
        "AVAILABLE_DIRECTIONAL_FORECAST",
        "OPTION_DIRECTION_ALIGNED",
        "EXPLICIT_SCENARIO_MODEL_OUTPUTS",
        "SCENARIO_FORECAST_FINGERPRINT_MATCHED",
        "ENTRY_AT_ASK_WITH_MID_REFERENCE",
        "EXPLICIT_OPTION_ECONOMIC_CAPITAL_DENOMINATOR",
    ]
    if not option.eligible:
        reasons.append("UPSTREAM_OPTION_SCREEN_REJECTED")
    if inputs.event_within_horizon:
        reasons.append("EVENT_WITHIN_FORECAST_HORIZON")
        if not inputs.event_risk_acceptable:
            reasons.append("EVENT_RISK_NOT_ACCEPTED")
    if not inputs.executable:
        reasons.append("UPSTREAM_EXECUTABILITY_REJECTED")
    if not inputs.risk_budget_ok:
        reasons.append("UPSTREAM_RISK_BUDGET_REJECTED")
    if not greeks_complete:
        reasons.append("OPTION_GREEKS_CONTEXT_INCOMPLETE")
    if not iv_context_complete:
        reasons.append("OPTION_IV_CONTEXT_INCOMPLETE")
    if not liquidity_context_complete:
        reasons.append("OPTION_LIQUIDITY_CONTEXT_INCOMPLETE")
    if not macro_context_complete:
        reasons.append("OPTION_RATE_DIVIDEND_CONTEXT_INCOMPLETE")
    if model_relative_undervalued:
        reasons.append("MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY")
    elif inputs.model_reference_premium_per_share is not None:
        reasons.append("MODEL_RELATIVE_UNDERVALUE_NOT_PRESENT")
    else:
        reasons.append("MODEL_REFERENCE_PREMIUM_UNAVAILABLE")
    reasons.extend(
        (
            "HISTORICAL_OPTION_PNL_UNCLAIMED",
            "OPTION_ECONOMIC_CANDIDATE_BUILT",
            "NO_SIMULATOR_RESERVATION_OR_EXECUTION_AUTHORITY_GRANTED",
        )
    )

    candidate = EconomicCandidate(
        identifier=(
            f"OPTION:{option.contract_ticker}:"
            f"{source_forecast_fingerprint[:16]}:"
            f"{inputs.scenario_model_fingerprint[:16]}"
        ),
        kind=InstrumentKind.OPTION,
        capital_required=inputs.capital_required_dollars,
        expected_net_value=expected_net_value,
        expected_return_on_capital=expected_return_on_capital,
        probability_profit=inputs.model_probability_profit,
        expected_gain_dollars=expected_gain_dollars,
        expected_loss_dollars=expected_loss_dollars,
        execution_cost_dollars=all_in_expression_cost,
        liquidity_score=inputs.liquidity_score,
        preference_score=expected_return_on_capital,
        executable=effective_executable,
        risk_budget_ok=inputs.risk_budget_ok,
        scenario_complete=scenario_complete,
        option_contract_complete=option_contract_complete,
        greeks_complete=greeks_complete,
        iv_context_complete=iv_context_complete,
        liquidity_context_complete=liquidity_context_complete,
        event_context_complete=event_context_complete,
        model_relative_undervalued=model_relative_undervalued,
    )

    return OptionEconomicsResult(
        contract_version=OPTION_ECONOMICS_CONTRACT_VERSION,
        contract_fingerprint=OPTION_ECONOMICS_CONTRACT_FINGERPRINT,
        source_forecast_fingerprint=source_forecast_fingerprint,
        option_contract_ticker=option.contract_ticker,
        direction=forecast.direction,
        candidate=candidate,
        contracts=inputs.contracts,
        contract_multiplier=inputs.contract_multiplier,
        capital_required_dollars=inputs.capital_required_dollars,
        entry_mid_per_share=option.mid,
        entry_ask_per_share=option.ask,
        entry_spread_cost_dollars=entry_spread_cost,
        expected_terminal_premium_per_share=inputs.expected_terminal_premium_per_share,
        favorable_terminal_premium_per_share=inputs.favorable_terminal_premium_per_share,
        adverse_terminal_premium_per_share=inputs.adverse_terminal_premium_per_share,
        expected_gross_pnl_dollars=expected_gross_pnl,
        all_in_expression_cost_dollars=all_in_expression_cost,
        expected_net_value_dollars=expected_net_value,
        expected_return_on_capital=expected_return_on_capital,
        expected_gain_dollars=expected_gain_dollars,
        expected_loss_dollars=expected_loss_dollars,
        option_contract_complete=option_contract_complete,
        greeks_complete=greeks_complete,
        iv_context_complete=iv_context_complete,
        liquidity_context_complete=liquidity_context_complete,
        event_context_complete=event_context_complete,
        macro_context_complete=macro_context_complete,
        scenario_complete=scenario_complete,
        model_relative_undervalued=model_relative_undervalued,
        reason_codes=tuple(reasons),
    )
