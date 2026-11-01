from __future__ import annotations

"""V90 synthetic signed quote-cash tests; no external source access."""

from packages.simulation.spy_v84_offline_three_family_economics import signed as sign84
from packages.simulation.spy_v86_original_option_exit_recheck import signed as sign86
from packages.simulation.spy_v90_six_family_capital_ledger import (
    simulate,verified,SCOPES,
)


def pair(session,family,day="2024-01-02",*,start="09:40:10",
         exit_at="09:41:10",pnl="90.00",unresolved=False,no_entry=False,
         lag=3,policy="balanced_35_100",rest=10):
    a=sign84({
        "contract":"atlas-v84-offline-three-family-option-quote-shadow-v1",
        "session":day,"strategy":family,"policy":policy,
        "lag_seconds":lag,
        "decision_at_et":day+"T09:40:01-05:00",
        "entry_action_at_et":None if no_entry else day+"T"+start+"-05:00",
        "entry_debit_usd":None if no_entry else "200.00",
        "entry_qty":0 if no_entry else 2,
        "status":"NO_ENTRY" if no_entry else "UNRESOLVED_POSITION" if unresolved else "CLOSED_QUOTE_REFERENCE",
        "reason":"ENTRY_REJECTED" if no_entry else "ORIGINAL_EXIT",
        "source_query_id":session,"provider_requests":0,"actual_broker_fills":0,
    })
    b=sign86({
        "contract":"atlas-v86-original-option-exit-limit-recheck-v1",
        "original_trial_sha":a["fingerprint"],
        "session":day,"strategy":family,"policy":policy,"lag_seconds":lag,
        "limit_rest_seconds":rest,
        "status":"NO_ENTRY" if no_entry else "UNRESOLVED_POSITION" if unresolved else "CLOSED_QUOTE_REFERENCE",
        "reason":"ENTRY_REJECTED" if no_entry else "ORIGINAL_EXIT",
        "exit_action_at_et":None if (unresolved or no_entry) else day+"T"+exit_at+"-05:00",
        "quote_reference_pnl_usd":None if (unresolved or no_entry) else pnl,
        "quote_reference_pnl_2pct_bid_haircut_usd":None if (unresolved or no_entry) else pnl,
        "provider_requests":0,"actual_broker_fills":0,
    })
    return a,b


def run(pairs,scope="all_six_new_families"):
    return simulate(pairs,scope=scope,policy="balanced_35_100",
                    lag_seconds=3,dwell_seconds=10)


def test_six_individual_scopes_and_shared_account_available():
    assert len(SCOPES)==7
    assert SCOPES[0]=="all_six_new_families"
    assert "impulse_0935" in SCOPES


def test_source_linked_closed_cash_and_complete_causal_journal():
    p=pair("one","acceleration_0940",pnl="35.20")
    r=run([p])
    assert verified(r)
    assert r["closed_trade_stressed_quote_pnl_usd"]=="35.20"
    assert r["ending_stressed_quote_cash_usd"]=="25035.20"
    assert r["terminal_equity_known_if_flat_usd"]=="25035.20"
    assert r["dispositions"]["HYPOTHETICAL_ENTRY_ASK_DEBIT"]==1
    assert r["dispositions"]["CLOSED_HYPOTHETICAL_QUOTE_EXIT"]==1
    assert len(r["all_considered_and_blocked_events"])==2
    assert r["actual_broker_fills"]==r["actual_broker_orders"]==0


def test_no_entry_is_retained_with_reason_and_does_not_change_cash():
    p=pair("two","early_reversal_0940",no_entry=True)
    r=run([p])
    assert r["dispositions"]["NO_ENTRY_REJECTED"]==1
    assert r["ending_stressed_quote_cash_usd"]=="25000.00"
    assert r["all_considered_and_blocked_events"][0]["reason"]=="ENTRY_REJECTED"


def test_parallel_families_same_clock_conflict_is_deterministic():
    a=pair("one","acceleration_0940",pnl="20.00")
    b=pair("two","pullback_resume_0940",pnl="500.00")
    r=run([a,b])
    assert r["dispositions"]["BLOCKED_SHARED_CAPITAL_POSITION_BUSY"]==1
    assert r["closed_trade_stressed_quote_pnl_usd"]=="20.00"
    assert r["original_opportunities"]==2
    # No cherry-picking the retrospectively profitable concurrent candidate.
    assert any(x["event"]=="CAPACITY_CONFLICT" for x in r["all_considered_and_blocked_events"])


def test_unresolved_exit_is_never_silently_liquidated_or_reused():
    a=pair("one","acceleration_0940",unresolved=True)
    b=pair("two","pullback_resume_0940",pnl="1000.00")
    r=run([a,b])
    assert r["dispositions"]["UNRESOLVED_POSITION_NO_FICTIONAL_EXIT"]==1
    assert r["dispositions"]["BLOCKED_SHARED_CAPITAL_POSITION_BUSY"]==1
    assert r["unresolved_exercise_or_expiry_cash"] is True
    assert r["terminal_equity_known_if_flat_usd"] is None
    assert r["closed_trade_stressed_quote_pnl_usd"]=="0.00"
    assert r["ending_stressed_quote_cash_usd"]=="24800.00"


def test_higher_reference_pnl_not_used_as_prior_hindsight_selection():
    a=pair("one","acceleration_0940",pnl="-60.00")
    b=pair("two","pullback_resume_0940",pnl="800.00")
    r=run([b,a])
    assert r["closed_trade_stressed_quote_pnl_usd"]=="-60.00"
    assert r["largest_positive_1_stressed_quote_usd"] is None
    assert r["pnl_excluding_top_two_positive_quote_outcomes_usd"]=="-60.00"
