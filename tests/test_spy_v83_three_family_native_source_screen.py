from __future__ import annotations

from datetime import date,datetime,timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts import run_spy_v83_three_family_native_source_screen as v83


class Calendar:
    def sessions_in_range(self,start,end):
        dates=[date(2025,8,19),date(2025,8,20)]
        return [x for x in dates if start<=x<=end]

    def regular_open_close(self,day):
        assert day in (date(2025,8,19),date(2025,8,20))
        return (
            datetime.fromisoformat(f"{day}T09:30:00-04:00"),
            datetime.fromisoformat(f"{day}T16:00:00-04:00"),
        )


def src(day):
    at=datetime.fromisoformat(f"{day}T09:30:00-04:00")
    rows=[]
    for i in range(10):
        stamp=at+timedelta(minutes=i)
        if i<5:
            values={"open":"100","high":"102","low":"98","close":"101"}
        else:
            values={"open":"100","high":"104","low":"100",
                    "close":"103" if i==9 else "101"}
        rows.append({"timestamp_utc":stamp,"symbol":"SPY",**values})
    return rows


def synthetic_sample(path,*,symbol,session_date):
    assert symbol=="SPY"
    if session_date==date(2025,8,19):
        return [{
            "timestamp_utc":datetime.fromisoformat(
                "2025-08-19T15:59:00-04:00"),
            "symbol":"SPY",
            "open":"99","high":"101","low":"99","close":"100",
        }]
    return src(session_date)


def fixtures():
    calls=[]
    unit=SimpleNamespace(
        year=2025,month=8,symbols=("SPY",),
        canonical_sha256="a"*64,
        canonical_path=Path("synthetic-original-no-disk"),
        unit_id="canonical-unit-a",
    )
    def discover(layout,*,target_year,target_month,progress):
        calls.append(("discover",target_year,target_month))
        return [unit]
    def verify(_unit,emit):
        calls.append(("verify",_unit.unit_id))
        return {"accepted":True}
    def validate(rows,*,sample_class,symbol,session_date):
        return {"accepted":True}
    return {
        "discover":discover,"verify":verify,
        "validate":validate,"sample":synthetic_sample,
        "calendar":Calendar(),
        "emit":lambda msg:None,
    },calls


def test_native_original_stock_source_three_families_no_provider(tmp_path):
    kw,calls=fixtures()
    result=v83.run(date(2025,8,20),date(2025,8,20),
                   tmp_path/"screen",**kw)
    assert result["sessions"]==1
    assert result["family_cases"]==3
    assert result["planned_exact_option_demands"]==1
    assert result["actual_fills"]==result["broker_orders"]==0
    assert calls==[("discover",2025,8),("verify","canonical-unit-a")]
    from json import loads
    report=loads((tmp_path/"screen"/"entry_screen.json").read_text())
    plan=loads((tmp_path/"screen"/"option_source_plan.json").read_text())
    assert report["cases"][0]["status"]=="OPTIONS_EXACT_SOURCE_DEMAND_PREPARED"
    assert report["cases"][0]["causal_decision"]["direction"]=="CALL"
    assert plan["demands"][0]["kwargs"]["strike"]=="103"
    assert plan["demands"][0]["kwargs"]["start_time_et"]=="09:40:01.000"
    assert report["cases"][1]["status"]=="NO_SIGNAL"
    assert report["cases"][2]["status"]=="NO_SIGNAL"


def test_explicit_cache_first_mode_no_arbitrary_demand_count_cap(tmp_path):
    kw,_=fixtures()
    captured=[]
    def resolve(settings,version,demands,*,continue_on_error,on_progress):
        values=list(demands)
        captured.extend(values)
        assert version=="spy_v82_three_family_registry_20261031"
        assert continue_on_error is True
        assert len(values)==1
        return {
            "contract":"atlas-strategy-options-data-demand-runtime-v39",
            "strategy_version":version,
            "source_uses_requested":len(values),
            "source_uses_resolved":1,
            "provider_dispatch_attempts":1,
            "source_uses_explicit_no_data":0,
            "source_uses_failed_or_unresolved":0,
            "persisted_cache_hits":0,
        }
    result=v83.run(
        date(2025,8,20),date(2025,8,20),tmp_path/"acquired",
        acquire_options=True,resolve=resolve,
        settings_factory=lambda *args:object(),**kw,
    )
    assert len(captured)==1
    assert result["source_resolution"]["source_uses_requested"]==1
    assert result["source_resolution"]["provider_dispatch_attempts"]==1
    assert result["source_resolution"]["fingerprint"]==_fingerprint({
        k:v for k,v in result["source_resolution"].items() if k!="fingerprint"
    })
    assert result["broker_orders"]==0


def test_no_real_market_session_is_not_silently_fabricated(tmp_path):
    kw,_=fixtures()
    with pytest.raises(ValueError,match="NO_REAL_XNYS_SESSIONS"):
        v83.run(date(2025,8,21),date(2025,8,22),
                tmp_path/"none",**kw)


def test_missing_original_bar_denies_entry_but_keeps_day_receipt(tmp_path):
    kw,_=fixtures()
    def short_sample(path,*,symbol,session_date):
        if session_date==date(2025,8,19):
            return synthetic_sample(path,symbol=symbol,session_date=session_date)
        return src(session_date)[:-1]
    kw["sample"]=short_sample
    r=v83.run(date(2025,8,20),date(2025,8,20),
              tmp_path/"missing",**kw)
    assert r["entry_dispositions"]["SOURCE_UNQUALIFIED_NO_TRADE"]==2
    assert r["planned_exact_option_demands"]==0
    assert r["broker_orders"]==0
