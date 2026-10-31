from __future__ import annotations

from datetime import date
from decimal import Decimal
import json

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v57_causal_exit_shadow import (
    AdaptiveShadowError,replay_adaptive_shadow,
)
from scripts.run_spy_v58_adaptive_cohort_comparison import (
    CohortError,evaluate,PARENT_CONTRACT,
)


def signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def baseline_day(day,starting):
    start=Decimal(starting)
    exit_equity=start-Decimal("189.20")
    doc={
        "session":day,"status":"CLOSED_QUOTE_REFERENCE",
        "starting_cash":str(start),"entry_debit":"474.60",
        "exit_credit":"285.40","trade_net_pnl":"-189.20",
        "terminal_equity_if_resolved":str(exit_equity),
        "actual_fills":0,"valid_historical_alpha":False,
        "source_query_id":"test-q-"+day,"source_sha256":"a"*64,
        "events":[
            {"type":"OPPORTUNITY"},
            {"type":"ORDER_ACTION_QUOTE_REFERENCE",
             "action":{"ask":"1.18","bid":"1.17",
                       "timestamp_et":day+"T09:36:02-04:00"}},
            {"type":"MODELED_ENTRY_QUOTE_REFERENCE",
             "ask":"1.18","qty":4,"at_et":day+"T09:36:02-04:00"},
            {"type":"EXIT_REVIEW","quote":{
                "timestamp_et":day+"T09:36:03-04:00","bid":"0.88",
                "ask":"0.90","bid_size":60,"ask_size":80}},
            {"type":"MODELED_EXIT_QUOTE_REFERENCE",
             "at_et":day+"T15:30:00-04:00"},
            {"type":"CLOSEOUT"},
        ],
    }
    return signed(doc)


def setup_cohort(path,days=("2025-06-09","2025-06-11")):
    path.mkdir()
    starting=Decimal("25000.00")
    rows=[]
    for day in days:
        r=baseline_day(day,starting)
        (path/f"{day}.json").write_text(json.dumps(r),encoding="utf8")
        rows.append({
            "session":day,"status":r["status"],
            "report_fingerprint":r["fingerprint"],
            "event_journal_tip":"b"*64,
            "source_query_id":r["source_query_id"],
            "source_sha256":r["source_sha256"]})
        starting=Decimal(r["terminal_equity_if_resolved"])
    summary=signed({
        "contract":PARENT_CONTRACT,
        "cohort_start":days[0],"cohort_end":days[-1],
        "sessions_evaluated":len(days),"sessions":rows,
        "starting_cash":"25000.00",
        "terminal_equity_if_complete":str(starting),
        "closed_net_pnl":str(starting-Decimal("25000.00")),
    })
    (path/"summary.json").write_text(json.dumps(summary),encoding="utf8")
    return summary


def fake_verify(path):
    r=json.loads(path.with_suffix(".json").read_text())
    return {"report_fingerprint":r["fingerprint"],
            "tip_sha256":"b"*64,"journal_rows":len(r["events"])+2}


def test_independent_account_uses_its_own_cash_for_each_next_day(tmp_path):
    cohort=tmp_path/"cohort"
    setup_cohort(cohort)
    output=tmp_path/"shadow"
    lines=[]
    assert evaluate(cohort,output,verify=fake_verify,emit=lines.append)==0
    result=json.loads((output/"summary.json").read_text())
    assert result["account_status"]=="INDEPENDENT_ADAPTIVE_QUOTE_REFERENCE_DEV"
    assert result["paired_closed_trades"]==2
    assert result["paired_candidate_minus_baseline"]=="128.00"
    assert result["adaptive_terminal_equity_if_complete"]=="24749.60"
    assert result["original_v56_baseline_terminal_equity_if_complete"]=="24621.60"
    assert result["sessions"][1]["independent_adaptive_starting_cash"]=="24874.80"
    second=json.loads((output/"2025-06-11.json").read_text())
    assert second["source_report_fingerprint"]==json.loads(
        (cohort/"2025-06-11.json").read_text())["fingerprint"]
    assert second["risk_budget_dollars"]=="124.37"
    assert second["initial_stop_bid"]=="0.882075"
    assert result["historical_profitability_validated"] is False
    assert result["theta_data_requests"]==0
    assert result["weekly"][0]["matched_closed_trades"]==2
    assert (output/"checkpoint.json").exists()
    assert len(result["independent_adaptive_account_curve"])==2
    assert any("PROGRESS_100PCT" in line for line in lines)


def test_parent_provenance_fingerprint_and_journal_must_match(tmp_path):
    cohort=tmp_path/"cohort"
    setup_cohort(cohort)
    r=json.loads((cohort/"2025-06-09.json").read_text())
    r["events"][3]["quote"]["bid"]="3.50"
    (cohort/"2025-06-09.json").write_text(json.dumps(r))
    with pytest.raises(CohortError,match="FINGERPRINT_MISMATCH"):
        evaluate(cohort,tmp_path/"out",verify=fake_verify,emit=lambda x:None)
    assert not (tmp_path/"out"/"2025-06-09.json").exists()


def test_journal_mismatch_blocks_before_shadowing(tmp_path):
    cohort=tmp_path/"cohort"
    setup_cohort(cohort)
    with pytest.raises(CohortError,match="JOURNAL_AND_RECEIPT_DISAGREE"):
        evaluate(cohort,tmp_path/"out",verify=lambda path:{
            "report_fingerprint":"0"*64,"tip_sha256":"b"*64},emit=lambda x:None)
    assert not (tmp_path/"out"/"2025-06-09.json").exists()


def test_censored_adaptive_trade_blocks_future_account_returns(tmp_path):
    cohort=tmp_path/"cohort"
    setup_cohort(cohort)
    doc=json.loads((cohort/"2025-06-09.json").read_text())
    doc["events"]=[e for e in doc["events"] if e["type"]!="EXIT_REVIEW"]
    doc=signed({k:v for k,v in doc.items() if k!="fingerprint"})
    (cohort/"2025-06-09.json").write_text(json.dumps(doc))
    root=json.loads((cohort/"summary.json").read_text())
    root["sessions"][0]["report_fingerprint"]=doc["fingerprint"]
    root=signed({k:v for k,v in root.items() if k!="fingerprint"})
    (cohort/"summary.json").write_text(json.dumps(root))
    assert evaluate(cohort,tmp_path/"out",verify=fake_verify,emit=lambda x:None)==2
    result=json.loads((tmp_path/"out"/"summary.json").read_text())
    assert result["sessions_evaluated"]==1
    assert result["account_status"]=="INCOMPLETE_CENSORED_OR_UNRESOLVED"
    assert result["adaptive_terminal_equity_if_complete"] is None
    assert result["paired_closed_trades"]==0
    assert result["blocker"]["reason"]=="CENSORED_AT_PARENT_BASELINE_EXIT"


def test_independent_cash_floor_refuses_more_premium_than_cash():
    original=baseline_day("2025-06-09",Decimal("25000.00"))
    with pytest.raises(AdaptiveShadowError,match="INDEPENDENT_ACCOUNT_INSUFFICIENT_ENTRY_CASH"):
        replay_adaptive_shadow(original,starting_cash_override="100.00")
    one=replay_adaptive_shadow(original,starting_cash_override="24874.80")
    assert one["source_report_fingerprint"]==original["fingerprint"]
    assert one["independent_account_cash_override"]=="24874.80"
    assert one["risk_budget_dollars"]=="124.37"
    assert one["terminal_equity_if_resolved"]=="24749.60"
