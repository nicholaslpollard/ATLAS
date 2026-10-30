from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import pytest

from packages.simulation.options_pair_chronological_runtime_v50 import (
    PairReplayError, replay_pairs,
)

CALL="SPY:2020-02-21:270:C"
PUT="SPY:2020-02-21:270:P"
ORDER="2020-01-02T15:01:00+00:00"
ACTION="2020-01-02T15:01:03+00:00"


def leg(identity, *, at, bid="4.90", ask="5.00", size=100, source="q"):
    return {
        "contract_identity":identity,
        "timestamp_et":at, "available_at_utc":at,
        "bid":bid, "ask":ask, "bid_size":size, "ask_size":size,
        "source_query_id":source, "source_sha256":"a"*64,
    }


def pair(*, at, bid="4.90", ask="5.00", skews=None, source="q"):
    a,b=(at,at) if skews is None else skews
    return {
        "call":leg(CALL,at=a,bid=bid,ask=ask,source=source),
        "put":leg(PUT,at=b,bid=bid,ask=ask,source=source),
    }


def review(at="2020-01-03T15:01:00+00:00", hold=1, *, bid="7", ask="7.10"):
    return {
        "review_at_utc":at, "hold_sessions":hold,
        "quote_pair":pair(at=at,bid=bid,ask=ask,source="exit"),
    }


def case(*, id="test1", signal="ENTER_LONG_PAIR", reviews=None):
    return {
        "opportunity_id":id, "strategy_version":"v50-fixture-not-real",
        "signal_status":signal, "signal_at_utc":"2020-01-02T15:00:00+00:00",
        "feature_available_at_utc":"2020-01-02T14:59:00+00:00",
        "causal_signal_evidence_verified":True,
        "reason_codes":["SELECTED_AT_DECISION"],
        "call_identity":CALL,"put_identity":PUT,
        "order_at_utc":ORDER, "action_at_utc":ACTION,
        "order_quote_pair":pair(at=ORDER,source="order"),
        "action_quote_pair":pair(at="2020-01-02T15:01:02+00:00",source="action"),
        "exit_reviews":[review()] if reviews is None else reviews,
        "source_context":{"prior_oi":120, "note":"fictional values, not historical"},
    }


def run(cases,**kw):
    return replay_pairs(cases,**kw)


def test_basic_dynamic_profit_target_entry_exit_account_and_full_provenance():
    r=run([case()])
    assert r["opportunities_evaluated"]==1
    assert r["modeled_quote_reference_entries"]==1
    assert r["modeled_quote_reference_exits"]==1
    assert r["terminal_equity_if_fully_resolved"]=="100397.40"
    assert r["open_unresolved_position_id"] is None
    kinds=[e["event_type"] for e in r["events"]]
    assert kinds==["OPPORTUNITY_DECISION","MODELED_ENTRY_QUOTE_REFERENCE",
                   "EXIT_REVIEW","MODELED_EXIT_QUOTE_REFERENCE"]
    assert r["events"][0]["disposition"]=="QUOTE_REFERENCE_ENTRY_ELIGIBLE"
    assert r["events"][2]["trigger"]=="PROFIT_TARGET"
    assert r["events"][3]["actual_fill"] is False
    assert r["broker_orders_or_fills"]==0
    assert r["strategy_pnl_validated"] is False
    assert r["fingerprint"]
    assert "source_query_id" in r["events"][0]["order_quote_observation"]["per_leg"]["call"]


def test_no_trade_signal_and_pit_failures_get_full_decision_events():
    a=case(signal="ABSTAIN",id="a")
    b=case(id="b")
    b["signal_at_utc"]="2020-01-03T15:00:00+00:00"
    b["feature_available_at_utc"]="2020-01-03T15:02:00+00:00"
    b["order_at_utc"]="2020-01-03T15:01:00+00:00"
    b["action_at_utc"]="2020-01-03T15:01:03+00:00"
    c=case(id="c")
    c["signal_at_utc"]="2020-01-06T15:00:00+00:00"
    c["causal_signal_evidence_verified"]=False
    c["exit_reviews"]=[]  # no planned reviews for an unqualified, never-entered opportunity
    c["order_at_utc"]="2020-01-06T15:01:00+00:00"
    c["action_at_utc"]="2020-01-06T15:01:03+00:00"
    result=run([c,b,a])
    assert result["modeled_quote_reference_entries"]==0
    assert result["opportunity_dispositions"]=={
        "ABSTAIN_OR_REJECT_SIGNAL":1,"CAUSAL_SIGNAL_INPUT_NOT_QUALIFIED":2
    }
    assert len(result["events"])==3
    assert result["terminal_equity_if_fully_resolved"]=="100000.00"


