from __future__ import annotations

"""Original option source-gaps: all cases, no invented historical fills/GETs."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

import packages.data.multiyear_option_gap_inventory_v1 as m
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint


def _case(identifier, year, signal, entry, expiration, price,
          status="VERIFIED_NATIVE_RAW_OPEN_NEEDS_ORIGINAL_PIT_CHAIN"):
    return {
        "case_id": identifier, "ticker": "TEST", "instrument_id": "TEST-ID",
        "signal_session": f"{year}-{signal}", "entry_session": f"{year}-{entry}",
        "expiration": f"{year}-{expiration}" if expiration else None,
        "planned_option_decision_at_utc": f"{year}-{entry}T14:35:00+00:00",
        "raw_underlying_price": price,
        "native_source_status": status,
        "original_stock_source_status": (
            "NEEDS_SEPARATE_2026_NATIVE_SOURCE"
            if status == "DEFERRED_ENTRY_2026_NATIVE_SOURCE_NOT_READ" else
            "ELIGIBLE_NEEDS_VERIFIED_NATIVE_RAW_OPEN_AND_PIT_CHAIN"
        ),
        "prior_24h_news_articles": 1,
        "prior_7d_news_articles": 3,
    }


def _native():
    cases = [
        _case("early2021",2021,"03-01","03-02","04-16","20.0"),
        _case("late2021",2021,"10-01","10-04","11-19","60.0"),
        _case("rank2022",2022,"03-01","03-02","04-14","50.0"),
        _case("same2022",2022,"03-01","03-02","04-14","51.0"),
        _case("other2022",2022,"04-01","04-04","05-20","52.0"),
        _case("noexpiry2022",2022,"05-02","05-03",None,"10.0",
              "VERIFIED_NATIVE_RAW_OPEN_NO_MONTHLY_EXPIRY"),
        _case("year2023",2023,"03-01","03-02","04-14","20.0"),
        _case("year2024",2024,"03-01","03-04","04-19","30.0"),
        _case("pilot2025",2025,"03-03","03-04","04-17","40.0"),
        {
            **_case("late2025",2025,"12-31","12-31","2026-02-20",None,
                    "DEFERRED_ENTRY_2026_NATIVE_SOURCE_NOT_READ"),
            "entry_session":"2026-01-02",
            "planned_option_decision_at_utc":"2026-01-02T14:35:00+00:00",
        },
    ]
    native = {
        "contract":m.NATIVE_CONTRACT,
        "status":"MULTIYEAR_NATIVE_RAW_OPEN_VERIFIED_SOURCE_ONLY",
        "authority":m.NATIVE_AUTHORITY,
        "provider_requests":0, "protected_outcomes_read":0,
        "case_denominator":len(cases),
        "verified_native_raw_open_cases":len(cases)-1,
        "deferred_2026_entry_cases":1,
        "rows":cases,
    }
    native["source_fingerprint"]=_fingerprint(native)
    return native


def _index():
    return {
        "quote_plan_fingerprint":m.ACCEPTED_2022_QUOTE_PLAN,
        "original_rank_zero_representatives":2643,
        "unique_original_quote_histories":6398,
        "same_key_case_ids":{"rank2022","same2022"},
        "rank_zero":{
            "rank2022":{
                "option_symbol":"TEST220414C00050000",
                "original_raw_open":"50",
                "original_expiration":"2022-04-15",
                "original_chain_request_identity":"a"*64,
                "original_chain_body_sha256":"b"*64,
            }
        },
    }


def test_full_case_inventory_statuses_and_only_provisional_groups():
    native,index=_native(),_index()
    result=m.freeze_option_source_gap_inventory(
        native,index,rolling_floor=date(2021,9,27)
    )
    assert result["case_denominator"]==10
    assert result["2022_case_overlaps_not_new_contract_selections"]==1
    assert result["provisional_group_count"]==4
    assert result["new_paid_requests"]==result["provider_requests"]==0
    assert sum(sum(y.values()) for y in result["by_year"].values())==10
    d={x["case_id"]:x for x in result["cases"]}
    assert d["early2021"]["source_disposition"]=="DECISION_OUTSIDE_ROLLING_PROVIDER_WINDOW"
    assert d["late2021"]["source_disposition"]=="PIT_CHAIN_SOURCE_REQUEST_CANDIDATE"
    assert d["rank2022"]["source_disposition"]=="ORIGINAL_2022_PREFERRED_CALL_PLAN_MATCH"
    assert d["rank2022"]["original_2022_option_symbol_pointer"]=="TEST220414C00050000"
    assert d["same2022"]["source_disposition"]=="ORIGINAL_2022_SAME_KEY_RECONCILIATION_REQUIRED"
    assert d["other2022"]["source_disposition"]=="ORIGINAL_2022_CHAIN_RECONCILIATION_REQUIRED"
    assert d["noexpiry2022"]["source_disposition"]=="NO_BOUNDED_MONTHLY_EXPIRATION"
    assert d["pilot2025"]["source_disposition"]=="ORIGINAL_2025_PILOT_RECONCILIATION_REQUIRED"
    assert d["late2025"]["source_disposition"]=="DEFERRED_2026_NATIVE_ENTRY"
    assert result["authority"]["2022_original_chain_coverage_inferred_from_quote_plan"] is False
    assert result["authority"]["new_paid_request_authority"] is False
    assert all(x["selected_for_new_paid_get"] is False for x in result["cases"])
    assert all(g["source_status"].startswith("PROVISIONAL_UNPAID") for g in
               result["provisional_chain_groups"])
    assert result["inventory_fingerprint"]==_fingerprint({
        k:v for k,v in result.items() if k!="inventory_fingerprint"
    })


def test_original_2022_rank_source_mismatch_and_missing_price_fail_closed():
    native,index=_native(),_index()
    index["rank_zero"]["rank2022"]["original_raw_open"]="999"
    with pytest.raises(m.MultiYearOptionInventoryError,match="original price"):
        m.freeze_option_source_gap_inventory(native,index,rolling_floor=date(2021,9,27))
    native,index=_native(),_index()
    native["rows"][0]["raw_underlying_price"]=None
    native["source_fingerprint"]=_fingerprint({
        k:v for k,v in native.items() if k!="source_fingerprint"
    })
    with pytest.raises(m.MultiYearOptionInventoryError,match="invented raw"):
        m.freeze_option_source_gap_inventory(native,index,rolling_floor=date(2021,9,27))


def test_builder_reuses_derived_inventory_without_reopening_2022_plan(tmp_path,monkeypatch):
    native,index=_native(),_index()
    monkeypatch.setattr(m,"original_2022_quote_index",
                        lambda plan:index if plan=={"original":"fake"} else pytest.fail("unexpected"))
    settings=SimpleNamespace(
        project_root=tmp_path, resolved_path=lambda path:tmp_path/path,
        assert_external_storage_binding=lambda name:
            None if name in {"options","research_evidence"} else pytest.fail("binding"),
    )
    original=settings.resolved_path(f"{m.PLAN_REL}/through_shard_070.json")
    original.parent.mkdir(parents=True)
    original.write_text(json.dumps({"original":"fake"}),encoding="utf-8")
    calls=[]
    def accepted(settings,*,progress=None):
        calls.append("native")
        return native,tmp_path/"already-complete.json","REUSED_VERIFIED_NATIVE_SOURCE_NO_RAW_RESCAN"
    first=m.build_option_source_gap_inventory(
        settings,rolling_floor=date(2021,9,27),native_builder=accepted
    )
    assert first[2]=="WRITTEN_NEW_OPTIONS_SOURCE_GAP_INVENTORY"
    original.unlink()
    second=m.build_option_source_gap_inventory(
        settings,rolling_floor=date(2021,9,27),native_builder=accepted
    )
    assert second[2]=="REUSED_VERIFIED_OPTION_INVENTORY_NO_SOURCE_RESCAN"
    assert first[0]==second[0] and len(calls)==2
    first[1].write_text("{}",encoding="utf-8")
    with pytest.raises(m.MultiYearOptionInventoryError,match="drifted"):
        m.build_option_source_gap_inventory(
            settings,rolling_floor=date(2021,9,27),native_builder=accepted
        )
