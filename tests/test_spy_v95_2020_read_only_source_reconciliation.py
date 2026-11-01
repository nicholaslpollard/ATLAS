from __future__ import annotations

"""V95 synthetic all-source census and read-only May 1 identity tests."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v89_six_family_causal_registry import FAMILIES,signed,verified
from scripts import run_spy_v95_2020_read_only_source_reconciliation as v95


def dump(path,doc):
    path.write_text(json.dumps(doc,sort_keys=True)+"\n",encoding="utf8")
    return doc


def source_fixture(folder):
    folder.mkdir()
    day="2020-05-01"
    req={"method":"option_history_exact_quote_tape",
         "kwargs":{"symbol":"SPY","date_et":day,"expiration":day,
                   "strike":"282","right":"call",
                   "start_time_et":"09:40:01.000",
                   "end_time_et":"15:30:00.000","interval":"1s"}}
    from packages.data.options_on_demand_source_cache_v38 import normalize_source_requirement
    norm=normalize_source_requirement(req["method"],req["kwargs"])
    qid=_fingerprint(norm)
    cid=f"SPY_{day}_impulse_0935_call"
    demand=signed({
        "candidate_id":cid,
        "query_id":qid,
        "method":req["method"],
        "kwargs":req["kwargs"],
        "strategy_decision_sha":"a"*64,
    })
    entry=dump(folder/"entry_screen.json",signed({
        "contract":"atlas-v89-six-family-original-source-campaign-v1",
        "start":"2020-01-01","end":"2020-12-31",
        "sessions":1,"cases":[{"strategy":x} for x in FAMILIES],
        "registry":FAMILIES,"registry_sha":_fingerprint(FAMILIES),
    }))
    plan=dump(folder/"exact_option_source_plan.json",signed({
        "contract":"atlas-v89-six-family-original-source-campaign-v1-source-plan-v1",
        "parent_entry_sha":entry["fingerprint"],
        "demands":[demand],
    }))
    prev=None
    events=[]
    for index,event,status in [
        (1,"source_started",None),
        (2,"provider_dispatch",None),
        (3,"source_failed","SOURCE_DISPATCH_OUTCOME_UNKNOWN"),
    ]:
        item=signed({
            "contract":"atlas-v89-six-family-original-source-campaign-v1-append-only-source-event-v1",
            "sequence":index,"parent_event_sha":prev,
            "event":event,"candidate_id":cid,"query_id":qid,
            "date_et":day,"source_status":status,"error_type":None,
        })
        events.append(item)
        prev=item["fingerprint"]
    (folder/"source_events.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in events),encoding="utf8")
    receipts=dump(folder/"source_receipts.json",signed({
        "contract":"atlas-v89-six-family-original-source-campaign-v1-source-receipts-v1",
        "parent_plan_sha":plan["fingerprint"],
        "original_provider_source_receipts":[],
        "source_event_count":len(events),"last_event_sha":prev,
        "broker_orders":0,
    }))
    summary=dump(folder/"summary.json",signed({
        "contract":"atlas-v89-six-family-original-source-campaign-v1-summary-v1",
        "entry_sha":entry["fingerprint"],
        "source_plan_sha":plan["fingerprint"],
        "receipt_sha":receipts["fingerprint"],
        "source_resolution":{"source_uses_requested":1},
        "exact_source_requirements":1,
        "all_required_sources_archived":False,"broker_orders":0,
    }))
    return qid


def test_unresolved_original_source_not_faked_as_absent_trade_or_retried(tmp_path):
    folder=tmp_path/"original";qid=source_fixture(folder)
    calls=[]
    def read(settings,query_id):
        calls.append(query_id)
        return {"cache_evidence":"EXACT_QUERY_NOT_IN_INDEX","source":None}
    r=v95.audit_2020(folder,tmp_path/"audit",settings_factory=lambda *x:object(),
                     cache_reader=read,reporter=lambda _:None)
    assert verified(r)
    assert calls==[qid]
    assert r["original_source_requirements"]==1
    assert r["unresolved_2020_source_requirements"]==1
    assert r["eligible_for_complete_2020_full_year_quote_pnl"] is False
    doc=json.loads((tmp_path/"audit"/"source_census.json").read_text())
    assert doc["source_dispositions"][0]["reconciliation_status"]=="UNRESOLVED_ORIGINAL_PROVIDER_OUTCOME"
    assert r["broker_orders"]==r["provider_requests"]==0


def test_existing_sha_verified_archive_is_identified_without_provider_calls(tmp_path):
    folder=tmp_path/"original";qid=source_fixture(folder)
    r=v95.audit_2020(folder,tmp_path/"audit",settings_factory=lambda *x:object(),
                     cache_reader=lambda settings,q:{
                         "cache_evidence":"CACHE_HIT",
                         "source":{"source_sha256":"c"*64}},
                     reporter=lambda _:None)
    assert r["extra_original_source_requirements_read_only_archived"]==1
    assert r["unresolved_2020_source_requirements"]==0
    assert r["eligible_for_complete_2020_full_year_quote_pnl"] is True


def test_tampering_signed_event_stops_before_output_or_source_read(tmp_path):
    folder=tmp_path/"original";source_fixture(folder)
    p=folder/"source_events.jsonl"
    lines=p.read_text().splitlines()
    doc=json.loads(lines[0]);doc["candidate_id"]="tampered"
    lines[0]=json.dumps(doc)
    p.write_text("\n".join(lines)+"\n")
    with pytest.raises(v95.V95Error,match="SOURCE_EVENT_SHA_CHAIN_INVALID"):
        v95.audit_2020(folder,tmp_path/"audit",settings_factory=lambda *x:object(),
                       cache_reader=lambda *x:pytest.fail("no cache call"),
                       reporter=lambda _:None)
    assert not (tmp_path/"audit").exists()