def test_bad_price_data_never_creates_modeled_fill_and_is_logged():
    s=case()
    s["action_quote_pair"]["put"]["ask"]="8.00"
    r=run([s])
    assert r["opportunity_dispositions"]=={"ORDER_OR_ACTION_SOURCE_UNQUALIFIED":1}
    assert r["modeled_quote_reference_entries"]==0
    s=case()
    s["action_quote_pair"]["put"]["bid"]="4.95"
    s["action_quote_pair"]["put"]["ask"]="5.20"
    r=run([s],maximum_adverse_action_drift_pct="1")
    assert r["opportunity_dispositions"]=={"LATENCY_OR_PRICE_DRIFT_UNQUALIFIED":1}
    assert "ACTION_PAIR_ADVERSE_PRICE_DRIFT_OVER_POLICY" in r["events"][0]["action_latency_diagnostic"]["reason_codes"]


def test_missing_delayed_action_quote_must_not_assume_unchanged_price():
    s=case()
    s.pop("action_quote_pair")
    r=run([s])
    assert r["opportunity_dispositions"]=={"ORDER_OR_ACTION_SOURCE_UNQUALIFIED":1}
    assert r["modeled_quote_reference_entries"]==0


def test_one_second_baseline_is_not_overridden_by_three_second_experiment():
    s=case()
    s["action_quote_pair"]=pair(at="2020-01-02T15:01:02+00:00",skews=(
        "2020-01-02T15:01:00+00:00","2020-01-02T15:01:02+00:00"),source="action")
    one=run([s],pair_skew_seconds=1)
    three=run([s],pair_skew_seconds=3)
    assert one["opportunity_dispositions"]=={"ORDER_OR_ACTION_SOURCE_UNQUALIFIED":1}
    assert three["opportunity_dispositions"]=={"QUOTE_REFERENCE_ENTRY_ELIGIBLE":1}
    assert three["policy"]["max_quote_skew_seconds"]==3
    assert three["strategy_pnl_validated"] is False


def test_risk_budget_and_open_slot_reject_later_opportunities():
    s=case(reviews=[review(at="2020-01-09T15:01:00+00:00",hold=1,bid="4.9",ask="5")])
    s2=case(id="case2",reviews=[review(at="2020-01-09T15:01:00+00:00",hold=1)])
    s2["signal_at_utc"]="2020-01-06T15:00:00+00:00"
    s2["order_at_utc"]="2020-01-06T15:01:00+00:00"
    s2["action_at_utc"]="2020-01-06T15:01:03+00:00"
    r=run([s2,s])
    assert r["opportunity_dispositions"]["OCCUPIED_OPEN_PAIR_SLOT"]==1
    assert r["open_unresolved_position_id"]=="test1"
    assert r["terminal_equity_if_fully_resolved"] is None
    too_costly=run([case()],cash_risk_fraction="0.005")
    assert too_costly["opportunity_dispositions"]=={"RISK_BUDGET_REJECT":1}


def test_stop_loss_and_maximum_hold_are_distinct_dynamic_exit_reasons():
    stop=run([case(reviews=[review(bid="3",ask="3.1")])])
    assert next(e for e in stop["events"] if e["event_type"]=="EXIT_REVIEW")["trigger"]=="STOP_LOSS"
    wait=run([case(reviews=[
        review(hold=1,bid="4.9",ask="5.0"),
        review(at="2020-01-06T15:01:00+00:00",hold=2,bid="4.9",ask="5.0"),
    ])], maximum_hold_reviews=2)
    triggers=[e["trigger"] for e in wait["events"] if e["event_type"]=="EXIT_REVIEW"]
    assert triggers==["HOLD_CONTINUES","MAXIMUM_HOLD"]
    assert wait["modeled_quote_reference_exits"]==1


def test_missing_required_exit_never_converts_position_to_zero_pnl_or_reuses_cash():
    s=case(reviews=[review()])
    s["exit_reviews"][0]["quote_pair"]["put"]["timestamp_et"]="2020-01-03T15:02:00+00:00"
    s["exit_reviews"][0]["quote_pair"]["put"]["available_at_utc"]="2020-01-03T15:02:00+00:00"
    r=run([s],maximum_hold_reviews=1)
    assert r["modeled_quote_reference_entries"]==1
    assert r["modeled_quote_reference_exits"]==0
    assert r["open_unresolved_position_id"]=="test1"
    assert r["terminal_equity_if_fully_resolved"] is None
    assert r["terminal_cash_excluding_unmarked_exposure"]=="98998.70"
    assert "EXIT_UNRESOLVED" in [e["event_type"] for e in r["events"]]
    assert "OPEN_POSITION_UNRESOLVED" in [e["event_type"] for e in r["events"]]


