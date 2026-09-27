from __future__ import annotations

"""Entire original case denominator; exactly 2022/2025 prior source reuse."""

from collections import Counter
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.multiyear_original_option_source_crosswalk_v1 as m
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_native_stock_open_v1 import (
    CONTRACT as NATIVE_CONTRACT, AUTHORITY as NATIVE_AUTHORITY,
)


def _fixtures():
    cases=[]
    native_rows=[]
    reps={}
    alt={}
    gaps={}
    pilot22={}
    pilot_by_key={}
    preferred={}
    pilot25=[]
    close25=[]
    def add(year, ident, category, *, ticker="TEST", signal=None, expiry=None,
            price="50", entry=None):
        sig=signal or f"{year}-03-01"
        exp=expiry if expiry is not None else f"{year}-04-15"
        ent=entry or f"{year}-03-02"
        cid=f"{year}-{ident}"
        cases.append({
            "case_id":cid,"year":str(year),"ticker":ticker,
            "signal_session":sig,"entry_session":ent,
            "expiration":exp,
            "decision_at_utc":f"{ent}T14:35:00+00:00",
            "source_disposition":category,
            "prior_24h_news_articles":0,
            "prior_7d_news_articles":2,
            "selected_for_new_paid_get":False,
        })
        native_rows.append({
            "case_id":cid,"raw_underlying_price":price,
        })
        return cases[-1]
    for k in range(5491):
        add(2021,f"x{k:04d}",
            "DECISION_OUTSIDE_ROLLING_PROVIDER_WINDOW" if k<4138
            else "PIT_CHAIN_SOURCE_REQUEST_CANDIDATE")
    for k in range(2643):
        row=add(2022,f"rank{k:04d}","ORIGINAL_2022_PREFERRED_CALL_PLAN_MATCH")
        source={"source_key":m._source_key(row),"raw_open":"50",
                "chain_request_identity":"a"*64,"chain_strike_window":"46.00-54.00",
                "source_sha256":"b"*64,"shard_index":0}
        reps[row["case_id"]]=source
        preferred[row["case_id"]]={
            "original_chain_request_identity":"a"*64,
            "option_symbol":"TEST220415C00050000"
        }
    for k in range(27):
        row=add(2022,f"alt{k:03d}","ORIGINAL_2022_SAME_KEY_RECONCILIATION_REQUIRED")
        alt[row["case_id"]]={
            **next(iter(reps.values())),
            "source_key":m._source_key(row),"representative_id":"2022-rank0000",
        }
    for k in range(169):
        row=add(2022,f"gap{k:03d}","ORIGINAL_2022_CHAIN_RECONCILIATION_REQUIRED")
        reps[row["case_id"]]={
            **next(iter(reps.values())), "source_key":m._source_key(row)
        }
        gaps[row["case_id"]]="NO_CALL_IN_COMPLETED_CHAIN"
    for k in range(36):
        symbol=f"P{k:02d}"
        row=add(2022,f"pilot{k:02d}","ORIGINAL_2022_CHAIN_RECONCILIATION_REQUIRED",
                ticker=symbol)
        key=m._source_key(row)
        source={
            "representative_id":row["case_id"],"request_identity":f"{k:064x}",
            "source_status":"COMPLETE","strike_window":"46.00-54.00",
            "original_chain_sha256":"c"*64, "raw_open":"50",
        }
        pilot22[row["case_id"]]=source
        pilot_by_key[key]={k:v for k,v in source.items() if k!="raw_open"}
    for k in range(5):
        row=add(2022,f"prior-alt{k:02d}","ORIGINAL_2022_CHAIN_RECONCILIATION_REQUIRED",
                ticker=f"P{k:02d}",price="50")
        assert m._source_key(row) in pilot_by_key
    for k in range(20):
        row=add(2022,f"noexp{k:02d}","NO_BOUNDED_MONTHLY_EXPIRATION")
        row["expiration"]=None
    for k in range(1601):
        add(2023,f"x{k:04d}","PIT_CHAIN_SOURCE_REQUEST_CANDIDATE")
    for k in range(1390):
        add(2024,f"x{k:04d}","PIT_CHAIN_SOURCE_REQUEST_CANDIDATE")
    for k in range(12):
        status="EXACT_QUERY_NO_DATA" if k==11 else "COMPLETE_ORIGINAL_CHAIN"
        row=add(2025,f"pilot{k:02d}",
                "ORIGINAL_2025_PILOT_RECONCILIATION_REQUIRED",
                ticker="FSLY" if k==11 else f"T{k:02d}")
        pilot25.append({
            "opportunity_id":row["case_id"],"ticker":row["ticker"],
            "chain_snapshot_date":row["signal_session"],
            "expiration":row["expiration"],
            "stock_decision_at_utc":row["decision_at_utc"],
            "accepted_raw_stock_open":"50.00",
            "request_identity":f"{k+40:064x}",
            "source_status":status,
            "provisional_nearest_atm_call":None if k==11 else
                f"T{k:02d}250415C00050000",
            "source_chain_body_sha256":"d"*64,
            "structural_call_count":0 if k==11 else 1,
        })
        close25.append({
            "opportunity_id":row["case_id"],
            "request_identity":f"{k+40:064x}",
            "source_coverage":"SOURCE_NO_DATA_VERIFIED" if k==11 else "REUSED_VERIFIED",
        })
    for k in range(3491):
        add(2025,f"other{k:04d}","ORIGINAL_2025_PILOT_RECONCILIATION_REQUIRED")
    for k in range(17):
        add(2025,f"deferred{k:02d}","DEFERRED_2026_NATIVE_ENTRY",
            expiry="2026-02-20",entry="2026-01-02",price=None)
    assert len(cases)==14902
    assert len(reps)==2812 and len(alt)==27 and len(gaps)==169
    assert len(pilot22)==36 and len(pilot25)==12
    inventory={
        "contract":m.INVENTORY_CONTRACT,
        "status":"FULL_DENOMINATOR_OPTIONS_SOURCE_GAP_INVENTORY_NO_PAID_GET",
        "authority":m.INVENTORY_AUTHORITY,
        "provider_requests":0,"new_paid_requests":0,
        "accepted_original_2022_quote_plan_fingerprint":m.ACCEPTED_2022_QUOTE_PLAN,
        "case_denominator":14902,
        "original_native_stock_source_fingerprint":"e"*64,
        "provisional_group_count":7654,
        "cases":cases,
    }
    inventory["inventory_fingerprint"]=_fingerprint(inventory)
    native={
        "contract":NATIVE_CONTRACT,
        "status":"MULTIYEAR_NATIVE_RAW_OPEN_VERIFIED_SOURCE_ONLY",
        "authority":NATIVE_AUTHORITY,
        "provider_requests":0,"protected_outcomes_read":0,
        "case_denominator":14902,
        "verified_native_raw_open_cases":14885,
        "deferred_2026_entry_cases":17,
        "rows":native_rows,
    }
    native["source_fingerprint"]=_fingerprint(native)
    sources={
        "pilot_members":pilot22, "pilot_by_key":pilot_by_key,
        "additive_representatives":reps,
        "additive_same_key":alt, "additive_gaps":gaps,
        "additive_exact_no_data_proofs":{},
        "original_preferred_calls":preferred,
        "original_2022_quote_plan_fingerprint":m.ACCEPTED_2022_QUOTE_PLAN,
        "original_pilot_plan_fingerprint":m.shards.FROZEN_PRIOR_PLAN,
    }
    shortlist={
        "stock_opportunities":12,"provisional_structural_symbols":11,
        "source_plan_fingerprint":"a"*64,
        "shortlist_fingerprint":"c"*64,
        "opportunities":pilot25,
    }
    closeout={
        "verified_opportunities":12,"plan_fingerprint":"a"*64,
        "closeout_fingerprint":"b"*64,
        "opportunities":close25,
    }
    return inventory,sources,shortlist,closeout,native


