from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from packages.simulation import options_opportunity_trace_v49 as v49


def q(timestamp, *, bid=9.8, ask=10.0, age=0, spread=None, pre=False):
    return {
        "status": "PRETRADE_QUOTE_0959_PASSES" if pre else "QUOTE_MICROSTRUCTURE_PASSES",
        "timestamp_et": timestamp,
        "bid": bid, "ask": ask, "bid_size": 10, "ask_size": 10,
        "age_seconds" if pre else "seconds_before_1001": age,
        "spread_fraction": (ask-bid)/((ask+bid)/2) if spread is None else spread,
        "source_query_id": "q-id", "source_sha256": "a"*64,
    }


def pair(*, skew=0, pre=False):
    clock="2020-01-02T09:59:00+00:00" if pre else "2020-01-02T10:01:00+00:00"
    first=datetime.fromisoformat(clock)
    return {
        "call": q(first.isoformat(), pre=pre),
        "put": q((first+timedelta(seconds=skew)).isoformat(), pre=pre),
        "skew_seconds": skew,
    }


def test_clock_sensitivity_separates_1s_and_3s_with_identical_quote_gate():
    p=pair(skew=2)
    assert not v49.clock_gate(p,"execution_1001",max_skew_seconds=1)["pass"]
    assert v49.clock_gate(p,"execution_1001",max_skew_seconds=3)["pass"]
    p["put"]["spread_fraction"]=0.2
    assert not v49.clock_gate(p,"execution_1001",max_skew_seconds=3)["pass"]
    p=pair(skew=3.01)
    assert not v49.clock_gate(p,"execution_1001",max_skew_seconds=3)["pass"]
    assert v49.clock_gate(None,"execution_1001",max_skew_seconds=3)["pass"] is None


def test_drift_uses_same_leg_ask_and_pair_cost_not_cross_right_prices():
    pre=pair(pre=True)
    post=pair()
    pre["call"]["ask"]=10
    pre["put"]["ask"]=20
    post["call"]["ask"]=10.1
    post["put"]["ask"]=20.2
    d=v49.same_contract_two_clock_drift(pre,post)
    assert d["status"]=="OBSERVED_TWO_CLOCK_PRICE_CHANGE_NOT_LATENCY"
    assert d["pair_ask"]["cost_change_pct"]==1.0
    assert d["pair_ask"]["diagnostic_only_price_band_pass"]["0.5"] is False
    assert d["pair_ask"]["diagnostic_only_price_band_pass"]["1"] is True
    assert d["pair_ask"]["diagnostic_only_price_band_pass"]["2"] is True
    assert d["is_execution_latency_measurement"] is False
    assert v49.same_contract_two_clock_drift(None,post)["pair_ask"] is None


def test_action_diagnostic_requires_observed_later_quote_and_checks_drift():
    initial=pair()
    nextq=pair()
    for right in v49.RIGHTS:
        nextq[right]["timestamp_et"]="2020-01-02T10:01:02+00:00"
        nextq[right]["ask"]=10.05
    base={"order_at":"2020-01-02T10:01:00+00:00",
          "action_at":"2020-01-02T10:01:03+00:00"}
    outcome=v49.execution_action_diagnostic(initial,nextq,**base,
        max_skew_seconds=1,max_adverse_pair_cost_change_pct="1")
    assert outcome["status"]=="COUNTERFACTUAL_QUOTE_GATES_PASS_NO_FILL"
    assert outcome["observed_action_lag_seconds"]==3.0
    assert not outcome["actual_order_fill_proven"]
    bad=copy.deepcopy(nextq)
    bad["put"]["ask"]=10.5
    rejected=v49.execution_action_diagnostic(initial,bad,**base,
        max_skew_seconds=3,max_adverse_pair_cost_change_pct="1")
    assert "ACTION_PAIR_ADVERSE_PRICE_DRIFT_OVER_POLICY" in rejected["reason_codes"]
    nonexistent=v49.execution_action_diagnostic(initial,{},**base,
        max_skew_seconds=1,max_adverse_pair_cost_change_pct="1")
    assert nonexistent["status"]=="COUNTERFACTUAL_QUOTE_GATES_REJECT"
    future=copy.deepcopy(nextq)
    future["put"]["timestamp_et"]="2020-01-02T10:01:04+00:00"
    c=v49.execution_action_diagnostic(initial,future,**base,
        max_skew_seconds=3,max_adverse_pair_cost_change_pct="1")
    assert "PUT_ACTION_PRICE_FUTURE_OR_OUT_OF_ORDER" in c["reason_codes"]


