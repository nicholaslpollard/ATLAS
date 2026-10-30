from __future__ import annotations

"""V51 experimental single-leg SPY 0DTE ORB quoted-price runtime, NOT fills.

Uses source-linked, independently supplied quotes for the original same-day
contract. Default published configuration is M/W/F, first observed breakout,
at most $500 premium budget, +100% target, -50% stop, 15:30 time exit.
Never infer an intraminute stop/target ordering from bar high/low.
"""

from collections import Counter
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
import re

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.strategies.spy_0dte_opening_range_candidate_v51 import (
    BASE, ALL_DAYS, CONTRACT as ORB_CONTRACT, DEMAND_CONTRACT, EASTERN, _when,
)

CONTRACT="atlas-spy-0dte-orb-single-leg-quote-reference-simulator-v51"
MULTIPLIER=Decimal("100")
FEE_PER_CONTRACT_SIDE=Decimal("0.65")
CAP=Decimal("500")
SERIES=re.compile(r"^SPY:(\d{4}-\d{2}-\d{2}):(\d+(?:\.\d+)?):([CP])$")


class OrbReplayError(ValueError):
    pass


def _amount(raw,*,zero=False):
    try:
        d=Decimal(str(raw))
    except (ValueError,InvalidOperation,TypeError) as exc:
        raise OrbReplayError("V51_INVALID_FINANCIAL_VALUE") from exc
    if not d.is_finite() or (d<0 if zero else d<=0):
        raise OrbReplayError("V51_NONFINITE_OR_INVALID_FINANCIAL_VALUE")
    return d


def _usd(v):
    return v.quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)


def _leg_quote(packet,identity,at):
    if not isinstance(packet,dict):
        return {"status":"UNQUALIFIED","reasons":["NO_HISTORICAL_EXACT_QUOTE"]}
    reasons=[]
    if packet.get("contract_identity")!=identity:
        reasons.append("EXACT_CONTRACT_IDENTITY_MISMATCH")
    if packet.get("historical_first_publication_verified") is not True:
        reasons.append("PUBLICATION_CLOCK_NOT_INDEPENDENTLY_QUALIFIED")
    if (not packet.get("source_query_id")
            or re.fullmatch(r"[0-9a-f]{64}",str(packet.get("source_sha256",""))) is None):
        reasons.append("SOURCE_RECEIPT_SHA_OR_QUERY_MISSING")
    observed=known=None
    try:
        observed=_when(packet["timestamp_et"])
        known=_when(packet["available_at_et"])
        if not observed<=known<=at or (at-observed).total_seconds()>30:
            reasons.append("QUOTE_FUTURE_NOT_YET_KNOWN_OR_STALE")
    except (ValueError,KeyError,TypeError):
        reasons.append("QUOTE_TIMESTAMPS_INVALID")
    bid=ask=None
    try:
        bid=_amount(packet.get("bid"),zero=True)
        ask=_amount(packet.get("ask"))
        bs=_amount(packet.get("bid_size"))
        a_s=_amount(packet.get("ask_size"))
        if (bs!=bs.to_integral_value() or a_s!=a_s.to_integral_value()):
            reasons.append("QUOTE_SIZE_NOT_INTEGER")
        if ask<bid or bid<=0:
            reasons.append("CROSSED_OR_NO_TWO_SIDED_BID")
        elif (ask-bid)/((ask+bid)/2)>Decimal("0.15"):
            reasons.append("RELATIVE_SPREAD_ABOVE_15_PERCENT")
    except OrbReplayError:
        reasons.append("BID_ASK_OR_SIZE_UNQUALIFIED")
    return {
        "status":"QUOTE_REFERENCE_QUALIFIED" if not reasons else "UNQUALIFIED",
        "reasons":sorted(set(reasons)),
        "bid":str(bid) if bid is not None else None,
        "ask":str(ask) if ask is not None else None,
        "quote_timestamp_et":observed.isoformat() if observed else None,
        "quote_known_at_et":known.isoformat() if known else None,
        "source_query_id":packet.get("source_query_id"),
        "source_sha256":packet.get("source_sha256"),
    }


