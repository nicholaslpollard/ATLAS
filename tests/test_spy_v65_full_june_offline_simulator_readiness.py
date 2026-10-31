from __future__ import annotations

from datetime import date,datetime,timedelta,timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import (
    normalize_source_requirement,
)
from packages.simulation.spy_v55_closed_bar_option_replay import closed_bar_signal
from scripts.run_spy_v65_full_june_offline_simulator_readiness import (
    V65Error, _lookup_source_receipt,_source_requirement,inspect,
)

DAY=date(2025,6,9)
SHA="f"*64


def source_unit():
    return SimpleNamespace(
        year=2025,month=6,symbols=("SPY",),unit_id="test-spy-june",
        canonical_sha256=SHA,
        canonical_path=Path("unneeded-in-fake-test.parquet"),
    )


def minute(day,index,close):
    base=datetime(day.year,day.month,day.day,9,30,
                  tzinfo=timezone(timedelta(hours=-4)))
    at=base+timedelta(minutes=index)
    return {"symbol":"SPY","timestamp_utc":at.astimezone(timezone.utc).isoformat(),
            "open":str(close),"high":str(close),"low":str(close),
            "close":str(close)}


def bars(day):
    base=[600,600,600,600,600,601]
    return [minute(day,i,val) for i,val in enumerate(base)]


def args(tmp_path,*,state="NOT_REGISTERED",archive_read=None):
    lookup_calls=[]
    def receipt(qid):
        lookup_calls.append(qid)
        if state=="NOT_REGISTERED":
            return None
        request=normalize_source_requirement(
            "option_history_exact_quote_tape",
            {"symbol":"SPY","date_et":"2025-06-09",
             "expiration":"2025-06-09","strike":"601","right":"call",
             "start_time_et":"09:36:01.000","end_time_et":"15:30:00.000",
             "interval":"1s"})
        assert _fingerprint(request)==qid
        return (qid,json.dumps(request,sort_keys=True,separators=(",",":")),
                state,SHA,3)
    calls=[]
    def read(settings,qid):
        calls.append(qid)
        if archive_read is not None:
            return archive_read(qid)
        raise AssertionError("No call to source cache unless archived")
    kwargs=dict(
        output=tmp_path/"v65.json",
        discover=lambda *a,**k:(source_unit(),),
        integrity=lambda unit,progress:{"accepted":True},
        sample=lambda *a,**kw:bars(kw["session_date"]),
        validate=lambda *a,**kw:{"accepted":True,"warnings":[]},
        settings_factory=lambda *a:object(),
        receipt_reader=receipt,cache_read=read,
        progress=lambda s:None)
    return kwargs,lookup_calls,calls


def test_source_scope_equals_v56_exact_original_one_second_protocol():
    sig=closed_bar_signal(bars(DAY),session=DAY,
                          source_sha256=SHA,source_unit_id="unit")
    req=_source_requirement(sig)
    assert req["method"]=="option_history_exact_quote_tape"
    assert req["kwargs"]["symbol"]=="SPY"
    assert req["kwargs"]["date_et"]=="2025-06-09"
    assert req["kwargs"]["expiration"]=="2025-06-09"
    assert req["kwargs"]["strike"]=="601"
    assert req["kwargs"]["right"]=="call"
    assert req["kwargs"]["start_time_et"]=="09:36:01.000"
    assert req["kwargs"]["end_time_et"]=="15:30:00.000"
    assert req["kwargs"]["interval"]=="1s"


def test_missing_source_evaluates_all_weekdays_without_paid_get(tmp_path):
    kwargs,lookup_calls,cache_calls=args(tmp_path)
    result=inspect(DAY,date(2025,6,10),**kwargs)
    assert result["weekdays_in_calendar_scope"]==2
    assert result["status_counts"]=={"NO_ENTRY":1,"NO_SIGNAL":1}
    assert result["option_source_state_counts"]=={"NOT_REGISTERED":1}
    assert len(lookup_calls)==1
    assert not cache_calls
    mon,tue=result["session_reports"]
    assert mon["selected_contract"]["right"]=="call"
    assert mon["exact_option_receipt"]["state"]=="NOT_REGISTERED"
    assert mon["standalone_replay_censor_reason"]=="OPTION_SOURCE_MISSING_OR_UNQUALIFIED"
    assert tue["selected_contract"] is None
    assert tue["signal_status"]=="WEEKDAY_OUTSIDE_MWF_VERSION"
    assert tue["exact_option_receipt"] is None
    assert result["broker_orders"]==0 and result["provider_requests"]==0
    assert result["historical_profitability_validated"] is False
    assert result["standalone_cash_not_chained_between_dates"] is True
    assert result["fingerprint"]==_fingerprint({k:v for k,v in result.items()
                                               if k!="fingerprint"})


