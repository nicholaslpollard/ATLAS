from __future__ import annotations

import math
from dataclasses import dataclass

from packages.execution.stock_economics_contract import (
    STOCK_ECONOMICS_CONTRACT,
    STOCK_ECONOMICS_CONTRACT_FINGERPRINT,
)
from packages.execution.trade_expression import EconomicCandidate, InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    UnderlyingMoveTimeForecast,
    forecast_fingerprint,
)


STOCK_ECONOMICS_CONTRACT_VERSION = str(STOCK_ECONOMICS_CONTRACT["contract_id"])


class StockEconomicsError(ValueError):
    pass


@dataclass(frozen=True)
class StockEconomicsInputs:
    """Explicit stock-expression assumptions supplied by simulation policy.

    Dollar costs are complete round-trip or forecast-horizon totals. The adapter
    never annualizes borrow/financing costs and never infers margin or leverage.
    """

    position_notional_dollars: float
    capital_required_dollars: float
    entry_slippage_bps: float
    exit_slippage_bps: float
    round_trip_commission_dollars: float
    round_trip_fees_dollars: float
    horizon_borrow_cost_dollars: float
    horizon_financing_cost_dollars: float
    net_probability_profit: float
    liquidity_score: float
    executable: bool
    risk_budget_ok: bool
    shortable_if_bearish: bool = True

    def __post_init__(self) -> None:
        numeric = (
            self.position_notional_dollars,
            self.capital_required_dollars,
            self.entry_slippage_bps,
            self.exit_slippage_bps,
            self.round_trip_commission_dollars,
            self.round_trip_fees_dollars,
            self.horizon_borrow_cost_dollars,
            self.horizon_financing_cost_dollars,
            self.net_probability_profit,
            self.liquidity_score,
        )
        if not all(math.isfinite(float(value)) for value in numeric):
            raise StockEconomicsError("stock economics inputs contain non-finite values")
        if self.position_notional_dollars <= 0.0:
            raise StockEconomicsError("position notional must be positive")
        if self.capital_required_dollars <= 0.0:
            raise StockEconomicsError("capital required must be positive")
        if self.entry_slippage_bps < 0.0 or self.exit_slippage_bps < 0.0:
            raise StockEconomicsError("slippage cannot be negative")
        costs = (
            self.round_trip_commission_dollars,
            self.round_trip_fees_dollars,
            self.horizon_borrow_cost_dollars,
            self.horizon_financing_cost_dollars,
        )
        if any(value < 0.0 for value in costs):
            raise StockEconomicsError("stock expression costs cannot be negative")
        if not 0.0 <= self.net_probability_profit <= 1.0:
            raise StockEconomicsError("net probability of profit must be in [0, 1]")
        if not 0.0 <= self.liquidity_score <= 1.0:
            raise StockEconomicsError("liquidity score must be in [0, 1]")
        for name in ("executable", "risk_budget_ok", "shortable_if_bearish"):
            if not isinstance(getattr(self, name), bool):
                raise StockEconomicsError(f"{name} must be boolean")


@dataclass(frozen=True)
class StockEconomicsResult:
    contract_version: str
    contract_fingerprint: str
    source_forecast_fingerprint: str
    direction: DiscoveryDirection
    candidate: EconomicCandidate | None
    position_notional_dollars: float
    capital_required_dollars: float
    gross_directional_sign_probability: float | None
    direction_adjusted_mean_return: float | None
    expected_gross_pnl_dollars: float | None
    slippage_cost_dollars: float | None
    all_in_expression_cost_dollars: float | None
    expected_net_value_dollars: float | None
    expected_return_on_capital: float | None
    expected_gain_dollars: float | None
    expected_loss_dollars: float | None
    reason_codes: tuple[str, ...]



def _empty_result(
    *,
    forecast: UnderlyingMoveTimeForecast,
    inputs: StockEconomicsInputs,
    reason: str,
) -> StockEconomicsResult:
    return StockEconomicsResult(
        contract_version=STOCK_ECONOMICS_CONTRACT_VERSION,
        contract_fingerprint=STOCK_ECONOMICS_CONTRACT_FINGERPRINT,
        source_forecast_fingerprint=forecast_fingerprint(forecast),
        direction=forecast.direction,
        candidate=None,
        position_notional_dollars=inputs.position_notional_dollars,
        capital_required_dollars=inputs.capital_required_dollars,
        gross_directional_sign_probability=None,
        direction_adjusted_mean_return=None,
        expected_gross_pnl_dollars=None,
        slippage_cost_dollars=None,
        all_in_expression_cost_dollars=None,
        expected_net_value_dollars=None,
        expected_return_on_capital=None,
        expected_gain_dollars=None,
        expected_loss_dollars=None,
        reason_codes=(reason, "NO_STOCK_ECONOMIC_CANDIDATE"),
    )



