from __future__ import annotations

from datetime import date,datetime,timedelta
from pathlib import Path
import json
from unittest.mock import patch

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v86_original_option_exit_recheck import (
    DWELLS,V86Error,recheck,signed,verified,
)
from scripts import run_spy_v86_original_exit_order_recheck as v86


DAY="2025-07-02"
ET="-04:00"


def _example(*,original_marketable=False,no_entry=False):
    req={"provider":"thetadata","method":"option_history_exact_quote_tape",
         "kwargs":{"date_et":DAY,"expiration":DAY,"symbol":"SPY","strike":"617",
                   "right":"call","interval":"1s",
                   "start_time_et":"09:40:01.000","end_time_et":"15:30:00.000"}}
    qid=_fingerprint(req)
    sha="a"*64
    original_bid="1.96" if original_marketable else "1.90"
    t=signed({
        "contract":"atlas-v84-offline-three-family-option-quote-shadow-v1",
        "session":DAY,"strategy":"failed_breakout_fade_0940",
        "policy":"balanced_35_100","lag_seconds":1,
        "decision_at_et":f"{DAY}T09:40:01{ET}",
        "entry_action_at_et":f"{DAY}T09:40:02{ET}" if not no_entry else None,
        "entry_debit_usd":"100.65" if not no_entry else None,
        "entry_qty":1 if not no_entry else 0,
        "exit":{"trigger_at_et":f"{DAY}T09:40:04{ET}",
                "action_at_et":f"{DAY}T09:40:05{ET}",
                "trigger_bid":"1.95","action_bid":original_bid,
                "reason":"PROFIT_TARGET",
                "original_trigger_limit_marketable_at_action":original_marketable,
                "quote_reference_credit_usd": "195.35" if original_marketable else "189.35"}
            if not no_entry else None,
        "hard_exit_at_et":f"{DAY}T15:05:00{ET}",
        "status":"NO_ENTRY" if no_entry else "CLOSED_QUOTE_REFERENCE",
        "reason":"ENTRY_ASK_ADVERSE_DRIFT_GT_1PCT" if no_entry else "PROFIT_TARGET",
        "source_query_id":qid,"source_sha256":sha,
        "quote_reference_pnl_usd":None if no_entry else "88.70",
        "quote_reference_pnl_2pct_exit_haircut_usd":None if no_entry else "84.90",
        "actual_broker_fills":0,"provider_requests":0,
        "observed_ask_bid_not_broker_fills":True,
    })
    source={"status":"CACHE_HIT","query_id":qid,"source_sha256":sha,
            "exact_requirement":req,"source_rows":[]}
    base=datetime.fromisoformat(f"{DAY}T09:40:01{ET}")
    bids={0:"1.85",1:"1.86",2:"1.87",3:"1.95",4:original_bid,
          5:"1.91",6:"1.96",7:"1.93",8:"1.90",9:"1.91",10:"1.90",
          11:"1.90",12:"1.90",13:"1.90",14:"1.91",15:"1.90"}
    prepared=[(base+timedelta(seconds=i),
               {"bid":bid,"ask":"2.05","bid_size":10,"ask_size":10},
               None,i) for i,bid in bids.items()]
    return t,source,prepared


def test_delayed_limit_recovery_uses_original_trigger_not_later_bid():
    t,s,p=_example()
    r=recheck(t,s,p,dwell_seconds=3)
    assert verified(r)
    assert r["outcome_class"]=="LATER_FIXED_LIMIT_QUOTE_MARKETABLE"
    assert r["exit_action_at_et"]==f"{DAY}T09:40:07{ET}"
    assert r["exit_bid_reference"]=="1.95"
    assert r["quote_reference_credit_usd"]=="194.35"
    assert r["quote_reference_pnl_usd"]=="93.70"
    assert r["provider_requests"]==r["actual_broker_fills"]==0


def test_zero_second_rest_requires_new_latency_and_reprice():
    t,s,p=_example()
    r=recheck(t,s,p,dwell_seconds=0)
    assert r["outcome_class"]=="REPRICED_BID_QUOTE_SHADOW"
    assert r["exit_action_at_et"]==f"{DAY}T09:40:06{ET}"
    assert r["exit_bid_reference"]=="1.91"
    assert r["quote_reference_pnl_usd"]=="89.70"
    assert r["historical_order_cancel_replace_unverified"]


def test_original_marketable_quote_kept_without_future_lookup():
    t,s,p=_example(original_marketable=True)
    r=recheck(t,s,p,dwell_seconds=30)
    assert r["outcome_class"]=="ORIGINAL_LIMIT_QUOTE_MARKETABLE"
    assert r["exit_action_at_et"]==f"{DAY}T09:40:05{ET}"
    assert r["quote_observations_examined"]==0
    assert r["exit_bid_reference"]=="1.96"


def test_missing_fallback_action_censors_and_never_creates_cash():
    t,s,p=_example()
    p=[r for r in p if r[0]<=datetime.fromisoformat(f"{DAY}T09:40:05{ET}")]
    r=recheck(t,s,p,dwell_seconds=0)
    assert r["status"]=="UNRESOLVED_POSITION"
    assert r["quote_reference_pnl_usd"] is None
    assert r["expiry_or_exercise_cash_unknown"]


def test_frozen_three_second_exit_lag_must_be_respected():
    original,source,tape=_example()
    payload={k:v for k,v in original.items() if k!="fingerprint"}
    payload["lag_seconds"]=3
    mutated=signed(payload)
    assert verified(mutated)
    with pytest.raises(V86Error,match="LATENCY_SHORTER_THAN_REGISTERED"):
        recheck(mutated,source,tape,dwell_seconds=10)