@pytest.mark.parametrize("state",["FAILED_RETRYABLE","IN_FLIGHT","NO_DATA_EXPLICIT"])
def test_failed_or_uncertain_source_never_invokes_original_cache_or_provider(tmp_path,state):
    kwargs,ids,calls=args(tmp_path,state=state)
    report=inspect(DAY,DAY,**kwargs)
    assert report["option_source_state_counts"]=={state:1}
    assert report["status_counts"]=={"NO_ENTRY":1}
    assert report["session_reports"][0]["exact_option_receipt"][
        "same_query_retry_permitted"] is False
    assert len(ids)==1 and not calls


def test_archived_source_is_sha_checked_and_standalone_only(tmp_path):
    sig=closed_bar_signal(bars(DAY),session=DAY,
                          source_sha256=SHA,source_unit_id="unit")
    requirement=_source_requirement(sig)
    qid=_fingerprint(requirement)
    source={
        "status":"CACHE_HIT","query_id":qid,
        "source_sha256":SHA,
        "exact_requirement":requirement,
        "source_rows":tuple([
            {"timestamp":"2025-06-09T09:36:01-04:00",
             "symbol":"SPY","expiration":"2025-06-09","strike":"601",
             "right":"call","bid":"1.00","ask":"1.02",
             "bid_size":4,"ask_size":4},
            {"timestamp":"2025-06-09T09:36:02-04:00",
             "symbol":"SPY","expiration":"2025-06-09","strike":"601",
             "right":"call","bid":"1.00","ask":"1.02",
             "bid_size":4,"ask_size":4},
        ]),
    }
    kwargs,ids,calls=args(tmp_path,state="ARCHIVED",
                          archive_read=lambda _:{"cache_evidence":"CACHE_HIT",
                                                 "source":source})
    report=inspect(DAY,DAY,**kwargs)
    assert report["option_source_state_counts"]=={"ARCHIVED":1}
    assert len(calls)==1 and calls[0]==qid
    r=report["session_reports"][0]["standalone_replay_report"]
    assert r["status"]=="UNRESOLVED_POSITION"
    assert r["trade_net_pnl"] is None
    assert report["missing_source_not_a_zero_return"] is True


def test_changed_sha_original_archives_never_promoted(tmp_path):
    sig=closed_bar_signal(bars(DAY),session=DAY,
                          source_sha256=SHA,source_unit_id="unit")
    req=_source_requirement(sig)
    qid=_fingerprint(req)
    kwargs,ids,calls=args(tmp_path,state="ARCHIVED",
        archive_read=lambda qid:{"cache_evidence":"CACHE_HIT",
            "source":{"query_id":qid,"exact_requirement":req,
                      "source_sha256":"a"*64,"status":"CACHE_HIT",
                      "source_rows":tuple([])}})
    with pytest.raises(V65Error,match="V65_ORIGINAL_OPTION_ARCHIVE_IDENTITY_CHANGED"):
        inspect(DAY,DAY,**kwargs)
    assert not (tmp_path/"v65.json").exists()


def test_no_accepted_spy_sha_blocks_every_session(tmp_path):
    kwargs,_,_=args(tmp_path)
    kwargs["integrity"]=lambda unit,progress:{"accepted":False}
    with pytest.raises(V65Error,match="V65_ORIGINAL_STOCK_FULL_SHA_UNQUALIFIED"):
        inspect(DAY,DAY,**kwargs)
    assert not (tmp_path/"v65.json").exists()


def test_report_immutable(tmp_path):
    kwargs,_,_=args(tmp_path)
    (tmp_path/"v65.json").write_text("original",encoding="utf-8")
    with pytest.raises(V65Error,match="V65_IMMUTABLE_OUTPUT_EXISTS"):
        inspect(DAY,DAY,**kwargs)
