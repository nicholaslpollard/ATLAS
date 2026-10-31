from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import json

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts.run_spy_v63_prior_option_surface_source import (
    PriorOptionSourceError,REQUEST,acquire,classify_option_source_rows,
    verify_stock_page_evidence,
)


DAY="2025-06-13"


def original(tmp,*,prior=True):
    path=tmp/"page_0001.json"
    q=[
        {"t":DAY+"T09:59:58.999999999-04:00","bp":598.1,"ap":598.2,
         "bs":10,"as":11,"c":[],"bx":"N","ax":"P"},
        {"t":DAY+"T10:00:00.999999999-04:00","bp":598.63,"ap":598.88,
         "bs":10,"as":11,"c":[],"bx":"N","ax":"P"},
    ] if prior else [{
        "t":DAY+"T10:00:01.000000001-04:00","bp":598.7,"ap":598.8,
        "bs":1,"as":2,"c":[],"bx":"N","ax":"P",
    }]
    raw=json.dumps({"symbol":"SPY","quotes":q,"next_page_token":None}).encode()
    path.write_bytes(raw)
    summary={
        "contract":"atlas-v62-bounded-alpaca-spy-historical-nbbo-source-v1",
        "session":DAY,"status":"COMPLETE_SOURCE_WINDOW","stock_feed":"sip",
        "parent_v61_report_fingerprint":"c"*64,
        "target_decision_at_et":DAY+"T10:00:01-04:00",
        "source_window_start":DAY+"T09:59:58-04:00",
        "source_window_end":DAY+"T10:00:02-04:00",
        "source_page_count":1,"original_quote_rows":len(q),
        "original_pages":[{"page_ordinal":1,"raw_file":str(path),
                           "raw_sha256":hashlib.sha256(raw).hexdigest(),
                           "original_raw_bytes":len(raw),"row_count":len(q)}],
    }
    summary["fingerprint"]=_fingerprint(summary)
    spath=tmp/"v62_summary.json"
    spath.write_text(json.dumps(summary),encoding="utf-8")
    return spath


def row(strike,*,bid=1.20,ask=1.25,t="09:59:59.000",expiry=DAY):
    return {
        "symbol":"SPY","strike":str(strike),"expiration":expiry,
        "right":"put","bid":bid,"ask":ask,"bid_size":10,"ask_size":10,
        "timestamp":DAY+"T"+t+"-04:00",
    }


def source(rows):
    return {
        "status":"FETCHED_AND_ARCHIVED",
        "exact_requirement":{"method":"option_at_time_quote_surface",
                             "kwargs":dict(REQUEST)},
        "source_rows":tuple(rows),
        "query_id":"f"*64,"source_sha256":"a"*64,
    }


def test_v62_original_sha_verified_and_nanosecond_cutoff(tmp_path):
    path=original(tmp_path)
    doc,ref=verify_stock_page_evidence(path)
    assert ref["original_quote_clock"]==DAY+"T09:59:58.999999999-04:00"
    assert ref["bid"]=="598.1"
    assert doc["source_page_count"]==1


def test_forensic_rejects_changed_original_page(tmp_path):
    path=original(tmp_path)
    page=tmp_path/"page_0001.json"
    page.write_text(page.read_text()+" ")
    with pytest.raises(PriorOptionSourceError,match="V63_STOCK_ORIGINAL_SHA_CHANGED"):
        verify_stock_page_evidence(path)


def test_source_surface_ignores_target_598_and_future_option_observations():
    data=classify_option_source_rows([
        row(598),row(597),row(599,t="10:00:00.000"),
        row(600,expiry="2025-06-20"),
        row(601,t="09:59:55.000"),
        row(596,bid=0.2,ask=0.6),
        {**row(595), "bid_size":1.5},
        {**row(594), "right":"P"},
    ])
    assert data["categorization"]["TARGET_PUT_EXCLUDED_FROM_INDEPENDENT_IV"]==1
    assert data["categorization"]["CANDIDATE_ALTERNATE_PUT_AT_PRIOR_CLOCK"]==1
    assert data["categorization"]["AFTER_PRECALIBRATION_TIMESTAMP"]==1
    assert data["categorization"]["OTHER_EXPIRY_NOT_0DTE"]==1
    assert data["categorization"]["STALE_PRIOR_QUOTE_OVER_2S"]==1
    assert data["categorization"]["WIDE_PRIOR_OPTION_SPREAD"]==1
    assert data["categorization"]["SOURCE_BID_ASK_UNQUALIFIED"]==1
    assert data["categorization"]["CANDIDATE_ALTERNATE_PUT_AT_PRIOR_CLOCK"]==2
    assert data["candidate_rows_do_not_equal_verified_independent_iv"] is True


def test_one_v38_source_call_and_no_provider_broker_side_effects(tmp_path):
    calls=[]
    def get(settings,method,kwargs):
        calls.append((settings,method,kwargs))
        return source([row(598),row(599)])
    path=original(tmp_path)
    result=acquire(path,tmp_path/"out.json",get=get,
                   settings_factory=lambda *a:object(),emit=lambda s:None)
    assert len(calls)==1
    assert calls[0][1]=="option_at_time_quote_surface"
    assert calls[0][2]==REQUEST
    assert result["status"]=="SOURCE_RECORDED_PRIOR_IV_NOT_YET_ESTIMATED"
    assert result["v38_source_row_classification"]["categorization"][
        "CANDIDATE_ALTERNATE_PUT_AT_PRIOR_CLOCK"]==1
    assert result["black_scholes_value_from_this_request"] is None
    assert result["volatility_calibration_status"]=="NOT_YET_CALIBRATED"
    assert result["broker_orders"]==0 and result["alpaca_provider_requests"]==0
    assert result["fingerprint"]==_fingerprint({k:v for k,v in result.items()
                                               if k!="fingerprint"})
    assert (tmp_path/"out.json").is_file()


def test_missing_spot_causes_no_thetadata_get(tmp_path):
    p=original(tmp_path,prior=False)
    calls=[]
    result=acquire(p,tmp_path/"no_source.json",
                   get=lambda *a:calls.append(a),
                   settings_factory=lambda *a:object(),emit=lambda s:None)
    assert not calls
    assert result["status"]=="ABSTAIN_NO_PRIOR_SPY_SPOT_AT_PRECALIBRATION"
    assert result["v38_query_id"] is None


def test_exact_provider_scope_cannot_be_falsified(tmp_path):
    path=original(tmp_path)
    r=source([row(599)])
    r["exact_requirement"]["kwargs"]["time_of_day_et"]="10:00:01.000"
    with pytest.raises(PriorOptionSourceError,match="V63_V38_SOURCE_PARAMETERS_CHANGED"):
        acquire(path,tmp_path/"bad.json",
                get=lambda *a:r,settings_factory=lambda *a:object(),
                emit=lambda s:None)
    assert not (tmp_path/"bad.json").exists()


def test_original_report_and_output_never_overwritten(tmp_path):
    path=original(tmp_path)
    target=tmp_path/"out.json"
    target.write_text("immutable",encoding="utf-8")
    with pytest.raises(PriorOptionSourceError,match="V63_IMMUTABLE_OUTPUT_ALREADY_EXISTS"):
        acquire(path,target,emit=lambda s:None)
    doc=json.loads(path.read_text())
    doc["status"]="FUTURE_UNKNOWN"
    path.write_text(json.dumps(doc))
    with pytest.raises(Exception,match="FINGERPRINT"):
        verify_stock_page_evidence(path)
