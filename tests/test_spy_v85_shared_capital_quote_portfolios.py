from __future__ import annotations

from datetime import date,datetime,timedelta
from pathlib import Path
import gzip
import hashlib
import json

import pytest

from packages.simulation.spy_v85_shared_capital_quote_ledger import (
    SCOPES, MODES, V85Error, simulate, signed, verified,
)
from scripts import run_spy_v85_shared_capital_quote_portfolios as v85


def trade(day, strategy, *,pol="control_50_100",lag=1,marketable=True,
          pnl="25.00",status="CLOSED_QUOTE_REFERENCE",entry_clock="09:40:02",
          exit_clock="10:00:00",qid=None):
    if qid is None:
        qid=f"{day}_{strategy}"
    pos={
        "contract":"atlas-v84-offline-three-family-option-quote-shadow-v1",
        "session":day,"strategy":strategy,"policy":pol,"lag_seconds":lag,
        "decision_at_et":day+"T09:40:01-04:00",
        "entry_action_at_et":day+"T"+entry_clock+"-04:00" if status!="NO_ENTRY" else None,
        "entry_debit_usd":"100.65" if status!="NO_ENTRY" else None,
        "entry_qty":1 if status!="NO_ENTRY" else 0,
        "exit":{"action_at_et":day+"T"+exit_clock+"-04:00",
                "quote_reference_credit_usd":str(
                    (10065+int(float(pnl)*100))/100),
                "original_trigger_limit_marketable_at_action":marketable}
                if status!="NO_ENTRY" else None,
        "status":status,"reason":"PROFIT_TARGET" if status!="NO_ENTRY"
                            else "ENTRY_ASK_ADVERSE_DRIFT_GT_1PCT",
        "source_query_id":qid,
        "source_sha256":"a"*64,
        "quote_reference_pnl_usd":pnl if status!="NO_ENTRY" else None,
        "quote_reference_pnl_2pct_exit_haircut_usd":"20.00" if status!="NO_ENTRY" else None,
        "actual_broker_fills":0,"provider_requests":0,
        "observed_ask_bid_not_broker_fills":True,
    }
    return signed(pos)


def test_chronological_one_position_capacity_conflict_and_next_day_release():
    first=trade("2025-08-20","failed_breakout_fade_0940",qid="a"*64)
    simultaneous=trade("2025-08-20","orb_continuation_0940",qid="b"*64)
    nextday=trade("2025-08-21","orb_continuation_0940",qid="c"*64)
    rejected=trade("2025-08-22","gap_fade_0935",status="NO_ENTRY",qid="d"*64)
    result=simulate([simultaneous,nextday,rejected,first],scope="all_families",
                    policy="control_50_100",lag_seconds=1,
                    mode="repriced_bid_quote_shadow")
    assert verified(result)
    assert result["candidate_opportunities"]==4
    assert result["dispositions"]["HYPOTHETICAL_ENTRY_AT_ACTION_ASK"]==2
    assert result["dispositions"]["BLOCKED_CAPACITY_POSITION_ALREADY_OPEN"]==1
    assert result["dispositions"]["ORIGINAL_NO_ENTRY"]==1
    assert result["dispositions"]["MODELED_EXIT_CREDIT_REFERENCE"]==2
    assert result["terminal_equity_if_flat_usd"]=="25050.00"
    assert result["terminal_equity_2pct_haircut_if_flat_usd"]=="25040.00"
    assert result["peak_open_positions"]==1
    assert result["broker_orders"]==result["provider_requests"]==0


def test_fixed_limit_nonmarketability_freezes_unknown_exercise_cash():
    first=trade("2025-08-20","failed_breakout_fade_0940",
                marketable=False,qid="e"*64)
    second=trade("2025-08-21","orb_continuation_0940",qid="f"*64)
    r=simulate([second,first],scope="all_families",
               policy="control_50_100",lag_seconds=1,
               mode="original_fixed_limit_censored")
    assert r["unresolved_exercise_or_expiry_cash"] is True
    assert r["terminal_equity_if_flat_usd"] is None
    assert r["ending_cash_reference_usd"]=="24899.35"
    assert r["dispositions"]["UNRESOLVED_ORIGINAL_LIMIT"]==1
    assert r["dispositions"]["BLOCKED_CAPACITY_POSITION_ALREADY_OPEN"]==1
    assert r["realized_closed_quote_reference_pnl_usd"]=="0"
    assert r["provider_requests"]==r["broker_orders"]==0


def test_modified_trial_signature_is_rejected():
    entry=trade("2025-08-20","failed_breakout_fade_0940")
    entry["entry_debit_usd"]="0.00"
    with pytest.raises(V85Error,match="SOURCE_TRIAL_INVALID"):
        simulate([entry],scope="all_families",policy="control_50_100",
                 lag_seconds=1,mode="repriced_bid_quote_shadow")


