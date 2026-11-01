from __future__ import annotations

"""V103 signed original V55/V65 replay and cash-censorship integration tests."""
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import gzip
import hashlib
import json

import pytest

from packages.simulation.spy_v103_offline_orb_causal_account import (
    V103Error, classify, chain_months, signed, verify, START,
)
from packages.simulation.spy_v55_closed_bar_option_replay import (
    closed_bar_signal, replay_source,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts.run_spy_v65_full_june_offline_simulator_readiness import _source_requirement
from scripts.run_spy_v103_multimonth_original_closedbar_orb import (
    month_bounds, frozen_calendar, run, original_gzip_once,
)

ET = ZoneInfo("America/New_York")
DAY = date(2025,6,9)
TUE = date(2025,6,10)
SHA = "a"*64


def minute(day, idx, price):
    at = datetime(day.year, day.month, day.day,9,30,tzinfo=ET)+timedelta(minutes=idx)
    return {"symbol":"SPY", "timestamp_utc":at.astimezone(ZoneInfo("UTC")).isoformat(),
            "open":str(price),"high":str(price),
            "low":str(price),"close":str(price)}


def original_pair(*, condition="CLOSED", day=DAY):
    bars = [minute(day,i,600) for i in range(5)]+[minute(day,5,601)]
    sig = closed_bar_signal(bars,session=day,source_sha256=SHA,source_unit_id="v103-unit")
    req = _source_requirement(sig)
    qid = _fingerprint(req)
    original = {
        "status":"CACHE_HIT","query_id":qid,
        "source_sha256":SHA,"exact_requirement":req,
        "source_rows":[
            {"timestamp":f"{day}T09:36:01-04:00","symbol":"SPY",
             "expiration":day.isoformat(),"strike":"601","right":"call",
             "bid":"1.00","ask":"1.02","bid_size":5,"ask_size":5},
            {"timestamp":f"{day}T09:36:02-04:00","symbol":"SPY",
             "expiration":day.isoformat(),"strike":"601","right":"call",
             "bid":"1.00","ask":"1.02","bid_size":5,"ask_size":5},
            {"timestamp":f"{day}T09:36:03-04:00","symbol":"SPY",
             "expiration":day.isoformat(),"strike":"601","right":"call",
             "bid":"2.04","ask":"2.07","bid_size":5,"ask_size":5},
        ],
    }
    if condition=="UNKNOWN":
        original["source_rows"]=original["source_rows"][:2]
    if condition=="MISSING":
        replay=replay_source(sig,None)
        receipt={"query_id":qid,"state":"NOT_REGISTERED",
                 "archive_sha256":None}
    else:
        replay=replay_source(sig,original)
        receipt={"query_id":qid,"state":"ARCHIVED",
                 "archive_sha256":SHA}
    row=signed({
        "session":day.isoformat(),
        "signal_fingerprint":sig["fingerprint"],
        "signal_status":sig["signal_status"],
        "exact_option_requirement":req,"exact_option_receipt":receipt,
        "standalone_replay_report":replay,
        "standalone_replay_disposition":replay["status"],
    })
    return row


def excluded_row(day=TUE):
    signal=closed_bar_signal([],session=day,source_sha256=SHA,
                             source_unit_id="v103-unit")
    replay=replay_source(signal,None)
    return signed({"session":day.isoformat(),
                   "signal_fingerprint":signal["fingerprint"],
                   "signal_status":signal["signal_status"],
                   "exact_option_requirement":None,"exact_option_receipt":None,
                   "standalone_replay_report":replay,
                   "standalone_replay_disposition":replay["status"]})


def v65_document(rows):
    return signed({
        "contract":"atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1",
        "start":rows[0]["session"],"end":rows[-1]["session"],
        "session_reports":rows,
        "provider_requests":0, "broker_orders":0,
    })


def test_original_v55_source_closed_account_is_not_fictitious_broker_fill():
    row=original_pair()
    status, result=classify(row,DAY)
    assert status=="CLOSED_QUOTE_REFERENCE"
    assert result["debit"]=="410.60"
    assert result["credit"]=="815.40"
    assert result["net_pnl"]=="404.80"
    account=chain_months([{"month":"2025-06","original_v65":v65_document(
        [row,excluded_row()])}],calendar_sessions=[DAY,TUE])
    assert verify(account)
    assert account["first_account_censor"] is None
    assert account["terminal_equity_if_source_complete_usd"]=="25404.80"
    assert account["pre_censor_flat_closes"]==1
    assert account["actual_broker_fills"]==0


def test_original_missing_options_source_is_not_valid_zero_pnl():
    row=original_pair(condition="MISSING")
    status,reason=classify(row,DAY)
    assert status=="OPTION_SOURCE_CENSORED"
    assert reason=="NOT_REGISTERED"
    account=chain_months([{"month":"2025-06",
        "original_v65":v65_document([row,excluded_row()])}],
        calendar_sessions=[DAY,TUE])
    assert account["terminal_equity_if_source_complete_usd"] is None
    assert account["first_account_censor"]["session"]==DAY.isoformat()
    assert account["all_sessions"][1]["account_step_quote_pnl_if_known"] is None


def test_original_unresolved_exit_keeps_cash_unknown():
    row=original_pair(condition="UNKNOWN")
    status,reason=classify(row,DAY)
    assert status=="UNKNOWN_EXIT_CENSORED"
    account=chain_months([{"month":"2025-06",
        "original_v65":v65_document([row])}],calendar_sessions=[DAY])
    assert account["terminal_equity_if_source_complete_usd"] is None
    assert account["first_account_censor"]["reason"]=="UNKNOWN_EXIT_CENSORED"


def test_compact_source_classification_reproduces_full_original_month():
    row=original_pair()
    signed_month=v65_document([row,excluded_row()])
    compact=[signed({"session":r["session"],
        "disposition":classify(r,date.fromisoformat(r["session"]))[0],
        "detail":classify(r,date.fromisoformat(r["session"]))[1],
        "original_v65_session_sha":r["fingerprint"],
        "compact_v103_disposition":True}) for r in signed_month["session_reports"]]
    original=chain_months([{"month":"2025-06","original_v65":signed_month}],
                          calendar_sessions=[DAY,TUE])
    restored=chain_months([{"month":"2025-06","original_v65_sha":signed_month["fingerprint"],
        "classified_sessions":compact}],calendar_sessions=[DAY,TUE])
    assert restored["terminal_equity_if_source_complete_usd"]==original["terminal_equity_if_source_complete_usd"]
    assert restored["dispositions"]==original["dispositions"]
    assert restored["first_account_censor"]==original["first_account_censor"]


def test_original_account_falsified_sha_and_quote_pnl_rejected():
    row=original_pair()
    row["standalone_replay_report"]["trade_net_pnl"]="999.00"
    with pytest.raises(V103Error,match="SIGNED_SESSION"):
        classify(row,DAY)
    row=original_pair()
    altered=dict(row["standalone_replay_report"])
    altered["trade_net_pnl"]="999.00"
    row=signed({**{k:v for k,v in row.items() if k!="fingerprint"},
                "standalone_replay_report":signed({
                    k:v for k,v in altered.items() if k!="fingerprint"})})
    with pytest.raises(V103Error,match="CLOSED_CASH_DRIFT"):
        classify(row,DAY)


def test_historical_source_gap_blocks_contiguous_equity_even_if_later_month_profitable():
    july=date(2025,7,7)
    account=chain_months([
        {"month":"2025-06","status":"MONTH_NOT_PRESENT"},
        {"month":"2025-07","status":"ORIGINAL_MONTH_AVAILABLE",
         "original_v65":v65_document([original_pair(day=july)])},
    ],calendar_sessions=[DAY,july])
    assert account["first_account_censor"]["session"]=="2025-06-09"
    assert account["cash_pnl_if_entire_window_complete_usd"] is None
    assert account["pre_censor_flat_closes"]==0
    assert account["all_sessions"][1]["account_step_quote_pnl_if_known"] is None


def test_month_bounds_never_include_sealed_2026_holdout():
    assert list(month_bounds(date(2025,6,9),date(2025,7,3))) == [
        (date(2025,6,9),date(2025,6,30)),
        (date(2025,7,1),date(2025,7,3)),
    ]
    with pytest.raises(V103Error,match="PROTECTED"):
        list(month_bounds(date(2026,4,15),date(2026,5,12)))


class Calendar:
    def __init__(self, dates, short=()):
        self.days=list(dates)
        self.short=set(short)
    def sessions_in_range(self,start,end):
        return [x for x in self.days if start<=x<=end]
    def regular_open_close(self,day):
        return (datetime(day.year,day.month,day.day,9,30,tzinfo=ET),
                datetime(day.year,day.month,day.day,
                         13 if day in self.short else 16,0,tzinfo=ET))


def test_early_close_exclusion_prevents_nonexistent_1530_exit():
    cal=Calendar([DAY,TUE],short=[TUE])
    _,standard,short=frozen_calendar(DAY,TUE,cal=cal)
    assert standard==[DAY]
    assert short==[TUE]


def test_gzip_retains_byte_identical_original_v65_journal(tmp_path):
    raw=tmp_path/"orig.json"
    gz=tmp_path/"orig.json.gz"
    original=json.dumps(v65_document([original_pair()]),sort_keys=True).encode()
    raw.write_bytes(original)
    receipt=original_gzip_once(raw,gz)
    assert not raw.exists() and gz.exists()
    assert gzip.decompress(gz.read_bytes())==original
    assert receipt["raw_sha256"]==hashlib.sha256(original).hexdigest()
    assert receipt["gzip_sha256"]==hashlib.sha256(gz.read_bytes()).hexdigest()


def test_end_to_end_month_runner_keeps_original_sha_and_causal_cash(tmp_path):
    checkpoint=tmp_path/"checkpoints"/"native_units"/"1m"/"year=2025"/"month=06"
    checkpoint.mkdir(parents=True)
    original=v65_document([original_pair(),excluded_row()])
    calls=[]
    def scanner(layout,**kwargs):
        calls.append(("discover",kwargs["target_month"]))
        return [SimpleNamespace(year=2025,month=6,symbols=("SPY",))]
    def inspector(lo,hi,output,*,session_calendar,progress):
        calls.append(("inspect",len(session_calendar(lo,hi))))
        output.write_text(json.dumps(original,sort_keys=True),encoding="utf8")
        return original
    summary=run(tmp_path/"campaign",
        start=DAY,end=TUE,discover=scanner,inspector=inspector,
        layout_factory=lambda _root:SimpleNamespace(checkpoints=tmp_path/"checkpoints"),
        calendar_factory=lambda:Calendar([DAY,TUE]),announce=lambda _:None)
    assert summary["continuous_cash_known"] is True
    assert summary["total_contiguous_quote_pnl_if_qualified"]=="404.80"
    assert summary["months"]==1
    assert calls==[("discover",6),("inspect",2)]
    artifacts=tmp_path/"campaign"/"months"
    assert len(list(artifacts.glob("*.gz")))==1
    signed_account=json.loads((tmp_path/"campaign"/"chronological_account.json").read_text())
    assert verify(signed_account)
    assert signed_account["account"]["terminal_equity_if_source_complete_usd"]=="25404.80"
