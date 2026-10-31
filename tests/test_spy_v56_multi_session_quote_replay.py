from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import json

import pytest

from packages.data.intraday_semantics_audit import discover_minute_units, IntradaySemanticsAuditError
from scripts.run_spy_v56_multi_session_quote_replay import simulate, dates_in_window

ET=ZoneInfo("America/New_York")


def spy_minutes(day):
    when=datetime(day.year,day.month,day.day,9,30,tzinfo=ET)
    def one(i,close="100",hi="101",lo="99"):
        return {"symbol":"SPY",
                "timestamp_utc":(when+timedelta(minutes=i)).astimezone(ZoneInfo("UTC")),
                "open":"100","high":hi,"low":lo,"close":close}
    return [one(i) for i in range(5)]+[one(5,close="102",hi="103",lo="100")]


def option_source(day,kwargs):
    def quote(second,bid="1.00",ask="1.10"):
        clock=datetime(day.year,day.month,day.day,9,36,second,tzinfo=ET)
        return {"timestamp_et":clock.isoformat(),"symbol":"SPY",
                "expiration":day.isoformat(),"strike":"102","right":"call",
                "bid":bid,"ask":ask,"bid_size":50,"ask_size":50}
    return {"status":"FETCHED_AND_ARCHIVED","query_id":f"query-{day}",
            "source_sha256":"b"*64,
            "source_rows":(quote(1),quote(2,bid="1.09",ask="1.10"),
                           quote(3,bid="2.30",ask="2.35")),
            "exact_requirement":{"method":"option_history_exact_quote_tape",
                                 "kwargs":kwargs}}


def fixtures(tmp_path,*,fail_on=None):
    calls={"discover":0,"integrity":0,"source":[],"sample":[]}
    unit=SimpleNamespace(
        year=2025,month=6,symbols=("SPY",),unit_id="unit-spy-june",
        canonical_sha256="a"*64,checkpoint_path=tmp_path/"month.json",
        canonical_path=tmp_path/"month.parquet",
    )
    def discovery(layout,*,target_year,target_month,progress):
        assert (target_year,target_month)==(2025,6)
        assert callable(progress)
        calls["discover"]+=1
        return (unit,)
    def integrity(u,emit):
        assert u is unit
        calls["integrity"]+=1
        emit("STAGE_PASS dummy_SHA_verification")
        return {"accepted":True}
    def sample(path,*,symbol,session_date):
        calls["sample"].append(session_date)
        return spy_minutes(session_date)
    def provider(settings,method,kwargs):
        day=date.fromisoformat(kwargs["date_et"])
        assert kwargs["interval"]=="1s" and kwargs["strike"]=="102"
        calls["source"].append(day)
        if fail_on==day:
            raise RuntimeError("PRIVATE_CREDENTIAL_SHOULD_NOT_LEAK")
        return option_source(day,kwargs)
    kw={"discover":discovery,"integrity":integrity,"sample":sample,
        "validate":lambda *args,**kwargs:{"accepted":True,"warnings":[]},
        "settings_factory":lambda *args:object(),"source_get":provider}
    return kw,calls


def test_scoped_discovery_searches_one_month_only_and_does_not_visit_other_checkpoint(tmp_path):
    month=tmp_path/"native_units"/"1m"/"year=2025"/"month=06"/"batch=0402"
    month.mkdir(parents=True)
    other=tmp_path/"native_units"/"1m"/"year=2024"/"month=10"/"batch=9999"
    other.mkdir(parents=True)
    (other/"broken.json").write_text("{ THIS MUST NEVER BE READ }")
    payload={
        "status":"COMPLETE",
        "unit_id":"native-unit-sha",
        "unit":{"year":2025,"month":6,"symbols":["SPY"],"canonical_timeframe":"1m"},
        "canonical":{"path":str(tmp_path/"canon.parquet"),"sha256":"a"*64},
        "raw_bundle":{"path":str(tmp_path/"orig.gz"),"sha256":"b"*64},
    }
    (month/"unit.json").write_text(json.dumps(payload))
    logs=[]
    units=discover_minute_units(SimpleNamespace(checkpoints=tmp_path),
             target_year=2025,target_month=6,progress=logs.append)
    assert len(units)==1 and units[0].unit_id=="native-unit-sha"
    assert any("completed=1/1" in x for x in logs)
    for n in range(10,101,10):
        assert any(x.startswith(f"PROGRESS_{n}PCT") for x in logs)
    assert any("year=2025" in x for x in logs)
    with pytest.raises(IntradaySemanticsAuditError,match="protected"):
        discover_minute_units(SimpleNamespace(checkpoints=tmp_path),
             target_year=2026,target_month=5)


