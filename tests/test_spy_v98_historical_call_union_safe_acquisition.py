from __future__ import annotations

"""V98 exact 0DTE CALL V38 identity + immutable preflight/source-only tests."""

from datetime import date,datetime
from pathlib import Path
import json
import sqlite3
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import normalize_source_requirement
from scripts import run_spy_v98_historical_call_union_safe_acquisition as v98


class Calendar:
    def __init__(self,early=False):
        self.early=early
    def sessions_in_range(self,a,b):
        return [a]
    def regular_open_close(self,day):
        tz=ZoneInfo("America/New_York")
        close=datetime(day.year,day.month,day.day,13 if self.early else 16,tzinfo=tz)
        open_=datetime(day.year,day.month,day.day,9,30,tzinfo=tz)
        return open_,close


def preview(session="2022-12-02",strike="400",clock="09:35:01"):
    return {
        "symbol":"SPY","right":"call","session":session,"expiry":session,
        "decision_clock_et":clock,"strike":strike,
        "source_contract_identity":"SPY_0DTE_1S_CALL",
        "strategy_variants":["V97B-impulse_0935-00"],
        "provider_calls":0,"broker_orders":0,
    }


def test_canonical_quote_end_normal_session_and_early_close():
    cal=Calendar()
    x=v98.build_requirement(preview(),cal)
    assert x["kwargs"]["end_time_et"]=="15:30:00.000"
    assert x["kwargs"]["start_time_et"]=="09:35:01.000"
    expected=normalize_source_requirement(x["method"],x["kwargs"])
    assert x["query_id"]==_fingerprint(expected)
    y=v98.build_requirement(preview("2022-11-25"),Calendar(early=True))
    assert y["kwargs"]["end_time_et"]=="12:05:00.000"
    assert y["query_id"]!=x["query_id"]


def test_actual_observed_original_2018_early_clock_source_query_reconstructed():
    x=v98.build_requirement(preview("2018-02-14","265","09:35:01"),Calendar())
    # Original V97B full data preserved source qid for 2018-02-14:
    assert x["query_id"]=="bfc3d4ec957070534a16f3dc677698844e6893e2d48198130c0129aede5651aa"


def test_historical_no_spy_weekly_or_bad_call_scope_rejected():
    with pytest.raises(v98.V98Error,match="HISTORICAL_EXPIRY"):
        v98.build_requirement(preview("2018-01-02"),Calendar())
    for change in ({"right":"put"},{"symbol":"QQQ"},{"decision_clock_et":"10:11:01"}):
        row=preview();row.update(change)
        with pytest.raises(v98.V98Error,match="SCOPE_INVALID"):
            v98.build_requirement(row,Calendar())


def test_sqlite_source_index_read_only_unknown_and_no_data(tmp_path,monkeypatch):
    root=tmp_path/"db.sqlite"
    with sqlite3.connect(root) as conn:
        conn.execute("CREATE TABLE sources (query_id TEXT PRIMARY KEY, request_json TEXT,"
                     "state TEXT, touched REAL, source_sha TEXT, gzip_sha TEXT,"
                     "stored_path TEXT, source_rows INTEGER)")
        states=[]
        for session,state in [("2022-12-02","FAILED_RETRYABLE"),
                              ("2022-12-05","NO_DATA_EXPLICIT"),
                              ("2022-12-07","ARCHIVED"),
                              ("2022-12-09","IN_FLIGHT")]:
            item=v98.build_requirement(preview(session),Calendar())
            states.append(item)
            expected=normalize_source_requirement(item["method"],item["kwargs"])
            conn.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?)",
                         (item["query_id"],json.dumps(expected,sort_keys=True,
                            separators=(",",":")),state,1,
                          "a"*64,"b"*64,"data/options/test.json.gz",1))
    missing=v98.build_requirement(preview("2022-12-12"),Calendar())
    calls=[]
    def unpack(settings,row,request):
        calls.append(row[2])
        return {"status":("CACHE_HIT" if row[2]=="ARCHIVED" else
                          "CACHED_EXPLICIT_NO_DATA"),
                "source_sha256":"a"*64}
    monkeypatch.setattr(v98,"_unpack",unpack)
    class Settings:
        def assert_external_storage_binding(self,name):
            assert name=="options"
        def resolved_path(self,relative):
            return root
    results=v98.read_only_v38_state(Settings(),states+[missing])
    assert [r["read_only_v38_state"] for r in results]==[
        "BLOCKED_POSSIBLY_DISPATCHED_NO_AUTO_RETRY",
        "EXPLICIT_NO_DATA",
        "ARCHIVED_SHA_VERIFIED",
        "BLOCKED_POSSIBLY_DISPATCHED_NO_AUTO_RETRY",
        "NOT_REGISTERED",
    ]
    assert calls==["NO_DATA_EXPLICIT","ARCHIVED"]
    assert sum(x["new_request_eligible_for_first_dispatch"] for x in results)==1


