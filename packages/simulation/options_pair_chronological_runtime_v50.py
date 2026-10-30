from __future__ import annotations

"""V50 chronological options-pair quote-reference SIMULATOR (not verified trades).

Source and decision adapters must supply independent, as-of, original-contract
quotes. Nothing is fetched, no broker order is placed, and a quote is NEVER a
verified fill. Every opportunity and every evaluated exit emits an event.
"""

from collections import Counter
from datetime import datetime, date
import re
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from packages.simulation.options_opportunity_trace_v49 import (
    PRICE_DRIFT_PCT, SKEW_SECONDS, execution_action_diagnostic, fingerprint,
)

CONTRACT = "atlas-chronological-long-options-pair-quote-reference-simulator-v50"
MULTIPLIER = Decimal("100")
FEE_PER_LEG_SIDE = Decimal("0.65")
VALID_SIGNAL = {"ENTER_LONG_PAIR", "ABSTAIN", "REJECT"}
MAX_CASES = 200000
MAX_REVIEWS = 10
MAX_SOURCE_AGE_SECONDS = Decimal("30")
EASTERN = ZoneInfo("America/New_York")
SERIES = re.compile(r"^([A-Z]{1,8}):(\d{4}-\d{2}-\d{2}):(\d+(?:\.\d+)?):([CP])$")


class PairReplayError(ValueError):
    pass


def _time(raw: Any) -> datetime:
    try:
        d = datetime.fromisoformat(raw)
    except (ValueError, TypeError) as exc:
        raise PairReplayError("V50_TIMESTAMP_INVALID") from exc
    if d.utcoffset() is None:
        raise PairReplayError("V50_TIMESTAMP_NAIVE")
    return d


def _dec(raw: Any, *, positive: bool = False) -> Decimal:
    try:
        d = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PairReplayError("V50_INVALID_DECIMAL") from exc
    if not d.is_finite() or (positive and d <= 0):
        raise PairReplayError("V50_NONFINITE_OR_NONPOSITIVE")
    return d


def _series(identity: str) -> tuple[str, date, Decimal, str]:
    match = SERIES.fullmatch(identity) if isinstance(identity,str) else None
    if match is None:
        raise PairReplayError("V50_ORIGINAL_OPTION_SERIES_FORMAT_INVALID")
    try:
        expiry=date.fromisoformat(match.group(2))
    except ValueError as exc:
        raise PairReplayError("V50_ORIGINAL_OPTION_EXPIRATION_INVALID") from exc
    strike=_dec(match.group(3),positive=True)
    return match.group(1),expiry,strike,match.group(4)


