from __future__ import annotations

"""One-pass V89 stock source test; all external provider paths injected."""

from datetime import date,datetime,timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import json

import pytest

from packages.simulation.spy_v89_six_family_causal_registry import FAMILIES,verified
from scripts import run_spy_v89_six_family_source_batch as v89

ET=ZoneInfo("America/New_York")
DAY=date(2024,1,2)


class OneDayMarket:
    def sessions_in_range(self,start,end):
        return [DAY] if start<=DAY<=end else []
    def regular_open_close(self,day):
        return (datetime(2024,1,2,9,30,tzinfo=ET),
                datetime(2024,1,2,16,0,tzinfo=ET))


def test_one_scan_records_all_six_with_no_network_or_broker(tmp_path):
    month=SimpleNamespace(
        year=2024,month=1,symbols=("SPY",),
        canonical_sha256="a"*64,raw_bundle_sha256="b"*64,
        unit_id="unit-202401",
        canonical_path=tmp_path/"canonical.parquet",
    )
    def discover(layout,*,target_year,target_month,progress):
        assert (target_year,target_month)==(2024,1)
        return [month]
    def sample(path,*,symbol,session_date):
        assert symbol=="SPY" and session_date==DAY
        rows=[]
        for i in range(10):
            at=datetime(2024,1,2,9,30,tzinfo=ET)+timedelta(minutes=i)
            o=100+i*.06
            c=o+.06
            rows.append({
                "timestamp_utc":at.astimezone(ZoneInfo("UTC")),
                "open":o,"high":c+.01,"low":o-.01,"close":c,
            })
        return rows
    output=tmp_path/"output"
    report=v89.run(
        DAY,DAY,output,acquire_options=False,
        discover=discover,verify=lambda u,emit:{"accepted":True},
        sample=sample,validate=lambda *args,**kw:{"accepted":True},
        market=OneDayMarket(),reporter=lambda _:None,
    )
    assert verified(report)
    assert report["market_sessions"]==1
    assert report["considered_decisions"]==len(FAMILIES)==6
    assert report["exact_source_requirements"]>0
    assert report["receipt_sha"] is None
    assert report["source_resolution"] is None
    assert report["broker_orders"]==0
    assert not (output/"source_receipts.json").exists()
    entry=json.loads((output/"entry_screen.json").read_text())
    plan=json.loads((output/"exact_option_source_plan.json").read_text())
    assert verified(entry) and verified(plan)
    assert plan["parent_entry_sha"]==entry["fingerprint"]
    assert len(entry["cases"])==6
    assert {x["strategy"] for x in entry["cases"]}==set(FAMILIES)
    assert all(x["status"] in (
        "NO_SIGNAL","OPTIONS_EXACT_SOURCE_DEMAND_PREPARED",
        "SOURCE_UNQUALIFIED_NO_TRADE") for x in entry["cases"])


def test_protected_master_holdout_and_existing_output_rejected(tmp_path):
    with pytest.raises(v89.V89Error,match="DATE_OR_IMMUTABLE"):
        v89.run(date(2026,5,12),date(2026,8,11),tmp_path/"sealed")
    assert not (tmp_path/"sealed").exists()
    existing=tmp_path/"existing";existing.mkdir()
    with pytest.raises(v89.V89Error,match="IMMUTABLE"):
        v89.run(DAY,DAY,existing)
