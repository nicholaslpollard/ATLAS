from __future__ import annotations

from copy import deepcopy
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

import pytest

from packages.strategies.spy_0dte_opening_range_candidate_v51 import (
    first_breakout_candidate,exact_entry_demands,
)
from packages.simulation.spy_0dte_orb_single_long_reference_v51 import (
    replay_orb_quote_reference,OrbReplayError,
)

ET=ZoneInfo("America/New_York")
DAY="2025-06-09"
IDENTITY="SPY:2025-06-09:102:C"


def minutes():
    out=[]
    for n in range(8):
        start=datetime(2025,6,9,9,30,tzinfo=ET)+timedelta(minutes=n)
        if n==5:
            hi,lo,op,cl=("100.5","99.5","100","100.2")
        elif n>=6:
            hi,lo,op,cl=("102","100","100.2","101.8")
        else:
            hi,lo,op,cl=("101","99","100","100")
        out.append({
            "symbol":"SPY","bar_start_et":start.isoformat(),
            "available_at_et":(start+timedelta(minutes=1)).isoformat(),
            "open":op,"high":hi,"low":lo,"close":cl,
            "source_query_id":f"spy-m{n}","source_sha256":"a"*64,
            "first_publication_proven":True,
        })
    return out


def quote(at,bid="1.20",ask="1.25",identity=IDENTITY,publication=True):
    return {
        "contract_identity":identity,
        "timestamp_et":at,"available_at_et":at,
        "bid":bid,"ask":ask,"bid_size":10,"ask_size":10,
        "source_query_id":"source-"+at,"source_sha256":"b"*64,
        "historical_first_publication_verified":publication,
    }


def case():
    cand=first_breakout_candidate(minutes())
    tick={
        "first_breakout_tick_verified":True,"same_day_first_breakout_certified":True,
        "timestamp_et":"2025-06-09T09:36:25-04:00",
        "available_at_et":"2025-06-09T09:36:25-04:00",
        "underlying_spot":"101.8",
        "source_query_id":"exact-tick-source","source_sha256":"c"*64,
    }
    d=exact_entry_demands(cand,tick)
    return {
        "orb_candidate":cand, "verified_entry_demand":d,
        "order_quote":quote("2025-06-09T09:36:25-04:00"),
        "action_quote":quote("2025-06-09T09:36:26-04:00"),
        "intraday_option_reviews":[
            {"at_et":"2025-06-09T09:37:00-04:00",
             "quote":quote("2025-06-09T09:37:00-04:00",bid="2.50",ask="2.55")}
        ],
    }


def run(cases,**kw):
    return replay_orb_quote_reference(cases,**kw)


def test_published_premium_500_whole_contracts_and_separate_fees_profit_exit():
    r=run([case()])
    assert r["contract"].endswith("simulator-v51")
    assert r["opportunity_count"]==1
    assert r["disposition_counts"]=={"MODELED_SINGLE_LONG_ENTRY_QUOTE_REFERENCE":1}
    assert r["terminal_equity_if_complete"]=="25494.80"
    assert r["unresolved_position"] is None
    assert [x["type"] for x in r["events"]]==[
        "DECISION","MODELED_ENTRY_QUOTE_REFERENCE",
        "EXIT_REVIEW","MODELED_EXIT_QUOTE_REFERENCE"]
    assert r["events"][1]["qty"]==4
    assert r["events"][1]["entry_debit_and_fees"]=="502.60"
    assert r["events"][2]["trigger"]=="PROFIT_PLUS_100"
    assert r["events"][2]["observed_option_bid_vs_entry_ask_pct"]=="100"
    assert r["events"][3]["modeled_closed_pnl"]=="494.80"
    assert r["broker_fills_verified"]==0
    assert r["original_published_0dte_pnl_verified"] is False