def _money(raw: Decimal) -> Decimal:
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quote_leg(
    packet: Any, identity: str, at: datetime, right: str,
) -> tuple[dict, tuple[str, ...]]:
    reasons: list[str] = []
    if not isinstance(packet, dict):
        return {}, (f"{right}_MISSING_QUOTE",)
    if packet.get("contract_identity") != identity:
        reasons.append(f"{right}_CONTRACT_IDENTITY_MISMATCH")
    if not packet.get("source_query_id") or not packet.get("source_sha256"):
        reasons.append(f"{right}_SOURCE_PROVENANCE_MISSING")
    observed = available = None
    try:
        observed = _time(packet.get("timestamp_et"))
        available = _time(packet.get("available_at_utc"))
    except PairReplayError:
        reasons.append(f"{right}_QUOTE_CLOCK_UNQUALIFIED")
    age = None
    if observed is not None and available is not None:
        age = _dec((at - observed).total_seconds())
        if observed > at or available > at or observed > available or age < 0 or age > MAX_SOURCE_AGE_SECONDS:
            reasons.append(f"{right}_QUOTE_FUTURE_STALE_OR_NOT_ASOF")
    bid = ask = bid_size = ask_size = None
    try:
        bid = _dec(packet.get("bid"), positive=True)
        ask = _dec(packet.get("ask"), positive=True)
        bid_size = _dec(packet.get("bid_size"), positive=True)
        ask_size = _dec(packet.get("ask_size"), positive=True)
    except PairReplayError:
        reasons.append(f"{right}_BID_ASK_OR_SIZE_MISSING")
    relative_spread = None
    if bid is not None and ask is not None:
        if ask < bid:
            reasons.append(f"{right}_CROSSED_MARKET")
        else:
            relative_spread = (ask-bid)/((ask+bid)/2)
            if relative_spread > Decimal("0.15"):
                reasons.append(f"{right}_SPREAD_OVER_15_PERCENT")
    if bid_size is not None and bid_size != bid_size.to_integral_value():
        reasons.append(f"{right}_BID_SIZE_NOT_INTEGER")
    if ask_size is not None and ask_size != ask_size.to_integral_value():
        reasons.append(f"{right}_ASK_SIZE_NOT_INTEGER")
    return {
        "identity": identity, "bid": str(bid) if bid is not None else None,
        "ask": str(ask) if ask is not None else None,
        "bid_size": str(bid_size) if bid_size is not None else None,
        "ask_size": str(ask_size) if ask_size is not None else None,
        "quote_timestamp_et": observed.isoformat() if observed else None,
        "quote_available_at_utc": available.isoformat() if available else None,
        "quote_age_seconds": float(age) if age is not None else None,
        "relative_spread": float(relative_spread) if relative_spread is not None else None,
        "source_query_id": packet.get("source_query_id"),
        "source_sha256": packet.get("source_sha256"),
    }, tuple(sorted(set(reasons)))


def _paired_quote(pair: Any, *, call: str, put: str, at: datetime, max_skew: int) -> dict:
    if not isinstance(pair, dict):
        return {"status":"PAIR_QUOTE_MISSING", "reason_codes":["PAIRED_SOURCE_MISSING"],
                "per_leg":{}, "pair_skew_seconds":None, "ask":None,"bid":None}
    legs = {}
    reasons = []
    for right, identity in (("CALL",call),("PUT",put)):
        detail, problems = _quote_leg(pair.get(right.lower()), identity, at, right)
        legs[right.lower()] = detail
        reasons.extend(problems)
    ts = [legs[r].get("quote_timestamp_et") for r in ("call","put")]
    skew = abs((_time(ts[0])-_time(ts[1])).total_seconds()) if all(ts) else None
    if skew is None:
        reasons.append("PAIR_QUOTE_TIMESTAMP_MISSING")
    elif skew > max_skew:
        reasons.append("PAIR_SKEW_OVER_POLICY")
    passed = not reasons
    return {
        "status": "PAIRED_QUALIFIED_QUOTE_REFERENCE" if passed else "PAIR_QUOTE_UNQUALIFIED",
        "reason_codes": sorted(set(reasons)), "per_leg":legs,
        "pair_skew_seconds": skew,
        "ask": str(sum((_dec(legs[r]["ask"]) for r in ("call","put")),Decimal(0))) if passed else None,
        "bid": str(sum((_dec(legs[r]["bid"]) for r in ("call","put")),Decimal(0))) if passed else None,
    }


