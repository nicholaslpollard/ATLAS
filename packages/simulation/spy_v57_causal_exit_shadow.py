from __future__ import annotations

"""V57 immutable V55/V56 replay shadow: dynamic exits from strictly prior quotes.

No historical execution claims. Stop loss and projected upside are QUOTE
references and heuristics, not guaranteed broker prices or proven forecasts.
"""

from collections import deque
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP
from math import sqrt

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-v57-past-only-adaptive-0dte-exit-shadow-v1"
POLICY = "risk-budget-trailing-high-water-past-quote-volatility-v1"
FEE=Decimal("0.65")
RISK_SHARE=Decimal("0.005")
ACTIVATE=Decimal("0.20")
TRAIL_BASE=Decimal("0.10")
TRAIL_MAX=Decimal("0.20")
CUTOFF=time(15,0)


class AdaptiveShadowError(ValueError):
    pass


def _decimal(x):
    try:
        value=Decimal(str(x))
    except Exception as exc:
        raise AdaptiveShadowError("NONNUMERIC_PRICE") from exc
    if not value.is_finite():
        raise AdaptiveShadowError("NONFINITE_PRICE")
    return value


def _money(x):
    return x.quantize(Decimal(".01"),rounding=ROUND_HALF_UP)


def _at(value):
    try:
        stamp=datetime.fromisoformat(str(value))
    except (ValueError,TypeError) as exc:
        raise AdaptiveShadowError("INVALID_QUOTE_CLOCK") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise AdaptiveShadowError("QUOTE_CLOCK_WITHOUT_TIMEZONE")
    return stamp


def _signed(record):
    return {**record,"fingerprint":_fingerprint(record)}


