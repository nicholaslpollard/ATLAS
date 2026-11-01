from __future__ import annotations

"""V99 offline 49x24 derived original quote case integrity; no provider calls."""

from datetime import date,datetime
import json
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import normalize_source_requirement
from packages.core.market_calendar import get_market_calendar
from packages.simulation.spy_v84_offline_three_family_economics import signed as sign84
from packages.simulation.spy_v86_original_option_exit_recheck import signed as sign86
from scripts import run_spy_v99_49_call_variant_quote_economics as v99


def fixture_case():
    kwargs={
        "symbol":"SPY","date_et":"2022-12-02",
        "expiration":"2022-12-02","strike":"400",
        "right":"call","start_time_et":"09:35:01.000",
        "end_time_et":"15:30:00.000","interval":"1s",
    }
    request=normalize_source_requirement("option_history_exact_quote_tape",kwargs)
    qid=_fingerprint(request)
    ev={
        "session":"2022-12-02","decision_clock_et":"09:35:01",
        "strike":"400","expiry":"2022-12-02",
        "original_decision_sha":"b"*64,"original_stock_sha256":"a"*64,
        "strategy":"impulse_0935","trial_id":"V97B-impulse_0935-00",
        "source_coverage_status":"NEW_EXACT_CALL_SOURCE_SCOPE_REQUIRES_SEPARATE_REVIEW",
    }
    source={
        "query_id":qid,"source_sha256":"c"*64,"status":"CACHE_HIT",
        "exact_requirement":request,
    }
    return ev,source


def test_derived_bullish_decision_and_exact_source_are_signed_and_asof():
    ev,source=fixture_case()
    d,q=v99.decision_and_demand(ev,source)
    assert d["strategy_id"]=="impulse_0935"
    assert d["direction"]=="CALL"
    assert d["session"]=="2022-12-02"
    assert d["decision_at_et"]=="2022-12-02T09:35:01-05:00"
    assert d["original_asof_v89_decision_sha"]==ev["original_decision_sha"]
    assert q["strategy_decision_sha"]==d["fingerprint"]
    assert q["query_id"]==source["query_id"]
    assert q["kwargs"]["right"]=="call"
    assert d["news_signal_used"] is False
    assert _fingerprint({k:v for k,v in d.items() if k!="fingerprint"})==d["fingerprint"]
    assert _fingerprint({k:v for k,v in q.items() if k!="fingerprint"})==q["fingerprint"]


def test_fake_changed_strike_and_put_never_promoted_to_call_source():
    ev,source=fixture_case()
    broken=dict(ev,strike="401")
    with pytest.raises(v99.V99Error,match="DERIVED_CALL_DECISION"):
        v99.decision_and_demand(broken,source)
    tampered=dict(source)
    req={**source["exact_requirement"],
         "kwargs":{**source["exact_requirement"]["kwargs"],"right":"put"}}
    tampered["exact_requirement"]=req
    with pytest.raises(v99.V99Error,match="DERIVED_CALL_DECISION"):
        v99.decision_and_demand(ev,tampered)


def test_censored_unresolved_exit_has_null_cash_for_every_dwell():
    a=sign84({
        "contract":"atlas-v84-offline-three-family-option-quote-shadow-v1",
        "session":"2022-12-02","strategy":"impulse_0935",
        "policy":"balanced_35_100","lag_seconds":3,
        "status":"UNRESOLVED_POSITION",
        "reason":"QUOTE_PATH_GAP",
        "source_sha256":"a"*64,
    })
    for dwell in (0,3,10,30):
        x=v99.censored_exit(a,dwell)
        assert x["status"]=="UNRESOLVED_POSITION"
        assert x["quote_reference_pnl_usd"] is None
        assert x["quote_reference_pnl_2pct_bid_haircut_usd"] is None
        assert x["exercise_or_expiry_cash_unknown"] is True
        assert x["original_trial_sha"]==a["fingerprint"]
        assert _fingerprint({k:v for k,v in x.items() if k!="fingerprint"})==x["fingerprint"]


