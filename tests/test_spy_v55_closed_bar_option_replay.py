from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import json

import pytest

from packages.simulation.spy_v55_closed_bar_option_replay import (
    closed_bar_signal, replay_source, V55Error,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

ET = ZoneInfo("America/New_York")
DAY = date(2025,6,9)


def minute(i, *, o="100", h="101", l="99", c="100"):
    stamp=datetime(2025,6,9,9,30,tzinfo=ET)+timedelta(minutes=i)
    return {"symbol":"SPY","timestamp_utc":stamp.astimezone(ZoneInfo("UTC")),
            "open":o,"high":h,"low":l,"close":c}


def minutes():
    return [minute(i) for i in range(5)]+[
        minute(5,o="100",h="103",l="100",c="102"),
        minute(6,o="102",h="103",l="101",c="102"),
    ]


def signal(rows=None):
    return closed_bar_signal(
        rows if rows is not None else minutes(),
        session=DAY,source_sha256="a"*64,source_unit_id="unit-2025-06",
    )


def quote(second, bid="1.05", ask="1.11"):
    return {
        "timestamp_et":f"2025-06-09T09:36:{second:02d}-04:00",
        "symbol":"SPY","expiration":"2025-06-09","strike":102,
        "right":"call", "bid":bid, "ask":ask, "bid_size":20,"ask_size":20,
    }


def source(rows):
    return {"status":"CACHE_HIT", "query_id":"z"*64,
            "source_sha256":"b"*64,
            "source_rows":list(rows),
            "exact_requirement":{
                "method":"option_history_exact_quote_tape",
                "kwargs":{"symbol":"SPY","date_et":"2025-06-09",
                          "expiration":"2025-06-09","strike":"102",
                          "right":"call","interval":"1s",
                          "start_time_et":"09:36:01.000",
                          "end_time_et":"15:30:00.000"}
            }}


def test_closed_bar_variant_sees_only_completed_close_not_high():
    rows=[minute(i) for i in range(5)]
    rows += [minute(5,o="100",h="103",l="99",c="100"),
             minute(6,o="100",h="102",l="99",c="101.5")]
    a=signal(rows)
    assert a["decision_at_et"].startswith("2025-06-09T09:37:01")
    assert a["selected_contract"]["strike"]=="102"
    assert not a["first_breakout_tick_proven"]
    assert not a["first_publication_independently_proven"]
    assert a["strategy_version"] != "external-spy-0dte-opening-range-breakout-published-v1"


def test_quote_reference_entry_exit_with_realistic_bid_ask_costs_and_logging():
    a=signal()
    logs=[]
    r=replay_source(a,source([quote(1,bid="1.00",ask="1.10"),
                               quote(2),
                               quote(3,bid="2.30",ask="2.34")]),
                    progress=logs.append)
    assert r["status"]=="CLOSED_QUOTE_REFERENCE"
    assert r["entry_debit"]=="446.60"
    assert r["exit_credit"]=="917.40"
    assert r["trade_net_pnl"]=="470.80"
    assert r["terminal_equity_if_resolved"]=="25470.80"
    assert [x["type"] for x in r["events"]].count("OPPORTUNITY")==1
    assert [x["type"] for x in r["events"]].count("MODELED_EXIT_QUOTE_REFERENCE")==1
    assert r["publication_verified"] is False
    assert r["valid_historical_alpha"] is False
    assert r["actual_fills"]==0
    assert "PROGRESS_100PCT" in " ".join(logs)


def test_stop_price_and_unresolved_long_path_not_silently_zero():
    a=signal()
    normal=source([quote(1),quote(2),quote(3,bid="0.50",ask="0.58")])
    r=replay_source(a,normal)
    assert r["status"]=="CLOSED_QUOTE_REFERENCE"
    assert r["trade_net_pnl"].startswith("-")
    skipped=replay_source(a,source([quote(1),quote(2),
                                    {"timestamp_et":"2025-06-09T09:39:10-04:00",
                                     "bid":"2.30","ask":"2.35",
                                     "bid_size":10,"ask_size":10}]))
    assert skipped["status"]=="UNRESOLVED_POSITION"
    assert skipped["terminal_equity_if_resolved"] is None
    assert skipped["trade_net_pnl"] is None
    assert skipped["censor_reason"]=="QUOTE_PATH_GAP_OVER_60_SECONDS"


def test_corrupted_future_price_does_not_reject_earlier_entry():
    a=signal()
    r=replay_source(a,source([quote(1),quote(2),quote(3,bid="2.30",ask="2.34"),
                              {"timestamp_et":"2025-06-09T09:36:04-04:00",
                               "bid":"corrupt","ask":"2.50"}]))
    assert r["status"]=="CLOSED_QUOTE_REFERENCE"
    assert r["trade_net_pnl"]=="470.80"
    # If the corrupt quote is encountered before exit, terminal value is unknown.
    x=replay_source(a,source([quote(1),quote(2),
                              {"timestamp_et":"2025-06-09T09:36:03-04:00",
                               "bid":"corrupt","ask":"2.50"}]))
    assert x["status"]=="UNRESOLVED_POSITION"
    assert x["terminal_equity_if_resolved"] is None


def test_invalid_source_identity_and_action_price_are_abstentions_not_fills():
    a=signal()
    q=source([quote(1),quote(2)])
    q["exact_requirement"]["kwargs"]["right"]="put"
    assert replay_source(a,q)["censor_reason"]=="OPTION_SOURCE_EXACT_IDENTITY_INVALID"
    q=source([quote(1),quote(2,bid="1.30",ask="1.40")])
    r=replay_source(a,q)
    assert r["status"]=="NO_ENTRY"
    assert r["censor_reason"]=="ACTION_ASK_PRICE_CHANGE_OVER_LIMIT"
    assert r["terminal_equity_if_resolved"]=="25000.00"


def test_no_signal_or_absent_prior_candle_cannot_generate_provider_demand():
    a=signal([minute(0),minute(1),minute(3),minute(4),minute(5,o="100",h="103",l="99",c="102")])
    assert a["selected_contract"] is None
    assert a["signal_status"]=="MISSING_OPENING_MINUTE"
    r=replay_source(a,None)
    assert r["status"]=="NO_SIGNAL"
    assert r["terminal_equity_if_resolved"]=="25000.00"


def test_reject_lookahead_bad_order_and_duplicate_timestamp():
    a=signal()
    duplicate=source([quote(1),quote(1)])
    assert replay_source(a,duplicate)["censor_reason"]=="AMBIGUOUS_OR_OUT_OF_ORDER_QUOTE_TAPE"
    with pytest.raises(V55Error,match="SIGNAL_FINGERPRINT_CHANGED"):
        replay_source(dict(a,selected_contract=None),None)


def test_workstation_runner_announces_blocking_stage_before_provider_and_saves(tmp_path, monkeypatch):
    from scripts import run_spy_v55_closed_bar_quote_replay as cli
    unit=SimpleNamespace(year=2025,month=6,symbols=("SPY",),
        unit_id="native-test",canonical_sha256="a"*64,
        checkpoint_path=tmp_path/"checkpoint.json",
        canonical_path=tmp_path/"unit.parquet")
    monkeypatch.setattr(cli,"discover_minute_units",lambda *args,**kwargs:(unit,))
    monkeypatch.setattr(cli,"_verify_monthly_unit_with_progress",
                        lambda _unit,emit:emit("STAGE_PASS original_SHA_test") or {"accepted":True})
    monkeypatch.setattr(cli,"_sample_rows",lambda *args,**kwargs:minutes())
    monkeypatch.setattr(cli,"validate_minute_rows",
                        lambda *args,**kwargs:{"accepted":True,"warnings":[]})
    monkeypatch.setattr(cli,"load_settings",lambda *args:object())
    lines=[]
    def provider(_settings,method,kwargs):
        assert any("STAGE_START exact_selected_contract_intraday_quote_source" in x for x in lines)
        assert method=="option_history_exact_quote_tape"
        assert kwargs["strike"]=="102" and kwargs["right"]=="call"
        return source([quote(1),quote(2),quote(3,bid="2.30",ask="2.34")])
    out=tmp_path/"run.json"
    rc=cli.run("2025-06-09",output=out,emit=lines.append,source_get=provider)
    assert rc==0 and out.is_file()
    assert out.with_suffix(".jsonl").is_file()
    result=json.loads(out.read_text())
    assert result["trade_net_pnl"]=="470.80"
    assert result["observed_provider_requests"]==0
    assert any("STAGE_START read_one_session" in x for x in lines)
    assert any("PROGRESS_10PCT" in x for x in lines)
    assert lines[-1].startswith("COMPLETE")


def test_one_source_failure_is_archived_as_no_entry_not_fake_loss(tmp_path,monkeypatch):
    from scripts import run_spy_v55_closed_bar_quote_replay as cli
    unit=SimpleNamespace(year=2025,month=6,symbols=("SPY",),
        unit_id="native-test",canonical_sha256="a"*64,
        checkpoint_path=tmp_path/"checkpoint.json",
        canonical_path=tmp_path/"unit.parquet")
    monkeypatch.setattr(cli,"discover_minute_units",lambda *args:(unit,))
    monkeypatch.setattr(cli,"_verify_monthly_unit_with_progress",lambda *args:{"accepted":True})
    monkeypatch.setattr(cli,"_sample_rows",lambda *args,**kwargs:minutes())
    monkeypatch.setattr(cli,"validate_minute_rows",lambda *args,**kwargs:{"accepted":True,"warnings":[]})
    monkeypatch.setattr(cli,"load_settings",lambda *args:object())
    def failed(*args,**kwargs):
        raise RuntimeError("private token must not appear")
    lines=[]
    path=tmp_path/"failure.json"
    rc=cli.run("2025-06-09",output=path,emit=lines.append,source_get=failed)
    result=json.loads(path.read_text())
    assert result["status"]=="NO_ENTRY"
    assert result["trade_net_pnl"] is None
    assert result["observed_provider_requests"] is None
    assert not any("private token" in x for x in lines)
    assert rc==2


def test_hash_chained_journal_detects_tampering_and_truncation(tmp_path):
    from packages.simulation.spy_v55_event_journal import save_journal,verify_journal,JournalError
    r=replay_source(signal(),source([quote(1),quote(2),quote(3,bid="2.30",ask="2.34")]))
    path=tmp_path/"journal.jsonl"
    receipt=save_journal(path,r)
    assert receipt["runtime_events"]==len(r["events"])
    assert receipt["tip_sha256"]==verify_journal(path)["tip_sha256"]
    with pytest.raises(JournalError,match="OUTPUT_EXISTS"):
        save_journal(path,r)
    raw=path.read_text()
    path.write_text(raw.replace("CLOSED_QUOTE_REFERENCE","FAKE_PROFIT",1))
    with pytest.raises(JournalError,match="BROKEN_SEQUENCE_OR_SHA"):
        verify_journal(path)
    path.write_text(raw.splitlines(True)[0])
    with pytest.raises(JournalError,match="TRUNCATED_OR_INCONSISTENT"):
        verify_journal(path)


def test_journal_streaming_milestones_are_real_record_counts(tmp_path):
    from packages.simulation.spy_v55_event_journal import save_journal
    r=replay_source(signal(),source([quote(1),quote(2),quote(3,bid="2.30",ask="2.34")]))
    lines=[]
    save_journal(tmp_path/"events.jsonl",r,progress=lines.append)
    for n in range(10,101,10):
        assert any(line.startswith(f"PROGRESS_{n}PCT") for line in lines)


def test_thetadata_history_naive_et_timestamp_is_explicitly_unverified():
    rows=[quote(1),quote(2),quote(3,bid="2.30",ask="2.34")]
    for item in rows:
        item["timestamp"]=item.pop("timestamp_et").replace("-04:00","")
    replay=replay_source(signal(),source(rows))
    assert replay["status"]=="CLOSED_QUOTE_REFERENCE"
    assert replay["naive_provider_history_timestamp_interpreted_as_ET_if_present"] is True
    assert replay["publication_verified"] is False
    assert replay["actual_fills"]==0
