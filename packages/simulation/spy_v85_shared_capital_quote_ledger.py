from __future__ import annotations

"""V85: causal opportunity-order shared capital for V84 original-quote shadows.

This is an offline research account, not an executed broker account. The
reprice-to-action-bid ledger intentionally assumes a hypothetical sell at the
observed bid. The fixed-trigger-limit ledger refuses to liquidate when its
original limit was not marketable: remaining exposure and eventual expiry
cash become UNKNOWN, never silently released to fund subsequent trades.
"""

from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT="atlas-v85-shared-capital-execution-sober-quote-ledger-v1"
STARTING_CASH=Decimal("25000.00")
MAX_OPEN_POSITIONS=1
MODES=("repriced_bid_quote_shadow","original_fixed_limit_censored")
SCOPES=("all_families","failed_breakout_fade_0940",
        "orb_continuation_0940","gap_fade_0935")
FAMILY_ORDER={"gap_fade_0935":0,"failed_breakout_fade_0940":1,
              "orb_continuation_0940":2}


class V85Error(ValueError):
    pass


def signed(row):
    return {**row,"fingerprint":_fingerprint(row)}


def verified(row):
    return isinstance(row,dict) and row.get("fingerprint")==_fingerprint({
        k:v for k,v in row.items() if k!="fingerprint"
    })


def _money(value):
    v=Decimal(str(value))
    if not v.is_finite():
        raise V85Error("V85_NONFINITE_AMOUNT")
    return v.quantize(Decimal(".01"))


