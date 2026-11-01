from __future__ import annotations

"""V86: causal original-source post-trigger option exit-order quote recheck.

A historical BID at or above a sell limit demonstrates indicative
marketability, NOT a fill. If the trigger limit is not marketable at the V84
action, observe a frozen 0/3/10/30-second limit-rest window; if never
marketable, model a *new* hypothetical repriced-BID reference after another
registered 1s/3s action lag. No order routing or settlement is presumed.
"""

from datetime import datetime,timedelta
from decimal import Decimal,ROUND_HALF_UP
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT="atlas-v86-original-option-exit-limit-recheck-v1"
DWELLS=(0,3,10,30)
FEE=Decimal(".65")
ET_SHIFT_SECONDS=0
FALLBACK_MAX_EXTRA_QUOTE_SECONDS=3
MAX_SOURCE_GAP_SECONDS=60


class V86Error(ValueError):
    pass


def signed(item):
    return {**item,"fingerprint":_fingerprint(item)}


def verified(item):
    return isinstance(item,dict) and item.get("fingerprint")==_fingerprint({
        k:v for k,v in item.items() if k!="fingerprint"
    })


def money(value):
    return Decimal(str(value)).quantize(Decimal(".01"),rounding=ROUND_HALF_UP)


def recheck(trial,source,prepared,*,dwell_seconds):
    if dwell_seconds not in DWELLS:
        raise V86Error("V86_UNREGISTERED_LIMIT_REST_DURATION")
    if (not verified(trial) or trial.get("actual_broker_fills")!=0
            or trial.get("provider_requests")!=0
            or source.get("query_id")!=trial["source_query_id"]
            or source.get("source_sha256")!=trial["source_sha256"]
            or source.get("status")!="CACHE_HIT"):
        raise V86Error("V86_ORIGINAL_SHA_SOURCE_OR_EXECUTION_DRIFT")
    lag=trial["lag_seconds"]
    if lag not in (1,3):
        raise V86Error("V86_UNREGISTERED_ACTION_LATENCY")
    checks=[]
    events=[]
    def step(name,**args):
        events.append({"event":name,**args})

    if trial["status"]=="NO_ENTRY":
        if trial.get("exit") is not None or trial.get("entry_debit_usd") is not None:
            raise V86Error("V86_CENSORED_SOURCE_BECAME_ENTRY")
        return signed({
            "contract":CONTRACT,"original_trial_sha":trial["fingerprint"],
            "original_source_query_id":trial["source_query_id"],
            "original_source_sha256":trial["source_sha256"],
            "session":trial["session"],"strategy":trial["strategy"],
            "policy":trial["policy"],"lag_seconds":lag,
            "limit_rest_seconds":dwell_seconds,"status":"NO_ENTRY",
            "reason":trial["reason"],"outcome_class":"ORIGINAL_ENTRY_REJECTED",
            "exit_action_at_et":None,"exit_bid_reference":None,
            "quote_reference_pnl_usd":None,
            "quote_reference_pnl_2pct_bid_haircut_usd":None,
            "quote_observations_examined":0,
            "events":[],"actual_broker_fills":0,"provider_requests":0,
            "marketability_not_guaranteed_execution":True,
        })
    if trial["status"]!="CLOSED_QUOTE_REFERENCE" or not isinstance(trial.get("exit"),dict):
        raise V86Error("V86_V84_UNRESOLVED_ENTRY_NEEDS_EXPLICIT_CENSOR")
    ex=trial["exit"]
    action=datetime.fromisoformat(ex["action_at_et"])
    hard=datetime.fromisoformat(trial["hard_exit_at_et"])
    decision=datetime.fromisoformat(trial["decision_at_et"])
    entry=datetime.fromisoformat(trial["entry_action_at_et"])
    if (action>hard or action<=entry or entry<decision
            or not (decision.date()==action.date()==hard.date())):
        raise V86Error("V86_CAUSAL_EXIT_OR_EXPIRY_CLOCK_INVALID")
    qty=trial["entry_qty"]
    paid=money(trial["entry_debit_usd"])
    trigger_bid=Decimal(str(ex["trigger_bid"]))
    trigger_at=datetime.fromisoformat(ex["trigger_at_et"])
    if (type(qty) is not int or qty<1 or paid<=0 or trigger_bid<=0
            or trigger_at>action or trigger_at<entry):
        raise V86Error("V86_INVALID_ORIGINAL_SELL_LIMIT_GEOMETRY")
    original_bid=Decimal(ex["action_bid"])
    orig_marketable=ex["original_trigger_limit_marketable_at_action"]
    if (type(orig_marketable) is not bool
            or orig_marketable!=(original_bid>=trigger_bid)):
        raise V86Error("V86_ORIGINAL_EXIT_MARKETABILITY_CHANGED")
    # Reconstruct V84 trigger and action BID from the same original tape
    # before extending the subsequent marketability-check clock.
    trigger_quote=next((q for at,q,err,idx in prepared if at==trigger_at),None)
    action_quote=next((q for at,q,err,idx in prepared if at==action),None)
    if (trigger_quote is None or action_quote is None
            or Decimal(trigger_quote["bid"])!=trigger_bid
            or Decimal(action_quote["bid"])!=original_bid
            or action_quote["bid_size"]<qty):
        raise V86Error("V86_ORIGINAL_TRIGGER_OR_ACTION_QUOTE_NOT_REPRODUCIBLE")

    def completed(at,bid,*,kind):
        credit=money(qty*(bid*100-FEE))
        stress_credit=money(qty*(bid*Decimal(".98")*100-FEE))
        step("HYPOTHETICAL_SELL_TO_CLOSE_QUOTE_REFERENCE",at_et=at.isoformat(),
             bid=str(bid),qty=qty,kind=kind,
             original_limit_at_action_marketable=orig_marketable,
             broker_fill_verified=False)
        return signed({
            "contract":CONTRACT,"original_trial_sha":trial["fingerprint"],
            "original_source_query_id":trial["source_query_id"],
            "original_source_sha256":trial["source_sha256"],
            "session":trial["session"],"strategy":trial["strategy"],
            "policy":trial["policy"],"lag_seconds":lag,
            "limit_rest_seconds":dwell_seconds,
            "status":"CLOSED_QUOTE_REFERENCE","reason":ex["reason"],
            "outcome_class":kind,
            "entry_action_at_et":entry.isoformat(),
            "original_exit_action_at_et":action.isoformat(),
            "exit_action_at_et":at.isoformat(),
            "original_trigger_limit_price":str(trigger_bid),
            "original_action_bid":str(original_bid),
            "original_action_limit_marketable":orig_marketable,
            "exit_bid_reference":str(bid),
            "quote_reference_credit_usd":str(credit),
            "quote_reference_pnl_usd":str(money(credit-paid)),
            "quote_reference_pnl_2pct_bid_haircut_usd":str(money(stress_credit-paid)),
            "quote_observations_examined":len(checks),
            "events":events,
            "actual_broker_fills":0,"provider_requests":0,
            "marketability_not_guaranteed_execution":True,
            "historical_order_cancel_replace_unverified":True,
        })

    def unresolved(reason):
        step("UNKNOWN_POSITION_AT_CUTOFF",reason=reason,
             hypothetical_source_not_order_execution=True,
             expiry_or_exercise_settlement_unknown=True)
        return signed({
            "contract":CONTRACT,"original_trial_sha":trial["fingerprint"],
            "original_source_query_id":trial["source_query_id"],
            "original_source_sha256":trial["source_sha256"],
            "session":trial["session"],"strategy":trial["strategy"],
            "policy":trial["policy"],"lag_seconds":lag,
            "limit_rest_seconds":dwell_seconds,
            "status":"UNRESOLVED_POSITION","reason":reason,
            "outcome_class":"NO_QUALIFIED_SOURCE_BACKED_EXIT_ACTION",
            "entry_action_at_et":entry.isoformat(),
            "original_exit_action_at_et":action.isoformat(),
            "exit_action_at_et":None,"exit_bid_reference":None,
            "quote_reference_pnl_usd":None,
            "quote_reference_pnl_2pct_bid_haircut_usd":None,
            "quote_observations_examined":len(checks),
            "events":events,
            "actual_broker_fills":0,"provider_requests":0,
            "marketability_not_guaranteed_execution":True,
            "expiry_or_exercise_cash_unknown":True,
        })

    # A marketable original *observed* BID is retained as an indicative
    # reference only; the order book, queue and fills are never reconstructed.
    if orig_marketable:
        step("ORIGINAL_FIXED_LIMIT_MARKETABLE_AT_ACTION",
             at_et=action.isoformat(),trigger_limit=str(trigger_bid),
             action_bid=str(original_bid),fill_unproven=True)
        return completed(action,original_bid,kind="ORIGINAL_LIMIT_QUOTE_MARKETABLE")

    step("ORIGINAL_LIMIT_UNMARKETABLE_AT_ACTION",
         at_et=action.isoformat(),trigger_limit=str(trigger_bid),
         observed_bid=str(original_bid))
    # Retain original resting limit for exactly dwell_seconds. Only the first
    # chronological valid BID >= limit with displayed quantity can qualify.
    end=min(action+timedelta(seconds=dwell_seconds),hard)
    for at,q,err,idx in prepared:
        if at<=action:
            continue
        if at>end:
            break
        checks.append(at)
        if q is None:
            step("RESTING_LIMIT_QUOTE_INVALID",at_et=at.isoformat(),
                 original_row=idx,reason=err)
            continue
        if q["bid_size"]<qty:
            step("RESTING_LIMIT_DISPLAYED_BID_SIZE_INSUFFICIENT",
                 at_et=at.isoformat(),original_row=idx,
                 bid_size=q["bid_size"],required_qty=qty)
            continue
        bid=Decimal(q["bid"])
        if bid>=trigger_bid:
            step("ORIGINAL_LIMIT_LATER_MARKETABLE_QUOTE",
                 at_et=at.isoformat(),observed_bid=str(bid),
                 trigger_limit=str(trigger_bid),broker_fill_unverified=True)
            # Conservatively do not assume price improvement above limit.
            return completed(at,trigger_bid,kind="LATER_FIXED_LIMIT_QUOTE_MARKETABLE")
    # If no fixed-limit marketability proof, cancel/replace is only a model.
    # Action latency starts AFTER the registered resting interval.
    if end>=hard:
        return unresolved("ORIGINAL_LIMIT_UNMARKETABLE_AT_HARD_CUTOFF")
    earliest=end+timedelta(seconds=lag)
    latest=min(earliest+timedelta(seconds=FALLBACK_MAX_EXTRA_QUOTE_SECONDS),hard)
    step("HYPOTHETICAL_CANCEL_REPLACE_INTENT",
         at_et=end.isoformat(),action_earliest_et=earliest.isoformat(),
         original_trigger_limit_unmarketable=True)
    if earliest>hard:
        return unresolved("REQUOTE_ACTION_AFTER_HARD_CUTOFF")
    for at,q,err,idx in prepared:
        if at<earliest:
            continue
        if at>latest:
            break
        checks.append(at)
        if q is None:
            step("REPRICE_ACTION_QUOTE_INVALID",at_et=at.isoformat(),
                 original_row=idx,reason=err)
            continue
        if q["bid_size"]<qty:
            step("REPRICE_ACTION_INSUFFICIENT_DISPLAYED_BID_SIZE",
                 at_et=at.isoformat(),bid_size=q["bid_size"],required_qty=qty)
            continue
        bid=Decimal(q["bid"])
        if bid<=0:
            continue
        step("REQUOTE_SOURCE_BID_OBSERVED",
             at_et=at.isoformat(),bid=str(bid),
             actual_cancel_replace_unverified=True)
        return completed(at,bid,kind="REPRICED_BID_QUOTE_SHADOW")
    return unresolved("NO_QUALIFIED_REPRICE_ACTION_QUOTE_WITHIN_WINDOW")
