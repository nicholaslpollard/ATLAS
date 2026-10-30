from __future__ import annotations

from copy import deepcopy
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import pytest

from packages.strategies.options_external_research_catalog_v51 import (
    CANDIDATES, CONTRACT as REGISTRY_CONTRACT, registry,
)
from packages.strategies.spy_0dte_opening_range_candidate_v51 import (
    ALL_DAYS, BASE, CONTRACT as ORB_CONTRACT, DEMAND_CONTRACT,
    OrbError, exact_entry_demands, first_breakout_candidate,
)

EASTERN=ZoneInfo("America/New_York")


def bar(day="2025-06-09",minute=0,*,high=101,low=99,open_=100,close=100,
        published=True):
    start=datetime.fromisoformat(f"{day}T09:30:00").replace(tzinfo=EASTERN)+timedelta(minutes=minute)
    return {
        "symbol":"SPY",
        "bar_start_et":start.isoformat(),
        "available_at_et":(start+timedelta(minutes=1)).isoformat(),
        "open":str(open_),"high":str(high),"low":str(low),"close":str(close),
        "source_query_id":f"spy_{day}_{minute}",
        "source_sha256":"a"*64,
        "first_publication_proven":published,
    }


def bars(day="2025-06-09"):
    raw=[bar(day,i) for i in range(5)]
    raw.append(bar(day,5,high=100.5,low=99.5,open_=100,close=100.1))
    raw.append(bar(day,6,high=102,low=100,open_=100.1,close=101.8))
    raw.append(bar(day,7,high=103,low=100,open_=101,close=102))
    return raw


def verified_tick(day="2025-06-09", spot="101.8", when="09:36:25"):
    return {
        "first_breakout_tick_verified":True,
        "same_day_first_breakout_certified":True,
        "timestamp_et":f"{day}T{when}-04:00",
        "available_at_et":f"{day}T{when}-04:00",
        "underlying_spot":spot,
        "source_query_id":"minute-independent-tick-source",
        "source_sha256":"b"*64,
    }


def test_external_registry_distinguishes_seven_primary_and_three_watch():
    r=registry()
    assert r["contract"]==REGISTRY_CONTRACT
    assert r["primary_candidate_count"]==7
    assert r["watch_candidate_count"]==3
    assert len(r["entries"])==10
    assert len(set(x["id"] for x in r["entries"]))==10
    assert [x["rank"] for x in r["entries"]]==list(range(1,11))
    assert all(x["atlas_historical_net_pnl"] is None for x in r["entries"])
    assert all(x["atlas_strategy_promotion_authorized"] is False for x in r["entries"])
    assert r["atlas_live_order_authority"] is False
    a=r["entries"][0]
    assert a["claims"]["trades"]==303
    assert "OPTIMIZED_IN_SAMPLE" in a["evidence_type"]
    assert r["entries"][1]["claims"]["third_party_combined_spxw_cagr_pct"]=="17.58"
    assert r["entries"][1]["claims"]["independent_spy_adaptation_combined_cagr_pct"]=="14.91"
    a["claims"]["trades"]=100
    assert registry()["entries"][0]["claims"]["trades"]==303


def test_opening_range_excludes_0935_minute_and_uses_first_breakout_candidate():
    t=first_breakout_candidate(bars())
    assert t["contract"]==ORB_CONTRACT
    assert t["date_et"]=="2025-06-09"
    assert t["opening_high"]=="101"
    assert t["opening_low"]=="99"
    assert t["first_possible_breakout_bar"]["bar_start_et"].startswith("2025-06-09T09:36:00")
    assert t["first_possible_breakout_bar"]["possible_breakout_direction"]=="CALL"
    assert t["status"]=="POSSIBLE_FIRST_BREAKOUT_NEEDS_TICK_CONFIRMATION"
    assert t["original_0dte_option_trades_executed"]==0
    assert t["requires_exact_tick_first_breakout_and_option_quotes"]


def test_source_only_mwf_versus_separately_registered_all_weekday_variant():
    t=first_breakout_candidate(bars("2025-06-10"),policy=BASE)
    assert t["status"]=="WEEKDAY_EXCLUDED_BY_FROZEN_STRATEGY"
    assert t["first_possible_breakout_bar"] is None
    alt=first_breakout_candidate(bars("2025-06-10"),policy=ALL_DAYS)
    assert alt["status"]=="POSSIBLE_FIRST_BREAKOUT_NEEDS_TICK_CONFIRMATION"
    assert alt["strategy_version"]!=t["strategy_version"]
    assert alt["original_0dte_option_trades_executed"]==0


def test_both_sides_breached_same_minute_is_ambiguous_not_selected_after_fact():
    raw=bars()
    raw[5]=bar(minute=5,high=103,low=98,open_=100,close=101)
    t=first_breakout_candidate(raw)
    assert t["status"]=="AMBIGUOUS_INTRAMINUTE_BREAKOUT"
    assert t["first_possible_breakout_bar"]["possible_breakout_direction"]=="AMBIGUOUS_BOTH"
    with pytest.raises(OrbError,match="NOT_ELIGIBLE"):
        exact_entry_demands(t,verified_tick())


