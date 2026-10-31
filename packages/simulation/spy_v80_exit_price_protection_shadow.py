from __future__ import annotations

"""V80 post-trade, original-quote-only options exit order-price protection.

This does NOT simulate fills: no venue queue/ack, cancel/replace, broker order,
partial fills, or overnight exercise is inferred from quote snapshots.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT="atlas-v80-option-exit-original-quote-action-price-protection-v1"
ALLOWED_BROKERS=("webull","alpaca")
BANDS=("0","0.5","1","2")
CENT=Decimal(".01")


class V80Error(ValueError):
    pass


def _signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def _verified(doc):
    return isinstance(doc,dict) and doc.get("fingerprint")==_fingerprint(
        {k:v for k,v in doc.items() if k!="fingerprint"})


def _price(v):
    try:
        x=Decimal(str(v))
    except (ValueError,InvalidOperation,TypeError) as exc:
        raise V80Error("V80_INVALID_ORIGINAL_PRICE") from exc
    if not x.is_finite() or x<=0:
        raise V80Error("V80_NONPOSITIVE_OR_NONFINITE_QUOTE")
    return x.quantize(CENT,rounding=ROUND_HALF_UP)


def evaluate(report,*,broker="webull",max_adverse_pct="1"):
    """Classify an original V76 exit quote without treating it as a fill.

    The trigger price acts as an initial SELL_TO_CLOSE limit reference.
    A later bid below that limit means the original order is NOT immediately
    marketable. An explicitly allowed price concession still requires a
    fresh order decision, broker action and reconciliation before booking cash.
    """
    if broker not in ALLOWED_BROKERS or max_adverse_pct not in BANDS:
        raise V80Error("V80_UNREGISTERED_ORDER_POLICY")
    if not _verified(report) or report.get("contract")!=(
            "atlas-v76-preregistered-multi-exit-causal-quote-research-v1"):
        raise V80Error("V80_ORIGINAL_EXIT_REPORT_INVALID")
    original=report.get("v74_inner_quote_shadow_report")
    if not _verified(original) or original.get("fingerprint") is None:
        raise V80Error("V80_V74_INNER_ORIGINAL_SIGNATURE_INVALID")
    if (report.get("broker_orders")!=0 or report.get("provider_calls")!=0 or
            original.get("actual_broker_fills")!=0 or
            original.get("provider_requests")!=0 or
            original.get("parent_v65_sha")!=report.get("parent_v65_sha") or
            original.get("original_option_archive_sha256")!=report.get("original_source_sha256") or
            original.get("status")!=report.get("status") or
            original.get("trade_net_pnl")!=report.get("trade_net_pnl")):
        raise V80Error("V80_PARENT_CHAIN_OR_NO_FILL_CONTRACT_CHANGED")
    events=original.get("events")
    if not isinstance(events,list):
        raise V80Error("V80_ORIGINAL_EVENTS_REQUIRED")
    entries=[e for e in events if e.get("type")=="ORIGINAL_ENTRY_REUSED"]
    intents=[e for e in events if e.get("type")=="EXIT_INTENT"]
    closes=[e for e in events if e.get("type")=="MODELED_SELL_TO_CLOSE_BID_REFERENCE"]
    if len(entries)!=1 or len(intents)>1 or len(closes)>1:
        raise V80Error("V80_AMBIGUOUS_ORIGINAL_ORDER_LIFECYCLE")
    qty=entries[0].get("qty")
    if type(qty) is not int or qty<=0:
        raise V80Error("V80_INVALID_ORIGINAL_QUANTITY")
    result={
        "contract":CONTRACT,"session":report["session"],
        "source_immutable_event_sha":report["fingerprint"],
        "parent_v65_sha":report["parent_v65_sha"],
        "original_option_archive_sha256":report["original_source_sha256"],
        "original_policy":report["policy"],"original_lag_seconds":report["lag_seconds"],
        "execution_broker_research_label":broker,
        "allowed_adverse_quote_concession_pct":max_adverse_pct,
        "selected_contract":original.get("selected_contract"),
        "side":"SELL_TO_CLOSE","order_type_research":"DAY_LIMIT",
        "quantity":qty,
        "original_quote_reference_pnl":report.get("trade_net_pnl"),
        "original_status":report["status"],
        "actual_broker_order_submitted":False,
        "actual_broker_ack":False,
        "actual_broker_fills":0,
        "credited_cash_from_shadow":None,
        "live_option_execution_not_enabled":True,
        "automatic_broker_failover":False,
        "broker_expiry_exercise_outcome_unknown":True,
        "original_quote_source_reused_no_provider_calls":True,
    }
    if report["status"]=="UNRESOLVED_POSITION":
        if closes:
            raise V80Error("V80_UNRESOLVED_WITH_MODELED_CLOSE")
        return _signed({
            **result,"status":"ORIGINAL_EXIT_UNRESOLVED_NO_CASH",
            "trigger_at_et":intents[0]["trigger_at_et"] if intents else None,
            "action_at_et":None,
            "requires_manual_source_and_order_state_review":True,
        })
    if report["status"]!="CLOSED_QUOTE_REFERENCE" or len(intents)!=1 or len(closes)!=1:
        raise V80Error("V80_UNSUPPORTED_ENTRY_ORIGINAL_DISPOSITION")
    intent=intents[0]
    action=closes[0]
    try:
        trigger_time=datetime.fromisoformat(intent["trigger_at_et"])
        action_time=datetime.fromisoformat(action["at_et"])
    except (KeyError,TypeError,ValueError) as exc:
        raise V80Error("V80_INVALID_CAUSAL_ORDER_TIMESTAMPS") from exc
    if (trigger_time.utcoffset() is None or action_time.utcoffset() is None
            or action_time<=trigger_time or
            (action_time-trigger_time).total_seconds()<report["lag_seconds"] or
            qty!=action.get("qty") or
            type(action.get("observed_bid_size")) is not int or
            action["observed_bid_size"]<qty or
            action.get("actual_broker_fill") is not False or
            action.get("limit_order_fill_guaranteed") is not False):
        raise V80Error("V80_ORIGINAL_ACTION_SIDE_NOT_CAUSAL_OR_QUALIFIED")
    trigger_bid=_price(intent["reference_bid"])
    action_bid=_price(action["observed_bid"])
    adverse=max(Decimal(0),(trigger_bid-action_bid)/trigger_bid*100)
    original_limit_marketable=action_bid>=trigger_bid
    within_band=adverse<=Decimal(max_adverse_pct)
    status=("ORIGINAL_TRIGGER_LIMIT_MARKETABLE_QUOTE_ONLY"
            if original_limit_marketable else
            "ADVERSE_REPRICE_ALLOWED_NOT_EXECUTED"
            if within_band else "ADVERSE_DRIFT_OUTSIDE_PRICE_PROTECTION")
    return _signed({
        **result,"status":status,
        "trigger_at_et":trigger_time.isoformat(),
        "action_at_et":action_time.isoformat(),
        "trigger_bid":str(trigger_bid),
        "action_bid":str(action_bid),
        "action_quote_displayed_size":action["observed_bid_size"],
        "original_trigger_limit_marketable_at_action_quote":original_limit_marketable,
        "adverse_bid_drift_pct":str(adverse.quantize(Decimal(".0001"),
                                                    rounding=ROUND_HALF_UP)),
        "within_registered_price_concession_band":within_band,
        "fresh_broker_acknowledgment_needed":True,
        "historical_limit_fill_not_proven":True,
        "new_price_decision_must_use_fresh_quote":not original_limit_marketable,
        "historical_action_quote_does_not_include_order_queue_or_depth":True,
    })
