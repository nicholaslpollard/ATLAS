from __future__ import annotations

"""No-network mathematical checks for model-derived, non-executable Greeks."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from packages.simulation.historical_option_greeks_v1 import (
    HistoricalGreeksError, ObservedOptionInputs, _price_and_greeks,
    derive_historical_greeks,
)


def _sample(**kwargs):
    row = ObservedOptionInputs(
        side="call", option_symbol="TEST270101C00100000",
        observation_utc=datetime(2026, 1, 1, 16, tzinfo=UTC),
        expiration_utc=datetime(2027, 1, 1, 16, tzinfo=UTC),
        observed_bid=10.40, observed_ask=10.50,
        observed_underlying_price=100.0, strike=100.0,
        historical_continuous_risk_free_rate=0.05,
        historical_continuous_dividend_yield=0.0,
        deliverable_is_standard_100_shares=True,
        stock_price_is_raw_as_traded=True,
        historical_rates_source_id="accepted-2026-rate-20260101",
        historical_dividends_source_id="accepted-2026-dividend-20260101",
    )
    return replace(row, **kwargs)


def test_standard_bsm_call_and_put_greeks_match_benchmarks():
    price, delta, gamma, theta, vega, rho = _price_and_greeks(
        "call", 100.0, 100.0, 1.0, 0.05, 0.0, 0.20
    )
    assert price == pytest.approx(10.450583572, abs=1e-6)
    assert delta == pytest.approx(0.636830651, abs=1e-6)
    assert gamma == pytest.approx(0.018762017, abs=1e-6)
    assert theta == pytest.approx(-6.414027546 / 365, abs=1e-7)
    assert vega == pytest.approx(37.5240347, abs=1e-5)
    assert rho == pytest.approx(53.2324815, abs=1e-5)
    p, pd, pg, pt, pv, pr = _price_and_greeks(
        "put", 100.0, 100.0, 1.0, 0.05, 0.0, 0.20
    )
    assert p == pytest.approx(5.573526, abs=1e-6)
    assert pd == pytest.approx(-0.363169349, abs=1e-6)
    assert pg == pytest.approx(gamma)
    assert pv == pytest.approx(vega)
    assert pt < 0 and pr < 0


@pytest.mark.parametrize("side", ["call", "put"])
def test_iv_recovers_synthetic_observed_mid_without_provider_access(side):
    exact = _price_and_greeks(side, 100.0, 100.0, 1.0, 0.05, 0.0, 0.20)[0]
    source = _sample(side=side, observed_bid=exact - 0.05, observed_ask=exact + 0.05)
    result = derive_historical_greeks(source)
    assert result.status == "MODEL_DERIVED_EUROPEAN_EQUIVALENT_ONLY"
    assert result.model_iv_fraction == pytest.approx(0.2, abs=1e-7)
    assert result.model_mid_reprice == pytest.approx(exact, abs=1e-7)
    assert result.historical_bid_ask_are_observed_not_model_prices is True
    assert result.exact_historical_executability_proven is False
    assert result.option_cash_pnl_authority is False


def test_missing_deliverable_or_rates_and_crossed_quote_fail_closed():
    with pytest.raises(HistoricalGreeksError, match="deliverable"):
        derive_historical_greeks(_sample(deliverable_is_standard_100_shares=False))
    with pytest.raises(HistoricalGreeksError, match="provenance"):
        derive_historical_greeks(_sample(historical_rates_source_id=""))
    with pytest.raises(HistoricalGreeksError, match="spread"):
        derive_historical_greeks(_sample(observed_bid=10.5, observed_ask=10.4))
    with pytest.raises(HistoricalGreeksError, match="timezone"):
        derive_historical_greeks(_sample(observation_utc=datetime(2026, 1, 1, 16)))
    with pytest.raises(HistoricalGreeksError, match="expired"):
        derive_historical_greeks(_sample(
            expiration_utc=datetime(2025, 1, 1, 16, tzinfo=UTC)
        ))


def test_mid_outside_bounds_does_not_invent_iv():
    result = derive_historical_greeks(
        _sample(observed_bid=100.0, observed_ask=100.1)
    )
    assert result.status == "IV_NOT_IDENTIFIABLE_FROM_OBSERVED_MID"
    assert result.model_iv_fraction is None
    assert result.delta is None and result.gamma is None
    assert result.option_cash_pnl_authority is False