def test_missing_opening_minute_or_unknown_pit_publication_fail_closed():
    missing=bars()[1:]
    s=first_breakout_candidate(missing)
    assert s["status"]=="OPENING_RANGE_INCOMPLETE"
    raw=bars()
    raw[2]["first_publication_proven"]=False
    s=first_breakout_candidate(raw)
    assert s["status"]=="SOURCE_PUBLICATION_UNQUALIFIED"
    raw=bars()
    raw[6]["first_publication_proven"]=False
    s=first_breakout_candidate(raw)
    assert s["status"]=="SOURCE_PUBLICATION_UNQUALIFIED"
    with pytest.raises(OrbError,match="FUTURE_MINUTE"):
        raw=bars()
        raw[0]["available_at_et"]=raw[0]["bar_start_et"]
        first_breakout_candidate(raw)


def test_first_tick_requires_independent_asof_provenance_before_demand_creation():
    c=first_breakout_candidate(bars())
    d=exact_entry_demands(c,verified_tick())
    assert d["contract"]==DEMAND_CONTRACT
    assert d["query_count"]==3
    assert d["selected_original_contract"]=={
        "underlying":"SPY","expiry":"2025-06-09","strike":"102","right":"call",
    }
    assert [x["purpose"] for x in d["demands"]]==[
        "order_reference","independent_action_plus_1s","independent_action_plus_3s"
    ]
    assert [x["kwargs"]["time_of_day_et"] for x in d["demands"]]==[
        "09:36:25.000","09:36:26.000","09:36:28.000"
    ]
    assert d["historical_quote_availability_qualified"] is False
    assert d["historical_trade_executed"] is False
    assert all(x["method"]=="option_at_time_quote" for x in d["demands"])
    assert all(x["kwargs"]["expiration"]==x["kwargs"]["date_et"] for x in d["demands"])
    assert d["exit_watches_must_be_generated_on_each_future_source_observation"]


def test_tampered_candidate_wrong_tick_or_future_minute_do_not_generate_option_trade():
    c=first_breakout_candidate(bars())
    tampered=deepcopy(c)
    tampered["opening_high"]="95"
    with pytest.raises(OrbError,match="SIGNED"):
        exact_entry_demands(tampered,verified_tick())
    bad=verified_tick()
    bad["source_sha256"]=None
    with pytest.raises(OrbError,match="PROVENANCE"):
        exact_entry_demands(c,bad)
    bad=verified_tick(spot="100")
    with pytest.raises(OrbError,match="DIRECTION"):
        exact_entry_demands(c,bad)
    bad=verified_tick(when="09:37:00")
    with pytest.raises(OrbError,match="FIRST_CANDIDATE"):
        exact_entry_demands(c,bad)
    bad=verified_tick(when="09:36:25")
    bad["available_at_et"]="2025-06-09T09:36:24-04:00"
    with pytest.raises(OrbError,match="TICK_TIME"):
        exact_entry_demands(c,bad)
    with pytest.raises(OrbError,match="UNREGISTERED"):
        exact_entry_demands(c,verified_tick(),action_lag_seconds=(0,5))


def test_missing_breakout_is_not_equivalent_to_a_nonprofitable_historical_trade():
    data=[bar(minute=i,high=101,low=99) for i in range(20)]
    c=first_breakout_candidate(data)
    assert c["status"]=="NO_BREAKOUT_WITHIN_OBSERVED_MINUTE_BARS"
    assert c["first_possible_breakout_bar"] is None
    assert c["qualified_historical_broker_fills"]==0
    assert c["original_0dte_option_trades_executed"]==0


def test_incorrect_bar_or_duplicate_or_cross_session_refused():
    data=bars()
    with pytest.raises(OrbError,match="DUPLICATE"):
        first_breakout_candidate(data+[data[1]])
    data=bars()
    data[1]["high"]="90"
    with pytest.raises(OrbError,match="OHLC_STRUCTURE"):
        first_breakout_candidate(data)
    data=bars()
    data[2]["symbol"]="SPX"
    with pytest.raises(OrbError,match="WRONG_UNDERLYING"):
        first_breakout_candidate(data)
    data=bars()
    data[2]["bar_start_et"]="2025-06-10T09:32:00-04:00"
    with pytest.raises(OrbError,match="MULTIPLE_SESSIONS"):
        first_breakout_candidate(data)


def test_missing_minute_before_first_breakout_blocks_claim_of_first_trade():
    b=bars()
    b=[x for i,x in enumerate(b) if i!=5]
    result=first_breakout_candidate(b)
    assert result["status"]=="BREAKOUT_MINUTE_SEQUENCE_INCOMPLETE"
    assert "MISSING_MINUTE_BEFORE_FIRST_POSSIBLE_BREAKOUT" in result["reason_codes"]


def test_verified_breakout_tick_cannot_be_invented_from_minutes_or_delayed_until_after_close():
    c=first_breakout_candidate(bars())
    late=verified_tick()
    late["available_at_et"]="2025-06-09T09:36:31-04:00"
    with pytest.raises(OrbError,match="PUBLICATION_LAG"):
        exact_entry_demands(c,late)
    late=verified_tick()
    late["source_sha256"]="not-a-sha"
    with pytest.raises(OrbError,match="PROVENANCE"):
        exact_entry_demands(c,late)
