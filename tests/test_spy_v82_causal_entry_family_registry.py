from __future__ import annotations

from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

import pytest

from packages.simulation import spy_v82_causal_entry_family_registry as v82

ET=ZoneInfo("America/New_York")
DAY="2025-08-20"
SHA="c"*64


def bars(*,first_open="100",hi="102",lo="98",first_last="101",
         recent_high="102.1",recent_low="99",last="103",minutes=10):
    result=[]
    start=datetime.fromisoformat(DAY+"T09:30:00-04:00")
    for i in range(minutes):
        at=start+timedelta(minutes=i)
        if i<5:
            values={"open":first_open,"high":hi,"low":lo,
                    "close":first_last}
        else:
            values={"open":"100","high":recent_high,
                    "low":recent_low,
                    "close":last if i==9 else "101"}
        if i==0:
            values["high"]=max((float(hi),float(first_open)))
            values["low"]=min((float(lo),float(first_open)))
        result.append({
            "minute_at_et":at.isoformat(),
            "available_at_et":(at+timedelta(minutes=1)).isoformat(),
            **{k:str(v) for k,v in values.items()},
        })
    return result


def evaluate(family,rows,**kwargs):
    return v82.evaluate(family,session=DAY,stock_source_sha=SHA,
                        bars=rows,market_session_verified=True,**kwargs)


def test_continuation_uses_only_completed_0940_bars():
    r=evaluate("orb_continuation_0940",
               bars(recent_high="104",recent_low="100",last="103"))
    assert r["direction"]=="CALL"
    assert r["decision_at_et"].endswith("09:40:01-04:00")
    assert r["status"]=="OPTIONS_CANDIDATE_SOURCE_SELECTION_REQUIRED"
    assert r["actual_orders"]==r["broker_fills"]==0
    assert r["stock_fallback_status"]=="UNPRICED_AND_UNAUTHORIZED"


def test_failed_breakout_fade_is_distinct_from_continuation():
    r=evaluate("failed_breakout_fade_0940",
               bars(recent_high="103",recent_low="99",last="100"))
    assert r["direction"]=="PUT"
    assert r["decision_at_et"].endswith("09:40:01-04:00")
    cont=evaluate("orb_continuation_0940",
                  bars(recent_high="103",recent_low="99",last="100"))
    assert cont["direction"] is None
    assert cont["status"]=="NO_SIGNAL"
    assert cont["fingerprint"]!=r["fingerprint"]


def test_gap_mean_reversion_0935_is_prior_close_qualified():
    r=evaluate("gap_fade_0935",
               bars(first_open="103",hi="104",lo="100",
                    first_last="101",minutes=5),
               prior_close="100",
               prior_close_at_et="2025-08-19T15:59:00-04:00",
               prior_close_available_at_et="2025-08-19T16:00:00-04:00")
    assert r["direction"]=="PUT"
    assert v82.REGISTRY["gap_fade_0935"]["minimum_gap_pct"]=="0.60"
    assert r["source_bar_count"]==5
    assert r["features"]["prior_closing_bar_publication_independently_proven"] is False


def test_unclosed_or_future_bar_rejected_without_source_calls():
    future=bars(recent_high="104",recent_low="100",last="103")
    future[-1]["available_at_et"]=DAY+"T09:40:02-04:00"
    with pytest.raises(v82.V82Error,match="FUTURE_OR_NOT_YET_CLOSED"):
        evaluate("orb_continuation_0940",future)
    missing=bars()[:-1]
    with pytest.raises(v82.V82Error,match="EXACT_REQUIRED"):
        evaluate("orb_continuation_0940",missing)


def test_invalid_stock_source_identity_or_future_prior_close_blocked():
    with pytest.raises(v82.V82Error,match="SOURCE_OR_SESSION"):
        v82.evaluate("orb_continuation_0940",session=DAY,
                     stock_source_sha=SHA,bars=bars(),
                     market_session_verified=False)
    with pytest.raises(v82.V82Error,match="PRIOR_CLOSE_FUTURE"):
        evaluate("gap_fade_0935",
                 bars(first_open="103",hi="104",lo="100",
                      first_last="101",minutes=5),
                 prior_close="100",
                 prior_close_at_et="2025-08-20T09:40:00-04:00",
                 prior_close_available_at_et="2025-08-20T09:41:00-04:00")


def test_exact_option_demand_reuses_normalized_v39_provider_shape():
    r=evaluate("orb_continuation_0940",
               bars(recent_high="104",recent_low="100",last="103"))
    source=v82.exact_option_demand(
        r,selected_contract={
            "symbol":"SPY","date_et":DAY,
            "expiration":DAY,"strike":"650","right":"call",
        },
        selection_at_et=DAY+"T09:39:59-04:00",
        selection_source_sha256="d"*64,
    )
    assert source["method"]=="option_history_exact_quote_tape"
    assert source["kwargs"]["start_time_et"]=="09:40:01.000"
    assert source["query_id"]
    item=v82.v39_demand(source)
    assert item["candidate_id"].startswith("SPY_2025-08-20_orb_continuation")
    assert item["method"]==source["method"]
    assert not source["provider_requests"] and not source["broker_orders"]


def test_future_selected_contract_or_wrong_right_cannot_request_source():
    r=evaluate("orb_continuation_0940",
               bars(recent_high="104",recent_low="100",last="103"))
    kwargs={
        "selected_contract":{
            "symbol":"SPY","date_et":DAY,
            "expiration":DAY,"strike":"650","right":"put",
        },
        "selection_at_et":DAY+"T09:39:59-04:00",
        "selection_source_sha256":"d"*64,
    }
    with pytest.raises(v82.V82Error,match="CONTRACT_NOT_ALIGNED"):
        v82.exact_option_demand(r,**kwargs)
    kwargs["selected_contract"]["right"]="call"
    kwargs["selection_at_et"]=DAY+"T09:40:01-04:00"
    with pytest.raises(v82.V82Error,match="FUTURE_SELECTED"):
        v82.exact_option_demand(r,**kwargs)


def test_no_signal_does_not_waste_paid_option_requests():
    r=evaluate("orb_continuation_0940",
               bars(recent_high="102.1",recent_low="99",last="101"))
    assert r["status"]=="NO_SIGNAL"
    with pytest.raises(v82.V82Error,match="NO_SIGNAL_CANNOT_DEMAND"):
        v82.exact_option_demand(r,selected_contract={
            "symbol":"SPY","date_et":DAY,
            "expiration":DAY,"strike":"650","right":"call",
        },selection_at_et=DAY+"T09:39:59-04:00",
        selection_source_sha256="d"*64)
