from __future__ import annotations

from datetime import date
import json
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts.run_spy_v59_offline_quote_forensics import (
    _source_summary,_focus_event,_local_cache_only,ForensicError,investigate,
    PARENT,
)

DAY="2025-06-13"
QID="f"*64
SHA="a"*64


def signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def quote(sec,bid="1.20",ask="1.22",size=30):
    return {"timestamp_et":f"{DAY}T10:30:{sec:02d}-04:00",
            "symbol":"SPY","date_et":DAY,"expiration":DAY,
            "strike":"600","right":"call",
            "bid":bid,"ask":ask,"bid_size":size,"ask_size":40}


def sample_report(status="UNRESOLVED_POSITION",reason="UNQUALIFIED_EXIT_QUOTE_PATH"):
    events=[
        {"type":"OPPORTUNITY"},
        {"type":"ORDER_ACTION_QUOTE_REFERENCE"},
        {"type":"MODELED_ENTRY_QUOTE_REFERENCE"},
        {"type":"EXIT_REVIEW","row":0,"quote":quote(0),"reason":"HOLD",
         "observed_gap_seconds":1.0},
        {"type":"EXIT_SOURCE_REJECTION","row":1,"at_et":f"{DAY}T10:30:01-04:00",
         "reason":"QUOTE_SPREAD_ABOVE_15_PERCENT"},
        {"type":"CLOSEOUT"},
    ]
    return signed({
        "session":DAY,"status":status,"censor_reason":reason,
        "source_status":"CACHE_HIT","source_query_id":QID,
        "source_sha256":SHA,
        "entry_debit":"474.60","exit_credit":None,"trade_net_pnl":None,
        "terminal_equity_if_resolved":None,
        "signal":{"signal_status":"COMPLETED_BAR_CLOSE_BREAKOUT",
                  "selected_contract":{"symbol":"SPY","date_et":DAY,
                                       "expiration":DAY,"strike":"600",
                                       "right":"call"},
                  "decision_at_et":DAY+"T10:29:58-04:00"},
        "events":events,
    })


def setup(tmp_path,status="UNRESOLVED_POSITION",reason="UNQUALIFIED_EXIT_QUOTE_PATH"):
    root=tmp_path/"cohort"
    root.mkdir()
    child=sample_report(status,reason)
    (root/f"{DAY}.json").write_text(json.dumps(child),encoding="utf8")
    parent=signed({
        "contract":PARENT,"sessions_evaluated":1,
        "calendar_weekday_sessions_expected":10,
        "account_status":"UNRESOLVED_OR_SOURCE_BLOCKED",
        "blocker":{"session":DAY,"reason":reason},
        "sessions":[{
            "session":DAY,"status":status,
            "report_fingerprint":child["fingerprint"],
            "event_journal_tip":"b"*64,
        }],
    })
    (root/"summary.json").write_text(json.dumps(parent),encoding="utf8")
    return root,child


def archive(quotes):
    return {
        "cache_evidence":"CACHE_HIT",
        "source":{"query_id":QID,"source_sha256":SHA,
                  "source_rows":quotes,
                  "exact_requirement":{
                      "method":"option_history_exact_quote_tape",
                      "kwargs":{"symbol":"SPY","date_et":DAY,
                                "expiration":DAY,"strike":"600",
                                "right":"call"}}},
    }


def verify(_path):
    return {"report_fingerprint":sample_report()["fingerprint"],
            "tip_sha256":"b"*64,"runtime_events":6}


