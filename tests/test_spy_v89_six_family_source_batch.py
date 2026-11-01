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
    def is_session(self,day):
        return day==DAY
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


def test_completed_six_family_cached_source_receipts_have_signed_event_chain(tmp_path):
    from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
    from packages.data.options_on_demand_source_cache_v38 import normalize_source_requirement
    from scripts.run_spy_v90_six_family_source_replay import audit_input

    unit=SimpleNamespace(year=2024,month=1,symbols=("SPY",),
        canonical_sha256="a"*64,raw_bundle_sha256="b"*64,
        unit_id="unit-202401",canonical_path=tmp_path/"native.parquet")
    def sample(path,*,symbol,session_date):
        rows=[]
        for i in range(10):
            at=datetime(2024,1,2,9,30,tzinfo=ET)+timedelta(minutes=i)
            o=100+i*.06
            rows.append({
                "timestamp_utc":at,
                "open":o,"high":o+.07,"low":o-.01,"close":o+.06,
            })
        return rows
    def resolve(settings,version,needs,*,continue_on_error,on_source,on_progress):
        needs=list(needs)
        assert version=="spy_v89_six_distinct_entry_hypotheses_20261101"
        for d in needs:
            qid=_fingerprint(normalize_source_requirement(d["method"],d["kwargs"]))
            base={"candidate_id":d["candidate_id"],"query_id":qid,
                  "date_et":d["kwargs"]["date_et"],"status":None,"error":None}
            on_progress("source_started",base)
            on_progress("source_done",{**base,"status":"CACHE_HIT"})
            on_source(d,{"query_id":qid,"status":"CACHE_HIT",
                         "source_sha256":"c"*64})
        return {
            "contract":"atlas-strategy-options-data-demand-runtime-v39",
            "source_uses_requested":len(needs),
            "provider_dispatch_attempts":0,
            "status":"ALL_REQUESTED_SOURCES_PRESENT",
        }
    output=tmp_path/"complete"
    report=v89.run(DAY,DAY,output,acquire_options=True,
        discover=lambda *a,**k:[unit],
        verify=lambda u,log:{"accepted":True},
        sample=sample,
        validate=lambda *a,**k:{"accepted":True},
        resolver=resolve,
        settings_factory=lambda *a:object(),
        market=OneDayMarket(),reporter=lambda _:None)
    assert report["all_required_sources_archived"]
    assert report["exact_source_requirements"]>0
    entry,plan,receipts,summary,actual=audit_input(output)
    assert len(actual)==report["exact_source_requirements"]
    assert verified(entry) and verified(plan) and verified(receipts)
    assert summary["fingerprint"]==report["fingerprint"]
    events=[json.loads(x) for x in (output/"source_events.jsonl").read_text().splitlines()]
    assert len(events)==report["exact_source_requirements"]*2
    assert receipts["last_event_sha"]==events[-1]["fingerprint"]

    # Exercise V90 orchestration with deterministic signed fake quote results.
    # No real ThetaData tape, provider request, or broker order is used.
    from unittest.mock import patch
    from scripts import run_spy_v90_six_family_source_replay as v90
    from packages.simulation.spy_v84_offline_three_family_economics import signed as sign84
    from packages.simulation.spy_v86_original_option_exit_recheck import signed as sign86

    def fake_replay(decision,demand,source,tape,*,policy,lag_seconds,market_close_et):
        return sign84({
            "contract":"atlas-v84-offline-three-family-option-quote-shadow-v1",
            "session":decision["session"],"strategy":decision["strategy_id"],
            "policy":policy,"lag_seconds":lag_seconds,
            "decision_at_et":decision["decision_at_et"],
            "entry_action_at_et":decision["session"]+"T09:41:00-05:00",
            "entry_debit_usd":"200.00","entry_qty":1,
            "status":"CLOSED_QUOTE_REFERENCE","reason":"SYNTHETIC_TEST_ONLY",
            "source_query_id":demand["query_id"],"provider_requests":0,
            "actual_broker_fills":0,
        })
    def fake_recheck(trial,source,tape,*,dwell_seconds):
        return sign86({
            "contract":"atlas-v86-original-option-exit-limit-recheck-v1",
            "original_trial_sha":trial["fingerprint"],
            "session":trial["session"],"strategy":trial["strategy"],
            "policy":trial["policy"],"lag_seconds":trial["lag_seconds"],
            "limit_rest_seconds":dwell_seconds,
            "status":"CLOSED_QUOTE_REFERENCE","reason":"SYNTHETIC_TEST_ONLY",
            "exit_action_at_et":trial["session"]+"T09:42:00-05:00",
            "quote_reference_pnl_usd":"15.00",
            "quote_reference_pnl_2pct_bid_haircut_usd":"12.00",
            "provider_requests":0,"actual_broker_fills":0,
        })
    replay_dir=tmp_path/"replay"
    with patch.object(v90,"prepare_original_tape",return_value=[]), \
         patch.object(v90,"replay",side_effect=fake_replay), \
         patch.object(v90,"recheck",side_effect=fake_recheck):
        replay=v90.run(
            output,replay_dir,
            reader=lambda settings,qid:{"cache_evidence":"CACHE_HIT",
                "source":{"query_id":qid,"source_sha256":"c"*64}},
            settings_factory=lambda *a:object(),
            market=OneDayMarket(),reporter=lambda _:None)
    assert replay["signed_quote_trial_journals"]==24*len(actual)
    assert replay["portfolio_scenarios"]==168
    assert replay["new_provider_requests"]==replay["broker_orders"]==0
    assert (replay_dir/"trial_manifest.json").is_file()
    assert (replay_dir/"portfolio_ledgers.json").is_file()

    # The first signed source-event alteration must fail closed.
    altered=dict(events[0])
    altered["event"]="provider_dispatch"
    lines=(output/"source_events.jsonl").read_text().splitlines()
    lines[0]=json.dumps(altered)
    (output/"source_events.jsonl").write_text("\n".join(lines)+"\n")
    with pytest.raises(Exception,match="SOURCE_EVENT_SHA_CHAIN_INVALID"):
        audit_input(output)