def test_policy_values_are_bounded_and_timestamp_timezone_required():
    p=pair()
    with pytest.raises(v49.TraceError):
        v49.clock_gate(p,"execution_1001",max_skew_seconds=10)
    with pytest.raises(v49.TraceError):
        v49.execution_action_diagnostic(p,p,order_at="2020-01-02T10:01:00",
            action_at="2020-01-02T10:01:02+00:00",
            max_skew_seconds=1,max_adverse_pair_cost_change_pct="1")
    with pytest.raises(v49.TraceError):
        v49.execution_action_diagnostic(p,p,order_at="2020-01-02T10:01:00+00:00",
            action_at="2020-01-02T10:01:04+00:00",
            max_skew_seconds=1,max_adverse_pair_cost_change_pct="1")


def test_unknown_or_modified_fingerprints_fail_closed():
    with pytest.raises(v49.TraceError,match="INPUT_FINGERPRINT"):
        v49._verified({"contract":v49.PINNED["v45"][0],
                       "fingerprint":v49.PINNED["v45"][1]},"v45")
    assert v49.fingerprint({"a":1})==v49.fingerprint({"a":1})


def test_full_361_opportunity_trace_includes_rejected_and_skips(monkeypatch):
    monkeypatch.setattr(v49,"_verified",lambda report,version:None)
    from datetime import date
    days=[(date(2018,1,1)+timedelta(days=i)).isoformat() for i in range(361)]
    origins=["ORIGINAL_V43"]*106+["NO_SOURCE_QUALITY_ELIGIBLE_PAIR"]*255
    adm=[]
    sig=[]
    exp=[]
    for i,day in enumerate(days):
        status="TWO_CLOCK_SOURCE_QUALITY_PASSES" if i<106 else "SOURCE_QUALITY_NOT_ELIGIBLE"
        adm.append({"date_et":day,"cohort_origin":origins[i],"status":status,
                    "reason_codes":[] if i<106 else ["OI_BELOW_REQUIRED"],
                    "quote_quality":{},"expiration":"2018-02-16",
                    "strike":"270","spot_0959":270.0})
        sc=v49.LONG if i<106 else "SOURCE_QUALITY_REJECTED"
        sig.append({"date_et":day,"cohort_origin":origins[i],
                    "source_quality_status":status, "scenario_screen_status":sc,
                    "scenario_results":[]})
        if i<106:
            holds={str(h):{"status":"PAIRED_EXIT_QUOTE_QUALIFIED"} for h in range(1,6)}
            if i<18:
                holds["1"]={"status":"CENSORED_EXIT_LEG_SKEW",
                    "exit_date_et":"2018-03-01",
                    "reason":{"skew_seconds":2.0 if i<14 else 4.0}}
            exp.append({"entry_date_et":day,"cohort_origin":origins[i],
                        "expiration":"2018-02-16", "strike":"270",
                        "holds":holds})
    r=v49.build_trace(
        {"cases":adm,"total_original_weekly_clocks":411,
         "original_abstentions_unchanged":50},
        {"cases":sig,"source_v45_fingerprint":v49.PINNED["v45"][1]},
        {"cases":exp,"source_v45_fingerprint":v49.PINNED["v45"][1],
         "source_v46_fingerprint":v49.PINNED["v46"][1],
         "hypothetical_long_candidates":106,"historical_strategy_profitability":None,
         "chronological_one_slot_quote_reference_accounts":[],
         "source_request_counts":{}}
    )
    assert len(r["opportunities"])==361
    assert r["hypothetical_screen_counts"]["SOURCE_QUALITY_REJECTED"]==255
    assert r["censored_future_exit_skew_within_3s_only"]==14
    assert r["censored_future_exit_skew_over_3s"]==4
    assert r["provider_requests"]==0
    assert r["no_strategy_filter_selected_using_retrospective_profits"] is True
    assert r["opportunities"][-1]["five_independent_fixed_hold_exit_observations"] is None
    assert r["opportunities"][0]["original_trade_decision_is_validated"] is False
    assert r["fingerprint"]==v49.fingerprint({k:v for k,v in r.items() if k!="fingerprint"})
