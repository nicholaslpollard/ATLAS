from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json
from zoneinfo import ZoneInfo

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v57_causal_exit_shadow import (
    AdaptiveShadowError, replay_adaptive_shadow,
)

ET=ZoneInfo("America/New_York")


def row(t,bid,ask=None,bid_size=40):
    return {
        "type":"EXIT_REVIEW",
        "quote":{
            "timestamp_et":t,"bid":str(bid),
            "ask":str(ask if ask is not None else bid+.02),
            "bid_size":bid_size,"ask_size":35,
        },
    }


def parent(quotes,*,entry_clock="2025-06-09T09:36:02-04:00"):
    doc={
        "session":"2025-06-09","actual_fills":0,"valid_historical_alpha":False,
        "starting_cash":"25000.00","entry_debit":"474.60",
        "exit_credit":"285.40","trade_net_pnl":"-189.20",
        "status":"CLOSED_QUOTE_REFERENCE","terminal_equity_if_resolved":"24810.80",
        "source_query_id":"test-query","source_sha256":"a"*64,
        "events":[
            {"type":"OPPORTUNITY"},
            {"type":"ORDER_ACTION_QUOTE_REFERENCE","action":{
                "ask":"1.18","bid":"1.17","timestamp_et":entry_clock}},
            {"type":"MODELED_ENTRY_QUOTE_REFERENCE",
             "ask":"1.18","qty":4,"at_et":entry_clock},
            *quotes,
            {"type":"MODELED_EXIT_QUOTE_REFERENCE","at_et":"2025-06-09T15:30:00-04:00"},
            {"type":"CLOSEOUT"},
        ],
    }
    doc["fingerprint"]=_fingerprint(doc)
    return doc


def test_declared_account_risk_stop_is_activated_with_fee_aware_cash():
    evidence=parent([row("2025-06-09T09:36:03-04:00",1.16),
                     row("2025-06-09T09:36:04-04:00",.88)])
    r=replay_adaptive_shadow(evidence)
    assert r["status"]=="CLOSED_ADAPTIVE_QUOTE_REFERENCE"
    assert r["exit_reason"]=="RISK_BUDGET_STOP"
    assert r["risk_budget_dollars"]=="125.00"
    assert r["initial_stop_bid"]=="0.8805"
    assert r["net_pnl"]=="-125.20"
    assert r["terminal_equity_if_resolved"]=="24874.80"
    assert r["historical_broker_fills"]==0
    assert r["historical_alpha_validated"] is False
    assert len(r["decision_journal"])==2
    assert r["fingerprint"]==_fingerprint({k:v for k,v in r.items() if k!="fingerprint"})


def test_adaptive_high_water_profit_trail_is_causal_and_not_best_future_high():
    quotes=[row("2025-06-09T09:36:03-04:00",1.20),
            row("2025-06-09T09:36:04-04:00",1.50),
            row("2025-06-09T09:36:05-04:00",1.60),
            row("2025-06-09T09:36:06-04:00",1.43)]
    prefix=replay_adaptive_shadow(parent(quotes))
    longer=replay_adaptive_shadow(parent(quotes+
        [row("2025-06-09T09:36:07-04:00",3.0)]))
    for report in (prefix,longer):
        assert report["exit_reason"]=="PROFIT_HIGH_WATER_TRAIL"
        assert report["candidate_exit"]["observed_bid"]=="1.43"
        assert report["net_pnl"]=="94.80"
        assert report["observed_quotes"]==4
        assert report["highest_bid_observed_before_exit"]=="1.60"
        assert report["terminal_equity_if_resolved"]=="25094.80"
        assert report["decision_journal"][2]["trail_active"] is True
        assert report["decision_journal"][-1]["decision"]=="PROFIT_HIGH_WATER_TRAIL"


def test_time_cutoff_respects_15_00_without_fictional_stop_fill():
    q=parent([row("2025-06-09T15:00:00-04:00",1.01)],
             entry_clock="2025-06-09T14:59:59-04:00")
    result=replay_adaptive_shadow(q)
    assert result["exit_reason"]=="TIME_15_00"
    assert result["net_pnl"]=="-73.20"


def test_missing_60_second_quote_path_censors_instead_of_zero_liquidation():
    q=parent([row("2025-06-09T09:39:00-04:00",1.80)])
    result=replay_adaptive_shadow(q)
    assert result["status"]=="CENSORED_MISSING_QUOTE_PATH"
    assert result["net_pnl"] is None
    assert result["terminal_equity_if_resolved"] is None


def test_baseline_early_exit_censors_adaptive_when_no_future_quotes():
    q=parent([row("2025-06-09T09:36:03-04:00",1.21)])
    result=replay_adaptive_shadow(q)
    assert result["status"]=="CENSORED_AT_PARENT_BASELINE_EXIT"
    assert result["net_pnl"] is None


def test_reject_parent_modification_and_missing_source_context():
    q=parent([row("2025-06-09T09:36:03-04:00",1.10)])
    q["events"][3]["quote"]["bid"]="0.01"
    with pytest.raises(AdaptiveShadowError,match="PARENT_REPORT_DIGEST_INVALID"):
        replay_adaptive_shadow(q)
    empty=parent([])
    empty["events"]=[{"type":"OPPORTUNITY"}]
    empty["fingerprint"]=_fingerprint({k:v for k,v in empty.items() if k!="fingerprint"})
    result=replay_adaptive_shadow(empty)
    assert result["status"]=="NO_ENTRY_IN_PARENT"


def test_verified_journal_gate_is_before_source_read(tmp_path,monkeypatch):
    from scripts import run_spy_v57_adaptive_exit_shadow as cli
    p=tmp_path/"accepted.json"
    q=parent([row("2025-06-09T09:36:03-04:00",1.16),
              row("2025-06-09T09:36:04-04:00",.88)])
    p.write_text(json.dumps(q))
    receipt={"report_fingerprint":q["fingerprint"],"journal_rows":8,
             "tip_sha256":"c"*64}
    checked=[]
    def verified(journal):
        checked.append(journal)
        return receipt
    monkeypatch.setattr(cli,"verify_journal",verified)
    result=cli.execute(p,tmp_path/"out.json")
    assert result==0
    assert checked==[tmp_path/"accepted.jsonl"]
    got=json.loads((tmp_path/"out.json").read_text())
    assert got["net_pnl"]=="-125.20"
    assert got["historical_alpha_validated"] is False
