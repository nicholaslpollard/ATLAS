from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import (
    normalize_source_requirement,
)
from scripts.run_spy_v64_offline_two_clock_forensics import (
    QUOTE_METHOD, REQUEST, V64Error,
    _receipt_row,_stock_by_clock,_options_by_clock,
    audit,verify_stock_page_evidence,
)


DAY="2025-06-13"
QID="f"*64
SHA="b"*64


def _signed(v):
    return {**v,"fingerprint":_fingerprint(v)}


def stock(t,bid,ask):
    return {
        "t":DAY+"T"+t+"-04:00",
        "bp":bid,"ap":ask,"bs":10,"as":11,"bx":"N","ax":"P","c":[],
    }


def fixture_files(tmp):
    original_rows=[
        stock("09:59:58.642976211",598.10,598.20),
        stock("09:59:59.999999999",598.30,598.32),
        stock("10:00:00.999999999",598.60,598.61),
        stock("10:00:01.000000001",599.80,599.90),
        stock("10:00:02.000000000",598.70,598.75),
    ]
    source=tmp/"page_0001.json"
    payload={"symbol":"SPY","quotes":original_rows,"next_page_token":None}
    raw=json.dumps(payload).encode()
    source.write_bytes(raw)
    v61=_signed({
        "contract":"atlas-v61-independent-action-side-source-readiness-v1",
        "session":DAY,
        "original_report":{
            "source_query_id":QID,"source_sha256":SHA,
            "selected_contract":{
                "symbol":"SPY","date_et":DAY,
                "expiration":DAY,"strike":"598","right":"put",
            },
        },
    })
    v61_path=tmp/"v61.json"
    v61_path.write_text(json.dumps(v61),encoding="utf-8")
    v62=_signed({
        "contract":"atlas-v62-bounded-alpaca-spy-historical-nbbo-source-v1",
        "status":"COMPLETE_SOURCE_WINDOW","session":DAY,"stock_feed":"sip",
        "source_window_start":DAY+"T09:59:58-04:00",
        "source_window_end":DAY+"T10:00:02-04:00",
        "original_quote_rows":len(original_rows),
        "target_decision_at_et":DAY+"T10:00:01-04:00",
        "source_page_count":1,
        "parent_v61_report_fingerprint":v61["fingerprint"],
        "original_pages":[{"page_ordinal":1,"raw_file":str(source),
                           "raw_sha256":hashlib.sha256(raw).hexdigest(),
                           "original_raw_bytes":len(raw),
                           "row_count":len(original_rows)}],
    })
    v62_path=tmp/"v62.json"
    v62_path.write_text(json.dumps(v62),encoding="utf-8")
    return v61_path,v62_path,v61,v62,source


def option_rows():
    quotes=[
        ("09:59:59","1.73","1.78"),
        ("10:00:00","1.70","1.81"),
        ("10:00:01","1.05","1.60"),
        ("10:00:02","1.39","1.60"),
    ]
    return tuple({
        "timestamp":DAY+"T"+stamp+"-04:00",
        "symbol":"SPY","expiration":DAY,"strike":"598","right":"put",
        "bid":bid,"ask":ask,"bid_size":2,"ask_size":5,
    } for stamp,bid,ask in quotes)


def cached():
    return {"cache_evidence":"CACHE_HIT","source":{
        "status":"CACHE_HIT","query_id":QID,"source_sha256":SHA,
        "source_rows":option_rows(),
    }}


def receipt(state="FAILED_RETRYABLE"):
    req=normalize_source_requirement(QUOTE_METHOD,dict(REQUEST))
    qid=_fingerprint(req)
    return (qid,json.dumps(req,sort_keys=True,separators=(",",":")),
            state,1761905705.0,None,None,None,None)


def test_read_only_failure_receipt_is_never_automatic_retry():
    rq=normalize_source_requirement(QUOTE_METHOD,dict(REQUEST))
    outcome=_receipt_row(None,reader=lambda qid:receipt())
    assert outcome["exact_query_id"]==_fingerprint(rq)
    assert outcome["state"]=="FAILED_RETRYABLE"
    assert outcome["v38_automatic_retry_risk"] is True
    assert outcome["provider_dispatch_outcome"]=="UNKNOWN_AFTER_EXCEPTION"
    assert outcome["safe_to_retry_same_exact_query"] is False