def test_multi_day_one_month_sha_once_skip_weekday_then_compound_cash_and_journals(tmp_path):
    config,calls=fixtures(tmp_path)
    lines=[]
    output=tmp_path/"multi"
    rc=simulate(date(2025,6,9),date(2025,6,11),
                outdir=output,emit=lines.append,**config)
    assert rc==0
    assert calls["discover"]==1 and calls["integrity"]==1
    assert calls["source"]==[date(2025,6,9),date(2025,6,11)]
    assert calls["sample"]==[date(2025,6,9),date(2025,6,11)]
    result=json.loads((output/"summary.json").read_text())
    assert result["sessions_evaluated"]==3
    assert result["modeled_completed_trades"]==2
    assert result["session_status_counts"]=={
        "CLOSED_QUOTE_REFERENCE":2,"NO_SIGNAL":1}
    assert result["source_counts"]=={"FETCHED_AND_ARCHIVED":2}
    assert result["starting_cash"]=="25000.00"
    assert result["closed_net_pnl"]=="949.60"
    assert result["terminal_equity_if_complete"]=="25949.60"
    assert result["weekly"][0]["closed_trades"]==2
    assert result["monthly"][0]["closed_trades"]==2
    assert result["annual"][0]["closed_trades"]==2
    assert result["historical_profitability_validated"] is False
    assert result["actual_broker_fills"]==0
    assert (output/"2025-06-09.jsonl").is_file()
    assert (output/"2025-06-11.jsonl").is_file()
    assert result["sessions"][1]["signal_status"]=="WEEKDAY_OUTSIDE_MWF_VERSION"
    from packages.simulation.spy_v55_event_journal import verify_journal
    assert verify_journal(output/"2025-06-09.jsonl")["runtime_events"]>0
    assert verify_journal(output/"2025-06-11.jsonl")["runtime_events"]>0
    for n in range(10,101,10):
        assert any(x.startswith(f"PROGRESS_{n}PCT phase=chronological_weekday_sessions") for x in lines)
    assert lines[0].startswith("START V56")
    assert lines[-1].startswith("COMPLETE V56")


def test_source_error_preserves_full_day_and_halts_unknown_account(tmp_path):
    config,calls=fixtures(tmp_path,fail_on=date(2025,6,9))
    lines=[]
    out=tmp_path/"blocked"
    rc=simulate(date(2025,6,9),date(2025,6,11),outdir=out,
                emit=lines.append,**config)
    assert rc==2
    result=json.loads((out/"summary.json").read_text())
    assert result["sessions_evaluated"]==1
    assert result["account_status"]=="UNRESOLVED_OR_SOURCE_BLOCKED"
    assert result["terminal_equity_if_complete"] is None
    assert result["blocker"]["reason"]=="RuntimeError"
    assert result["sessions"][0]["trade_net_pnl"] is None
    assert result["source_counts"]=={"PROVIDER_OR_ARCHIVE_ERROR":1}
    assert (out/"2025-06-09.jsonl").is_file()
    assert (out/"checkpoint.json").is_file()
    assert not any("PRIVATE_CREDENTIAL" in x for x in lines)
    assert any("STAGE_START dynamic_exact_option_source" in x for x in lines)
    assert calls["source"]==[date(2025,6,9)]


def test_protected_period_and_no_overwrite():
    assert list(dates_in_window(date(2025,6,9),date(2025,6,11)))==[
        date(2025,6,9),date(2025,6,10),date(2025,6,11)]
    with pytest.raises(ValueError,match="PROTECTED"):
        list(dates_in_window(date(2026,5,11),date(2026,5,12)))