def _validate_exit_review_schedule(reviews, action_at):
    """Validate entire supplied chronology before modeling ANY entry or exit.

    Early profit/stop events may end the economical position, but later corrupt
    input records must not evade the source-input validation simply because a
    prior quote happened to hit a target in the development sample.
    """
    if not isinstance(reviews,list) or len(reviews)>390:
        raise OrbReplayError("V51_OPTION_REVIEW_SCOPE_INVALID")
    previous=action_at
    for index,review in enumerate(reviews):
        if not isinstance(review,dict) or not isinstance(review.get("at_et"),str):
            raise OrbReplayError("V51_EXIT_REVIEW_CLOCK_INVALID_OR_OUT_OF_ORDER")
        try:
            at=_when(review["at_et"])
        except (ValueError,TypeError,KeyError) as exc:
            raise OrbReplayError("V51_EXIT_REVIEW_CLOCK_INVALID_OR_OUT_OF_ORDER") from exc
        if (at<=previous or at.date()!=action_at.date()
                or at.time()>time(15,30)):
            raise OrbReplayError("V51_EXIT_REVIEW_CLOCK_INVALID_OR_OUT_OF_ORDER")
        previous=at


def replay_orb_quote_reference(
    input_cases:list[dict], *,
    starting_cash="25000.00", adverse_action_price_change_limit_pct="1",
    action_lag_seconds=1,
) -> dict:
    if action_lag_seconds not in (1,3) or adverse_action_price_change_limit_pct not in ("0.5","1","2"):
        raise OrbReplayError("V51_UNREGISTERED_ACTION_POLICY")
    if not isinstance(input_cases,list) or not 1<=len(input_cases)<=10000:
        raise OrbReplayError("V51_BAD_OPPORTUNITY_POPULATION")
    cash=_usd(_amount(starting_cash))
    original=cash
    events=[]
    stats=Counter()
    unresolved=None
    seen_days=set()
    cases=sorted(input_cases,key=lambda c:(c["orb_candidate"]["date_et"],c["orb_candidate"]["strategy_version"]))
    for item in cases:
        cand=item["orb_candidate"]
        if (cand.get("contract")!=ORB_CONTRACT
                or cand.get("fingerprint")!=_fingerprint({k:v for k,v in cand.items() if k!="fingerprint"})):
            raise OrbReplayError("V51_SOURCE_CANDIDATE_FINGERPRINT_INVALID")
        day=cand["date_et"]
        clock=datetime.fromisoformat(day+"T09:35:00").replace(tzinfo=EASTERN)
        evidence={
            "candidate_fingerprint":cand["fingerprint"],
            "date_et":day,"strategy_version":cand["strategy_version"],
            "source_disposition":cand["status"],
            "source_reason_codes":cand["reason_codes"],
            "opening_high":cand["opening_high"],"opening_low":cand["opening_low"],
            "first_possible_breakout_bar":cand["first_possible_breakout_bar"],
        }
        if unresolved is not None:
            status="UNRESOLVED_EARLIER_POSITION_BLOCKS_CAPITAL"
        elif day in seen_days:
            status="ONE_TRADE_PER_DAY_ALREADY_EVALUATED"
        elif cand["status"]!="POSSIBLE_FIRST_BREAKOUT_NEEDS_TICK_CONFIRMATION":
            status="NO_QUALIFIED_BREAKOUT_SOURCE"
        else:
            demand=item.get("verified_entry_demand")
            if (not isinstance(demand,dict) or demand.get("contract")!=DEMAND_CONTRACT
                    or demand.get("fingerprint")!=_fingerprint({k:v for k,v in demand.items() if k!="fingerprint"})
                    or demand.get("candidate_fingerprint")!=cand["fingerprint"]):
                status="NO_VERIFIED_FIRST_BREAKOUT_TICK_AND_EXACT_STRIKE"
            else:
                status=None
        if status is not None:
            stats[status]+=1
            events.append({"type":"DECISION","at_et":clock.isoformat(),
                           **evidence,"disposition":status,"modeled_fill":False})
            seen_days.add(day)
            continue
        seen_days.add(day)
        contract=demand["selected_original_contract"]
        expiry,strike,right=contract["expiry"],contract["strike"],contract["right"]
        identity=f"SPY:{expiry}:{strike}:{'C' if right=='call' else 'P'}"
        if expiry!=day or SERIES.fullmatch(identity) is None:
            raise OrbReplayError("V51_EXACT_0DTE_CONTRACT_INVALID")
        order_at=_when(demand["first_known_tick_et"])
        action_at=order_at+timedelta(seconds=action_lag_seconds)
        reviews=item.get("intraday_option_reviews",[])
        _validate_exit_review_schedule(reviews,action_at)
        order=_leg_quote(item.get("order_quote"),identity,order_at)
        action=_leg_quote(item.get("action_quote"),identity,action_at)
        if order["status"]!="QUOTE_REFERENCE_QUALIFIED" or action["status"]!="QUOTE_REFERENCE_QUALIFIED":
            status="ORDER_OR_ACTION_QUOTE_UNQUALIFIED"
            details={"order":order,"action":action}
        else:
            original_ask=_amount(order["ask"])
            action_ask=_amount(action["ask"])
            increase=(action_ask/original_ask-1)*100
            details={"order":order,"action":action,
                     "observed_adverse_premium_change_pct":str(max(Decimal(0),increase)),
                     "observed_absolute_premium_change_pct":str(abs(increase))}
            if increase>_amount(adverse_action_price_change_limit_pct):
                status="ADVERSE_ACTION_PRICE_CHANGE_OVER_POLICY"
            else:
                # The published $500 sizing is PREMIUM, not premium+fees.
                # Fees are charged in the cash ledger separately.
                premium_per_contract=action_ask*MULTIPLIER
                qty=int((CAP/premium_per_contract).to_integral_value(rounding=ROUND_FLOOR))
                unit_cost=_usd(premium_per_contract+FEE_PER_CONTRACT_SIDE)
                if qty<1 or unit_cost*qty>cash:
                    status="PREMIUM_CAP_OR_AVAILABLE_CASH_INSUFFICIENT"
                else:
                    status="MODELED_SINGLE_LONG_ENTRY_QUOTE_REFERENCE"
        stats[status]+=1
        events.append({
            "type":"DECISION","at_et":order_at.isoformat(),
            **evidence,"disposition":status,
            "underlying_confirmed_first_tick_et":demand["first_verified_tick_et"],
            "original_contract_identity":identity,
            "quote_diagnostics":details,
            "modeled_fill":False,
        })
        if status!="MODELED_SINGLE_LONG_ENTRY_QUOTE_REFERENCE":
            continue
        debit=unit_cost*qty
        before=cash
        cash=_usd(cash-debit)
        events.append({"type":"MODELED_ENTRY_QUOTE_REFERENCE",
                       "at_et":action_at.isoformat(),
                       "opportunity_id":f"{day}:{identity}",
                       "qty":qty,"unit_reference_ask":str(action_ask),
                       "entry_debit_and_fees":str(debit),
                       "cash_before":str(before),"cash_after":str(cash),
                       "actual_broker_fill":False})
        exit_complete=False
        failed_path=False
        last_observed=action_at
        last_review=None
        for rr in reviews:
            at=_when(rr["at_et"])
            if at<=last_observed or at.date()!=action_at.date() or at.time()>time(15,30):
                raise OrbReplayError("V51_EXIT_REVIEW_CLOCK_INVALID_OR_OUT_OF_ORDER")
            gap_seconds=(at-last_observed).total_seconds()
            q=_leg_quote(rr.get("quote"),identity,at)
            bid=_amount(q["bid"]) if q["status"]=="QUOTE_REFERENCE_QUALIFIED" else None
            gross=bid*MULTIPLIER*qty if bid is not None else None
            net=_usd(gross-FEE_PER_CONTRACT_SIDE*qty) if gross is not None else None
            gross_option_change=(bid/action_ask-1)*100 if bid is not None else None
            gain=(net/debit-1)*100 if net is not None else None
            trigger=("TIME_15:30" if at.time()==time(15,30) else
                     "PROFIT_PLUS_100" if gross_option_change is not None and gross_option_change>=100 else
                     "STOP_MINUS_50" if gross_option_change is not None and gross_option_change<=-50 else "HOLD")
            if gap_seconds>60:
                failed_path=True
            events.append({"type":"EXIT_REVIEW","at_et":at.isoformat(),
                           "opportunity_id":f"{day}:{identity}",
                           "quote_diagnostics":q,
                           "observed_option_bid_vs_entry_ask_pct":str(gross_option_change) if gross_option_change is not None else None,
                           "reference_net_after_fee_return_pct":str(gain) if gain is not None else None,
                           "observation_gap_seconds":gap_seconds,
                           "intrabar_trigger_order_independently_proven":False,
                           "trigger":trigger,"missing_path_censored":failed_path,
                           "actual_fill":False})
            last_observed=at
            last_review=at
            if failed_path or q["status"]!="QUOTE_REFERENCE_QUALIFIED":
                # A later apparently better price cannot retroactively
                # resolve missing/unknown path or an earlier unqualified stop.
                break
            if trigger!="HOLD":
                before=cash
                cash=_usd(cash+net)
                events.append({"type":"MODELED_EXIT_QUOTE_REFERENCE",
                               "at_et":at.isoformat(),
                               "opportunity_id":f"{day}:{identity}",
                               "exit_reason":trigger,
                               "reference_liquidation_credit":str(net),
                               "modeled_closed_pnl":str(_usd(net-debit)),
                               "cash_before":str(before),"cash_after":str(cash),
                               "actual_broker_fill":False})
                exit_complete=True
                break
        if not exit_complete:
            unresolved={"date_et":day,"identity":identity,"qty":qty,
                        "entry_debit":str(debit),
                        "reason":"UNCERTIFIED_OBSERVATION_PATH_OR_MISSING_15:30_LIQUIDATION",
                        "last_review_at":last_review.isoformat() if last_review else None}
            events.append({"type":"OPEN_UNRESOLVED","at_et":last_review.isoformat() if last_review else action_at.isoformat(),
                           "opportunity_id":f"{day}:{identity}","unresolved":unresolved,
                           "mark_and_equity":None})
    report={
        "contract":CONTRACT,"status":"OFFLINE_DEVELOPMENT_QUOTE_REFERENCE_NOT_VERIFIED_LIVE_EXECUTION",
        "starting_cash":str(original),"last_cash_excludes_unresolved_mark":str(cash),
        "terminal_equity_if_complete":str(cash) if unresolved is None else None,
        "unresolved_position":unresolved,
        "opportunity_count":len(input_cases),
        "disposition_counts":dict(sorted(stats.items())),
        "policy":{"original_premium_cap_usd":str(CAP),
                  "profit_target_pct":"100","stop_pct":"-50",
                  "time_exit_et":"15:30","action_lag_seconds":action_lag_seconds,
                  "max_adverse_price_change_pct":adverse_action_price_change_limit_pct},
        "events":events,
        "broker_fills_verified":0,"provider_requests":0,
        "original_published_0dte_pnl_verified":False,
        "invalid_or_missing_quotes_never_substituted":True,
        "2018_2025_and_2026_historical_outcomes_are_not_fresh_holdout":True,
    }
    report["fingerprint"]=_fingerprint(report)
    return report
