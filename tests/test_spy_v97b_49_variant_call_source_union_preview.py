from __future__ import annotations

"""V97B original CALL-only source-union synthetic tests, zero provider calls."""
from pathlib import Path
import json
import pytest

from scripts.run_spy_v97b_49_variant_call_source_union_preview import (
    V97BError,BASELINES,bullish,compute,params,source_key,read,
    historical_expiry,signed,
)

def row(family,features,side=None,source=None,session="2022-01-05",
        time="09:40:01",strike="400"):
    return {
        "cohort":"2022_full","session":session,"strategy":family,
        "original_side":side,
        "original_signal_status":(
            "OPTIONS_EXACT_SOURCE_DEMAND_PREPARED" if side else "NO_SIGNAL"
        ),
        "source_unqualified_null_original_decision":False,
        "CALL_only_source_status":source or (
            "NO_ORIGINAL_EXECUTABLE_OPTION_DEMAND" if not side else
            "CALL_VERIFIED_ORIGINAL_ARCHIVE"),
        "decision_at_et":f"{session}T{time}-05:00",
        "as_of_stock_feature_values":{
            "opening_price":"399.90","last_completed_close":strike,
            "first_leg_pct":"0.01","second_leg_pct":"0.00",**features},
        "exact_option_query_id":"b"*64 if side else None,
        "call_original_source_sha256":(
            "a"*64 if side and source!="CALL_ORIGINAL_SOURCE_UNRESOLVED" else None),
        "original_call_strike":strike if side else None,
        "original_call_expiry":session if side else None,
        "predecision_news_status":"PIT_NEWS_METADATA_SOURCE_WINDOW_AWAITING_SHA_CHECK",
        "original_decision_sha":"c"*64,"original_stock_sha256":"d"*64,
    }

def samples():
    return [
        row("impulse_0935",{"first_leg_pct":"0.20"},side="CALL",time="09:35:01"),
        row("acceleration_0940",{"first_leg_pct":"0.10","second_leg_pct":"0.20"},
            side="CALL",source="CALL_ORIGINAL_SOURCE_UNRESOLVED"),
        row("early_reversal_0940",{"first_leg_pct":"-0.10","second_leg_pct":"0.15"}),
        row("pullback_resume_0940",{"first_leg_pct":"0.25",
            "retracement_fraction":"0.40"},side="CALL",strike="401"),
        row("gap_followthrough_0940",{"gap_pct":"0.40","followthrough_pct":"0.10"}),
        row("compression_release_0940",{"compression_ratio":"0.60",
            "close_location_fraction":"0.90"},strike="402"),
    ]

def test_49_trials_reproduce_original_base_bullish_and_historical_listing():
    choices=params()
    assert len(choices)==49
    assert len({x["trial_id"] for x in choices})==49
    for item in samples():
        assert bullish(item["strategy"],item,BASELINES[item["strategy"]])==(
            item["original_side"]=="CALL")
    assert source_key(samples()[0])==("2022-01-05","09:35:01","400")
    assert historical_expiry("2018-01-02") is False
    assert historical_expiry("2018-02-26") is True
    assert historical_expiry("2022-11-22") is True

def test_new_source_preview_never_includes_original_unknown_or_provider_action():
    _,variants,events,needs,stats,archived,unknown=compute({},{"decisions":samples()})
    assert len(variants)==49 and events
    assert archived==2 and unknown==1 and needs
    assert all(x["provider_request_constructed_or_dispatched"] is False for x in needs)
    assert ("2022-01-05","09:40:01","400") not in {
        (x["session"],x["decision_clock_et"],x["strike"]) for x in needs
    }
    assert stats["ORIGINAL_PROVIDER_DISPATCH_UNKNOWN_NO_RETRY"]>0
    assert stats["NEW_EXACT_CALL_SOURCE_SCOPE_REQUIRES_SEPARATE_REVIEW"]>0
    assert all(e["point_in_time_news_counts_qualified"] is False for e in events)
    assert all(e["profitability_computed"] is False for e in events)

def test_changed_original_frozen_bullish_decision_is_not_accepted():
    rows=samples();rows[0]["original_side"]=None
    with pytest.raises(V97BError,match="BASELINE_FEATURE_REPRODUCTION_MISMATCH"):
        compute({},{"decisions":rows})

def test_conflicting_original_source_sha_or_query_fails_closed():
    rows=samples()
    duplicate=dict(rows[0],strategy="gap_followthrough_0940",
                   original_side="CALL",exact_option_query_id="e"*64)
    with pytest.raises(V97BError,match="CONFLICTING_EXACT_CALL_QUERY_SOURCE"):
        compute({},{"decisions":rows+[duplicate]})

def test_tampered_original_source_signature_cannot_be_reused(tmp_path):
    p=tmp_path/"source.json"
    doc=signed({"contract":"test","records":[1,2]})
    p.write_text(json.dumps(doc))
    assert read(p,"test")==doc
    doc["records"].append(3)
    p.write_text(json.dumps(doc))
    with pytest.raises(V97BError,match="SIGNED_ROOT_INVALID"):
        read(p,"test")
