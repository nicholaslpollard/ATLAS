from __future__ import annotations

"""V90: one-slot quote-reference cash ledger for newly registered V89 families.

Input is already-source-linked signed V84/V86 decision evidence, not actual
fills. Unresolved exits have unknown exercise/expiry cash and NEVER become
assumed zero-valued liquidations. Original chronology and no-entry decisions
are retained. No option network API or broker interaction.
"""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from collections import Counter, defaultdict

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v89_six_family_causal_registry import FAMILIES
from packages.simulation.spy_v84_offline_three_family_economics import (
    verified as verified_v84,
)
from packages.simulation.spy_v86_original_option_exit_recheck import (
    verified as verified_v86,
)

CONTRACT="atlas-v90-new-six-family-execution-sober-ledger-v1"
START=Decimal("25000.00")
SCOPES=("all_six_new_families",)+tuple(FAMILIES)
ORDER={f:i for i,f in enumerate(FAMILIES)}


class V90Error(ValueError):
    pass


def amount(x):
    v=Decimal(str(x))
    if not v.is_finite():
        raise V90Error("V90_NONFINITE_CASH")
    return v.quantize(Decimal(".01"),rounding=ROUND_HALF_UP)


def signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def verified(doc):
    return isinstance(doc,dict) and doc.get("fingerprint")==_fingerprint({
        k:v for k,v in doc.items() if k!="fingerprint"
    })