def test_first_time_acquisition_queues_only_read_only_not_registered(
    tmp_path,monkeypatch
):
    summary=v98.signed({"contract":"original"})
    events=v98.signed({"contract":"events"})
    original=v98.signed({"contract":"preview"})
    fresh=v98.build_requirement(preview(),Calendar())
    missing_state={
        "query_id":fresh["query_id"],"date_et":fresh["kwargs"]["date_et"],
        "decision_clock_et":"09:35:01","strike":"400","right":"call",
        "normalized_requirement":normalize_source_requirement(
            fresh["method"],fresh["kwargs"]),
        "original_variant_ids":["V97B-impulse_0935-00"],
        "read_only_v38_state":"NOT_REGISTERED",
        "read_only_source_sha256":None,"new_request_eligible_for_first_dispatch":True,
        "query_retry_automatically_authorized":False,
    }
    blocked={**missing_state,
        "query_id":"9"*64,
        "read_only_v38_state":"BLOCKED_POSSIBLY_DISPATCHED_NO_AUTO_RETRY",
        "new_request_eligible_for_first_dispatch":False,
    }
    monkeypatch.setattr(v98,"verify_preview",lambda *_:(summary,events,original,[fresh]))
    monkeypatch.setattr(v98,"read_only_v38_state",lambda *x:[blocked,missing_state])
    dispatched=[]
    def resolver(settings,version,demands,**kw):
        rows=list(demands)
        dispatched.extend(rows)
        assert kw["continue_on_error"] is True
        kw["on_progress"]("source_started",{
            "candidate_id":rows[0]["candidate_id"],
            "query_id":fresh["query_id"],"date_et":"2022-12-02",
            "status":None,"error":None,
        })
        kw["on_progress"]("provider_dispatch",{
            "candidate_id":rows[0]["candidate_id"],
            "query_id":fresh["query_id"],"date_et":"2022-12-02",
            "status":None,"error":None,
        })
        kw["on_source"](rows[0],{
            "query_id":fresh["query_id"],"source_sha256":"a"*64,
            "status":"FETCHED_AND_ARCHIVED","source_rows":({"one":1},),
        })
        kw["on_progress"]("source_done",{
            "candidate_id":rows[0]["candidate_id"],
            "query_id":fresh["query_id"],"date_et":"2022-12-02",
            "status":"FETCHED_AND_ARCHIVED","error":None,
        })
        return {
            "contract":"atlas-strategy-options-data-demand-runtime-v39",
            "source_uses_requested":1,"provider_dispatch_attempts":1,
            "source_uses_resolved":1,"source_uses_explicit_no_data":0,
            "source_uses_failed_or_unresolved":0,
        }
    out=tmp_path/"output"
    report=v98.run(tmp_path,out,acquire=True,
                    settings_factory=lambda *x:object(),
                    resolver=resolver,calendar=Calendar(),reporter=lambda _:None)
    assert report["mode"]=="CACHE_FIRST_SOURCE_ONLY"
    assert len(dispatched)==1
    assert dispatched[0]["method"]=="option_history_exact_quote_tape"
    assert dispatched[0]["kwargs"]["right"]=="call"
    assert dispatched[0]["kwargs"]["strike"]=="400"
    assert report["provider_dispatch_attempts"]==1
    assert report["broker_orders"]==0
    assert (out/"first_dispatch_source_intents.json").exists()
    progress=(out/"source_events.jsonl").read_text().splitlines()
    assert len(progress)==3
    assert json.loads(progress[2])["previous_event_sha"]==json.loads(progress[1])["fingerprint"]


def test_preview_only_does_not_call_resolver(tmp_path,monkeypatch):
    s=v98.signed({"contract":"original"})
    monkeypatch.setattr(v98,"verify_preview",lambda *_:(s,s,s,[preview()]))
    monkeypatch.setattr(v98,"read_only_v38_state",lambda *x:[])
    def deny(*args,**kwargs):
        pytest.fail("provider-capable resolver invoked in preview-only mode")
    out=tmp_path/"preview"
    result=v98.run(tmp_path,out,acquire=False,
        settings_factory=lambda *x:object(),resolver=deny,
        calendar=Calendar(),reporter=lambda _:None)
    assert result["mode"]=="READ_ONLY_NO_NEW_PROVIDER_CALLS"
    assert result["provider_dispatch_attempts"]==0
    assert not (out/"first_dispatch_source_intents.json").exists()
