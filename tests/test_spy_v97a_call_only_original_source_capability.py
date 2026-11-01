from __future__ import annotations

"""Synthetic offline V97A source identities; no ThetaData, no broker calls."""

from pathlib import Path
import json

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v89_six_family_causal_registry import (
    FAMILIES,
)
from scripts.run_spy_v89_six_family_source_batch import CONTRACT as V89
from scripts import run_spy_v97a_call_only_original_source_capability as v97


def signed(item):
    return {**item,"fingerprint":_fingerprint(item)}


def dump(path,obj):
    path.write_text(json.dumps(obj,sort_keys=True),encoding="utf8")


def fixture(tmp_path,*,missing_call=False):
    root=tmp_path/"repo"
    folder=root/"data"/"research"/"spy_v95_v89_six_families_2022_full_fake"
    folder.mkdir(parents=True)
    (root/"packages"/"strategies").mkdir(parents=True)
    cases=[]
    demands=[]
    receipts=[]
    for index,family in enumerate(FAMILIES):
        if index<2:
            direction="CALL" if index==0 else "PUT"
            status="OPTIONS_EXACT_SOURCE_DEMAND_PREPARED"
            cid=f"SPY_2022-01-05_{family}_{direction.lower()}"
        else:
            direction=None
            status="NO_SIGNAL"
            cid=None
        decision=signed({
            "contract":"synthetic",
            "strategy_id":family,"session":"2022-01-05",
            "direction":direction,
            "decision_at_et":"2022-01-05T09:40:01-05:00",
            "features":{"first_range":"2.1"},
        })
        source_sha="a"*64
        source_id=None
        if direction:
            source=signed({
                "contract":"synthetic-demand",
                "candidate_id":cid,
                "kwargs":{
                    "date_et":"2022-01-05",
                    "expiration":"2022-01-05","right":direction.lower(),
                    "strike":"400","symbol":"SPY","interval":"1s",
                },
                "query_id":str(index+1)*64,
                "method":"option_history_exact_quote_tape",
                "strategy_decision_sha":decision["fingerprint"],
                "selection_prior_source_sha256":source_sha,
            })
            source_id=source["fingerprint"]
            demands.append(source)
            if not missing_call or direction=="PUT":
                receipts.append({
                    "candidate_id":cid,
                    "status":"FETCHED_AND_ARCHIVED",
                    "source_sha256":str(index+5)*64,
                    "query_id":source["query_id"],
                })
        cases.append({
            "session":"2022-01-05","strategy":family,"status":status,
            "reason":"FROZEN_NEW_HYPOTHESIS_MATCH" if direction else
                     "FROZEN_HYPOTHESIS_NOT_MET",
            "causal_decision":decision,
            "source_demand_sha":source_id,
            "stock_source_sha256":source_sha,
        })
    entry=signed({
        "contract":V89,"start":"2022-01-01","end":"2022-12-31",
        "registry":FAMILIES,"registry_sha":_fingerprint(FAMILIES),
        "cases":cases,"sessions":1,
    })
    plan=signed({
        "contract":V89+"-source-plan-v1",
        "parent_entry_sha":entry["fingerprint"],"demands":demands,
    })
    rec=signed({
        "contract":V89+"-source-receipts-v1",
        "parent_plan_sha":plan["fingerprint"],
        "original_provider_source_receipts":receipts,
        "broker_orders":0,
    })
    summary=signed({
        "contract":V89+"-summary-v1",
        "entry_sha":entry["fingerprint"],"source_plan_sha":plan["fingerprint"],
        "receipt_sha":rec["fingerprint"],"broker_orders":0,
        "exact_source_requirements":len(demands),
    })
    for name,doc in [
        ("entry_screen.json",entry),
        ("exact_option_source_plan.json",plan),
        ("source_receipts.json",rec),
        ("summary.json",summary),
    ]:
        dump(folder/name,doc)
    return root,folder


def test_qualified_call_only_excludes_put_and_preserves_all_no_signals(tmp_path,monkeypatch):
    root,folder=fixture(tmp_path)
    monkeypatch.setattr(v97,"COHORTS",{
        "2022_full":("2022-01-01","2022-12-31",
                     "spy_v95_v89_six_families_2022_full_*")})
    monkeypatch.setattr(v97,"code_census",lambda root:{
        "generic_stock_implementations_are_not_executable_CALL_trades":True})
    r=v97.run(root,tmp_path/"report",reporter=lambda _:None)
    assert v97.verify(r)
    assert r["original_six_family_considerations"]==6
    assert r["original_CALL_sources_archived"]==1
    assert r["original_CALL_sources_unresolved"]==0
    assert r["original_PUT_sources_not_eligible_for_CALL_only"]==1
    assert r["no_signal_or_no_demand_considerations"]==4
    assert r["distinct_qualifying_call_query_ids"]==1
    doc=json.loads((tmp_path/"report"/"original_call_source_considerations.json").read_text())
    assert v97.verify(doc) and doc["fingerprint"]==r["original_all_considerations_sha"]
    assert len(doc["decisions"])==6
    call=next(x for x in doc["decisions"] if x["original_side"]=="CALL")
    assert call["call_original_source_sha256"]=="5"*64
    assert call["news_event_counts"] is None
    assert call["historical_broker_fill_verified"] is False
    assert r["provider_requests"]==r["broker_orders"]==0


def test_unresolved_exact_call_source_not_turned_into_zero_pnl(tmp_path,monkeypatch):
    root,_=fixture(tmp_path,missing_call=True)
    monkeypatch.setattr(v97,"COHORTS",{
        "2020_full_SOURCE_INCOMPLETE":(
            "2022-01-01","2022-12-31",
            "spy_v95_v89_six_families_2022_full_*")})
    monkeypatch.setattr(v97,"code_census",lambda root:{})
    result=v97.run(root,tmp_path/"report",reporter=lambda _:None)
    assert result["original_CALL_sources_archived"]==0
    assert result["original_CALL_sources_unresolved"]==1
    assert result["historical_complete_source_cohorts"]==0
    assert result["historical_incomplete_source_cohorts"]==[
        "2020_full_SOURCE_INCOMPLETE"]
    assert result["actual_historical_option_fill_or_pnl_recomputed"] is False


def test_unsigned_or_modified_original_decision_fails_before_output(tmp_path,monkeypatch):
    root,folder=fixture(tmp_path)
    doc=json.loads((folder/"entry_screen.json").read_text())
    doc["cases"][0]["causal_decision"]["direction"]="PUT"
    doc=signed({k:v for k,v in doc.items() if k!="fingerprint"})
    dump(folder/"entry_screen.json",doc)
    monkeypatch.setattr(v97,"COHORTS",{
        "2022_full":("2022-01-01","2022-12-31",
                     "spy_v95_v89_six_families_2022_full_*")})
    with pytest.raises(v97.V97AError,match="COHORT_ROOT_MISMATCH|STOCK_DECISION_SHA"):
        v97.run(root,tmp_path/"should_not_exist",reporter=lambda _:None)
    assert not (tmp_path/"should_not_exist").exists()


def test_static_strategy_code_inventory_counts_reference_not_placeholders():
    root=Path(__file__).resolve().parents[1]
    r=v97.code_census(root)
    assert len(r["reference_daily_stock_rule_ids"])==9
    assert len(r["generic_daily_strategy_registry_ids"])==8
    assert r["empty_placeholders"]>=1
    assert r["outside_V89_strategies_option_adapter_is_not_yet_qualified"] is True
