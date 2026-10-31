from __future__ import annotations

from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import json
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts.run_spy_v61_independent_source_readiness import (
    ReadinessError,_prior_completed_spy_bar,_original_decision,probe,ORIGINAL,
)

ET=ZoneInfo("America/New_York")
DAY="2025-06-13"
TIP="b"*64
SOURCE_SHA="a"*64


def signed(v):
    return {**v,"fingerprint":_fingerprint(v)}


def bar(hour,minute,close,high=None,low=None):
    at=datetime(2025,6,13,hour,minute,tzinfo=ET)
    return {
        "symbol":"SPY","timestamp_utc":at.astimezone(timezone.utc).isoformat(),
        "open":close,"close":close,
        "high":close if high is None else high,
        "low":close if low is None else low,
    }


def fake_cohort(tmp_path):
    folder=tmp_path/"cohort"
    folder.mkdir()
    action={
        "type":"ORDER_ACTION_QUOTE_REFERENCE",
        "order":{"timestamp_et":DAY+"T09:59:01-04:00","ask":"1.15"},
        "action":{"timestamp_et":DAY+"T09:59:02-04:00","ask":"1.18"},
        "adverse_ask_change_pct":"2.6086956",
    }
    day=signed({
        "session":DAY,"status":"UNRESOLVED_POSITION",
        "censor_reason":"UNQUALIFIED_EXIT_QUOTE_PATH",
        "signal":{"selected_contract":{
            "symbol":"SPY","date_et":DAY,
            "expiration":DAY,"strike":"598","right":"put"},
            "decision_at_et":DAY+"T09:59:01-04:00"},
        "source_query_id":"c"*64,"source_sha256":SOURCE_SHA,
        "events":[{"type":"OPPORTUNITY"},action,{"type":"CLOSEOUT"}],
    })
    (folder/f"{DAY}.json").write_text(json.dumps(day),encoding="utf8")
    parent=signed({
        "contract":ORIGINAL,
        "sessions":[{"session":DAY,"status":"UNRESOLVED_POSITION",
                     "report_fingerprint":day["fingerprint"],
                     "event_journal_tip":TIP}],
    })
    (folder/"summary.json").write_text(json.dumps(parent),encoding="utf8")
    return folder,day,parent


def fake_verify(_):
    return {"report_fingerprint":fake_verify.fingerprint,
            "tip_sha256":TIP}
fake_verify.fingerprint=None


def test_last_completed_minute_never_leaks_current_minute_close():
    rows=[bar(9,58,599),bar(9,59,600,high=600.1,low=598.9),
          bar(10,0,10000)]
    source=_prior_completed_spy_bar(rows,DAY+"T10:00:01-04:00")
    assert source["available"] is True
    assert source["last_bar_close"]=="600"
    assert source["last_bar_high"]=="600.1"
    assert source["original_bar_start_et"]==DAY+"T09:59:00-04:00"
    assert source["second_level_spot_price_proven"] is False
    assert source["bar_close_first_publication_latency_proven"] is False
    assert source["market_price_at_exact_action_second_known"] is False


def test_no_completed_source_is_not_stock_spot_tick():
    source=_prior_completed_spy_bar([bar(10,0,600)],DAY+"T10:00:01-04:00")
    assert source["available"] is False
    assert source["second_level_spot_price_proven"] is False


def test_readiness_accepts_verified_archive_only_and_abstains(tmp_path):
    root,day,parent=fake_cohort(tmp_path)
    fake_verify.fingerprint=day["fingerprint"]
    unit=SimpleNamespace(year=2025,month=6,symbols=("SPY",),
                         unit_id="test-stock-month",
                         canonical_path=tmp_path/"stock.parquet",
                         canonical_sha256="d"*64,
                         checkpoint_path=tmp_path/"chk.json")
    lines=[]
    result=probe(
        root,tmp_path/"v61.json",
        day=DAY,decision_time="10:00:01",
        verify=fake_verify,
        discover=lambda layout,**kwargs:(unit,),
        integrity=lambda u,emit:{"accepted":True},
        sample=lambda *a,**k:[bar(9,59,600),bar(10,0,10000)],
        validate=lambda *a,**k:{"accepted":True},
        settings_factory=lambda *a:object(),
        source_inventory=lambda settings,day,qid:{
            "state":"READ_ONLY_RECEIPT_INDEX_INVENTORY",
            "candidate_receipts":[{"source_query_id":qid}],
            "candidate_counts":{"ARCHIVED":1},
            "independent_prior_volatility_verified":False,
        },
        progress=lines.append)
    assert result["original_report"]["original_report_fingerprint"]==day["fingerprint"]
    assert result["historical_stock_bar_evidence"]["last_bar_close"]=="600"
    assert result["historical_stock_bar_evidence"]["monthly_unit_source_sha256"]=="d"*64
    assert result["cached_options_receipt_inventory"]["candidate_receipts"][0][
        "source_query_id"]=="c"*64
    assert result["side_aware_bsm_reference_status"]=="ABSTAIN_MISSING_INDEPENDENT_MODEL_INPUTS"
    assert result["historical_independent_iv_band_verified"] is False
    assert result["provider_requests"]==0
    assert result["broker_orders"]==0
    assert result["cash_pnl_or_execution_changed"] is False
    assert (tmp_path/"v61.json").is_file()
    assert result["fingerprint"]==_fingerprint({k:v for k,v in result.items()
                                                 if k!="fingerprint"})
    assert any("COMPLETE V61" in line for line in lines)


def test_day_source_fingerprint_tamper_refused(tmp_path):
    root,day,parent=fake_cohort(tmp_path)
    fake_verify.fingerprint=day["fingerprint"]
    p=root/f"{DAY}.json"
    altered=json.loads(p.read_text())
    altered["status"]="CLOSED_QUOTE_REFERENCE"
    p.write_text(json.dumps(altered))
    with pytest.raises(Exception,match="FINGERPRINT"):
        _original_decision(parent,DAY,root,fake_verify)


def test_journal_tampering_refused(tmp_path):
    root,day,parent=fake_cohort(tmp_path)
    fake_verify.fingerprint="0"*64
    with pytest.raises(ReadinessError,match="V61_ORIGINAL_DAY_OR_JOURNAL_DISAGREES"):
        _original_decision(parent,DAY,root,fake_verify)


def test_readiness_output_not_overwritten(tmp_path):
    root,day,parent=fake_cohort(tmp_path)
    (tmp_path/"v61.json").write_text("immutable")
    with pytest.raises(ReadinessError,match="V61_IMMUTABLE_OUTPUT_EXISTS"):
        probe(root,tmp_path/"v61.json",verify=lambda p:None,progress=lambda s:None)