def simulate(trials,*,scope,policy,lag_seconds,mode,
             starting_cash=STARTING_CASH,max_positions=MAX_OPEN_POSITIONS):
    if (scope not in SCOPES or mode not in MODES
            or type(lag_seconds) is not int or lag_seconds not in (1,3)
            or not policy or max_positions!=1 or starting_cash!=STARTING_CASH):
        raise V85Error("V85_UNREGISTERED_CAUSAL_LEDGER_VARIANT")
    options=[j for j in trials if j["policy"]==policy and
             j["lag_seconds"]==lag_seconds and
             (scope=="all_families" or j["strategy"]==scope)]
    options.sort(key=lambda r:(
        datetime.fromisoformat(r["decision_at_et"]).timestamp(),
        FAMILY_ORDER[r["strategy"]],r["source_query_id"]))
    cash=starting_cash
    stressed_cash=starting_cash
    open_pos=None
    events=[]
    disposition=Counter()
    realized=Decimal("0")
    realized_stress=Decimal("0")
    realized_by_month=defaultdict(lambda:Decimal("0"))
    stressed_by_month=defaultdict(lambda:Decimal("0"))
    realized_by_week=defaultdict(lambda:Decimal("0"))
    stressed_by_week=defaultdict(lambda:Decimal("0"))
    realized_by_year=defaultdict(lambda:Decimal("0"))
    stressed_by_year=defaultdict(lambda:Decimal("0"))
    max_drawdown=Decimal("0")
    peak_flat_equity=starting_cash
    max_deployed=Decimal("0")
    highest_open=0

    def release(at):
        nonlocal cash,stressed_cash,open_pos,realized,realized_stress,peak_flat_equity,max_drawdown
        if open_pos is None or open_pos["release_at"]>at:
            return
        pos=open_pos
        if pos["release_at"].year==9999:
            return
        # Fixed-limit nonmarketability never becomes a fictional cash credit.
        if mode=="original_fixed_limit_censored" and not pos["marketable"]:
            events.append({"type":"EXIT_LIMIT_NOT_MARKETABLE_POSITION_UNRESOLVED",
                           "session":pos["session"],"strategy":pos["strategy"],
                           "source_query_id":pos["source_query_id"],
                           "attempt_at_et":pos["release_at"].isoformat(),
                           "original_trigger_limit_marketable":False,
                           "unknown_exercise_or_expiry_cash":True})
            disposition["UNRESOLVED_ORIGINAL_LIMIT"]+=1
            pos["release_at"]=datetime.max.replace(tzinfo=pos["release_at"].tzinfo)
            return
        cash+=pos["credit"]
        stressed_cash+=pos["stress_credit"]
        realized+=pos["pnl"]
        realized_stress+=pos["stress_pnl"]
        month=pos["session"][:7]
        realized_by_month[month]+=pos["pnl"]
        stressed_by_month[month]+=pos["stress_pnl"]
        year,week,_=datetime.fromisoformat(pos["release_at"].isoformat()).isocalendar()
        wk=f"{year}-W{week:02d}"
        realized_by_week[wk]+=pos["pnl"]
        stressed_by_week[wk]+=pos["stress_pnl"]
        realized_by_year[pos["session"][:4]]+=pos["pnl"]
        stressed_by_year[pos["session"][:4]]+=pos["stress_pnl"]
        disposition["MODELED_EXIT_CREDIT_REFERENCE"]+=1
        events.append({"type":"MODELED_EXIT_BID_CREDIT_REFERENCE",
                       "session":pos["session"],"strategy":pos["strategy"],
                       "source_query_id":pos["source_query_id"],
                       "at_et":pos["release_at"].isoformat(),
                       "original_trigger_limit_marketable":pos["marketable"],
                       "observed_bid_reference_credit_usd":str(pos["credit"]),
                       "two_pct_bid_haircut_credit_usd":str(pos["stress_credit"]),
                       "reference_pnl_usd":str(pos["pnl"]),
                       "two_pct_bid_haircut_pnl_usd":str(pos["stress_pnl"]),
                       "broker_fill_verified":False})
        open_pos=None
        # Flat-equity drawdown, not marked-to-market intraposition drawdown.
        peak_flat_equity=max(peak_flat_equity,cash)
        max_drawdown=max(max_drawdown,peak_flat_equity-cash)

    for trial in options:
        if (not verified(trial) or trial["actual_broker_fills"]!=0
                or trial["provider_requests"]!=0):
            raise V85Error("V85_ORIGINAL_SOURCE_TRIAL_INVALID")
        decision=datetime.fromisoformat(trial["decision_at_et"])
        if trial["status"]=="NO_ENTRY":
            disposition["ORIGINAL_NO_ENTRY"]+=1
            events.append({"type":"ORIGINAL_ENTRY_REJECTED",
                           "session":trial["session"],"strategy":trial["strategy"],
                           "source_query_id":trial["source_query_id"],
                           "at_et":decision.isoformat(),"reason":trial["reason"]})
            continue
        if trial["status"]!="CLOSED_QUOTE_REFERENCE" or trial["exit"] is None:
            raise V85Error("V85_UNRESOLVED_V84_TRIAL_REQUIRES_NEW_POLICY")
        action=datetime.fromisoformat(trial["entry_action_at_et"])
        exit_at=datetime.fromisoformat(trial["exit"]["action_at_et"])
        if action<decision or exit_at<=action or action.date()!=exit_at.date():
            raise V85Error("V85_NONCAUSAL_OPTION_ENTRY_EXIT_CLOCK")
        release(action)
        if open_pos is not None:
            disposition["BLOCKED_CAPACITY_POSITION_ALREADY_OPEN"]+=1
            events.append({"type":"OPPORTUNITY_DECLINED_POSITION_BUSY",
                           "session":trial["session"],"strategy":trial["strategy"],
                           "source_query_id":trial["source_query_id"],
                           "at_et":action.isoformat(),
                           "held_source_query_id":open_pos["source_query_id"],
                           "held_exit_unresolved":open_pos["release_at"].year==9999})
            continue
        entry=_money(trial["entry_debit_usd"])
        qty=trial["entry_qty"]
        if (type(qty) is not int or not 1<=qty<=4 or entry<=0
                or entry>Decimal("500.00")):
            raise V85Error("V85_ENTRY_PREMIUM_OR_QUANTITY_OUTSIDE_REGISTERED_BUDGET")
        if cash<entry or stressed_cash<entry:
            disposition["BLOCKED_INSUFFICIENT_SHARED_CASH"]+=1
            events.append({"type":"OPPORTUNITY_DECLINED_CASH",
                           "session":trial["session"],"strategy":trial["strategy"],
                           "source_query_id":trial["source_query_id"],
                           "at_et":action.isoformat(),
                           "cash_available_usd":str(cash),
                           "two_pct_stress_cash_available_usd":str(stressed_cash),
                           "entry_debit_usd":str(entry)})
            continue
        pnl=_money(trial["quote_reference_pnl_usd"])
        stress_pnl=_money(trial["quote_reference_pnl_2pct_exit_haircut_usd"])
        credit=entry+pnl
        stress_credit=entry+stress_pnl
        if credit<0 or stress_credit<0:
            raise V85Error("V85_EXIT_CREDIT_NEGATIVE")
        marketable=trial["exit"]["original_trigger_limit_marketable_at_action"]
        if type(marketable) is not bool:
            raise V85Error("V85_ORIGINAL_LIMIT_MARKETABILITY_MISSING")
        if trial["exit"]["quote_reference_credit_usd"]!=str(credit):
            raise V85Error("V85_SOURCE_EXIT_CREDIT_INCONSISTENT")
        cash-=entry
        stressed_cash-=entry
        max_deployed=max(max_deployed,entry)
        highest_open=max(highest_open,1)
        open_pos={
            "session":trial["session"],"strategy":trial["strategy"],
            "source_query_id":trial["source_query_id"],
            "release_at":exit_at,"marketable":marketable,
            "credit":credit,"stress_credit":stress_credit,
            "pnl":pnl,"stress_pnl":stress_pnl,
        }
        disposition["HYPOTHETICAL_ENTRY_AT_ACTION_ASK"]+=1
        events.append({"type":"MODELED_ENTRY_ASK_DEBIT_REFERENCE",
                       "session":trial["session"],"strategy":trial["strategy"],
                       "source_query_id":trial["source_query_id"],
                       "at_et":action.isoformat(),
                       "qty":qty,"debit_usd":str(entry),
                       "cash_after_debit_usd":str(cash),
                       "two_pct_stress_cash_after_debit_usd":str(stressed_cash),
                       "fixed_limit_at_exit_marketable_if_observed":marketable,
                       "broker_fill_verified":False})
    if open_pos is not None:
        release(datetime.max.replace(tzinfo=open_pos["release_at"].tzinfo))
    unresolved=open_pos is not None
    if unresolved:
        events.append({"type":"UNKNOWN_TERMINAL_POSITION",
                       "original_source_query_id":open_pos["source_query_id"],
                       "unknown_exercise_or_expiry_cash":True})
    return signed({
        "contract":CONTRACT,"scope":scope,"policy":policy,
        "lag_seconds":lag_seconds,"execution_reference_mode":mode,
        "starting_cash_usd":str(starting_cash),
        "maximum_open_positions":max_positions,
        "candidate_opportunities":len(options),
        "dispositions":dict(sorted(disposition.items())),
        "realized_closed_quote_reference_pnl_usd":str(realized),
        "realized_closed_2pct_exit_haircut_pnl_usd":str(realized_stress),
        "realized_by_month":{k:str(v) for k,v in sorted(realized_by_month.items())},
        "realized_2pct_haircut_by_month":{k:str(v) for k,v in sorted(stressed_by_month.items())},
        "realized_by_week":{k:str(v) for k,v in sorted(realized_by_week.items())},
        "realized_2pct_haircut_by_week":{k:str(v) for k,v in sorted(stressed_by_week.items())},
        "realized_by_year":{k:str(v) for k,v in sorted(realized_by_year.items())},
        "realized_2pct_haircut_by_year":{k:str(v) for k,v in sorted(stressed_by_year.items())},
        "ending_cash_reference_usd":str(cash),
        "ending_cash_2pct_haircut_usd":str(stressed_cash),
        "terminal_cash_only_not_liquidation_equity":True,
        "terminal_equity_if_flat_usd":str(cash) if not unresolved else None,
        "terminal_equity_2pct_haircut_if_flat_usd":str(stressed_cash) if not unresolved else None,
        "unresolved_exercise_or_expiry_cash":unresolved,
        "max_flat_to_flat_drawdown_usd":str(max_drawdown),
        "max_entry_debit_deployed_at_once_usd":str(max_deployed),
        "peak_open_positions":highest_open,
        "opportunity_log":events,
        "observed_quote_not_broker_execution":True,
        "result_not_historical_trading_profits":True,
        "no_assumed_autoexercise_settlement":True,
        "actual_broker_fills":0,"provider_requests":0,"broker_orders":0,
    })
