from __future__ import annotations

"""V74: causal, quote-reference dynamic sell-to-close exit policy.

No broker calls, autoexercise, guaranteed fills, hindsight, or made-up quotes.
Previously accepted V55 baseline original entries remain frozen.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_closed_bar_option_replay import (
    _quote, _read_timestamp, _dec,
)

ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v74-spy-causal-dynamic-sell-to-close-quote-shadow-v1"
BROKERS=("webull","alpaca")
# These are conservative ATLAS research cutoffs, not broker promises or
# representations of automatic broker intervention times.
PROFILES={
    "webull": {"planned_exit":"15:00:00", "hard_liquidation":"15:05:00",
               "broker_auto_sale_guaranteed":False,
               "historical_webull_option_order_fill_verified":False},
    "alpaca": {"planned_exit":"15:00:00", "hard_liquidation":"15:05:00",
               "broker_risk_review_from":"15:30:00",
               "broker_auto_sale_guaranteed":False,
               "historical_alpaca_option_order_fill_verified":False},
}
FEE=Decimal("0.65")


class V74Error(ValueError):
    pass


def signed(x):
    return {**x,"fingerprint":_fingerprint(x)}


def verified(doc):
    return isinstance(doc,dict) and doc.get("fingerprint")==_fingerprint({
        k:v for k,v in doc.items() if k!="fingerprint"
    })


def money(x):
    # Prices must be positive; signed financial P&L must also accept zero
    # and losses. Do not reuse V55._dec (a strictly positive quote validator).
    try:
        number = Decimal(str(x))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise V74Error("V74_NONNUMERIC_FINANCIAL_AMOUNT") from exc
    if not number.is_finite():
        raise V74Error("V74_NONFINITE_FINANCIAL_AMOUNT")
    return number.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def replay(original, source, *,broker="webull",action_lag_seconds=1,
           trailing_arm_pct="20",trail_from_high_pct="15",
           max_bad_quote_seconds=30,max_observation_gap_seconds=60,
           max_hold_minutes=180,stop_loss_option_pct="-50",
           take_profit_option_pct="100",market_close_et=None):
    # The original V74 default remains bit-for-bit stable. Nondefault
    # V76 research variants are a small, preregistered finite policy set.
    # This function never enables a new provider or broker operation.
    if (broker not in BROKERS or action_lag_seconds not in (1,3)
            or trailing_arm_pct not in ("10","20","30") or
            trail_from_high_pct not in ("10","15","20")
            or stop_loss_option_pct not in ("-25","-35","-50")
            or take_profit_option_pct not in ("40","75","100","150")
            or max_bad_quote_seconds not in (15,30) or
            max_observation_gap_seconds != 60 or max_hold_minutes not in (60,120,180)):
        raise V74Error("V74_UNREGISTERED_PREDECLARED_EXIT_VARIANT")
    if not verified(original) or not verified(original.get("standalone_replay_report")):
        raise V74Error("V74_PARENT_ORIGINAL_SIGNATURE_INVALID")
    trade=original["standalone_replay_report"]
    if trade.get("actual_fills")!=0 or trade.get("policy",{}).get("lag_seconds")!=1 or str(trade.get("policy",{}).get("max_adverse_pct"))!="1":
        raise V74Error("V74_PARENT_EXECUTION_POLICY_CHANGED")
    day=date.fromisoformat(original["session"])
    contract=original["selected_contract"]
    parent_status=trade["status"]
    entry=[x for x in trade["events"] if x["type"]=="MODELED_ENTRY_QUOTE_REFERENCE"]
    if parent_status in ("NO_SIGNAL","NO_ENTRY"):
        if entry:
            raise V74Error("V74_CENSORED_PARENT_HAS_ENTRY")
        return signed({
            "contract":CONTRACT,"session":original["session"],
            "broker_research_policy":broker,"status":parent_status,
            "reason":"ORIGINAL_BASELINE_ENTRY_DISPOSITION_PRESERVED",
            "parent_v65_sha":original["fingerprint"],
            "parent_trade_sha":trade["fingerprint"],
            "entry_debit":None,"exit_credit":None,"trade_net_pnl":None,
            "events":[],"actual_broker_fills":0,"provider_requests":0,
        })
    if parent_status not in ("CLOSED_QUOTE_REFERENCE","UNRESOLVED_POSITION") or len(entry)!=1:
        raise V74Error("V74_UNSUPPORTED_PARENT_ENTRY_DISPOSITION")
    receipt=original.get("exact_option_receipt")
    requirement=original.get("exact_option_requirement")
    if (not isinstance(receipt,dict) or receipt.get("state")!="ARCHIVED"
            or receipt.get("query_id")!=_fingerprint(requirement)
            or trade["source_query_id"]!=receipt["query_id"]
            or trade["source_sha256"]!=receipt["archive_sha256"]
            or not isinstance(source,dict)
            or source.get("query_id")!=receipt["query_id"]
            or source.get("source_sha256")!=receipt["archive_sha256"]
            or source.get("exact_requirement")!=requirement
            or source.get("status") != "CACHE_HIT"
            or not isinstance(source.get("source_rows"),(tuple,list))):
        raise V74Error("V74_EXACT_ORIGINAL_SOURCE_SHA_OR_IDENTITY_UNQUALIFIED")
    original_entry=entry[0]
    entry_at=datetime.fromisoformat(original_entry["at_et"])
    ask=_dec(original_entry["ask"])
    qty=original_entry["qty"]
    debit=money(trade["entry_debit"])
    if (type(qty) is not int or qty<=0 or debit!=money(qty*(ask*100+FEE))
            or original_entry["debit_plus_entry_fees"]!=str(debit)):
        raise V74Error("V74_ORIGINAL_ENTRY_COST_OR_QUANTITY_MISMATCH")
    src=source["source_rows"]
    stamps=[_read_timestamp(row,day) for row in src]
    if stamps!=sorted(set(stamps)) or not stamps:
        raise V74Error("V74_ORIGINAL_QUOTE_CLOCK_AMBIGUOUS")
    try:
        ix=stamps.index(entry_at)
        observed=_quote(src[ix],day=day,contract=contract)
    except (ValueError,KeyError,TypeError) as exc:
        raise V74Error("V74_ORIGINAL_ENTRY_QUOTE_NOT_OBSERVED") from exc
    if _dec(observed["ask"])!=ask or qty>observed["ask_size"]:
        raise V74Error("V74_ORIGINAL_ENTRY_SIDE_NOT_PROVEN")
    base=datetime.combine(day,time(9,30),ET)
    plan=PROFILES[broker]
    planned=datetime.combine(day,time.fromisoformat(plan["planned_exit"]),ET)
    hard=datetime.combine(day,time.fromisoformat(plan["hard_liquidation"]),ET)
    # Optional future V76 cohort uses the publicly known exchange schedule.
    # Legacy V74 calls without an explicit schedule retain identical clocks.
    early_close=False
    if market_close_et is not None:
        if (not isinstance(market_close_et,datetime)
                or market_close_et.utcoffset() is None
                or market_close_et.astimezone(ET).date()!=day):
            raise V74Error("V76_INVALID_EXCHANGE_CLOSE_CLOCK")
        close=market_close_et.astimezone(ET)
        official_regular=datetime.combine(day,time(16,0),ET)
        if close>official_regular or close.time()<time(11,0):
            raise V74Error("V76_INVALID_EXCHANGE_SESSION_BOUNDARY")
        if close<official_regular:
            early_close=True
            # Known NYSE early close (typically 13:00 ET): initiate exit
            # one hour before market close, last action 55 minutes before.
            # These are conservative experimental ATLAS risk clocks, not
            # either broker's promised liquidation cutoff.
            planned=min(planned,close-timedelta(minutes=60))
            hard=min(hard,close-timedelta(minutes=55))
    max_hold=entry_at+timedelta(minutes=max_hold_minutes)
    events=[{
        "type":"ORIGINAL_ENTRY_REUSED",
        "at_et":entry_at.isoformat(),"ask":str(ask),"qty":qty,
        "debit_plus_fees":str(debit),"parent_trade_sha":trade["fingerprint"],
        "actual_broker_fill":False,
    }]
    high=Decimal("0")
    trailing=None
    last_good=entry_at
    bad_since=None
    intent=None
    stop=ask*(1+Decimal(stop_loss_option_pct)/100)
    target=ask*(1+Decimal(take_profit_option_pct)/100)
    if stop<=0 or target<=ask:
        raise V74Error("V76_EXIT_THRESHOLD_GEOMETRY_INVALID")
    def result(status,reason,*,exit_at=None,bid=None,credit=None):
        return signed({
            "contract":CONTRACT,"session":day.isoformat(),
            "broker_research_policy":broker,"status":status,"reason":reason,
            "parent_v65_sha":original["fingerprint"],
            "parent_trade_sha":trade["fingerprint"],
            "original_option_archive_sha256":receipt["archive_sha256"],
            "original_query_id":receipt["query_id"],
            "selected_contract":contract,
            "strategy_params":{
                "original_entry_lag_seconds":1,
                "original_max_adverse_entry_ask_pct":"1",
                "dynamic_action_lag_seconds":action_lag_seconds,
                "trailing_arm_profit_pct":trailing_arm_pct,
                "trailing_pct_from_high":trail_from_high_pct,
                "original_stop_option_pct":"-50",
                "original_profit_target_pct":"100",
                **({
                    "registered_v76_stop_loss_option_pct":stop_loss_option_pct,
                    "registered_v76_profit_target_option_pct":take_profit_option_pct,
                } if (stop_loss_option_pct!="-50" or
                      take_profit_option_pct!="100") else {}),
                "max_bad_quote_seconds":max_bad_quote_seconds,
                "max_observation_gap_seconds":max_observation_gap_seconds,
                "max_hold_minutes":max_hold_minutes,
                "planned_liquidation_et":planned.time().isoformat() if early_close else plan["planned_exit"],
                "last_attempt_et":hard.time().isoformat() if early_close else plan["hard_liquidation"],
                **({"early_exchange_close_cutoff_applied":True,
                    "original_exchange_session_close_et":market_close_et.astimezone(ET).isoformat()}
                   if early_close else {}),
                "broker_automatic_sale_guaranteed":False,
            },
            "entry_debit":str(debit),
            "exit_credit":str(credit) if credit is not None else None,
            "trade_net_pnl":str(money(credit-debit)) if credit is not None else None,
            "exit_at_et":exit_at.isoformat() if exit_at else None,
            "exit_bid":str(bid) if bid is not None else None,
            "events":events,"original_baseline_status":parent_status,
            "quote_reference_not_broker_execution":True,
            "actual_broker_fills":0,"provider_requests":0,
            "cash_balance_after_if_unresolved":None,
            "exercise_or_expiry_cash_assumed":False,
            "market_impact_or_partial_fill_proven":False,
        })
    for i in range(ix+1,len(src)):
        at=stamps[i]
        if at>hard:
            break
        if (at-last_good).total_seconds()>max_observation_gap_seconds:
            events.append({"type":"QUOTE_PATH_GAP","at_et":at.isoformat(),
                           "seconds":(at-last_good).total_seconds()})
            return result("UNRESOLVED_POSITION","OBSERVATION_GAP_OVER_60_SECONDS")
        try:
            q=_quote(src[i],day=day,contract=contract)
        except (ValueError,KeyError,TypeError) as exc:
            if bad_since is None:
                bad_since=at
            events.append({"type":"QUOTE_REJECTED_HELD_NOT_CASH",
                           "at_et":at.isoformat(),"row":i,
                           "reason":str(exc)})
            if (at-bad_since).total_seconds()>max_bad_quote_seconds:
                return result("UNRESOLVED_POSITION","INVALID_QUOTE_BLACKOUT_EXCEEDED")
            continue
        bad_since=None
        last_good=at
        bid=_dec(q["bid"])
        high=max(high,bid)
        if high>=ask*(1+_dec(trailing_arm_pct)/100):
            candidate=high*(1-_dec(trail_from_high_pct)/100)
            trailing=max(trailing or Decimal("0"),candidate)
        reason=(("BASELINE_PROFIT_TARGET" if take_profit_option_pct=="100"
                 else "REGISTERED_VARIANT_PROFIT_TARGET") if bid>=target else
                ("BASELINE_STOP" if stop_loss_option_pct=="-50"
                 else "REGISTERED_VARIANT_STOP") if bid<=stop else
                "CAUSAL_TRAILING_PROFIT" if trailing is not None and bid<=trailing else
                "MAX_HOLD" if at>=max_hold else
                "PRE_EXPIRY_SELL_TO_CLOSE" if at>=planned else None)
        if intent is None and reason:
            intent={"trigger_at_et":at.isoformat(),
                    "reference_bid":str(bid),"reason":reason,
                    "earliest_action":at+timedelta(seconds=action_lag_seconds)}
            events.append({"type":"EXIT_INTENT",**{
                k:(v.isoformat() if isinstance(v,datetime) else v)
                for k,v in intent.items()
            },"original_qty":qty})
        # Intent is kept pending while quoted liquidity or execution clock
        # prevents an action. This is NOT simulated broker order placement.
        if intent is not None:
            if at<intent["earliest_action"]:
                events.append({"type":"PENDING_EXIT_ACTION_LATENCY",
                               "at_et":at.isoformat(),"bid":str(bid)})
                continue
            if q["bid_size"]<qty:
                events.append({"type":"PENDING_EXIT_INSUFFICIENT_DISPLAYED_SIZE",
                               "at_et":at.isoformat(),"bid":str(bid),
                               "bid_size":q["bid_size"],"required_qty":qty,
                               "partial_fill_not_assumed":True})
                continue
            if (at-intent["earliest_action"]).total_seconds()>max_observation_gap_seconds:
                return result("UNRESOLVED_POSITION","NO_FRESH_ACTION_QUOTE")
            credit=money(qty*(bid*100-FEE))
            events.append({
                "type":"MODELED_SELL_TO_CLOSE_BID_REFERENCE",
                "at_et":at.isoformat(),"observed_bid":str(bid),
                "observed_bid_size":q["bid_size"],"qty":qty,
                "trigger_at_et":intent["trigger_at_et"],
                "trigger_reason":intent["reason"],
                "expected_bid_at_trigger":intent["reference_bid"],
                "observed_bid_change_since_trigger":
                    str(bid-_dec(intent["reference_bid"])),
                "credit_after_fees":str(credit),
                "actual_broker_fill":False,
                "limit_order_fill_guaranteed":False,
            })
            return result("CLOSED_QUOTE_REFERENCE",intent["reason"],
                          exit_at=at,bid=bid,credit=credit)
        # Compact event per valid observation retains causal decision state.
        events.append({
            "type":"EXIT_REVIEW",
            "at_et":at.isoformat(),"row":i,
            "bid":str(bid),"ask":q["ask"],"bid_size":q["bid_size"],
            "high_bid_so_far":str(high),
            "trail_floor":str(trailing) if trailing is not None else None,
            "decision":"HOLD",
        })
    if intent is None:
        events.append({"type":"PRE_EXPIRY_DEADLINE_NO_EXIT_SIGNAL",
                       "hard_cutoff_et":hard.isoformat()})
        return result("UNRESOLVED_POSITION","NO_QUALIFIED_TIME_EXIT_BEFORE_CUTOFF")
    events.append({"type":"PENDING_EXIT_EXPIRED_UNFILLED_REFERENCE",
                   "hard_cutoff_et":hard.isoformat()})
    return result("UNRESOLVED_POSITION","EXIT_INTENT_WITHOUT_QUALIFIED_ACTION_QUOTE")
