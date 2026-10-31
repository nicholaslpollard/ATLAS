from __future__ import annotations

from dataclasses import replace
from datetime import datetime,timedelta,timezone

import pytest

from packages.simulation.historical_option_greeks_v1 import _price_and_greeks
from packages.simulation.spy_v60_independent_action_side_valuation import (
    IndependentActionEvidence,QuoteSideError,classify_action_side,
)

NOW=datetime(2025,6,13,15,0,0,tzinfo=timezone.utc)
EXP=datetime(2025,6,13,20,0,0,tzinfo=timezone.utc)
T=(EXP-NOW).total_seconds()/(365*86400)


def model(right="call",sigma=.5):
    return _price_and_greeks(right,100,100,T,.04,.01,sigma)[0]


def evidence(action="buy",right="call",*,other_side_bad=True):
    fair=model(right)
    if action=="buy":
        ask=fair
        bid=fair-.40 if other_side_bad else fair-.01
    else:
        bid=fair
        ask=fair+.40 if other_side_bad else fair+.01
    return IndependentActionEvidence(
        action=action,option_right=right,
        quote_at=NOW-timedelta(milliseconds=100),
        decision_at=NOW,expiration_at=EXP,
        bid=bid,ask=ask,bid_size=10,ask_size=10,contracts=2,
        spot=100.0,spot_at=NOW-timedelta(milliseconds=300),
        independent_iv_lower=.499,independent_iv_upper=.501,
        volatility_at=NOW-timedelta(seconds=1),
        historical_rate_observed_at=NOW-timedelta(hours=4),
        dividend_observed_at=NOW-timedelta(days=1),
        historical_rate=.04,historical_dividend_yield=.01,strike=100,
        spot_source_id="independent-tick-spy-prior-sha",
        iv_source_id="calibrated-prior-cross-strike-iv-sha",
        rate_source_id="pit-treasury-rate",dividend_source_id="pit-dividend-receipt",
        acted_quote_source_id="exact-option-quote-snapshot-sha",
        standard_100_share_deliverable=True,raw_spot_as_traded=True,
    )


@pytest.mark.parametrize("action",["buy","sell"])
@pytest.mark.parametrize("right",["call","put"])
def test_side_aware_fair_acting_side_survives_abnormal_other_side(action,right):
    q=evidence(action,right)
    result=classify_action_side(q)
    assert result["status"]=="ACTION_SIDE_MODEL_CONSISTENT"
    assert result["spread_over_original_15pct"] is True
    assert result["historical_fills"]==0
    assert result["historical_alpha_validated"] is False
    assert result["reason"]=="ACTED_SIDE_NEAR_INDEPENDENT_FAIR_VALUE_OTHERSIDE_SUSPECT"
    assert result["volatility_source_id"]!=result["acted_quote_source_id"]


@pytest.mark.parametrize("action",["buy","sell"])
def test_suspicious_acting_side_rejected_even_if_other_side_near_fair(action):
    q=evidence(action)
    fair=model()
    if action=="buy":
        q=replace(q,bid=fair,ask=fair+.4)
    else:
        q=replace(q,bid=fair-.4,ask=fair)
    result=classify_action_side(q)
    assert result["status"]=="REJECT_ACTION_SIDE_DEVIATION"
    assert result["reason"]==("BUY_ASK_ABOVE_INDEPENDENT_FAIR_RANGE" if action=="buy"
                              else "SELL_BID_BELOW_INDEPENDENT_FAIR_RANGE")


def test_wide_quote_without_independent_model_cannot_be_automatically_accepted():
    q=evidence()
    assert classify_action_side(replace(q,iv_derived_from_current_acted_quote=True))[
        "status"]=="ABSTAIN_UNTRUSTED_REFERENCE"
    assert classify_action_side(replace(q,iv_source_id=q.acted_quote_source_id))[
        "status"]=="ABSTAIN_UNTRUSTED_REFERENCE"
    assert classify_action_side(replace(q,standard_100_share_deliverable=False))[
        "status"]=="ABSTAIN_UNTRUSTED_REFERENCE"


def test_action_side_must_have_sufficient_displayed_size():
    q=evidence("sell")
    assert classify_action_side(replace(q,bid_size=1))["status"]=="REJECT_ACTION_SIDE_SIZE"
    q=evidence("buy")
    assert classify_action_side(replace(q,ask_size=1))["status"]=="REJECT_ACTION_SIDE_SIZE"


def test_spot_and_volatility_must_precede_action_not_future():
    q=evidence()
    assert classify_action_side(replace(q,spot_at=NOW+timedelta(milliseconds=1)))[
        "status"]=="ABSTAIN_STALE_OR_FUTURE_REFERENCE"
    assert classify_action_side(replace(q,volatility_at=NOW-timedelta(seconds=11)))[
        "status"]=="ABSTAIN_STALE_OR_FUTURE_REFERENCE"
    assert classify_action_side(replace(q,quote_at=NOW-timedelta(seconds=2)))[
        "status"]=="ABSTAIN_STALE_OR_FUTURE_REFERENCE"
    assert classify_action_side(replace(q,historical_rate_observed_at=NOW+timedelta(seconds=1)))[
        "status"]=="ABSTAIN_STALE_OR_FUTURE_REFERENCE"
    assert classify_action_side(replace(q,expiration_at=NOW))[
        "status"]=="ABSTAIN_STALE_OR_FUTURE_REFERENCE"


def test_uninformative_model_range_must_abstain():
    q=evidence()
    r=classify_action_side(replace(
        q,independent_iv_lower=.2,independent_iv_upper=1.1))
    assert r["status"]=="ABSTAIN_MODEL_UNCERTAIN"


def test_too_good_to_be_true_not_fake_arb_profit():
    q=evidence("buy")
    fair=model()
    r=classify_action_side(replace(q,ask=fair-.2,bid=fair-.4))
    assert r["status"]=="ABSTAIN_TOO_FAVORABLE_TO_VERIFY"
    q=evidence("sell")
    r=classify_action_side(replace(q,bid=fair+.2,ask=fair+.4))
    assert r["status"]=="ABSTAIN_TOO_FAVORABLE_TO_VERIFY"


def test_normal_spread_still_compatible_without_recovery():
    q=evidence("buy",other_side_bad=False)
    r=classify_action_side(q)
    assert r["status"]=="ACTION_SIDE_MODEL_CONSISTENT"
    assert not r["spread_over_original_15pct"]


def test_invalid_crossed_size_and_naive_clock_cannot_be_qualified():
    q=evidence()
    with pytest.raises(QuoteSideError,match="INVALID_PRICE_VOL_OR_SIZE"):
        classify_action_side(replace(q,bid=q.ask+.01))
    with pytest.raises(QuoteSideError,match="DECISION_WITHOUT_TIMEZONE"):
        classify_action_side(replace(q,decision_at=NOW.replace(tzinfo=None)))
    with pytest.raises(QuoteSideError,match="INVALID_PRICE_VOL_OR_SIZE"):
        classify_action_side(replace(q,contracts=0))