def test_archive_not_mistaken_for_safe_to_retry():
    r=_receipt_row(None,reader=lambda qid:receipt("ARCHIVED"))
    assert r["state"]=="ARCHIVED"
    assert r["original_archive_integrity"]=="ARCHIVED_METADATA_ONLY_INJECTED_TEST"
    assert r["safe_to_retry_same_exact_query"] is False


def test_missing_receipt_not_assumed_never_dispatched():
    row=_receipt_row(None,reader=lambda qid:None)
    assert row["state"]=="NO_V38_RECORD"
    assert row["query_is_not_proven_never_dispatched"]
    assert row["safe_to_retry_same_exact_query"] is False


def test_spy_seconds_exclude_future_nano_quotes(tmp_path):
    v61,v62,_,_,_=fixture_files(tmp_path)
    doc,stocks,prior=_stock_by_clock(v62)
    assert doc["original_quote_rows"]==5
    assert stocks["10:00:00"]["original_quote_clock"].endswith(
        "09:59:59.999999999-04:00")
    assert stocks["10:00:01"]["original_quote_clock"].endswith(
        "10:00:00.999999999-04:00")
    assert stocks["10:00:01"]["bid"]=="598.6"
    assert "599.80" not in str(stocks["10:00:01"])
    assert prior["original_quote_clock"]==DAY+"T09:59:58.642976211-04:00"
    assert stocks["10:00:02"]["usable_at_june_13_10_00_01"] is False


def test_option_invalid_bid_retained_not_interpolated():
    from datetime import date
    source=cached()["source"]
    contract={"symbol":"SPY","date_et":DAY,"right":"put",
              "strike":"598","expiration":DAY}
    report=_options_by_clock(source,contract)
    assert report["10:00:01"]["status"]=="ORIGINAL_V55_QUOTE_REJECTED"
    assert report["10:00:01"]["bid"]=="1.05"
    assert report["10:00:01"]["ask"]=="1.60"
    assert report["10:00:00"]["bid"]=="1.70"
    assert report["10:00:02"]["original_quote_not_executable_fill"]


def test_complete_offline_report_preserves_sources_and_no_fills(tmp_path):
    v61,v62,original,stock_doc,raw_path=fixture_files(tmp_path)
    report=audit(
        v62,v61,tmp_path/"v64.json",
        settings_factory=lambda *args:object(),
        receipt_read=lambda qid:receipt(),
        cache_read=lambda settings,qid:cached(),
        log=lambda _:None,
    )
    assert report["v63_exact_cache_receipt"]["state"]=="FAILED_RETRYABLE"
    assert report["option_price_change_1000_1001"]["bid_change_dollars"]=="-0.65"
    assert report["option_price_change_1000_1001"]["ask_change_dollars"]=="-0.21"
    assert report["option_price_change_1000_1001"]["bid_more_negative_than_ask"] is True
    assert report["stock_mid_change_1000_1001"]["mid_change_dollars"]=="0.295"
    assert report["independent_iv_estimated"] is False
    assert report["action_side_rescued"] is False
    assert report["provider_requests"]==0
    assert report["broker_orders"]==0
    assert report["cash_equity_modified"] is False
    assert report["fingerprint"]==_fingerprint({
        k:v for k,v in report.items() if k!="fingerprint"
    })
    assert raw_path.is_file()


def test_unchanged_stock_source_sha_required(tmp_path):
    v61,v62,_,_,source=fixture_files(tmp_path)
    source.write_bytes(source.read_bytes()+b" ")
    with pytest.raises(V64Error,match="STOCK_ORIGINAL_PAGE_SHA_CHANGED"):
        verify_stock_page_evidence(v62)


def test_parent_identity_mismatch_stops_audit(tmp_path):
    v61,v62,_,_,_=fixture_files(tmp_path)
    doc=json.loads(v62.read_text())
    doc["parent_v61_report_fingerprint"]="c"*64
    doc["fingerprint"]=_fingerprint({
        k:v for k,v in doc.items() if k!="fingerprint"
    })
    v62.write_text(json.dumps(doc))
    with pytest.raises(V64Error,match="V64_V61_V62_PARENT_DISAGREEMENT"):
        audit(v62,v61,tmp_path/"blocked.json",
              settings_factory=lambda *args:object(),
              receipt_read=lambda qid:receipt(),
              cache_read=lambda settings,qid:cached(),
              log=lambda _:None)
    assert not (tmp_path/"blocked.json").exists()