def build_stock_economic_candidate(
    *,
    forecast: UnderlyingMoveTimeForecast,
    inputs: StockEconomicsInputs,
) -> StockEconomicsResult:
    """Translate underlying forecast evidence into one stock economic candidate.

    This function performs arithmetic only. It does not read a provider or
    broker, choose position size, infer leverage, create an order, or grant
    PAPER/LIVE/promotion authority.
    """

    if forecast.availability != ForecastAvailability.AVAILABLE:
        return _empty_result(
            forecast=forecast,
            inputs=inputs,
            reason="FORECAST_UNAVAILABLE",
        )
    if forecast.direction == DiscoveryDirection.NEUTRAL:
        return _empty_result(
            forecast=forecast,
            inputs=inputs,
            reason="FORECAST_DIRECTION_NEUTRAL",
        )

    assert forecast.mean_signed_return is not None
    assert forecast.probability_positive_return is not None
    assert forecast.mean_mfe is not None
    assert forecast.mean_mae is not None

    bullish = forecast.direction == DiscoveryDirection.BULLISH
    gross_directional_sign_probability = (
        forecast.probability_positive_return
        if bullish
        else 1.0 - forecast.probability_positive_return
    )
    gross_directional_sign_probability = min(
        1.0,
        max(0.0, gross_directional_sign_probability),
    )
    if inputs.net_probability_profit > gross_directional_sign_probability + 1e-12:
        raise StockEconomicsError(
            "net probability of profit cannot exceed the forecast gross directional sign probability"
        )

    direction_adjusted_mean_return = (
        forecast.mean_signed_return if bullish else -forecast.mean_signed_return
    )
    expected_gross_pnl = (
        inputs.position_notional_dollars * direction_adjusted_mean_return
    )
    slippage_cost = inputs.position_notional_dollars * (
        inputs.entry_slippage_bps + inputs.exit_slippage_bps
    ) / 10_000.0
    all_in_cost = (
        slippage_cost
        + inputs.round_trip_commission_dollars
        + inputs.round_trip_fees_dollars
        + inputs.horizon_borrow_cost_dollars
        + inputs.horizon_financing_cost_dollars
    )
    expected_net_value = expected_gross_pnl - all_in_cost
    expected_return_on_capital = expected_net_value / inputs.capital_required_dollars
    expected_gain_dollars = inputs.position_notional_dollars * forecast.mean_mfe
    expected_loss_dollars = inputs.position_notional_dollars * forecast.mean_mae

    shortability_ok = bullish or inputs.shortable_if_bearish
    effective_executable = inputs.executable and shortability_ok
    reasons = [
        "AVAILABLE_DIRECTIONAL_FORECAST",
        "EXPLICIT_NOTIONAL_AND_CAPITAL",
        "EXPLICIT_ALL_IN_COSTS",
        "EXPLICIT_NET_PROFIT_PROBABILITY",
    ]
    if not shortability_ok:
        reasons.append("BEARISH_STOCK_NOT_SHORTABLE")
    if not inputs.executable:
        reasons.append("UPSTREAM_EXECUTABILITY_REJECTED")
    if not inputs.risk_budget_ok:
        reasons.append("UPSTREAM_RISK_BUDGET_REJECTED")
    reasons.extend(("STOCK_ECONOMIC_CANDIDATE_BUILT", "NO_EXECUTION_AUTHORITY_GRANTED"))

    candidate = EconomicCandidate(
        identifier=(
            f"STOCK:{forecast.instrument_id}:"
            f"{forecast_fingerprint(forecast)[:16]}"
        ),
        kind=InstrumentKind.STOCK,
        capital_required=inputs.capital_required_dollars,
        expected_net_value=expected_net_value,
        expected_return_on_capital=expected_return_on_capital,
        probability_profit=inputs.net_probability_profit,
        expected_gain_dollars=expected_gain_dollars,
        expected_loss_dollars=expected_loss_dollars,
        execution_cost_dollars=all_in_cost,
        liquidity_score=inputs.liquidity_score,
        preference_score=expected_return_on_capital,
        executable=effective_executable,
        risk_budget_ok=inputs.risk_budget_ok,
        scenario_complete=True,
    )
    return StockEconomicsResult(
        contract_version=STOCK_ECONOMICS_CONTRACT_VERSION,
        contract_fingerprint=STOCK_ECONOMICS_CONTRACT_FINGERPRINT,
        source_forecast_fingerprint=forecast_fingerprint(forecast),
        direction=forecast.direction,
        candidate=candidate,
        position_notional_dollars=inputs.position_notional_dollars,
        capital_required_dollars=inputs.capital_required_dollars,
        gross_directional_sign_probability=gross_directional_sign_probability,
        direction_adjusted_mean_return=direction_adjusted_mean_return,
        expected_gross_pnl_dollars=expected_gross_pnl,
        slippage_cost_dollars=slippage_cost,
        all_in_expression_cost_dollars=all_in_cost,
        expected_net_value_dollars=expected_net_value,
        expected_return_on_capital=expected_return_on_capital,
        expected_gain_dollars=expected_gain_dollars,
        expected_loss_dollars=expected_loss_dollars,
        reason_codes=tuple(reasons),
    )