def test_stop_minus_50_uses_option_bid_vs_original_ask_not_after_fee_pnl():
    c=case()
    c["intraday_option_reviews"][0]["quote"]=quote(
        "2025-06-09T09:37:00-04:00",bid="0.625",ask="0.650")
    r=run([c])
    assert r["events"][2]["trigger"]=="STOP_MINUS_50"
    assert r["terminal_equity_if_complete"] is not None
    assert r["events"][-1]["modeled_closed_pnl"].startswith("-")


def test_no_breakout_decision_is_logged_and_leaves_account_cash_unchanged():
    c=case()
    c["orb_candidate"]=first_breakout_candidate(minutes()[:5])
    c.pop("verified_entry_demand")
    r=run([c])
    assert r["events"][0]["disposition"]=="NO_QUALIFIED_BREAKOUT_SOURCE"
    assert r["events"][0]["first_possible_breakout_bar"] is None
    assert r["terminal_equity_if_complete"]=="25000.00"


def test_missing_delayed_quote_or_unproven_first_publication_cannot_fill():
    c=case()
    c["action_quote"]=None
    r=run([c])
    assert r["events"][0]["disposition"]=="ORDER_OR_ACTION_QUOTE_UNQUALIFIED"
    assert len(r["events"])==1
    c=case()
    c["order_quote"]["historical_first_publication_verified"]=False
    r=run([c])
    assert "PUBLICATION_CLOCK_NOT_INDEPENDENTLY_QUALIFIED" in r["events"][0]["quote_diagnostics"]["order"]["reasons"]


def test_adverse_price_drift_policy_rejects_favorable_hindsight_repricing():
    c=case()
    c["action_quote"]=quote("2025-06-09T09:36:26-04:00",bid="1.27",ask="1.30")
    r=run([c])
    assert r["disposition_counts"]=={"ADVERSE_ACTION_PRICE_CHANGE_OVER_POLICY":1}
    assert len(r["events"])==1
    with pytest.raises(OrbReplayError,match="UNREGISTERED"):
        run([case()],adverse_action_price_change_limit_pct="10")


def test_absent_stop_path_or_missing_required_quote_keeps_equity_null():
    c=case()
    c["intraday_option_reviews"][0]["quote"]=None
    r=run([c])
    assert r["unresolved_position"]["reason"].startswith("UNCERTIFIED")
    assert r["terminal_equity_if_complete"] is None
    assert r["last_cash_excludes_unresolved_mark"]=="24497.40"
    assert [e["type"] for e in r["events"]][-1]=="OPEN_UNRESOLVED"
    c=case()
    c["intraday_option_reviews"]=[{
        "at_et":"2025-06-09T09:40:00-04:00",
        "quote":quote("2025-06-09T09:40:00-04:00",bid="2.50",ask="2.55")
    }]
    r=run([c])
    assert r["terminal_equity_if_complete"] is None
    assert r["events"][2]["missing_path_censored"] is True


def test_full_intraday_path_reaches_1530_time_stop_without_invented_earlier_trigger():
    c=case()
    beginning=datetime(2025,6,9,9,37,tzinfo=ET)
    stop=datetime(2025,6,9,15,30,tzinfo=ET)
    series=[]
    t=beginning
    while t<=stop:
        series.append({"at_et":t.isoformat(),"quote":quote(t.isoformat())})
        t+=timedelta(minutes=1)
    c["intraday_option_reviews"]=series
    r=run([c])
    assert r["events"][-1]["exit_reason"]=="TIME_15:30"
    assert r["unresolved_position"] is None
    assert r["terminal_equity_if_complete"] is not None
    assert r["events"][-2]["missing_path_censored"] is False


def test_one_published_entry_per_day_and_unresolved_cannot_compound_artificially():
    c=case()
    r=run([c,deepcopy(c)])
    assert r["opportunity_count"]==2
    assert r["disposition_counts"]["ONE_TRADE_PER_DAY_ALREADY_EVALUATED"]==1
    assert sum(e["type"]=="MODELED_ENTRY_QUOTE_REFERENCE" for e in r["events"])==1
    c=case()
    c["intraday_option_reviews"]=[]
    r=run([c,deepcopy(c)])
    assert r["terminal_equity_if_complete"] is None
    assert r["disposition_counts"]["UNRESOLVED_EARLIER_POSITION_BLOCKS_CAPITAL"]==1