def _case_check(cases: list[dict]) -> list[dict]:
    if not isinstance(cases,list) or not 1<=len(cases)<=MAX_CASES:
        raise PairReplayError("V50_CASE_COUNT_INVALID")
    ids=set()
    ordered=sorted(cases,key=lambda c:(_time(c["signal_at_utc"]),c["opportunity_id"]))
    for case in ordered:
        cid=case.get("opportunity_id")
        if not isinstance(cid,str) or not cid or cid in ids:
            raise PairReplayError("V50_DUPLICATE_OR_INVALID_CASE_ID")
        ids.add(cid)
        signal_at=_time(case["signal_at_utc"])
        if case.get("signal_status") not in VALID_SIGNAL:
            raise PairReplayError("V50_UNKNOWN_SIGNAL_STATE")
        for key in ("call_identity","put_identity","strategy_version"):
            if not isinstance(case.get(key),str) or not case[key]:
                raise PairReplayError("V50_MISSING_STRATEGY_OR_ORIGINAL_CONTRACT")
        call_series=_series(case["call_identity"])
        put_series=_series(case["put_identity"])
        if (call_series[:3]!=put_series[:3] or
                call_series[3]!="C" or put_series[3]!="P"):
            raise PairReplayError("V50_CALL_PUT_UNDERLYING_EXPIRY_STRIKE_OR_RIGHT_MISMATCH")
        if signal_at.astimezone(EASTERN).date()>call_series[1]:
            raise PairReplayError("V50_ENTRY_AFTER_ORIGINAL_OPTION_EXPIRATION")
        if case["signal_status"]=="ENTER_LONG_PAIR":
            order_at=_time(case["order_at_utc"])
            action_at=_time(case["action_at_utc"])
            if not signal_at < order_at <= action_at or (action_at-order_at).total_seconds()>3:
                raise PairReplayError("V50_DECISION_ORDER_ACTION_CLOCK_INVALID")
        reviews=case.get("exit_reviews",[])
        if not isinstance(reviews,list) or len(reviews)>MAX_REVIEWS:
            raise PairReplayError("V50_REVIEW_SCOPE_INVALID")
        before=signal_at
        previous_hold=0
        for review in reviews:
            at=_time(review["review_at_utc"])
            hold=review.get("hold_sessions")
            if at<=before or type(hold) is not int or not previous_hold<hold<=MAX_REVIEWS:
                raise PairReplayError("V50_EXIT_REVIEW_SEQUENCE_OR_HOLD_INVALID")
            before=at
            previous_hold=hold
    return ordered


def _closed_trade_periods(events: list[dict], *, account_incomplete: bool) -> dict:
    """Closed modeled quote-reference sales only; no invented open-position P&L."""
    cohorts={"week":{},"month":{},"year":{}}
    completed=[]
    for event in events:
        if event["event_type"]!="MODELED_EXIT_QUOTE_REFERENCE":
            continue
        pnl=_dec(event["modeled_realized_pnl"])
        at=_time(event["at_utc"]).astimezone(EASTERN)
        iso=at.isocalendar()
        date_keys={
            "week":f"{iso.year:04d}-W{iso.week:02d}",
            "month":f"{at.year:04d}-{at.month:02d}",
            "year":f"{at.year:04d}",
        }
        completed.append({
            "opportunity_id":event["opportunity_id"],
            "exit_date_et":at.date().isoformat(),
            "exit_reason":event["cause"],
            "net_reference_pnl_dollars":str(_money(pnl)),
            "reference_cash_after":event["cash_after"],
            "proven_broker_fill":False,
        })
        for unit,key in date_keys.items():
            d=cohorts[unit].setdefault(key,{"closed":0,"wins":0,"losses":0,
                                           "breakeven":0,"net":Decimal("0")})
            d["closed"]+=1
            d["net"]+=pnl
            d["wins"]+=int(pnl>0)
            d["losses"]+=int(pnl<0)
            d["breakeven"]+=int(pnl==0)
    for unit in cohorts:
        cohorts[unit]=[
            {"period":key,"closed_reference_pairs":v["closed"],
             "winning_reference_pairs":v["wins"],
             "losing_reference_pairs":v["losses"],
             "breakeven_reference_pairs":v["breakeven"],
             "modeled_net_reference_pnl_dollars":str(_money(v["net"])),
             "whole_account_economic_window_proven":False}
            for key,v in sorted(cohorts[unit].items())
        ]
    return {
        "status":"CLOSED_QUOTE_REFERENCE_PERIODS_NOT_VALIDATED_STRATEGY_PNL",
        "account_terminal_unresolved":account_incomplete,
        "closed_trades":completed,
        "weekly":cohorts["week"],"monthly":cohorts["month"],
        "annual":cohorts["year"],
        "unfinished_positions_excluded_from_realized_summary":True,
    }


