from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v84_offline_three_family_economics import (
    V84Error, prepare_original_tape, replay, signed, verified, POLICIES, LAGS,
)
from scripts import run_spy_v84_offline_three_family_economics as campaign

DAY = "2025-08-20"
SOURCE_SHA = "a"*64


def fixture(*, drift=False, lower_on_action=False):
    decision = signed({
        "contract":"atlas-v82-options-first-three-independent-entry-family-registry-v1",
        "strategy_id":"orb_continuation_0940",
        "session":DAY,"direction":"CALL","decision_at_et":DAY+"T09:40:01-04:00",
    })
    kwargs = {
        "symbol":"SPY","date_et":DAY,"expiration":DAY,
        "right":"call","strike":"650","interval":"1s",
        "start_time_et":"09:40:01.000","end_time_et":"15:30:00.000",
    }
    requirement = {"provider":"thetadata","method":"option_history_exact_quote_tape","kwargs":kwargs}
    demand = signed({
        "strategy_decision_sha":decision["fingerprint"],
        "candidate_id":"SPY_2025-08-20_orb_continuation_0940_call",
        "method":requirement["method"],"kwargs":kwargs,
        "query_id":_fingerprint(requirement),
    })
    rows=[]
    start=datetime.fromisoformat(DAY+"T09:40:01-04:00")
    for i in range(80):
        t=start+timedelta(seconds=i)
        if i==0:
            bid,ask="0.99","1.00"
        elif i<4:
            bid,ask=("1.05","1.06") if drift else ("0.99","1.00")
        elif i==10:
            bid,ask="2.00","2.03"
        elif i==11:
            bid,ask=("1.95","1.98") if lower_on_action else ("2.00","2.03")
        else:
            bid,ask="1.00","1.02"
        rows.append({
            "ms_of_day":(9*3600+40*60+1+i)*1000,
            "symbol":"SPY","right":"call","expiration":DAY,"strike":"650",
            "bid":bid,"ask":ask,"bid_size":10,"ask_size":10,
        })
    source={"status":"CACHE_HIT","source_sha256":SOURCE_SHA,
            "query_id":demand["query_id"],"exact_requirement":requirement,
            "source_rows":tuple(rows)}
    return decision,demand,source


def test_source_binds_exact_quote_and_dynamic_exit_limit_marketability():
    d,need,source=fixture(lower_on_action=True)
    series=prepare_original_tape(source,{
        "symbol":"SPY","date_et":DAY,"expiration":DAY,"strike":"650","right":"call"
    },DAY)
    assert len(series)==80
    r=replay(d,need,source,series,policy="control_50_100",
             lag_seconds=1,market_close_et=datetime.fromisoformat(DAY+"T16:00:00-04:00"))
    assert verified(r)
    assert r["status"]=="CLOSED_QUOTE_REFERENCE"
    assert r["entry_action_ask"]=="1.00"
    assert r["entry_qty"]==4
    assert r["exit"]["reason"]=="PROFIT_TARGET"
    assert r["exit"]["original_trigger_limit_marketable_at_action"] is False
    assert r["exit"]["requires_new_lower_limit_if_false"] is True
    assert r["actual_broker_fills"]==r["provider_requests"]==0
    assert r["quote_reference_pnl_usd"] is not None
    assert r["quote_reference_pnl_2pct_exit_haircut_usd"] is not None
    assert not r["portfolio_cash_or_position_conflicts_not_simulated"] is False


def test_adverse_entry_drift_rejected_without_false_execution():
    d,need,source=fixture(drift=True)
    series=prepare_original_tape(source,{
        "symbol":"SPY","date_et":DAY,"expiration":DAY,"strike":"650","right":"call"
    },DAY)
    result=replay(d,need,source,series,policy="balanced_35_100",
                  lag_seconds=1,market_close_et=datetime.fromisoformat(DAY+"T16:00:00-04:00"))
    assert result["status"]=="NO_ENTRY"
    assert result["reason"]=="ENTRY_ASK_ADVERSE_DRIFT_GT_1PCT"
    assert result["entry_debit_usd"] is None
    assert result["quote_reference_pnl_usd"] is None


