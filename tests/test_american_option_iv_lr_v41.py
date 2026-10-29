from __future__ import annotations

from math import exp, erf, log, sqrt

import pytest

from packages.simulation.american_option_iv_lr_v41 import (
    AmericanIvError, VerifiedAmericanQuote, american_lr_price,
    american_lr_implied_volatility, qualify_american_iv,
    frozen_variance_screen,
)


def bsm_call(spot=100.0,strike=100.0,rate=.05,years=1.,sigma=.2):
    d1=(log(spot/strike)+(rate+sigma*sigma/2)*years)/(sigma*sqrt(years))
    d2=d1-sigma*sqrt(years)
    cdf=lambda z:.5*(1+erf(z/sqrt(2)))
    return spot*cdf(d1)-strike*exp(-rate*years)*cdf(d2)


def test_american_call_without_dividend_converges_to_european_analytic_price():
    price=american_lr_price("call",spot=100,strike=100,years=1,
                           rate=.05,dividend_yield=0,volatility=.2)
    assert price == pytest.approx(bsm_call(),abs=.025)
    assert price == pytest.approx(10.45055,abs=.025)


def test_american_put_early_exercise_premium_and_dividend_call():
    put=american_lr_price("put",spot=100,strike=100,years=1,
                          rate=.05,dividend_yield=0,volatility=.2)
    euro_put=bsm_call()-(100-100*exp(-.05))
    assert put > euro_put
    assert put == pytest.approx(6.0872,abs=.025)
    dividend_call=american_lr_price("call",spot=100,strike=100,years=1,
                                   rate=.05,dividend_yield=.10,volatility=.2)
    assert dividend_call > 0
    assert dividend_call < bsm_call()


@pytest.mark.parametrize("right",["call","put"])
def test_mid_quote_iv_recovers_known_101step_lr_volatility(right):
    quoted=american_lr_price(right,spot=100,strike=100,years=.25,
                             rate=.03,dividend_yield=.015,volatility=.28)
    recovered=american_lr_implied_volatility(
        right,bid=quoted-.025,ask=quoted+.025,spot=100,strike=100,
        years=.25,rate=.03,dividend_yield=.015)
    assert recovered == pytest.approx(.28,abs=.002)


def test_unqualified_rates_and_dividends_never_generate_iv():
    q=VerifiedAmericanQuote(
        right="call",spot=100,strike=100,years=.25,bid=4,ask=4.2,
        rate=None,dividend_yield=None,
        quote_pit_available=True,rate_pit_available=False,
        dividend_pit_available=False,standard_deliverable_verified=True,
        original_quote_source_id="sha_quote_1",rate_source_id=None,dividend_source_id=None,
    )
    x=qualify_american_iv(q)
    assert x["status"]=="BLOCKED"
    assert x["model_iv_annual_decimal"] is None
    assert "PIT_RATE_UNPROVEN" in x["reasons"]
    assert "PIT_DIVIDEND_UNPROVEN" in x["reasons"]
    assert x["historical_trade_account_pnl_authority"] is False


def test_qualified_mathematical_inputs_return_source_gated_iv_not_fills():
    price=american_lr_price("put",spot=100,strike=100,years=.2,
                            rate=.03,dividend_yield=.01,volatility=.21)
    q=VerifiedAmericanQuote(
        right="put",spot=100,strike=100,years=.2,bid=price-.01,ask=price+.01,
        rate=.03,dividend_yield=.01,
        quote_pit_available=True,rate_pit_available=True,
        dividend_pit_available=True,standard_deliverable_verified=True,
        original_quote_source_id="source_123",rate_source_id="PIT_SOFR_2023",
        dividend_source_id="PIT_DIV_2023",
    )
    x=qualify_american_iv(q)
    assert x["status"]=="MODEL_IV_READY_SOURCE_EVIDENCE_GATED"
    assert x["model_iv_annual_decimal"] == pytest.approx(.21,abs=.002)
    assert x["quote_is_real_order_fill"] is False
    assert x["discrete_dividend_ex_date_model_qualified"] is False


def test_frozen_twenty_prior_returns_signal_and_strict_missing_data_gate():
    items=tuple((.01,86400.) for _ in range(20))
    case=frozen_variance_screen(
        twenty_previous_completed_log_return_intervals=items,
        maturity_seconds=30*86400.,
        call_iv=.1,put_iv=.1,
        prior_return_adjustments_pit_qualified=True,
        option_iv_sources_pit_qualified=True)
    assert case["decision"]=="LONG_STRADDLE"
    assert case["forecast_same_maturity_calendar_variance"]==pytest.approx(.003)
    assert case["implied_same_maturity_pair_variance"]==pytest.approx(
        (.1**2)*(30/365))
    abstain=frozen_variance_screen(
        twenty_previous_completed_log_return_intervals=items,
        maturity_seconds=30*86400.,
        call_iv=.5,put_iv=.5,
        prior_return_adjustments_pit_qualified=True,
        option_iv_sources_pit_qualified=True)
    assert abstain["decision"]=="ABSTAIN"
    blocked=frozen_variance_screen(
        twenty_previous_completed_log_return_intervals=items,
        maturity_seconds=30*86400.,
        call_iv=.1,put_iv=None,
        prior_return_adjustments_pit_qualified=False,
        option_iv_sources_pit_qualified=False)
    assert blocked["decision"]=="BLOCKED"
    assert blocked["forecast_same_maturity_calendar_variance"] is None


def test_invalid_american_tree_and_observed_quote_rejected():
    with pytest.raises(AmericanIvError):
        american_lr_price("call",spot=100,strike=100,years=1,rate=.05,
                          dividend_yield=0,volatility=.2,steps=100)
    with pytest.raises(AmericanIvError):
        american_lr_price("put",spot=0,strike=100,years=1,rate=.05,
                          dividend_yield=0,volatility=.2)
    with pytest.raises(AmericanIvError,match="QUOTE"):
        american_lr_implied_volatility(
            "call",bid=2.1,ask=2,spot=100,strike=100,years=.25,
            rate=.03,dividend_yield=.01)
    with pytest.raises(AmericanIvError,match="20RETURN"):
        frozen_variance_screen(
            twenty_previous_completed_log_return_intervals=((.01,86400),),
            maturity_seconds=20*86400,call_iv=.2,put_iv=.2,
            prior_return_adjustments_pit_qualified=True,
            option_iv_sources_pit_qualified=True)