def replay_pairs(
    cases: list[dict], *,
    starting_cash: str = "100000.00",
    cash_risk_fraction: str = "0.05",
    profit_target_pct: str = "20",
    stop_loss_pct: str = "-10",
    maximum_hold_reviews: int = 5,
    pair_skew_seconds: int = 1,
    maximum_adverse_action_drift_pct: str = "1",
) -> dict:
    """One-position sequential model, conservative missing quote/mark handling.

    Thresholds are explicit hypotheses (NOT empirically validated). Exit at
    independently observed same-contract future bids when profit/stop/max-hold
    fires; when a required source is missing, the position remains unresolved.
    """
    if (pair_skew_seconds not in SKEW_SECONDS or maximum_hold_reviews not in range(1,MAX_REVIEWS+1)
            or _dec(maximum_adverse_action_drift_pct) not in PRICE_DRIFT_PCT):
        raise PairReplayError("V50_UNREGISTERED_TIMING_OR_EXIT_POLICY")
    cash=_money(_dec(starting_cash,positive=True))
    initial=cash
    fraction=_dec(cash_risk_fraction,positive=True)
    if fraction>1:
        raise PairReplayError("V50_CASH_RISK_FRACTION_OVER_ONE")
    target=_dec(profit_target_pct)
    stop=_dec(stop_loss_pct)
    if target <= 0 or stop >= 0 or stop <= -100:
        raise PairReplayError("V50_PROFIT_STOP_POLICY_INVALID")
    records=_case_check(cases)
    events: list[dict] = []
    counts: Counter[str] = Counter()
    opened=None
    review_index=0

    def record(typ: str, case_id: str, at: datetime, **fields: Any):
        seq=len(events)
        event={"seq":seq,"event_type":typ,"opportunity_id":case_id,
               "at_utc":at.isoformat(),**fields}
        events.append(event)
        if typ=="OPPORTUNITY_DECISION":
            counts[fields["disposition"]]+=1

    def process_reviews(until: datetime | None):
        nonlocal opened,cash,review_index
        if opened is None:
            return
        reviews=opened["reviews"]
        while opened is not None and review_index < len(reviews):
            review=reviews[review_index]
            at=_time(review["review_at_utc"])
            if until is not None and at > until:
                return
            review_index+=1
            q=_paired_quote(review.get("quote_pair"),
                call=opened["call"],put=opened["put"],at=at,max_skew=pair_skew_seconds)
            if at.astimezone(EASTERN).date()>opened["expiry"]:
                q["status"]="PAIR_QUOTE_UNQUALIFIED_EXPIRED"
                q["reason_codes"]=sorted(set(q["reason_codes"]+[
                    "POST_EXPIRY_ASSIGNMENT_OR_EXERCISE_EVIDENCE_REQUIRED"]))
                q["ask"]=None
                q["bid"]=None
            pct=None
            reasons=list(q["reason_codes"])
            if q["status"]=="PAIRED_QUALIFIED_QUOTE_REFERENCE":
                net_exit=_money(_dec(q["bid"])*MULTIPLIER-2*FEE_PER_LEG_SIDE)
                pct=(_dec((net_exit-opened["entry_debit"])/opened["entry_debit"])*100)
            else:
                net_exit=None
            hit_profit=pct is not None and pct>=target
            hit_stop=pct is not None and pct<=stop
            hit_time=review["hold_sessions"]>=maximum_hold_reviews
            trigger= ("PROFIT_TARGET" if hit_profit else "STOP_LOSS" if hit_stop
                      else "MAXIMUM_HOLD" if hit_time else "HOLD_CONTINUES")
            record("EXIT_REVIEW",opened["id"],at,
                   hold_sessions=review["hold_sessions"],
                   evaluation_clock=review["review_at_utc"],
                   original_contracts={"call":opened["call"],"put":opened["put"]},
                   quote_observations=q, cash_before=str(cash),
                   entry_debit=str(opened["entry_debit"]),
                   modeled_exit_return_pct=float(pct) if pct is not None else None,
                   profit_target_pct=float(target),stop_loss_pct=float(stop),
                   trigger=trigger,
                   review_reason_codes=reasons,
                   journal_never_implies_fill=True)
            if trigger!="HOLD_CONTINUES":
                if net_exit is None:
                    record("EXIT_UNRESOLVED",opened["id"],at,
                        trigger=trigger,
                        reason_codes=["EXIT_TRIGGERED_BUT_NO_EXECUTABLE_QUOTE_REFERENCE",*reasons],
                        accounted_position_value=None)
                    continue
                prior=cash
                cash=_money(cash+net_exit)
                record("MODELED_EXIT_QUOTE_REFERENCE",opened["id"],at,
                       cause=trigger, pair_bid_per_share=q["bid"],
                       exit_credit_less_fees=str(net_exit),
                       modeled_realized_pnl=str(net_exit-opened["entry_debit"]),
                       cash_before=str(prior),cash_after=str(cash),
                       actual_fill=False, same_day_quote_reference_cash_not_settlement=True)
                opened=None
                review_index=0
                return

    for c in records:
        cid=c["opportunity_id"]
        at=_time(c["signal_at_utc"])
        process_reviews(at)
        common={
            "strategy_version":c["strategy_version"],
            "signal_status":c["signal_status"],
            "reason_codes":list(c.get("reason_codes",[])),
            "source_context":c.get("source_context",{}),
            "feature_available_at_utc":c.get("feature_available_at_utc"),
            "original_contracts":{"call":c["call_identity"],"put":c["put_identity"]},
            "cash_before":str(cash),
            "open_position_id":opened["id"] if opened else None,
        }
        if c["signal_status"]!="ENTER_LONG_PAIR":
            record("OPPORTUNITY_DECISION",cid,at,
                disposition="ABSTAIN_OR_REJECT_SIGNAL",**common)
            continue
        if opened is not None:
            record("OPPORTUNITY_DECISION",cid,at,
                disposition="OCCUPIED_OPEN_PAIR_SLOT",**common)
            continue
        available_raw=c.get("feature_available_at_utc")
        feature_asof=None
        try:
            feature_asof=_time(available_raw)
        except PairReplayError:
            pass
        if (not c.get("causal_signal_evidence_verified",False)
                or feature_asof is None or feature_asof>at):
            record("OPPORTUNITY_DECISION",cid,at,
                disposition="CAUSAL_SIGNAL_INPUT_NOT_QUALIFIED",**common)
            continue
        order_at=_time(c["order_at_utc"])
        action_at=_time(c["action_at_utc"])
        order_pair=c.get("order_quote_pair")
        action_pair=c.get("action_quote_pair")
        order_q=_paired_quote(order_pair,call=c["call_identity"],put=c["put_identity"],
                              at=order_at,max_skew=pair_skew_seconds)
        action_q=_paired_quote(action_pair,call=c["call_identity"],put=c["put_identity"],
                               at=action_at,max_skew=pair_skew_seconds)
        if order_q["ask"] is None or action_q["ask"] is None:
            record("OPPORTUNITY_DECISION",cid,at,disposition="ORDER_OR_ACTION_SOURCE_UNQUALIFIED",
                   order_quote_observation=order_q,action_quote_observation=action_q,**common)
            continue
        # Reuse V49 independent delayed-action diagnostic. The action quote
        # is observed at the action clock; neither a real order nor a fill.
        try:
            latency=execution_action_diagnostic(
                order_pair,action_pair,order_at=order_at.isoformat(),
                action_at=action_at.isoformat(),max_skew_seconds=pair_skew_seconds,
                max_adverse_pair_cost_change_pct=maximum_adverse_action_drift_pct)
        except (ValueError,KeyError,TypeError) as exc:
            raise PairReplayError("V50_ACTION_QUOTE_DIAGNOSTIC_INVALID") from exc
        if latency["status"]!="COUNTERFACTUAL_QUOTE_GATES_PASS_NO_FILL":
            record("OPPORTUNITY_DECISION",cid,at,disposition="LATENCY_OR_PRICE_DRIFT_UNQUALIFIED",
                   order_quote_observation=order_q,action_quote_observation=action_q,
                   action_latency_diagnostic=latency,**common)
            continue
        debit=_money(_dec(action_q["ask"])*MULTIPLIER+2*FEE_PER_LEG_SIDE)
        cap=_money(cash*fraction)
        if debit>cap:
            record("OPPORTUNITY_DECISION",cid,at,disposition="RISK_BUDGET_REJECT",
                   reference_entry_debit=str(debit),current_risk_cap=str(cap),
                   action_latency_diagnostic=latency,**common)
            continue
        record("OPPORTUNITY_DECISION",cid,at,disposition="QUOTE_REFERENCE_ENTRY_ELIGIBLE",
               reference_entry_debit=str(debit),current_risk_cap=str(cap),
               order_quote_observation=order_q,action_quote_observation=action_q,
               action_latency_diagnostic=latency,**common)
        before=cash
        cash=_money(cash-debit)
        record("MODELED_ENTRY_QUOTE_REFERENCE",cid,action_at,
               assumed_entry_ask_pair_per_share=action_q["ask"],
               entry_debit_including_fees=str(debit),
               cash_before=str(before),cash_after=str(cash),
               original_contracts={"call":c["call_identity"],"put":c["put_identity"]},
               actual_fill=False,broker_order_id=None,
               independent_broker_execution_verified=False)
        opened={"id":cid,"call":c["call_identity"],"put":c["put_identity"],
                "expiry":_series(c["call_identity"])[1],
                "entry_debit":debit,"reviews":c.get("exit_reviews",[])}
        review_index=0
    process_reviews(None)
    missing_review=opened is not None
    if missing_review:
        record("OPEN_POSITION_UNRESOLVED",opened["id"],
               _time(opened["reviews"][-1]["review_at_utc"])
               if opened["reviews"] else _time(records[-1]["signal_at_utc"]),
               reason_codes=["NO_QUALIFIED_EXIT_OR_SETTLEMENT_PROOF"],
               pending_original_contracts={"call":opened["call"],"put":opened["put"]},
               assumed_entry_debit=str(opened["entry_debit"]),
               account_equity=None)
    # Cash excludes the open option's unknown mark. It must not be passed off
    # as terminal equity or a completed trade.
    result={
        "contract":CONTRACT,
        "status":"HYPOTHETICAL_QUOTE_REFERENCE_SIMULATOR_NOT_A_HISTORICAL_FILL_BACKTEST",
        "initial_cash":str(initial),
        "terminal_cash_excluding_unmarked_exposure":str(cash),
        "terminal_equity_if_fully_resolved":str(cash) if not missing_review else None,
        "open_unresolved_position_id":opened["id"] if opened else None,
        "cash_risk_fraction":str(fraction),
        "policy":{"max_quote_skew_seconds":pair_skew_seconds,
                  "max_adverse_action_drift_pct":maximum_adverse_action_drift_pct,
                  "profit_target_pct":str(target),"stop_loss_pct":str(stop),
                  "maximum_hold_reviews":maximum_hold_reviews,
                  "source_age_seconds":str(MAX_SOURCE_AGE_SECONDS)},
        "opportunities_evaluated":len(records),
        "opportunity_dispositions":dict(sorted(counts.items())),
        "modeled_quote_reference_entries":sum(e["event_type"]=="MODELED_ENTRY_QUOTE_REFERENCE" for e in events),
        "modeled_quote_reference_exits":sum(e["event_type"]=="MODELED_EXIT_QUOTE_REFERENCE" for e in events),
        "reference_realized_periods":_closed_trade_periods(events,account_incomplete=missing_review),
        "events":events,
        "broker_orders_or_fills":0,"provider_requests":0,
        "strategy_pnl_validated":False,
        "original_quote_policy_auto_tuned_using_outcomes":False,
    }
    result["fingerprint"]=fingerprint(result)
    return result