def test_all_14902_cases_2022_2900_exact_and_original_2025_12():
    inventory,sources,shortlist,closeout,native=_fixtures()
    result=m.reconcile_original_sources(
        inventory,sources,shortlist,closeout,native=native
    )
    assert result["case_denominator"]==14902
    assert result["2022_total_original_cases_reconciled"]==2900
    assert result["2022_unmatched_cases_remaining"]==0
    assert result["2022_original_additive_representatives"]==2812
    assert result["2022_original_additive_same_key_members"]==27
    assert result["2022_original_additive_source_abstentions"]==169
    assert result["2022_original_pilot_representatives"]==36
    assert result["2022_pilot_same_key_other_cases"]==5
    assert result["2025_original_pilot_matched_cases"]==12
    assert result["2025_original_pilot_source_statuses"]=={
        "ORIGINAL_2025_PILOT_PREFERRED_CALL_POINTER_REUSED":11,
        "ORIGINAL_2025_PILOT_EXACT_QUERY_NO_DATA":1,
    }
    assert result["by_year"]["2022"]=={
        "ORIGINAL_2022_PREFERRED_CALL_PLAN_POINTER_REUSED":2643,
        "ORIGINAL_2022_SAME_KEY_CHAIN_REUSED_OWN_RANK_NOT_SELECTED":27,
        "ORIGINAL_2022_NO_CALL_IN_COMPLETED_CHAIN":169,
        "ORIGINAL_2022_PILOT_COMPLETE":36,
        "ORIGINAL_2022_PILOT_KEY_OTHER_CASE_OWN_RANK_REQUIRED":5,
        "ORIGINAL_2022_FROZEN_MONTHLY_EXPIRY_GAP":20,
    }
    assert result["by_year"]["2025"]=={
        "ORIGINAL_2025_PILOT_PREFERRED_CALL_POINTER_REUSED":11,
        "ORIGINAL_2025_PILOT_EXACT_QUERY_NO_DATA":1,
        "ORIGINAL_2025_NOT_IN_TWELVE_CASE_PILOT":3491,
        "DEFERRED_2026_NATIVE_ENTRY":17,
    }
    assert result["provider_requests"]==result["new_paid_requests"]==0
    assert result["provisional_groups_after_physical_reconciliation"] is None
    assert all(x["new_paid_request_authority"] is False for x in result["cases"])
    assert result["crosswalk_fingerprint"]==_fingerprint({
        k:v for k,v in result.items() if k!="crosswalk_fingerprint"
    })