def test_signed_but_unreproducible_original_action_quote_is_rejected():
    original,source,tape=_example()
    payload={k:v for k,v in original.items() if k!="fingerprint"}
    payload["exit"]={**original["exit"],"action_bid":"1.91"}
    altered=signed(payload)
    assert verified(altered)
    with pytest.raises(V86Error,match="QUOTE_NOT_REPRODUCIBLE"):
        recheck(altered,source,tape,dwell_seconds=10)


def test_rejected_entry_is_frozen_and_never_turned_into_exit():
    t,s,p=_example(no_entry=True)
    r=recheck(t,s,p,dwell_seconds=10)
    assert r["status"]=="NO_ENTRY"
    assert r["quote_reference_pnl_usd"] is None
    assert r["quote_observations_examined"]==0


def test_altered_v84_signed_trial_or_original_source_is_fatal():
    t,s,p=_example()
    t["exit"]["trigger_bid"]="4"
    with pytest.raises(V86Error,match="SOURCE_OR_EXECUTION_DRIFT"):
        recheck(t,s,p,dwell_seconds=3)
    t,s,p=_example()
    s["source_sha256"]="b"*64
    with pytest.raises(V86Error,match="SOURCE_OR_EXECUTION_DRIFT"):
        recheck(t,s,p,dwell_seconds=3)


def test_v86_provenance_101_archives_606_journals_2424_rechecks(tmp_path):
    # Contract-test the orchestration with synthetic original reports; no
    # actual SPY provider bytes are embedded in this test or in Git.
    p83=tmp_path/"v83";p84=tmp_path/"v84";p83.mkdir();p84.mkdir()
    one,one_source,one_prepared=_example()
    pre=signed({"contract":"pretend-v83-parent","broker_orders":0})
    early=signed({"contract":"pretend-v84-parent","broker_orders":0})
    screen=signed({"contract":"pretend-v83-screen","cases":[]})
    plans=[];requests={};trials=[];original_lookup={};demand_bindings={}
    for i in range(101):
        day=(date(2025,7,2)+timedelta(days=i)).isoformat()
        kwargs={**one_source["exact_requirement"]["kwargs"],
                "date_et":day,"expiration":day}
        req={"provider":"thetadata","method":"option_history_exact_quote_tape",
             "kwargs":kwargs}
        qid=_fingerprint(req)
        plans.append({"query_id":qid,"method":req["method"],"kwargs":kwargs})
        demand_bindings[qid]={"query_id":qid,"method":req["method"],"kwargs":kwargs}
        srcrows=[]
        for j in range(17):
            bid="1.91" if j!=9 else "1.96"
            if j==3:bid="1.95"
            if j in (4,6):bid="1.90"
            srcrows.append({
                "ms_of_day":(9*3600+40*60+1+j)*1000,
                "symbol":"SPY","expiration":day,"strike":"617","right":"call",
                "bid":bid,"ask":"2.05","bid_size":10,"ask_size":10,
            })
        source={"status":"CACHE_HIT","query_id":qid,
                "source_sha256":"a"*64,"exact_requirement":req,
                "source_rows":tuple(srcrows)}
        requests[qid]=source
        original_lookup[qid]={"source_sha256":"a"*64}
        for policy in ("control_50_100","balanced_35_100","runner_35_150"):
            for lag in (1,3):
                base={k:v for k,v in one.items() if k!="fingerprint"}
                base.update({
                    "session":day,"policy":policy,"lag_seconds":lag,
                    "decision_at_et":f"{day}T09:40:01{ET}",
                    "entry_action_at_et":f"{day}T09:40:02{ET}",
                    "hard_exit_at_et":f"{day}T15:05:00{ET}",
                    "source_query_id":qid,
                    "exit":{**base["exit"],
                            "trigger_at_et":f"{day}T09:40:04{ET}",
                            "action_at_et":f"{day}T09:40:{5 if lag==1 else 7:02d}{ET}"},
                })
                trials.append(signed(base))
    settings=object()
    with patch.object(v86,"verify_input",return_value=(pre,screen,early,{},trials)), \
         patch.object(v86,"_load_campaign",return_value=(screen,{"demands":plans},pre,
                                                         demand_bindings,original_lookup)), \
         patch.object(v86,"prepare_original_tape",wraps=v86.prepare_original_tape), \
         patch.object(v86,"simulate",wraps=v86.simulate):
        r=v86.run(p83,p84,tmp_path/"out",
            settings_factory=lambda *a:settings,
            source_reader=lambda settings,qid:{
                "cache_evidence":"CACHE_HIT","source":requests[qid]},
            announce=lambda _:None)
    assert verified(r)
    assert r["original_sha_verified_option_tapes"]==101
    assert r["original_sha_verified_v84_trials"]==606
    assert r["v86_recheck_journals"]==2424
    assert r["portfolio_scenarios"]==96
    assert r["provider_calls"]==r["broker_orders"]==0
    assert (tmp_path/"out"/"portfolio_comparisons.json").is_file()
    assert len(list((tmp_path/"out"/"journals").glob("*.json.gz")))==2424


def test_outcome_rejects_missing_or_modified_original_source_before_writing(tmp_path):
    p83=tmp_path/"v83";p84=tmp_path/"v84";p83.mkdir();p84.mkdir()
    with pytest.raises(Exception):
        v86.run(p83,p84,tmp_path/"no_outputs",announce=lambda _:None)
    assert not (tmp_path/"no_outputs").exists()