def test_offline_forensic_extracts_exact_rejected_quote_and_neighbors(tmp_path):
    root,child=setup(tmp_path)
    rows=[quote(0),quote(1,bid="1.00",ask="1.30"),quote(2)]
    output=tmp_path/"audit.json"
    got=investigate(root,output,dates=[DAY],
                    cache_reader=lambda q:archive(rows),
                    verify=verify,emit=lambda _:None)
    assert output.is_file()
    assert got["provider_requests"]==0
    assert got["broker_requests"]==0
    assert got["original_expected_weekdays"]==10
    assert got["original_evaluated_days"]==1
    row=got["dates"][0]
    assert row["status"]=="UNRESOLVED_POSITION"
    assert row["censor_reason"]=="UNQUALIFIED_EXIT_QUOTE_PATH"
    assert row["focus_event"]["source_row_index"]==1
    assert row["quote_quality_audit"]["original_source_rows"]==3
    assert row["quote_quality_audit"]["quality_class_counts"]["QUALIFIED_QUOTES"]==2
    focus=row["quote_quality_audit"]["focus_quote_neighborhood"][1]
    assert focus["validation"]=="UNQUALIFIED"
    assert "QUOTE_SPREAD_ABOVE_15_PERCENT" in focus["validation_reason"]
    assert got["fingerprint"]==_fingerprint({
        k:v for k,v in got.items() if k!="fingerprint"})


def test_parent_journal_mismatch_blocks_prior_to_archive_inspection(tmp_path):
    root,_=setup(tmp_path)
    seen=[]
    with pytest.raises(ForensicError,match="DAY_CHAIN_RECEIPT_DISAGREES"):
        investigate(root,tmp_path/"audit.json",
                    cache_reader=lambda q:seen.append(q),
                    verify=lambda p:{"report_fingerprint":"0"*64,
                                     "tip_sha256":"b"*64},
                    emit=lambda _:None)
    assert seen==[]
    assert not (tmp_path/"audit.json").exists()


def test_undamaged_original_source_fingerprint_is_required(tmp_path):
    root,_=setup(tmp_path)
    data=json.loads((root/f"{DAY}.json").read_text())
    data["entry_debit"]="12.00"
    (root/f"{DAY}.json").write_text(json.dumps(data))
    with pytest.raises(ForensicError,match="SOURCE_REPORT_FINGERPRINT_INVALID"):
        investigate(root,tmp_path/"audit.json",
                    cache_reader=lambda q:archive([]),
                    verify=verify,emit=lambda _:None)


def test_cached_source_identity_mismatch_is_never_promoted(tmp_path):
    root,_=setup(tmp_path)
    s=archive([quote(0)])
    s["source"]["source_sha256"]="c"*64
    with pytest.raises(ForensicError,match="CACHED_SOURCE_AND_DAY_REPORT_SHA_MISMATCH"):
        investigate(root,tmp_path/"audit.json",
                    cache_reader=lambda q:s,
                    verify=verify,emit=lambda _:None)


def test_no_archive_is_reported_as_unknown_without_get(tmp_path):
    root,_=setup(tmp_path)
    got=investigate(root,tmp_path/"audit.json",
                    cache_reader=lambda q:{"cache_evidence":"EXACT_QUERY_NOT_IN_INDEX",
                                            "source":None},
                    verify=verify,emit=lambda _:None)
    assert got["dates"][0]["quote_quality_audit"] is None
    assert got["dates"][0]["quote_archive_evidence"]=="EXACT_QUERY_NOT_IN_INDEX"
    assert got["dates"][0]["focus_event"]["reason"]=="QUOTE_SPREAD_ABOVE_15_PERCENT"
    assert got["provider_requests"]==0


def test_largest_gap_and_bad_quote_qualifiers_do_not_fabricate_cash():
    contract={"symbol":"SPY","expiration":DAY,"right":"call","strike":"600"}
    r=_source_summary({"source_rows":[quote(0),quote(1),
              quote(20,bid="1.00",ask="1.70",size=0)]},
              date.fromisoformat(DAY),contract,2)
    assert r["original_source_rows"]==3
    assert r["max_observation_gap_seconds"]==19
    assert r["quality_class_counts"]["QUALIFIED_QUOTES"]==2
    assert r["focus_quote_neighborhood"][-1]["validation"]=="UNQUALIFIED"


def test_focus_event_on_source_gap_returns_triggering_row():
    a=sample_report()
    doc={
        **a,"censor_reason":"QUOTE_PATH_GAP_OVER_60_SECONDS",
        "events":[{"type":"EXIT_REVIEW","row":10,
                   "observed_gap_seconds":70,
                   "quote":quote(0),"reason":"HOLD"}],
    }
    focus=_focus_event(doc)
    assert focus["source_row_index"]==10
    assert focus["observed_gap_seconds"]==70