def test_original_raw_stock_price_and_2025_source_id_drift_fails_closed():
    inventory,sources,shortlist,closeout,native=_fixtures()
    native["rows"][5491]["raw_underlying_price"]="49999"
    native["source_fingerprint"]=_fingerprint({
        k:v for k,v in native.items() if k!="source_fingerprint"
    })
    inventory["original_native_stock_source_fingerprint"]=native["source_fingerprint"]
    inventory["inventory_fingerprint"]=_fingerprint({
        k:v for k,v in inventory.items() if k!="inventory_fingerprint"
    })
    with pytest.raises(m.OriginalCrosswalkError,match="preferred source member drifted"):
        m.reconcile_original_sources(
            inventory,sources,shortlist,closeout,native=native
        )
    inventory,sources,shortlist,closeout,native=_fixtures()
    shortlist["opportunities"][0]["accepted_raw_stock_open"]="111"
    with pytest.raises(m.OriginalCrosswalkError,match="pilot no longer matches"):
        m.reconcile_original_sources(
            inventory,sources,shortlist,closeout,native=native
        )


def test_original_pilot_strike_envelope_not_assumed_full():
    assert m._strike_coverage("46.00-54.00","50.00")==(
        "ORIGINAL_STRIKE_ENVELOPE_COVERS_8PCT"
    )
    assert m._strike_coverage("47.00-53.00","50.00")==(
        "ORIGINAL_STRIKE_ENVELOPE_PARTIAL_FOR_THIS_RAW_OPEN"
    )
    assert m._price_equal("50","50.000") is True
    assert m._price_equal("50","51") is False


def test_build_reuses_crosswalk_without_old_shard_or_pilot_reads(tmp_path,monkeypatch):
    inventory,sources,shortlist,closeout,native=_fixtures()
    settings=SimpleNamespace(
        resolved_path=lambda p:tmp_path/p,
        assert_external_storage_binding=lambda name:
            None if name in {"options","research_evidence"} else pytest.fail("wrong binding"),
    )
    def prior(*args,**kwargs):
        return inventory,tmp_path/"inventory.json","REUSED_VERIFIED_OPTION_INVENTORY_NO_SOURCE_RESCAN"
    monkeypatch.setattr(m,"build_option_source_gap_inventory",prior)
    monkeypatch.setattr(m,"read_2022_original_memberships",lambda *args,**kwargs:sources)
    monkeypatch.setattr(m,"read_accepted_shortlist",lambda *args,**kwargs:shortlist)
    monkeypatch.setattr(m,"read_frozen_source_closeout",lambda *args,**kwargs:closeout)
    monkeypatch.setattr(m,"build_multiyear_native_raw_open_source",
                        lambda *args,**kwargs:(native,tmp_path/"native.json","REUSED_VERIFIED_NATIVE_SOURCE_NO_RAW_RESCAN"))
    original=settings.resolved_path(f"{m.PLAN_REL}/through_shard_070.json")
    original.parent.mkdir(parents=True)
    original.write_text("{}",encoding="utf-8")
    first=m.build_original_source_crosswalk(settings)
    assert first[2]=="WRITTEN_NEW_ORIGINAL_SOURCE_CROSSWALK"
    assert first[0]["case_denominator"]==14902
    original.unlink()
    second=m.build_original_source_crosswalk(settings)
    assert second[2]=="REUSED_VERIFIED_ORIGINAL_SOURCE_CROSSWALK_NO_RESOURCES_REOPENED"
    assert second[0]==first[0]
    first[1].write_text("{}",encoding="utf-8")
    with pytest.raises(m.OriginalCrosswalkError,match="changed"):
        m.build_original_source_crosswalk(settings)