def simulate(pairs,*,scope,policy,lag_seconds,dwell_seconds):
    if (scope not in SCOPES or type(lag_seconds) is not int
            or lag_seconds not in (1,3) or dwell_seconds not in (0,3,10,30)):
        raise V90Error("V90_UNREGISTERED_QUOTE_PORTFOLIO_VARIANT")
    selected=[]
    for a,b in pairs:
        if (not verified_v84(a) or not verified_v86(b)
                or b["original_trial_sha"]!=a["fingerprint"]
                or a["strategy"]!=b["strategy"]
                or a["session"]!=b["session"]
                or a["lag_seconds"]!=lag_seconds
                or a["policy"]!=policy
                or b["limit_rest_seconds"]!=dwell_seconds
                or a["strategy"] not in FAMILIES
                or a["actual_broker_fills"]!=0
                or b["actual_broker_fills"]!=0):
            raise V90Error("V90_BROKEN_ORIGINAL_TRIAL_SOURCE_PAIR")
        if scope=="all_six_new_families" or a["strategy"]==scope:
            selected.append((a,b))
    selected.sort(key=lambda pair:(
        datetime.fromisoformat(pair[0]["decision_at_et"]),
        ORDER[pair[0]["strategy"]],
        pair[0]["source_query_id"],
    ))
    cash=START
    stressed=START
    open_position=None
    entries=[]
    events=[]
    disp=Counter()
    by_month=defaultdict(lambda:Decimal("0"))
    by_week=defaultdict(lambda:Decimal("0"))
    max_flat_drawdown=Decimal("0")
    peak_flat=START

    def release(now):
        nonlocal cash,stressed,open_position,max_flat_drawdown,peak_flat
        if open_position is None or open_position["exit_at"] is None:
            return
        if open_position["exit_at"]>now:
            return
        pos=open_position
        cash+=pos["credit"]
        stressed+=pos["stress_credit"]
        disp["CLOSED_HYPOTHETICAL_QUOTE_EXIT"]+=1
        month=pos["session"][:7]
        by_month[month]+=pos["stress_pnl"]
        y,w,_=pos["exit_at"].isocalendar()
        by_week[f"{y}-W{w:02d}"]+=pos["stress_pnl"]
        events.append({
            "event":"MODELED_EXIT_QUOTE_CREDIT",
            "session":pos["session"],"family":pos["family"],
            "at_et":pos["exit_at"].isoformat(),
            "source_query_id":pos["qid"],
            "exit_outcome_sha":pos["outcome_sha"],
            "observed_bid_credit_usd":str(pos["credit"]),
            "two_pct_haircut_credit_usd":str(pos["stress_credit"]),
            "two_pct_haircut_pnl_usd":str(pos["stress_pnl"]),
            "broker_fill_verified":False,
        })
        entries.append(pos["stress_pnl"])
        peak_flat=max(peak_flat,stressed)
        max_flat_drawdown=max(max_flat_drawdown,peak_flat-stressed)
        open_position=None

    for trial,exit_quote in selected:
        decision=datetime.fromisoformat(trial["decision_at_et"])
        release(decision)
        if trial["status"]=="NO_ENTRY":
            if exit_quote["status"]!="NO_ENTRY" or trial["entry_debit_usd"] is not None:
                raise V90Error("V90_NO_ENTRY_CANNOT_GENERATE_EXIT")
            disp["NO_ENTRY_REJECTED"]+=1
            events.append({
                "event":"ORIGINAL_ENTRY_REJECTED","session":trial["session"],
                "family":trial["strategy"],"reason":trial["reason"],
                "source_query_id":trial["source_query_id"],
                "trial_sha":trial["fingerprint"],
            })
            continue
        if trial["status"] not in ("CLOSED_QUOTE_REFERENCE","UNRESOLVED_POSITION"):
            raise V90Error("V90_UNKNOWN_ORIGINAL_TRIAL_STATUS")
        action=datetime.fromisoformat(trial["entry_action_at_et"])
        release(action)
        if open_position is not None:
            disp["BLOCKED_SHARED_CAPITAL_POSITION_BUSY"]+=1
            events.append({
                "event":"CAPACITY_CONFLICT","session":trial["session"],
                "family":trial["strategy"],
                "source_query_id":trial["source_query_id"],
                "previous_source_query_id":open_position["qid"],
                "unknown_previous_exit":open_position["exit_at"] is None,
            })
            continue
        debit=amount(trial["entry_debit_usd"])
        if (debit<=0 or debit>500
                or type(trial["entry_qty"]) is not int
                or not 1<=trial["entry_qty"]<=4):
            raise V90Error("V90_PREMIUM_OR_SIZE_OUTSIDE_FROZEN_BUDGET")
        if cash<debit or stressed<debit:
            disp["BLOCKED_INSUFFICIENT_CASH"]+=1
            events.append({
                "event":"INSUFFICIENT_SHARED_CASH",
                "session":trial["session"],"family":trial["strategy"],
                "available_cash_usd":str(cash),
                "original_debit_usd":str(debit),
            })
            continue
        cash-=debit
        stressed-=debit
        disp["HYPOTHETICAL_ENTRY_ASK_DEBIT"]+=1
        events.append({
            "event":"ENTRY_ASK_REFERENCE_ONLY",
            "session":trial["session"],"family":trial["strategy"],
            "action_at_et":action.isoformat(),
            "source_query_id":trial["source_query_id"],
            "original_v84_trial_sha":trial["fingerprint"],
            "debit_usd":str(debit),
            "contract_quantity":trial["entry_qty"],
            "broker_fill_verified":False,
        })
        if exit_quote["status"]=="UNRESOLVED_POSITION":
            disp["UNRESOLVED_POSITION_NO_FICTIONAL_EXIT"]+=1
            open_position={
                "exit_at":None,
                "qid":trial["source_query_id"],
                "family":trial["strategy"],"session":trial["session"],
            }
            events.append({
                "event":"UNKNOWN_EXPIRY_OR_EXERCISE_CASH",
                "source_query_id":trial["source_query_id"],
                "reason":exit_quote["reason"],
                "source_exit_sha":exit_quote["fingerprint"],
            })
            continue
        if (trial["status"]!="CLOSED_QUOTE_REFERENCE"
                or exit_quote["status"]!="CLOSED_QUOTE_REFERENCE"):
            raise V90Error("V90_SOURCE_EXIT_NOT_QUALIFIED")
        exit_at=datetime.fromisoformat(exit_quote["exit_action_at_et"])
        pnl=amount(exit_quote["quote_reference_pnl_usd"])
        stress_pnl=amount(exit_quote["quote_reference_pnl_2pct_bid_haircut_usd"])
        credit=debit+pnl
        stress_credit=debit+stress_pnl
        if (exit_at<=action or exit_at.date()!=action.date()
                or min(credit,stress_credit)<0):
            raise V90Error("V90_EXIT_CLOCK_OR_CASH_INVALID")
        open_position={
            "exit_at":exit_at,"qid":trial["source_query_id"],
            "family":trial["strategy"],"session":trial["session"],
            "credit":credit,"stress_credit":stress_credit,
            "stress_pnl":stress_pnl,"outcome_sha":exit_quote["fingerprint"],
        }
    if open_position is not None and open_position["exit_at"] is not None:
        release(open_position["exit_at"])
    unresolved=open_position is not None
    if unresolved:
        disp["TERMINAL_POSITION_UNRESOLVED"]+=1
    pnl=amount(sum(entries,Decimal("0")))
    positive=sorted((v for v in entries if v>0),reverse=True)
    negative=[v for v in entries if v<0]
    return signed({
        "contract":CONTRACT,"scope":scope,"policy":policy,
        "lag_seconds":lag_seconds,"limit_rest_seconds":dwell_seconds,
        "capital_rule":"one_position_25000_frozen_original_cash",
        "strategy_count":len(FAMILIES),
        "original_opportunities":len(selected),
        "dispositions":dict(sorted(disp.items())),
        "all_considered_and_blocked_events":events,
        "starting_cash_usd":str(START),
        "ending_quote_cash_usd":str(cash),
        "ending_stressed_quote_cash_usd":str(stressed),
        "flat_to_flat_max_stressed_drawdown_usd":str(max_flat_drawdown),
        "stressed_month_pnl_usd":{k:str(v) for k,v in sorted(by_month.items())},
        "stressed_week_pnl_usd":{k:str(v) for k,v in sorted(by_week.items())},
        "closed_trade_stressed_quote_pnl_usd":str(pnl),
        "positive_closed":len(positive),"negative_closed":len(negative),
        "zero_closed":len(entries)-len(positive)-len(negative),
        "largest_positive_1_stressed_quote_usd":str(positive[0]) if positive else None,
        "largest_positive_2_stressed_quote_usd":str(positive[1]) if len(positive)>1 else None,
        "pnl_excluding_top_two_positive_quote_outcomes_usd":str(
            amount(pnl-sum(positive[:2],Decimal("0")))),
        "terminal_equity_known_if_flat_usd":str(stressed) if not unresolved else None,
        "unresolved_exercise_or_expiry_cash":unresolved,
        "closed_cash_only_not_live_broker_equity":True,
        "original_limit_quote_marketable_not_a_fill":True,
        "actual_broker_orders":0,"actual_broker_fills":0,
        "no_provider_calls":True,
    })