def test_early_close_hard_exit_cannot_extend_beyond_archived_tape():
    d,need,source=fixture()
    demand=signed({**{k:v for k,v in need.items() if k!="fingerprint"},
                   "kwargs":{**need["kwargs"],"end_time_et":"12:05:00.000"},
                   "query_id":_fingerprint({"provider":"thetadata","method":need["method"],
                                            "kwargs":{**need["kwargs"],"end_time_et":"12:05:00.000"}})})
    source["query_id"]=demand["query_id"]
    source["exact_requirement"]["kwargs"]["end_time_et"]="12:05:00.000"
    prepared=prepare_original_tape(source,{"symbol":"SPY","date_et":DAY,
                                "expiration":DAY,"strike":"650","right":"call"},DAY)
    r=replay(d,demand,source,prepared,policy="runner_35_150",
             lag_seconds=3,market_close_et=datetime.fromisoformat(DAY+"T13:00:00-04:00"))
    assert r["hard_exit_at_et"].endswith("12:05:00-04:00")
    assert r["actual_broker_fills"]==0
    with pytest.raises(V84Error,match="HARD_EXIT_OUTSIDE"):
        replay(d,demand,source,prepared,policy="runner_35_150",
               lag_seconds=3,market_close_et=datetime.fromisoformat(DAY+"T16:00:00-04:00"))


def test_campaign_signed_v83_read_only_replay(tmp_path):
    d,need,source=fixture()
    source_dir=tmp_path/"v83"
    source_dir.mkdir()
    source_case={
        "session":DAY,"strategy":"orb_continuation_0940",
        "status":"OPTIONS_EXACT_SOURCE_DEMAND_PREPARED",
        "source_demand_sha":need["fingerprint"],"causal_decision":d,
    }
    entry=signed({"contract":campaign.V83,"cases":[source_case]})
    plan=signed({"contract":campaign.V83+"-exact-source-plan-v1",
                 "entry_screen_sha":entry["fingerprint"],"demands":[need]})
    receipts=signed({
        "contract":campaign.V83+"-source-receipts-v1",
        "option_source_plan_sha":plan["fingerprint"],
        "source_use_requested":1,
        "original_provider_source_receipts":[{
            "query_id":need["query_id"],"candidate_id":need["candidate_id"],
            "source_sha256":SOURCE_SHA,"status":"FETCHED_AND_ARCHIVED",
        }],
    })
    summary=signed({
        "contract":campaign.V83+"-summary-v1",
        "entry_screen_sha":entry["fingerprint"],
        "option_source_plan_sha":plan["fingerprint"],
        "source_receipt_report_sha":receipts["fingerprint"],
        "family_cases":1,"planned_exact_option_demands":1,
        "broker_orders":0,"option_selection_and_trade_execution_not_qualified":True,
        "source_resolution":{"status":"ALL_REQUESTED_SOURCES_PRESENT"},
    })
    for name,row in [("entry_screen",entry),("option_source_plan",plan),
                     ("source_receipts",receipts),("summary",summary)]:
        (source_dir/(name+".json")).write_text(json.dumps(row))
    class Cal:
        def is_session(self,day):
            return day==date.fromisoformat(DAY)
        def regular_open_close(self,day):
            return (datetime.fromisoformat(DAY+"T09:30:00-04:00"),
                    datetime.fromisoformat(DAY+"T16:00:00-04:00"))
    calls=[]
    def reader(settings,qid):
        calls.append(qid)
        return {"cache_evidence":"CACHE_HIT","source":source}
    result=campaign.run(source_dir,tmp_path/"out",
        source_reader=reader,settings_factory=lambda *args:object(),
        calendar=Cal(),reporter=lambda x:None)
    assert calls==[need["query_id"]]
    assert result["candidate_sources"]==1
    assert result["trial_count"]==len(POLICIES)*len(LAGS)
    assert result["provider_requests"]==result["broker_orders"]==0
    assert verified(result)
    audit=json.loads((tmp_path/"out"/"candidate_outcomes.json").read_text())
    assert len(audit["trials"])==6
    assert all(Path(tmp_path/"out"/j["journal"]).exists() for j in audit["trials"])
    economics=json.loads((tmp_path/"out"/"window_economics.json").read_text())
    assert verified(economics)
