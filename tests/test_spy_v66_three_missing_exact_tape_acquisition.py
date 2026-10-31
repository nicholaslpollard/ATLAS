from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts.run_spy_v66_three_missing_exact_tape_acquisition import (
    CONTRACT,SCOPE,V65,V66Error,dispatch,input_sessions,
)


def signed(d):
    return {**d,"fingerprint":_fingerprint(d)}


def report(tmp):
    # Synthesize a complete V65 report with the exact intended V66 inputs.
    # The production parser continues to require the original V65 parent SHA.
    rows=[]
    days=["2025-06-09","2025-06-10","2025-06-11","2025-06-12",
          "2025-06-13","2025-06-16","2025-06-17","2025-06-18",
          "2025-06-19","2025-06-20"]
    for day in days:
        if day in SCOPE:
            exp=SCOPE[day]
            req={"provider":"thetadata","method":"option_history_exact_quote_tape",
                 "kwargs":{
                    "symbol":"SPY","date_et":day,"expiration":day,
                    "right":"call","strike":exp["strike"],
                    "start_time_et":exp["decision"][11:19]+".000",
                    "end_time_et":"15:30:00.000","interval":"1s",
                }}
            row={"session":day,"signal_status":"COMPLETED_BAR_BREAKOUT_DEVELOPMENT",
                 "signal_decision_at_et":exp["decision"],
                 "selected_contract":{
                    "symbol":"SPY","date_et":day,"expiration":day,
                    "right":"call","strike":exp["strike"],
                 },
                 "exact_option_requirement":req,
                 "exact_option_receipt":{
                    "state":"NOT_REGISTERED","query_id":exp["query"]},
                 "standalone_replay_disposition":"NO_ENTRY",
                 "standalone_replay_censor_reason":"OPTION_SOURCE_MISSING_OR_UNQUALIFIED",
            }
        else:
            row={"session":day}
        rows.append(signed(row))
    doc=signed({
        "contract":V65,"start":"2025-06-09","end":"2025-06-20",
        "weekdays_in_calendar_scope":10,
        "session_reports":rows,"provider_requests":0,"broker_orders":0,
    })
    p=tmp/"v65.json"
    p.write_text(json.dumps(doc),encoding="utf-8")
    return p,doc["fingerprint"]


def run_kwargs(tmp,*,states=None,fail_day=None):
    path,digest=report(tmp)
    preflights=[]
    fetches=[]
    verified=[]
    def reader(qid):
        preflights.append(qid)
        state=(states or {}).get(qid,"NOT_REGISTERED")
        if state=="NOT_REGISTERED":
            return None
        day=next(d for d,s in SCOPE.items() if s["query"]==qid)
        item=next(r for r in json.loads(path.read_text())["session_reports"]
                  if r["session"]==day)
        req=item["exact_option_requirement"]
        return (qid,json.dumps(req,sort_keys=True,separators=(",",":")),state,
                "a"*64,3)
    def request(settings,method,kwargs):
        day=kwargs["date_et"]
        fetches.append(day)
        if fail_day==day:
            raise RuntimeError("synthetic ambiguous worker timeout")
        req={"provider":"thetadata","method":method,"kwargs":kwargs}
        return {"query_id":SCOPE[day]["query"],
                "exact_requirement":req,"status":"FETCHED_AND_ARCHIVED",
                "source_sha256":"a"*64}
    def read(settings,qid):
        verified.append(qid)
        day=next(d for d,s in SCOPE.items() if s["query"]==qid)
        source={"status":"CACHE_HIT","query_id":qid,"source_sha256":"a"*64,
                "exact_requirement":next(r for r in json.loads(path.read_text())[
                    "session_reports"] if r["session"]==day)["exact_option_requirement"],
                "source_rows":tuple({"bid":1,"ask":1.02} for _ in range(3))}
        return {"cache_evidence":"CACHE_HIT","source":source}
    kwargs={
        "expected_report_fingerprint":digest,"setting_fn":lambda *args:object(),
        "receipt_reader":reader,"source_get":request,"cache_get":read,
        "emit":lambda msg:None,
    }
    return path,kwargs,preflights,fetches,verified


def test_original_three_exact_queries_cannot_be_rewritten(tmp_path):
    p,fp=report(tmp_path)
    parent,scope=input_sessions(p,expected_report_fingerprint=fp)
    assert parent==fp and len(scope)==3
    assert [x["session"] for x in scope]==list(SCOPE)
    assert [x["query_id"] for x in scope]==[v["query"] for v in SCOPE.values()]