def _fixture_campaign(tmp_path, *, source_count=101, sessions=128):
    v83dir=tmp_path/"v83";v84dir=tmp_path/"v84";v83dir.mkdir();v84dir.mkdir()
    (v84dir/"journals").mkdir()
    families=SCOPES[1:]
    source_cases=[]
    trials=[]
    original_signal_ids=[]
    for i in range(source_count):
        day=(date(2025,7,1)+timedelta(days=i)).isoformat()
        strategy=families[i%3]
        qid=f"{i+1:064x}"
        original_signal_ids.append((day,strategy,qid))
        source_cases.append({"session":day,"strategy":strategy,
                            "status":"OPTIONS_EXACT_SOURCE_DEMAND_PREPARED"})
    for i in range(3*sessions-source_count):
        source_cases.append({"session":"2025-09-02",
                             "strategy":families[i%3],"status":"NO_SIGNAL"})
    v83screen=signed({"contract":v85.V83,"cases":source_cases})
    v83summary=signed({
        "contract":v85.V83+"-summary-v1",
        "entry_screen_sha":v83screen["fingerprint"],
        "family_cases":3*sessions,"planned_exact_option_demands":source_count,
        "sessions":sessions,"broker_orders":0,
    })
    outcomes=[]
    from packages.simulation.spy_v84_offline_three_family_economics import POLICIES,LAGS
    for i,(day,strategy,qid) in enumerate(original_signal_ids):
        for policy in POLICIES:
            for lag in LAGS:
                t=trade(day,strategy,pol=policy,lag=lag,qid=qid)
                rel=f"journals/{i:04d}_{policy}_{lag}s.json.gz"
                raw=(json.dumps(t,sort_keys=True,separators=(",",":"))+"\n").encode()
                packed=gzip.compress(raw,mtime=0)
                (v84dir/rel).write_bytes(packed)
                outcomes.append({
                    "journal":rel,"journal_gzip_sha256":hashlib.sha256(packed).hexdigest(),
                    "journal_raw_bytes":len(raw),"journal_gzip_bytes":len(packed),
                    "trial_fingerprint":t["fingerprint"],
                    "source_query_id":qid,"source_sha256":t["source_sha256"],
                    "session":day,"strategy":strategy,"policy":policy,
                    "lag_seconds":lag,"status":t["status"],
                    "quote_reference_pnl_usd":t["quote_reference_pnl_usd"],
                    "quote_reference_pnl_2pct_exit_haircut_usd":
                        t["quote_reference_pnl_2pct_exit_haircut_usd"],
                })
    v84out=signed({"contract":v85.V84+"-candidate-outcomes-v1",
                   "parent_v83_summary_sha":v83summary["fingerprint"],
                   "trials":outcomes})
    v84windows=signed({"contract":v85.V84+"-windows-v1",
                       "parent_candidate_outcomes_sha":v84out["fingerprint"]})
    v84summary=signed({
        "contract":v85.V84,
        "parent_v83_summary_sha":v83summary["fingerprint"],
        "parent_v83_entry_sha":v83screen["fingerprint"],
        "candidate_outcomes_sha":v84out["fingerprint"],
        "window_economics_sha":v84windows["fingerprint"],
        "candidate_sources":source_count,"trial_count":source_count*6,
        "broker_orders":0,"provider_requests":0,"actual_broker_fills":0,
    })
    for folder,rows in ((v83dir,(("summary",v83summary),("entry_screen",v83screen))),
                        (v84dir,(("summary",v84summary),
                                  ("candidate_outcomes",v84out),
                                  ("window_economics",v84windows)))):
        for stem,obj in rows:
            (folder/(stem+".json")).write_text(json.dumps(obj))
    return v83dir,v84dir


def test_all_606_archived_journals_are_verified_in_48_portfolios(tmp_path):
    v83dir,v84dir=_fixture_campaign(tmp_path)
    evidence=v85.run(v83dir,v84dir,tmp_path/"v85",announce=lambda msg:None)
    assert verified(evidence)
    assert evidence["original_spy_sessions"]==128
    assert evidence["all_original_strategy_decisions"]==384
    assert evidence["original_no_signal_decisions"]==283
    assert evidence["original_sha_verified_trial_journals"]==606
    assert evidence["portfolio_scenarios"]==48
    assert evidence["provider_requests"]==evidence["broker_orders"]==0
    compare=json.loads((tmp_path/"v85"/"portfolio_comparisons.json").read_text())
    assert verified(compare)
    assert len(compare["results"])==48
    assert all(x["historical_broker_fills"]==0 for x in compare["results"])



def test_2026_period_77_sources_dynamic_census(tmp_path):
    v83dir,v84dir=_fixture_campaign(tmp_path,source_count=77,sessions=82)
    result=v85.run(v83dir,v84dir,tmp_path/"janapr_replay",announce=lambda _:None)
    assert verified(result)
    assert result["original_spy_sessions"]==82
    assert result["all_original_strategy_decisions"]==246
    assert result["original_no_signal_decisions"]==169
    assert result["original_signed_option_candidates"]==77
    assert result["original_sha_verified_trial_journals"]==462
    assert result["portfolio_scenarios"]==48
    assert result["provider_requests"]==result["broker_orders"]==0


def test_dynamic_denominators_fail_closed_if_prior_census_drifts(tmp_path):
    v83dir,v84dir=_fixture_campaign(tmp_path,source_count=77,sessions=82)
    pre=json.loads((v83dir/"summary.json").read_text())
    pre["sessions"]=83
    pre=signed({k:v for k,v in pre.items() if k!="fingerprint"})
    (v83dir/"summary.json").write_text(json.dumps(pre))
    with pytest.raises(V85Error,match="PARENT_CHAIN"):
        v85.run(v83dir,v84dir,tmp_path/"should_not_exist",announce=lambda _:None)
    assert not (tmp_path/"should_not_exist").exists()

def test_tampered_original_gzip_fails_before_simulation(tmp_path):
    v83dir,v84dir=_fixture_campaign(tmp_path)
    target=next((v84dir/"journals").iterdir())
    target.write_bytes(b"not-a-genuine-options-journal")
    with pytest.raises(V85Error,match="JOURNAL_GZIP_SHA_CHANGED"):
        v85.run(v83dir,v84dir,tmp_path/"denied",announce=lambda msg:None)
    assert not (tmp_path/"denied").exists()