def test_missing_original_source_never_becomes_complete_pnl():
    a=sign84({
        "contract":"atlas-v84-offline-three-family-option-quote-shadow-v1",
        "session":"2022-12-02","strategy":"impulse_0935",
        "policy":"balanced_35_100","lag_seconds":3,
        "decision_at_et":"2022-12-02T09:35:01-05:00",
        "entry_action_at_et":"2022-12-02T09:35:04-05:00",
        "entry_debit_usd":"150.00","entry_qty":1,
        "status":"CLOSED_QUOTE_REFERENCE","reason":"CAUSAL_TRAIL",
        "source_query_id":"1"*64,"provider_requests":0,"actual_broker_fills":0,
    })
    b=sign86({
        "contract":"atlas-v86-original-option-exit-limit-recheck-v1",
        "original_trial_sha":a["fingerprint"],
        "session":"2022-12-02","strategy":"impulse_0935",
        "policy":"balanced_35_100","lag_seconds":3,
        "limit_rest_seconds":10,
        "status":"CLOSED_QUOTE_REFERENCE",
        "reason":"CAUSAL_TRAIL",
        "exit_action_at_et":"2022-12-02T09:36:04-05:00",
        "quote_reference_pnl_usd":"20.00",
        "quote_reference_pnl_2pct_bid_haircut_usd":"16.00",
        "provider_requests":0,"actual_broker_fills":0,
    })
    missing=[{"session":"2022-01-19","source_reason":"PROVIDER_EXPLICIT_NO_DATA"}]
    out=v99.exact_ledger([(a,b)],scope="impulse_0935",
        policy="balanced_35_100",lag=3,dwell=10,missing=missing)
    assert out["original_v90_account_ledger"]["closed_trade_stressed_quote_pnl_usd"]=="16.00"
    assert out["source_complete"] is False
    assert out["original_stressed_quote_pnl_usd_if_complete"] is None
    assert out["cash_equity_known"] is False
    assert out["unqualified_causal_candidate_sources"]==missing
    complete=v99.exact_ledger([(a,b)],scope="impulse_0935",
        policy="balanced_35_100",lag=3,dwell=10,missing=[])
    assert complete["original_stressed_quote_pnl_usd_if_complete"]=="16.00"
    assert complete["cash_equity_known"] is True


def test_protected_holdout_not_part_of_historical_cohorts():
    assert v99.cohort("2020-05-01")=="2020_SOURCE_PARTIAL"
    assert v99.cohort("2022-01-19")=="2022_full"
    assert v99.cohort("2026-04-30")=="2026_janapr"
    with pytest.raises(v99.V99Error,match="PROTECTED"):
        v99.cohort("2026-05-12")
    with pytest.raises(v99.V99Error,match="PROTECTED"):
        v99.cohort("2026-08-11")
    assert len(v99.DEFINITIONS)==24
    assert v99.V99_REQUIRED_COMPLETE_COEFFICIENTS==1176


def test_actual_original_signed_v97b_v98_admission_if_on_research_workstation():
    root=Path(__file__).resolve().parents[1]/"data"/"research"
    a=sorted(p for p in root.glob("spy_v97b_49_variant_call_only_source_union_*")
             if p.is_dir() and (p/"summary.json").is_file())
    b=sorted(p for p in root.glob("spy_v98_safe_call_source_acquisition_*")
             if p.is_dir() and (p/"summary.json").is_file())
    if len(a)!=1 or len(b)!=1:
        pytest.skip("Original signed V97B/V98 workstation stage folders not available")
    source,summary,events,entries,qualified,no_data,unknown=v99.inspect_v98(
        a[0],b[0],get_market_calendar("XNYS"))
    assert len(entries)==2482
    assert len(qualified)==576
    assert len(unknown)==1 and len(no_data)==1
    assert source["provider_dispatch_attempts"]==209
    assert source["source_uses_resolved"]==208
    assert source["source_uses_explicit_no_data"]==1
    assert any(ev["session"]=="2022-01-19" and ev["new_source_explicit_no_data"]
               for ev in entries)
    assert all(ev["session"]<="2026-04-30" for ev in entries)