def test_three_first_time_missing_receipts_dispatch_once_each(tmp_path):
    path,kwargs,preflights,calls,verified=run_kwargs(tmp_path)
    out=tmp_path/"out"
    doc=dispatch(path,out,**kwargs)
    assert doc["status"]=="COMPLETE_SOURCE_CENSUS"
    assert len(calls)==3
    assert calls==list(SCOPE)
    assert len(preflights)==3 and len(verified)==3
    assert doc["result_counts"]=={"SOURCE_ARCHIVED_AND_REVERIFIED":3}
    assert doc["new_provider_request_count_upper_bound"]==3
    for i,day in enumerate(SCOPE,1):
        intent=json.loads((out/f"intent_{i:02d}_{day}.json").read_text())
        assert intent["automatic_same_query_retry"] is False
        assert intent["fingerprint"]==_fingerprint({
            k:v for k,v in intent.items() if k!="fingerprint"})
    assert doc["broker_orders"]==0 and not doc["historical_profitability_validated"]
    assert json.loads((out/"summary.json").read_text())["fingerprint"]==doc["fingerprint"]


def test_failed_or_inflight_first_query_stops_before_dispatch(tmp_path):
    p,kwargs,preflights,calls,verified=run_kwargs(tmp_path,
        states={SCOPE["2025-06-16"]["query"]:"FAILED_RETRYABLE"})
    doc=dispatch(p,tmp_path/"result",**kwargs)
    assert doc["status"]=="COMPLETE_WITH_BLOCKED_SOURCES"
    assert doc["completed_scopes"]==3
    assert doc["remaining_not_attempted"]==[]
    assert doc["new_provider_request_count_upper_bound"]==2
    assert calls==["2025-06-18","2025-06-20"]
    assert len(verified)==2
    assert not (tmp_path/"result"/"intent_01_2025-06-16.json").exists()
    assert (tmp_path/"result"/"intent_02_2025-06-18.json").exists()
    assert (tmp_path/"result"/"intent_03_2025-06-20.json").exists()


def test_provider_failure_never_retries_then_keeps_partial_receipt(tmp_path):
    p,kwargs,preflights,calls,verified=run_kwargs(
        tmp_path,fail_day="2025-06-18")
    out=tmp_path/"sources"
    doc=dispatch(p,out,**kwargs)
    assert doc["status"]=="COMPLETE_WITH_BLOCKED_SOURCES"
    assert calls==["2025-06-16","2025-06-18","2025-06-20"]
    assert doc["remaining_not_attempted"]==[]
    assert len(verified)==2
    assert doc["per_scope"][1]["exception_type_only"]=="RuntimeError"
    assert (out/"intent_02_2025-06-18.json").exists()
    assert (out/"intent_03_2025-06-20.json").exists()
    assert doc["historical_broker_fills"]==0


def test_previously_cached_sources_are_sha_verified_not_fetched(tmp_path):
    states={v["query"]:"ARCHIVED" for v in SCOPE.values()}
    p,kwargs,preflights,calls,verified=run_kwargs(tmp_path,states=states)
    doc=dispatch(p,tmp_path/"out",**kwargs)
    assert doc["status"]=="COMPLETE_SOURCE_CENSUS"
    assert not calls and len(verified)==3
    assert doc["new_provider_request_count_upper_bound"]==0
    assert doc["result_counts"]=={"ORIGINAL_ARCHIVE_VERIFIED_REUSED":3}


def test_explicit_no_data_never_dispatches(tmp_path):
    states={v["query"]:"NO_DATA_EXPLICIT" for v in SCOPE.values()}
    p,kwargs,preflights,calls,verified=run_kwargs(tmp_path,states=states)
    doc=dispatch(p,tmp_path/"out",**kwargs)
    assert doc["result_counts"]=={"CACHED_EXPLICIT_NO_DATA":3}
    assert not calls and not verified


def test_parent_report_tampering_stops_before_external_effect(tmp_path):
    p,kwargs,preflights,calls,verified=run_kwargs(tmp_path)
    original=json.loads(p.read_text())
    original["session_reports"][0]["session"]="2025-06-05"
    p.write_text(json.dumps(original))
    with pytest.raises(V66Error,match="V66_V65_FINGERPRINT_CHANGED"):
        dispatch(p,tmp_path/"out",**kwargs)
    assert not calls and not preflights
    assert not (tmp_path/"out").exists()


def test_immutable_output_directory_blocks_duplicate_dispatch(tmp_path):
    p,kwargs,preflights,calls,verified=run_kwargs(tmp_path)
    (tmp_path/"out").mkdir()
    with pytest.raises(V66Error,match="V66_IMMUTABLE_OUTPUT_DIRECTORY_EXISTS"):
        dispatch(p,tmp_path/"out",**kwargs)
    assert not calls