def replay_adaptive_shadow(original):
    """Replay existing historical quote observations, never future data.

    Exact predeclared developmental exit rules:
    0.5% account RISK BUDGET (not guaranteed maximum realized loss);
    +20% option gain enables high-water trailing 10%-20% based on last 60
    observed bid changes; exit on risk floor, trail, or 15:00 ET.
    """
    if (not isinstance(original,dict)
            or original.get("fingerprint")!=_fingerprint({
                k:v for k,v in original.items() if k!="fingerprint"})):
        raise AdaptiveShadowError("PARENT_REPORT_DIGEST_INVALID")
    if original.get("actual_fills")!=0 or original.get("valid_historical_alpha") is not False:
        raise AdaptiveShadowError("PARENT_EXECUTION_EVIDENCE_NOT_QUALIFIED")
    baseline={k:original.get(k) for k in (
        "status","session","entry_debit","exit_credit","trade_net_pnl",
        "terminal_equity_if_resolved")}
    result={
        "contract":CONTRACT,"policy":POLICY,
        "source_report_fingerprint":original["fingerprint"],
        "source_query_id":original.get("source_query_id"),
        "source_sha256":original.get("source_sha256"),
        "session":original.get("session"),"baseline":baseline,
        "rules":{"equity_risk_budget_pct":"0.5",
                 "trailing_activation_favorable_bid_pct":"20",
                 "trailing_min_pct":"10","trailing_max_pct":"20",
                 "rolling_prior_bid_changes":60,"risk_stop_observed_not_guaranteed":True,
                 "force_time_exit_et":"15:00",
                 "future_peak_is_unknown_at_each_decision":True,
                 "estimated_next_300_seconds_high_unvalidated":True},
        "status":None,"exit_reason":None,"candidate_exit":None,
        "entry_cost":None,"risk_budget_dollars":None,"initial_stop_bid":None,
        "net_pnl":None,"terminal_equity_if_resolved":None,
        "observed_quotes":0,"decision_journal":[],
        "highest_bid_observed_before_exit":None,
        "lowest_bid_observed_before_exit":None,
        "historical_broker_fills":0,"historical_alpha_validated":False,
        "first_publication_proven":False,
        "parameters_chosen_after_original_june_9_outcome":True,
        "upside_projection_is_only_a_heuristic":True,
    }
    events=original.get("events") or []
    entries=[e for e in events if e.get("type")=="MODELED_ENTRY_QUOTE_REFERENCE"]
    actions=[e for e in events if e.get("type")=="ORDER_ACTION_QUOTE_REFERENCE"]
    if not entries:
        result["status"]="NO_ENTRY_IN_PARENT"
        return _signed(result)
    if len(entries)!=1 or len(actions)!=1:
        raise AdaptiveShadowError("AMBIGUOUS_PARENT_POSITION")
    entry=entries[0]
    ask=_decimal(entry["ask"])
    qty=entry.get("qty")
    if type(qty) is not int or qty<=0 or ask<=0:
        raise AdaptiveShadowError("ENTRY_IDENTITY_OR_SIZE_INVALID")
    if ask!=_decimal(actions[0]["action"]["ask"]):
        raise AdaptiveShadowError("ENTRY_VERSUS_ACTION_QUOTE_CONFLICT")
    starting=_decimal(original["starting_cash"])
    paid=_decimal(original["entry_debit"])
    if paid!=_money(qty*(ask*100+FEE)):
        raise AdaptiveShadowError("ENTRY_CASH_RECONCILIATION_FAILED")
    budget=_money(starting*RISK_SHARE)
    stop=max(Decimal(0),ask-(budget-2*FEE*qty)/(100*qty))
    entry_clock=_at(entry["at_et"])
    high=low=last_bid=_decimal(actions[0]["action"]["bid"])
    last_at=entry_clock
    noise_recent=deque(maxlen=60)
    trail_enabled=False
    protected_trail_floor=None
    result["entry_cost"]=str(paid)
    result["risk_budget_dollars"]=str(budget)
    result["initial_stop_bid"]=str(stop)
    for item in events:
        if item.get("type")!="EXIT_REVIEW":
            continue
        quote=item["quote"]
        t=_at(quote["timestamp_et"])
        if t<=last_at:
            raise AdaptiveShadowError("NONCHRONOLOGICAL_QUOTE_EVENT")
        seconds=(t-last_at).total_seconds()
        if seconds>60:
            result["status"]="CENSORED_MISSING_QUOTE_PATH"
            result["exit_reason"]="OBSERVATION_GAP_OVER_60_SECONDS"
            break
        bid,quote_ask=_decimal(quote["bid"]),_decimal(quote["ask"])
        bid_size,ask_size=quote["bid_size"],quote["ask_size"]
        if (bid<=0 or bid>quote_ask or type(bid_size) is not int or bid_size<=0
                or type(ask_size) is not int or ask_size<=0
                or (quote_ask-bid)/((quote_ask+bid)/2)>Decimal(".15")):
            result["status"]="CENSORED_UNQUALIFIED_QUOTE"
            result["exit_reason"]="INVALID_PRICE_SIZE_OR_SPREAD"
            break
        noise_recent.append(abs(bid-last_bid))
        mean_abs_delta=sum(noise_recent,Decimal(0))/len(noise_recent)
        high=max(high,bid)
        low=min(low,bid)
        if high>=ask*(1+ACTIVATE):
            trail_enabled=True
        noise_width=3*mean_abs_delta/high
        trail_pct=min(TRAIL_MAX,max(TRAIL_BASE,noise_width))
        if trail_enabled:
            candidate_floor=high*(1-trail_pct)
            protected_trail_floor=(candidate_floor if protected_trail_floor is None
                                   else max(protected_trail_floor,candidate_floor))
        trailing_floor=protected_trail_floor
        floor=max(stop,trailing_floor) if trailing_floor is not None else stop
        reason=("RISK_BUDGET_STOP" if bid<=stop else
                "PROFIT_HIGH_WATER_TRAIL" if trailing_floor is not None and bid<=trailing_floor else
                "TIME_15_00" if t.time()>=CUTOFF else "HOLD")
        # This is NOT a learned distribution of the future maximum. It
        # estimates a plausible 300s noise envelope from observed PAST bids.
        projected_upside=bid+mean_abs_delta*Decimal(str(sqrt(300)))
        result["observed_quotes"]+=1
        result["decision_journal"].append({
            "at_et":t.isoformat(),"bid":str(bid),"ask":str(quote_ask),
            "bid_size":bid_size,"ask_size":ask_size,
            "spread_pct":str(100*(quote_ask-bid)/quote_ask),
            "high_water_bid_at_decision":str(high),
            "decline_from_high_water_pct":str(100*(high-bid)/high),
            "last_60_mean_abs_bid_change":str(mean_abs_delta),
            "unvalidated_300s_upside_envelope":str(projected_upside),
            "risk_stop_bid":str(stop),"trail_active":trail_enabled,
            "trail_distance_pct":str(100*trail_pct),"exit_floor_bid":str(floor),
            "hypothetical_pnl_if_exited_now":str(_money(qty*(bid*100-FEE)-paid)),
            "decision":reason,"since_last_quote_seconds":seconds,
        })
        last_bid=bid
        last_at=t
        if reason!="HOLD":
            if bid_size<qty:
                result["status"]="CENSORED_NO_EXIT_BID_CAPACITY"
                result["exit_reason"]="INSUFFICIENT_BID_SIZE_FOR_HYPOTHETICAL_EXIT"
                break
            credit=_money(qty*(bid*100-FEE))
            result["status"]="CLOSED_ADAPTIVE_QUOTE_REFERENCE"
            result["exit_reason"]=reason
            result["candidate_exit"]={
                "at_et":t.isoformat(),"observed_bid":str(bid),
                "bid_size":bid_size,"credit_after_exit_commission":str(credit)}
            result["net_pnl"]=str(_money(credit-paid))
            result["terminal_equity_if_resolved"]=str(_money(starting-paid+credit))
            break
    result["highest_bid_observed_before_exit"]=str(high)
    result["lowest_bid_observed_before_exit"]=str(low)
    if result["status"] is None:
        result["status"]="CENSORED_AT_PARENT_BASELINE_EXIT"
        result["exit_reason"]="NO_QUOTE_HISTORY_PAST_PARENT_EXIT"
    return _signed(result)