def test_above_premium_cap_or_invalid_quote_identity_fails_closed():
    c=case()
    c["order_quote"]=quote("2025-06-09T09:36:25-04:00",bid="5.98",ask="6.00")
    c["action_quote"]=quote("2025-06-09T09:36:26-04:00",bid="5.98",ask="6.00")
    r=run([c])
    assert r["events"][0]["disposition"]=="PREMIUM_CAP_OR_AVAILABLE_CASH_INSUFFICIENT"
    c=case()
    c["order_quote"]["contract_identity"]="SPY:2025-06-09:101:C"
    r=run([c])
    assert r["events"][0]["disposition"]=="ORDER_OR_ACTION_QUOTE_UNQUALIFIED"
    assert "EXACT_CONTRACT_IDENTITY_MISMATCH" in r["events"][0]["quote_diagnostics"]["order"]["reasons"]


def test_future_source_claim_and_reverse_clock_and_tampered_candidate_rejected():
    c=case()
    c["order_quote"]["available_at_et"]="2025-06-09T09:36:30-04:00"
    r=run([c])
    assert r["events"][0]["disposition"]=="ORDER_OR_ACTION_QUOTE_UNQUALIFIED"
    c=case()
    c["intraday_option_reviews"].append({
        "at_et":"2025-06-09T09:36:59-04:00",
        "quote":quote("2025-06-09T09:36:59-04:00"),
    })
    with pytest.raises(OrbReplayError,match="OUT_OF_ORDER"):
        run([c])
    c=case()
    c["orb_candidate"]["opening_high"]="1"
    with pytest.raises(OrbReplayError,match="FINGERPRINT"):
        run([c])


def test_later_exit_price_does_not_change_prior_signal_or_entry_ledger():
    a=run([case()])
    c=case()
    c["intraday_option_reviews"][0]["quote"]["bid"]="0.625"
    c["intraday_option_reviews"][0]["quote"]["ask"]="0.650"
    b=run([c])
    assert a["events"][0]==b["events"][0]
    assert a["events"][1]==b["events"][1]
    assert a["events"][2]!=b["events"][2]
    assert a["fingerprint"]!=b["fingerprint"]


def test_full_review_schedule_fails_before_modeling_even_when_early_exit_would_fire():
    # First review at 09:37 realizes +100%; a later invalid 09:36:59
    # record must not be silently ignored as if it were a valid source tape.
    a=case()
    a["intraday_option_reviews"].append({
        "at_et":"2025-06-09T09:36:59-04:00",
        "quote":quote("2025-06-09T09:36:59-04:00"),
    })
    with pytest.raises(OrbReplayError,match="OUT_OF_ORDER"):
        run([a])
    # Invalid date/time bounds similarly fail, regardless of prior profit.
    a=case()
    a["intraday_option_reviews"].append({
        "at_et":"2025-06-10T09:38:00-04:00",
        "quote":quote("2025-06-10T09:38:00-04:00"),
    })
    with pytest.raises(OrbReplayError,match="OUT_OF_ORDER"):
        run([a])
    a=case()
    a["intraday_option_reviews"].append({
        "at_et":"2025-06-09T15:30:01-04:00",
        "quote":quote("2025-06-09T15:30:01-04:00"),
    })
    with pytest.raises(OrbReplayError,match="OUT_OF_ORDER"):
        run([a])


def test_first_profit_exit_still_closes_normally_with_valid_later_unused_source():
    a=case()
    a["intraday_option_reviews"].append({
        "at_et":"2025-06-09T09:38:00-04:00",
        "quote":quote("2025-06-09T09:38:00-04:00"),
    })
    r=run([a])
    assert r["terminal_equity_if_complete"] is not None
    assert [e["type"] for e in r["events"]].count("MODELED_EXIT_QUOTE_REFERENCE")==1
    assert [e["type"] for e in r["events"]].count("EXIT_REVIEW")==1
