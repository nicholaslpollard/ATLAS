from __future__ import annotations

"""V41 101-step Leisen-Reimer American option IV + frozen variance signal.

Source admission precedes IV. This model never substitutes a synthetic quote
for an actual bid/ask, a present-day rate for a PIT rate, or a zero-dividend
assumption for missing historical corporate-action evidence.

Leisen-Reimer inverts Peizer-Pratt's binomial CDF. The dividend input here is
an explicitly supplied, PIT-qualified continuous *yield equivalent*; real
discrete ex-date cash dividends require separately qualified modeling before
the exact historical pilot can be accepted.
"""

from dataclasses import dataclass
from math import copysign, exp, expm1, isfinite, log, sqrt
from typing import Literal

CONTRACT = "atlas-leisen-reimer-american-iv-v41"
STEPS = 101
SECONDS_PER_YEAR = 365.0 * 86400.0
RIGHTS = ("call", "put")
EntryDecision = Literal["LONG_STRADDLE", "ABSTAIN", "BLOCKED"]


class AmericanIvError(ValueError):
    pass


def _pp(x: float, n: int) -> float:
    """Peizer-Pratt second-inversion approximation for an odd-step tree."""
    denom = n + 1.0 / 3.0 + 0.1 / (n + 1)
    exponent = -(x / denom) ** 2 * (n + 1.0 / 6.0)
    magnitude = sqrt(max(0.0, -expm1(exponent)))
    return 0.5 + copysign(0.5 * magnitude, x)


def american_lr_price(
    right: Literal["call", "put"], *,
    spot: float, strike: float, years: float, rate: float,
    dividend_yield: float, volatility: float, steps: int = STEPS,
) -> float:
    """American early-exercise 101-step LR premium per one underlying share."""
    values = (spot, strike, years, rate, dividend_yield, volatility)
    if (right not in RIGHTS or type(steps) is not int or steps < 5
            or steps % 2 != 1 or
            any(not isinstance(z, (int, float)) or not isfinite(z) for z in values)
            or spot <= 0 or strike <= 0 or years <= 0 or volatility <= 0
            or dividend_yield < 0 or years > 10 or volatility > 10
            or not -1 < rate < 1 or dividend_yield > 1):
        raise AmericanIvError("V41_INVALID_MODEL_INPUT_OR_STEP_COUNT")
    dt = years / steps
    d1 = (log(spot / strike) + (rate - dividend_yield
          + 0.5 * volatility * volatility) * years) / (volatility * sqrt(years))
    d2 = d1 - volatility * sqrt(years)
    p = _pp(d2, steps)
    p_up_tilted = _pp(d1, steps)
    if not 0 < p < 1:
        raise AmericanIvError("V41_LR_TRANSITION_PROBABILITY_SATURATED")
    growth = exp((rate - dividend_yield) * dt)
    up = growth * p_up_tilted / p
    down = (growth - p * up) / (1 - p)
    if not (isfinite(up) and isfinite(down) and 0 < down < growth < up):
        raise AmericanIvError("V41_LR_TREE_NO_ARBITRAGE_VIOLATION")
    ratio = up / down
    s = spot * down**steps
    values_at_step = []
    for _ in range(steps + 1):
        values_at_step.append(max(0.0, s - strike) if right == "call" else
                              max(0.0, strike - s))
        s *= ratio
    discount = exp(-rate * dt)
    for level in range(steps - 1, -1, -1):
        s = spot * down**level
        for j in range(level + 1):
            continuation = discount * (
                p * values_at_step[j + 1] + (1 - p) * values_at_step[j]
            )
            immediate = max(0.0, s - strike) if right == "call" else max(
                0.0, strike - s
            )
            values_at_step[j] = max(immediate, continuation)
            s *= ratio
    return values_at_step[0]


def american_lr_implied_volatility(
    right: Literal["call", "put"], *, bid: float, ask: float,
    spot: float, strike: float, years: float, rate: float,
    dividend_yield: float, steps: int = STEPS,
) -> float | None:
    """Solve the American-LR midpoint IV; return NULL for non-solvable quotes."""
    if (not all(isinstance(z, (int, float)) and isfinite(z) for z in (bid, ask))
            or bid <= 0 or ask < bid):
        raise AmericanIvError("V41_INVALID_OBSERVED_TWO_SIDED_QUOTE")
    mid = (bid + ask) / 2
    low, high = 0.001, 5.0
    try:
        plow = american_lr_price(
            right, spot=spot, strike=strike, years=years, rate=rate,
            dividend_yield=dividend_yield, volatility=low, steps=steps,
        )
        phigh = american_lr_price(
            right, spot=spot, strike=strike, years=years, rate=rate,
            dividend_yield=dividend_yield, volatility=high, steps=steps,
        )
    except AmericanIvError:
        return None
    if not plow - 0.001 <= mid <= phigh + 0.001 or plow > phigh:
        return None
    if abs(mid - plow) <= 0.001:
        return low
    for _ in range(46):
        guess = (low + high) / 2
        price = american_lr_price(
            right, spot=spot, strike=strike, years=years, rate=rate,
            dividend_yield=dividend_yield, volatility=guess, steps=steps,
        )
        if abs(price - mid) < 0.0005:
            return guess
        if price > mid:
            high = guess
        else:
            low = guess
    return (low + high) / 2