def test_bad_timestamps_duplicate_ids_bad_signal_fail_closed():
    duplicate=case()
    with pytest.raises(PairReplayError,match="DUPLICATE"):
        run([duplicate,deepcopy(duplicate)])
    q=case()
    q["signal_at_utc"]="2020-01-02T15:00:00"
    with pytest.raises(PairReplayError,match="NAIVE"):
        run([q])
    q=case()
    q["action_at_utc"]="2020-01-02T15:01:04+00:00"
    with pytest.raises(PairReplayError,match="CLOCK_INVALID"):
        run([q])
    q=case()
    q["signal_status"]="BUY_A_LAMBO"
    with pytest.raises(PairReplayError,match="UNKNOWN_SIGNAL"):
        run([q])
    with pytest.raises(PairReplayError,match="UNREGISTERED"):
        run([case()],pair_skew_seconds=4)


def test_changed_future_exit_quotes_cannot_affect_prior_entry_selection():
    s=case()
    alternative=deepcopy(s)
    alternative["exit_reviews"][0]["quote_pair"]["call"]["bid"]="0.01"
    a=run([s])
    b=run([alternative])
    assert a["events"][0]==b["events"][0]
    assert a["events"][1]==b["events"][1]
    assert a["events"][2]!=b["events"][2]
    assert a["fingerprint"]!=b["fingerprint"]


def test_same_underlying_expiration_strike_right_and_expiry_proof_are_required():
    unrelated=case()
    unrelated["put_identity"]="QQQ:2020-02-21:270:P"
    with pytest.raises(PairReplayError,match="MISMATCH"):
        run([unrelated])
    put_wrong_strike=case()
    put_wrong_strike["put_identity"]="SPY:2020-02-21:275:P"
    with pytest.raises(PairReplayError,match="MISMATCH"):
        run([put_wrong_strike])
    put_wrong_right=case()
    put_wrong_right["put_identity"]="SPY:2020-02-21:270:C"
    with pytest.raises(PairReplayError,match="MISMATCH"):
        run([put_wrong_right])
    invalid=case()
    invalid["call_identity"]="O:SPY200221C00270000"
    with pytest.raises(PairReplayError,match="FORMAT"):
        run([invalid])
    after_expiry=case()
    after_expiry["signal_at_utc"]="2020-02-24T15:00:00+00:00"
    with pytest.raises(PairReplayError,match="EXPIRATION"):
        run([after_expiry])


def test_post_expiry_future_quote_cannot_force_account_sale_without_exercise_evidence():
    original=case(reviews=[review(
        at="2020-02-24T15:01:00+00:00",hold=1,bid="9",ask="9.1"
    )])
    actual=run([original],maximum_hold_reviews=1)
    exit_review=next(e for e in actual["events"] if e["event_type"]=="EXIT_REVIEW")
    assert "POST_EXPIRY_ASSIGNMENT_OR_EXERCISE_EVIDENCE_REQUIRED" in exit_review["review_reason_codes"]
    assert actual["open_unresolved_position_id"]=="test1"
    assert actual["terminal_equity_if_fully_resolved"] is None


def test_input_offset_variants_sorted_by_actual_utc_instant_not_raw_iso_string():
    first=case(id="first",signal="ABSTAIN")
    first["signal_at_utc"]="2020-01-02T09:00:00-05:00"  # 14:00 UTC
    second=case(id="second",signal="ABSTAIN")
    second["signal_at_utc"]="2020-01-02T14:30:00+00:00"
    result=run([second,first])
    assert [e["opportunity_id"] for e in result["events"]]==["first","second"]


def test_weekly_monthly_annual_reference_cash_periods_keep_unresolved_separate():
    complete=run([case()])
    periods=complete["reference_realized_periods"]
    assert periods["status"]=="CLOSED_QUOTE_REFERENCE_PERIODS_NOT_VALIDATED_STRATEGY_PNL"
    assert periods["closed_trades"][0]["net_reference_pnl_dollars"]=="397.40"
    assert periods["weekly"][0]["period"]=="2020-W01"
    assert periods["monthly"][0]["period"]=="2020-01"
    assert periods["annual"][0]["period"]=="2020"
    assert periods["annual"][0]["modeled_net_reference_pnl_dollars"]=="397.40"
    assert periods["annual"][0]["whole_account_economic_window_proven"] is False
    none=run([case(reviews=[])])
    assert none["terminal_equity_if_fully_resolved"] is None
    assert none["reference_realized_periods"]["annual"]==[]
    assert none["reference_realized_periods"]["account_terminal_unresolved"] is True
