from __future__ import annotations

"""Historical European-equivalent IV/Greeks from *observed* option quote inputs.

This is a deterministic, model-derived research feature for the integrated
simulator. U.S. equity contracts can be American-style and adjusted; the
European-equivalent result never substitutes for historical executable quotes.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from math import erf, exp, isfinite, log, pi, sqrt
from typing import Literal

CONTRACT = "atlas-historical-european-equivalent-greeks-v1"
NORMALIZATION = "VEGA_PER_1_00_VOL_FRACTION_THETA_PER_CALENDAR_DAY"
OptionSide = Literal["call", "put"]


class HistoricalGreeksError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ObservedOptionInputs:
    """All source/economic inputs must be supplied; no default current rate or q."""

    side: OptionSide
    option_symbol: str
    observation_utc: datetime
    expiration_utc: datetime
    observed_bid: float
    observed_ask: float
    observed_underlying_price: float
    strike: float
    historical_continuous_risk_free_rate: float
    historical_continuous_dividend_yield: float
    deliverable_is_standard_100_shares: bool
    stock_price_is_raw_as_traded: bool
    historical_rates_source_id: str
    historical_dividends_source_id: str


@dataclass(frozen=True, slots=True)
class LocalGreeks:
    contract: str
    status: str
    option_symbol: str
    observation_utc: str
    expiry_utc: str
    option_mid: float | None
    model_iv_fraction: float | None
    delta: float | None
    gamma: float | None
    theta_per_calendar_day: float | None
    vega_per_one_vol_fraction: float | None
    rho_per_one_rate_fraction: float | None
    model_mid_reprice: float | None
    model_name: str
    model_is_european_equivalent_not_american_contract_valuation: bool
    historical_bid_ask_are_observed_not_model_prices: bool
    exact_historical_executability_proven: bool
    option_cash_pnl_authority: bool
    rates_source_id: str
    dividends_source_id: str
    reason: str | None


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


def _price_and_greeks(
    side: OptionSide, spot: float, strike: float, years: float,
    rate: float, yield_rate: float, volatility: float,
) -> tuple[float, float, float, float, float, float]:
    root = sqrt(years)
    d1 = (
        log(spot / strike)
        + (rate - yield_rate + 0.5 * volatility * volatility) * years
    ) / (volatility * root)
    d2 = d1 - volatility * root
    discount = exp(-rate * years)
    dividend = exp(-yield_rate * years)
    if side == "call":
        price = spot * dividend * _cdf(d1) - strike * discount * _cdf(d2)
        delta = dividend * _cdf(d1)
        theta_year = (
            -spot * dividend * _pdf(d1) * volatility / (2 * root)
            -rate * strike * discount * _cdf(d2)
            +yield_rate * spot * dividend * _cdf(d1)
        )
        rho = strike * years * discount * _cdf(d2)
    else:
        price = strike * discount * _cdf(-d2) - spot * dividend * _cdf(-d1)
        delta = dividend * (_cdf(d1) - 1.0)
        theta_year = (
            -spot * dividend * _pdf(d1) * volatility / (2 * root)
            +rate * strike * discount * _cdf(-d2)
            -yield_rate * spot * dividend * _cdf(-d1)
        )
        rho = -strike * years * discount * _cdf(-d2)
    gamma = dividend * _pdf(d1) / (spot * volatility * root)
    vega = spot * dividend * _pdf(d1) * root
    return price, delta, gamma, theta_year / 365.0, vega, rho


def _validate(x: ObservedOptionInputs) -> float:
    if x.side not in ("call", "put") or not x.option_symbol.strip():
        raise HistoricalGreeksError("option identity and right are required")
    if (
        not isinstance(x.observation_utc, datetime)
        or not isinstance(x.expiration_utc, datetime)
        or x.observation_utc.tzinfo is None or x.expiration_utc.tzinfo is None
    ):
        raise HistoricalGreeksError("observed quote and expiration need aware UTC times")
    if not x.deliverable_is_standard_100_shares or not x.stock_price_is_raw_as_traded:
        raise HistoricalGreeksError("adjusted/unknown contract deliverable or price basis")
    if not x.historical_rates_source_id or not x.historical_dividends_source_id:
        raise HistoricalGreeksError("point-in-time rate and dividend provenance required")
    values = (
        x.observed_bid, x.observed_ask, x.observed_underlying_price, x.strike,
        x.historical_continuous_risk_free_rate,
        x.historical_continuous_dividend_yield,
    )
    if any(isinstance(v, bool) or not isinstance(v, (float, int))
           or not isfinite(v) for v in values):
        raise HistoricalGreeksError("finite numeric inputs required")
    if (
        x.observed_bid <= 0 or x.observed_ask < x.observed_bid
        or x.observed_underlying_price <= 0 or x.strike <= 0
        or not -0.05 <= x.historical_continuous_risk_free_rate <= 0.30
        or not 0 <= x.historical_continuous_dividend_yield <= 0.30
    ):
        raise HistoricalGreeksError("invalid spread, price, or rate/yield bounds")
    years = (
        x.expiration_utc.astimezone(UTC) - x.observation_utc.astimezone(UTC)
    ).total_seconds() / (365.0 * 86400.0)
    if not 0 < years <= 3:
        raise HistoricalGreeksError("quote observation is expired or beyond model tenor")
    return years


def derive_historical_greeks(
    inputs: ObservedOptionInputs, *, tolerance: float = 1e-8,
    iterations: int = 100,
) -> LocalGreeks:
    """Solve an observed MID implied-volatility; never invent a missing quote.

    European-equivalent BSM is *not* an American-option early exercise engine.
    The observed bid/ask remains the source; this function cannot authorize fills.
    """
    years = _validate(inputs)
    mid = (inputs.observed_bid + inputs.observed_ask) / 2.0
    base = dict(
        contract=CONTRACT, option_symbol=inputs.option_symbol,
        observation_utc=inputs.observation_utc.astimezone(UTC).isoformat(),
        expiry_utc=inputs.expiration_utc.astimezone(UTC).isoformat(),
        option_mid=mid, model_name="EUROPEAN_EQUIVALENT_BLACK_SCHOLES_MERTON",
        model_is_european_equivalent_not_american_contract_valuation=True,
        historical_bid_ask_are_observed_not_model_prices=True,
        exact_historical_executability_proven=False,
        option_cash_pnl_authority=False,
        rates_source_id=inputs.historical_rates_source_id,
        dividends_source_id=inputs.historical_dividends_source_id,
    )
    s, k = inputs.observed_underlying_price, inputs.strike
    r, q = inputs.historical_continuous_risk_free_rate, inputs.historical_continuous_dividend_yield
    discounted_s, discounted_k = s * exp(-q * years), k * exp(-r * years)
    intrinsic_lower = (
        max(0.0, discounted_s - discounted_k) if inputs.side == "call"
        else max(0.0, discounted_k - discounted_s)
    )
    maximum = discounted_s if inputs.side == "call" else discounted_k
    if mid <= intrinsic_lower + tolerance or mid >= maximum - tolerance:
        return LocalGreeks(
            **base, status="IV_NOT_IDENTIFIABLE_FROM_OBSERVED_MID",
            model_iv_fraction=None, delta=None, gamma=None,
            theta_per_calendar_day=None, vega_per_one_vol_fraction=None,
            rho_per_one_rate_fraction=None, model_mid_reprice=None,
            reason="observed mid at/outside European no-arbitrage bounds",
        )
    low, high = 1e-6, 5.0
    low_p = _price_and_greeks(inputs.side, s, k, years, r, q, low)[0]
    high_p = _price_and_greeks(inputs.side, s, k, years, r, q, high)[0]
    if not low_p <= mid <= high_p:
        return LocalGreeks(
            **base, status="IV_OUTSIDE_MODEL_VOL_RANGE",
            model_iv_fraction=None, delta=None, gamma=None,
            theta_per_calendar_day=None, vega_per_one_vol_fraction=None,
            rho_per_one_rate_fraction=None, model_mid_reprice=None,
            reason="historical mid cannot be inverted in [1e-6, 5] volatility",
        )
    for _ in range(iterations):
        implied = (low + high) / 2.0
        price = _price_and_greeks(inputs.side, s, k, years, r, q, implied)[0]
        if abs(price - mid) <= tolerance:
            break
        if price < mid:
            low = implied
        else:
            high = implied
    price, delta, gamma, theta, vega, rho = _price_and_greeks(
        inputs.side, s, k, years, r, q, implied
    )
    return LocalGreeks(
        **base, status="MODEL_DERIVED_EUROPEAN_EQUIVALENT_ONLY",
        model_iv_fraction=implied, delta=delta, gamma=gamma,
        theta_per_calendar_day=theta, vega_per_one_vol_fraction=vega,
        rho_per_one_rate_fraction=rho, model_mid_reprice=price,
        reason=None,
    )