@dataclass(frozen=True)
class VerifiedAmericanQuote:
    """Source verification is an external gate; no self-verified PIT inputs."""

    right: Literal["call", "put"]
    spot: float
    strike: float
    years: float
    bid: float
    ask: float
    rate: float | None
    dividend_yield: float | None
    quote_pit_available: bool
    rate_pit_available: bool
    dividend_pit_available: bool
    standard_deliverable_verified: bool
    original_quote_source_id: str
    rate_source_id: str | None
    dividend_source_id: str | None


def qualify_american_iv(q: VerifiedAmericanQuote) -> dict:
    """A computed IV is never published if required historical evidence is absent."""
    blocked = []
    if not q.quote_pit_available or not q.original_quote_source_id:
        blocked.append("HISTORICAL_QUOTE_PIT_UNPROVEN")
    if not q.rate_pit_available or not q.rate_source_id or q.rate is None:
        blocked.append("PIT_RATE_UNPROVEN")
    if not q.dividend_pit_available or not q.dividend_source_id or q.dividend_yield is None:
        blocked.append("PIT_DIVIDEND_UNPROVEN")
    if not q.standard_deliverable_verified:
        blocked.append("OCC_DELIVERABLE_UNPROVEN")
    iv = None
    if not blocked:
        iv = american_lr_implied_volatility(
            q.right, bid=q.bid, ask=q.ask, spot=q.spot, strike=q.strike,
            years=q.years, rate=q.rate, dividend_yield=q.dividend_yield,
        )
        if iv is None:
            blocked.append("OBSERVED_MID_UNSOLVABLE_IN_LR_MODEL")
    return {
        "contract": CONTRACT, "right": q.right,
        "source_original_quote_id": q.original_quote_source_id,
        "rate_source_id": q.rate_source_id,
        "dividend_source_id": q.dividend_source_id,
        "model": "LEISEN_REIMER_101STEP_AMERICAN_CONTINUOUS_DIVIDEND_YIELD",
        "model_iv_annual_decimal": iv,
        "status": "MODEL_IV_READY_SOURCE_EVIDENCE_GATED" if iv is not None else "BLOCKED",
        "reasons": blocked,
        "quote_is_real_order_fill": False,
        "discrete_dividend_ex_date_model_qualified": False,
        "historical_trade_account_pnl_authority": False,
    }


def frozen_variance_screen(
    *,
    twenty_previous_completed_log_return_intervals: tuple[tuple[float, float], ...],
    maturity_seconds: float,
    call_iv: float | None, put_iv: float | None,
    prior_return_adjustments_pit_qualified: bool,
    option_iv_sources_pit_qualified: bool,
) -> dict:
    """Frozen 20-return calendar variance rate vs same-maturity IV variance.

    Missing or unqualified inputs BLOCK rather than becoming a negative signal.
    No future realized return or later trade outcome is accepted in this API.
    """
    if (len(twenty_previous_completed_log_return_intervals) != 20
            or not isfinite(maturity_seconds) or maturity_seconds <= 0
            or maturity_seconds > 365 * 86400):
        raise AmericanIvError("V41_INVALID_20RETURN_MATURITY_SCOPE")
    forecast = None
    implied = None
    reasons = []
    if not prior_return_adjustments_pit_qualified:
        reasons.append("20_RETURN_CORPORATE_ACTION_PIT_UNQUALIFIED")
    if not option_iv_sources_pit_qualified or call_iv is None or put_iv is None:
        reasons.append("CALL_PUT_IV_PIT_UNQUALIFIED")
    total_duration = 0.0
    sum_squared = 0.0
    for ret, seconds in twenty_previous_completed_log_return_intervals:
        if (not isfinite(ret) or not isfinite(seconds)
                or seconds <= 0 or seconds > 10 * 86400
                or abs(ret) > 2):
            raise AmericanIvError("V41_INVALID_PRIOR_LOG_RETURN_INTERVAL")
        total_duration += seconds
        sum_squared += ret**2
    if not reasons:
        if (not isfinite(call_iv) or not isfinite(put_iv)
                or call_iv <= 0 or put_iv <= 0 or
                call_iv > 5 or put_iv > 5):
            raise AmericanIvError("V41_BAD_SOURCE_MODEL_IV")
        forecast = sum_squared / total_duration * maturity_seconds
        implied = (call_iv**2 + put_iv**2) / 2 * maturity_seconds / SECONDS_PER_YEAR
    return {
        "contract": CONTRACT,
        "status": "BLOCKED" if reasons else "SCREEN_COMPUTED_PIT_INPUTS",
        "decision": (
            "BLOCKED" if reasons else
            "LONG_STRADDLE" if forecast > implied else "ABSTAIN"
        ),
        "forecast_same_maturity_calendar_variance": forecast,
        "implied_same_maturity_pair_variance": implied,
        "reasons": reasons,
        "fixed_20_returns_used": 20,
        "future_outcomes_used": False,
        "broker_fill_asserted": False,
        "strategy_historical_profitability_proven": False,
    }
