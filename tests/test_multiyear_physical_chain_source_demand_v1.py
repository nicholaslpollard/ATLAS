from __future__ import annotations

from collections import Counter
from datetime import date
from types import SimpleNamespace

import pytest

import packages.data.multiyear_physical_chain_source_demand_v1 as m
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_original_option_source_crosswalk_v1 import (
    reconcile_original_sources,
)
from test_multiyear_original_option_source_crosswalk_v1 import _fixtures


def _inputs():
    inv,src,shortlist,closeout,native=_fixtures()
    # Original cohort has three accepted prior-year signals whose entries
    # land in the next calendar year and whose old 2022 physical key is absent.
    for i,(ticker,ident) in enumerate((
        ("ENPH","2022-prior-alt00"),
        ("ESLT","2022-prior-alt01"),
        ("MSTR","2022-prior-alt02"),
    )):
        row=next(x for x in inv["cases"] if x["case_id"]==ident)
        row.update(ticker=ticker,signal_session="2022-12-30",
                   entry_session="2023-01-03",expiration="2023-02-17",
                   decision_at_utc="2023-01-03T14:35:00+00:00")
    inv["rolling_five_year_floor"]="2021-09-27"
    inv["inventory_fingerprint"]=_fingerprint({
        k:v for k,v in inv.items() if k!="inventory_fingerprint"
    })
    cross=reconcile_original_sources(inv,src,shortlist,closeout,native=native)
    assert cross["2022_unmatched_cases_remaining"]==3
    assert cross["2022_pilot_same_key_other_cases"]==0
    by_id={r["case_id"]:r for r in inv["cases"]}
    cross_by_id={r["case_id"]:r for r in cross["cases"]}
    eligible=[r for r in inv["cases"] if r["source_disposition"] in {
        "PIT_CHAIN_SOURCE_REQUEST_CANDIDATE",
        "ORIGINAL_2025_PILOT_RECONCILIATION_REQUIRED",
    }]
    assert len(eligible)==7847
    # Unique synthetic physical keys, with 193 legitimate two-member groups.
    # Real production grouping is the already fingerprinted original preview.
    pairs=[eligible[i:i+2] for i in range(0,386,2)]
    singles=[[r] for r in eligible[386:]]
    groups=pairs+singles
    assert len(groups)==7654
    for i,members in enumerate(groups):
        ticker=f"T{i:05d}"
        for row in members:
            by_id[row["case_id"]]["ticker"]=ticker
            cross_by_id[row["case_id"]]["ticker"]=ticker
        head=members[0]
        assert all(x["year"]==head["year"] for x in members)
        groups[i]={
            "year":head["year"],"ticker":ticker,
            "snapshot_date":head["signal_session"],
            "expiration":head["expiration"],"side":"call",
            "strike_window":"46.00,54.00",
            "member_case_ids":sorted(x["case_id"] for x in members),
            "original_case_count":len(members),
            "source_status":"PROVISIONAL_UNPAID_CHAIN_QUERY_NEEDS_RECEIPT_RECONCILIATION",
        }
    inv["provisional_chain_groups"]=groups
    inv["inventory_fingerprint"]=_fingerprint({
        k:v for k,v in inv.items() if k!="inventory_fingerprint"
    })
    cross["source_inventory_fingerprint"]=inv["inventory_fingerprint"]
    cross["crosswalk_fingerprint"]=_fingerprint({
        k:v for k,v in cross.items() if k!="crosswalk_fingerprint"
    })
    return cross,inv


def test_freeze_all_years_reuses_old_sources_and_keeps_2026_explicit():
    cross,inv=_inputs()
    out=m.freeze_physical_chain_source_demand(cross,inv)
    assert out["case_denominator"]==14902
    assert len(out["case_coverage"])==14902
    assert out["new_stock_source_case_denominator_needing_preview"]==7838
    assert out["unique_unreconciled_physical_preview_queries"]==7645
    assert out["by_year_preview_case_memberships"]=={
        "2021":1353,"2022":3,"2023":1601,"2024":1390,"2025":3491
    }
    assert out["2021_before_five_year_floor_cases"]==4138
    assert out["2026_deferred_2025_signal_native_entry_cases"]==17
    assert out["2026_accepted_new_stock_signal_cases"]==0
    assert out["original_2022_exact_quote_histories_reused_by_pointer_only"]==6398
    assert out["original_2022_old_source_key_absence_count"]==3
    gaps=[r for r in out["requests"] if r["source_lineage"].startswith(
        "ACCEPTED_2022_DECEMBER"
    )]
    assert len(gaps)==3
    assert {r["ticker"] for r in gaps}=={"ENPH","ESLT","MSTR"}
    assert {r["params"]["date"] for r in gaps}=={"2022-12-30"}
    assert {r["params"]["expiration"] for r in gaps}=={"2023-02-17"}
    assert all(r["request_sides"]==["call","put"] for r in gaps)
    assert all(not r["new_paid_request_proven"] and
               not r["historical_option_fill_verified"]
               for r in out["requests"])
    assert out["new_paid_requests_proven"]==out["provider_requests"]==0
    assert sum(sum(s.values()) for s in out["by_year"].values())==14902
    assert out["demand_fingerprint"]==_fingerprint({
        k:v for k,v in out.items() if k!="demand_fingerprint"
    })


def test_invalid_source_identity_or_original_group_fails_closed():
    cross,inv=_inputs()
    inv["provisional_chain_groups"][0]["member_case_ids"]=[
        "missing-stock-case", *inv["provisional_chain_groups"][0]["member_case_ids"][1:]
    ]
    inv["inventory_fingerprint"]=_fingerprint({
        k:v for k,v in inv.items() if k!="inventory_fingerprint"
    })
    cross["source_inventory_fingerprint"]=inv["inventory_fingerprint"]
    cross["crosswalk_fingerprint"]=_fingerprint({
        k:v for k,v in cross.items() if k!="crosswalk_fingerprint"
    })
    with pytest.raises(m.PhysicalSourceDemandError,match="physical preview key/membership"):
        m.freeze_physical_chain_source_demand(cross,inv)
    cross,inv=_inputs()
    cross["provider_requests"]=1
    with pytest.raises(m.PhysicalSourceDemandError,match="lineage changed"):
        m.freeze_physical_chain_source_demand(cross,inv)


def test_build_reuses_immutable_D_manifest_without_old_sources(tmp_path,monkeypatch):
    cross,inv=_inputs()
    settings=SimpleNamespace(
        resolved_path=lambda rel:tmp_path/rel,
        assert_external_storage_binding=lambda key:
            None if key in {"options","research_evidence"} else pytest.fail("wrong binding"),
    )
    monkeypatch.setattr(m,"build_original_source_crosswalk",
                        lambda *args,**kwargs:(cross,tmp_path/"old","REUSED"))
    monkeypatch.setattr(m,"build_option_source_gap_inventory",
                        lambda *args,**kwargs:(inv,tmp_path/"inventory","REUSED"))
    first=m.build_physical_chain_source_demand(settings)
    assert first[2]=="WRITTEN_NEW_PHYSICAL_SOURCE_DEMAND_PREVIEW"
    second=m.build_physical_chain_source_demand(settings)
    assert second[2]=="REUSED_VERIFIED_PHYSICAL_DEMAND_NO_REBUILD"
    assert second[0]==first[0]
    assert first[1].is_file()
    first[1].write_text("{}",encoding="utf-8")
    with pytest.raises(m.PhysicalSourceDemandError,match="manifest changed"):
        m.build_physical_chain_source_demand(settings)
