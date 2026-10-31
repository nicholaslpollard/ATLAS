from __future__ import annotations

"""V81 original-evidence-bound, broker-neutral OPTIONS order lifecycle fixture.

This is a deterministic *synthetic* broker-receipt state machine for simulator
acceptance, not an adapter, execution authorization, source getter, or proof
that any historical quote would fill. Real settled account cash stays unknown.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT="atlas-v81-broker-neutral-options-order-lifecycle-synthetic-fixture-v1"
ORIGIN="SYNTHETIC_ORDER_FIXTURE_ONLY"
BROKERS=("webull","alpaca")
EVENTS=frozenset({
    "QUOTE_OBSERVED","SUBMIT_REQUESTED","BROKER_ACK","PARTIAL_FILL",
    "FINAL_FILL","CANCEL_REQUESTED","CANCEL_ACK",
    "BROKER_REJECT","BROKER_TIMEOUT","BROKER_RECONCILIATION",
})
FINAL=frozenset({"FILLED","CANCELLED","REJECTED","RECONCILED_FINAL"})
CENT=Decimal("0.01")


class V81Error(ValueError):
    pass


def _dec(value: Any,*, positive=True)->Decimal:
    try:
        d=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError) as exc:
        raise V81Error("V81_FINANCIAL_NUMBER_INVALID") from exc
    if not d.is_finite() or (positive and d<=0) or (not positive and d<0):
        raise V81Error("V81_FINANCIAL_NUMBER_OUT_OF_RANGE")
    return d


def _clock(value:Any)->datetime:
    try:
        d=datetime.fromisoformat(value) if isinstance(value,str) else value
    except (ValueError,TypeError) as exc:
        raise V81Error("V81_EVENT_CLOCK_INVALID") from exc
    if not isinstance(d,datetime) or d.utcoffset() is None:
        raise V81Error("V81_EVENT_CLOCK_NAIVE")
    return d


def _signed(payload:dict)->dict:
    return {**payload,"fingerprint":_fingerprint(payload)}


def _valid_signed(payload:Any)->bool:
    return isinstance(payload,dict) and payload.get("fingerprint")==_fingerprint({
        k:v for k,v in payload.items() if k!="fingerprint"
    })


def _require_identity(intent:dict)->None:
    if (not _valid_signed(intent) or
            intent.get("contract")!="atlas-v81-option-sell-to-close-intent-v1" or
            intent.get("origin")!=ORIGIN or
            intent.get("broker") not in BROKERS or
            intent.get("side")!="SELL_TO_CLOSE" or
            intent.get("order_type")!="LIMIT" or
            intent.get("time_in_force")!="DAY" or
            type(intent.get("quantity")) is not int or intent["quantity"]<=0 or
            type(intent.get("client_order_id")) is not str or
            not intent["client_order_id"].strip() or
            type(intent.get("option_contract")) is not dict or
            not intent["option_contract"].get("symbol") or
            not intent.get("original_quote_event_sha")):
        raise V81Error("V81_SIGNED_SYNTHETIC_INTENT_INVALID")
    _dec(intent["limit_price"])
    _dec(intent["per_contract_exit_fee"],positive=False)
    if _clock(intent["expires_at_et"])<=_clock(intent["created_at_et"]):
        raise V81Error("V81_INVALID_ORDER_EXPIRY")
    if (not isinstance(intent.get("source_policy"),str) or
            intent["source_policy"]!="SIGNED_ORIGINAL_OPTION_TAPE_RESEARCH_ONLY"):
        raise V81Error("V81_ORIGINAL_SOURCE_BINDING_MISSING")


def intent(*,broker:str,client_order_id:str,option_contract:dict,
           original_quote_event_sha:str,quantity:int,limit_price:str,
           created_at_et:str,expires_at_et:str,
           per_contract_exit_fee:str="0.65")->dict:
    payload={
        "contract":"atlas-v81-option-sell-to-close-intent-v1",
        "origin":ORIGIN,"broker":broker,
        "client_order_id":client_order_id,
        "option_contract":option_contract,
        "original_quote_event_sha":original_quote_event_sha,
        "quantity":quantity,"limit_price":limit_price,
        "created_at_et":created_at_et,"expires_at_et":expires_at_et,
        "per_contract_exit_fee":per_contract_exit_fee,
        "side":"SELL_TO_CLOSE","order_type":"LIMIT",
        "time_in_force":"DAY",
        "source_policy":"SIGNED_ORIGINAL_OPTION_TAPE_RESEARCH_ONLY",
        "actual_broker_submission_authorized":False,
        "broker_switch_authorized":False,
    }
    result=_signed(payload)
    _require_identity(result)
    return result


def event(*,event_id:str,kind:str,at_et:str,available_at_et:str,
          broker:str,client_order_id:str,
          broker_order_id:str|None=None,**payload)->dict:
    result=_signed({
        "contract":"atlas-v81-synthetic-broker-event-v1",
        "origin":ORIGIN,
        "event_id":event_id,"kind":kind,"at_et":at_et,
        "available_at_et":available_at_et,"broker":broker,
        "client_order_id":client_order_id,
        "broker_order_id":broker_order_id,
        **payload,
    })
    return result


def replay(order:dict,events:list[dict]|tuple[dict,...],*,as_of_et:str)->dict:
    """Replay explicit synthetic broker receipts without crediting actual cash.

    Quotes alone cannot progress a broker order. Unacknowledged/unknown state
    cannot be retried, repriced, or switched to the fallback. Filled events
    require original limit price, broker order ID, monotone cumulative quantity
    and proof-like fixture event identity. No partial fills are invented.
    """
    _require_identity(order)
    cutoff=_clock(as_of_et)
    created=_clock(order["created_at_et"])
    expires=_clock(order["expires_at_et"])
    if cutoff<created or not isinstance(events,(tuple,list)):
        raise V81Error("V81_INVALID_AS_OF_OR_EVENT_COLLECTION")
    quantity=order["quantity"]
    limit=_dec(order["limit_price"])
    fee=_dec(order["per_contract_exit_fee"],positive=False)
    seen=set()
    previous=created
    status="PLANNED"
    filled=0
    proceeds=Decimal("0")
    broker_id=None
    records=[]
    unknown=False
    for item in events:
        if not _valid_signed(item) or item.get("contract")!="atlas-v81-synthetic-broker-event-v1" or item.get("origin")!=ORIGIN:
            raise V81Error("V81_UNSIGNED_OR_REAL_BROKER_EVENT_NOT_ACCEPTED")
        kind=item.get("kind")
        eid=item.get("event_id")
        if (kind not in EVENTS or not isinstance(eid,str) or not eid or eid in seen or
                item.get("broker")!=order["broker"] or
                item.get("client_order_id")!=order["client_order_id"]):
            raise V81Error("V81_EVENT_IDENTITY_OR_TYPE_INVALID")
        seen.add(eid)
        at=_clock(item["at_et"])
        available=_clock(item["available_at_et"])
        if at<previous or available<at or available>cutoff or at>expires:
            raise V81Error("V81_EVENT_CAUSAL_CLOCK_OR_EXPIRY_INVALID")
        previous=at
        oid=item.get("broker_order_id")
        if oid is not None and (not isinstance(oid,str) or not oid):
            raise V81Error("V81_INVALID_PROVIDER_ORDER_ID")
        if broker_id is not None and oid is not None and oid!=broker_id:
            raise V81Error("V81_BROKER_ORDER_ID_DRIFT")
        reason=None
        if kind=="QUOTE_OBSERVED":
            # Quote is context, never a substitute for broker acknowledgements.
            bid=_dec(item.get("bid"))
            ask=_dec(item.get("ask"))
            size=item.get("bid_size")
            if bid>ask or type(size) is not int or size<0:
                raise V81Error("V81_QUOTE_CROSSED_OR_INVALID_SIZE")
            reason="CONTEXT_ONLY_NO_FILL_INFERENCE"
        elif status in FINAL:
            raise V81Error("V81_TERMINAL_ORDER_MUTATION")
        elif kind=="SUBMIT_REQUESTED":
            if status!="PLANNED" or oid is not None:
                raise V81Error("V81_DUPLICATE_OR_INVALID_SUBMISSION")
            status="SUBMISSION_UNCONFIRMED"
            unknown=True
            reason="NO_BROKER_ACKNOWLEDGMENT"
        elif kind=="BROKER_ACK":
            if status!="SUBMISSION_UNCONFIRMED" or oid is None:
                raise V81Error("V81_ACK_WITHOUT_PENDING_SUBMISSION")
            broker_id=oid
            status="WORKING"
            unknown=False
            reason="ACK_FIXTURE_NOT_HISTORICAL_BROKER_EVIDENCE"
        elif kind in ("PARTIAL_FILL","FINAL_FILL"):
            if status not in ("WORKING","PARTIALLY_FILLED","CANCEL_PENDING") or oid!=broker_id:
                raise V81Error("V81_FILL_WITHOUT_ACK_OR_WRONG_ORDER")
            cumulative=item.get("cumulative_filled")
            price=_dec(item.get("fill_price"))
            if (type(cumulative) is not int or
                    not filled<cumulative<=quantity or price<limit):
                raise V81Error("V81_FILL_QTY_OR_SELL_LIMIT_VIOLATION")
            if (kind=="PARTIAL_FILL" and cumulative==quantity or
                    kind=="FINAL_FILL" and cumulative!=quantity):
                raise V81Error("V81_PARTIAL_FINAL_STATE_CONTRADICTION")
            delta=cumulative-filled
            proceeds+=price*Decimal(delta)*100-fee*Decimal(delta)
            filled=cumulative
            status="FILLED" if cumulative==quantity else "PARTIALLY_FILLED"
            reason=f"SYNTHETIC_FILL_DELTA_{delta}_UNVERIFIED"
        elif kind=="CANCEL_REQUESTED":
            if status not in ("WORKING","PARTIALLY_FILLED") or oid!=broker_id:
                raise V81Error("V81_CANCEL_WITHOUT_ACK")
            status="CANCEL_PENDING"
            unknown=True
            reason="CANCEL_REQUEST_NOT_CANCELLATION_ACK"
        elif kind=="CANCEL_ACK":
            if status!="CANCEL_PENDING" or oid!=broker_id:
                raise V81Error("V81_CANCEL_ACK_WITHOUT_PENDING")
            status="CANCELLED"
            unknown=False
            reason="CANCELLED_REMAINDER_ONLY"
        elif kind=="BROKER_REJECT":
            if status not in ("SUBMISSION_UNCONFIRMED","WORKING","CANCEL_PENDING") or (
                    status!="SUBMISSION_UNCONFIRMED" and oid!=broker_id):
                raise V81Error("V81_REJECT_STATE_INVALID")
            status="REJECTED"
            unknown=False
            reason="BROKER_FIXTURE_REJECT_NO_FILL_ASSUMED"
        elif kind=="BROKER_TIMEOUT":
            if status not in ("SUBMISSION_UNCONFIRMED","WORKING","PARTIALLY_FILLED","CANCEL_PENDING"):
                raise V81Error("V81_TIMEOUT_NOT_A_PENDING_ORDER")
            status="UNKNOWN_NEEDS_RECONCILIATION"
            unknown=True
            reason="NO_NEW_ORDER_OR_BROKER_SWITCH_ALLOWED"
        elif kind=="BROKER_RECONCILIATION":
            if status!="UNKNOWN_NEEDS_RECONCILIATION":
                raise V81Error("V81_RECONCILE_ONLY_UNKNOWN_STATE")
            # Recovery explicitly references a known broker ID, including
            # the case where an original submit timed out before its ACK.
            if oid is None or (broker_id is not None and oid!=broker_id):
                raise V81Error("V81_RECONCILIATION_ORDER_ID_REQUIRED")
            broker_id=oid
            reported=item.get("cumulative_filled")
            resolved=item.get("resolved_status")
            if (type(reported) is not int or reported<filled or reported>quantity or
                    resolved not in ("WORKING","CANCELLED","REJECTED","FILLED")):
                raise V81Error("V81_RECONCILIATION_STATUS_OR_QUANTITY_INVALID")
            # A greater reconciled filled count cannot be used to invent
            # missing execution price/fee; stay unknown until real provenance.
            if reported!=filled or resolved=="FILLED" and filled!=quantity:
                raise V81Error("V81_RECONCILED_MISSING_FILL_PRICE_EVIDENCE")
            if resolved=="REJECTED" and filled:
                raise V81Error("V81_REJECT_CANNOT_ERASE_PARTIAL_FILL")
            # A reconciliation claiming WORKING cannot erase known
            # partially-filled quantity. Preserve outstanding exposure.
            status=("PARTIALLY_FILLED" if resolved=="WORKING" and filled>0
                    else resolved)
            unknown=False
            reason="RECONCILED_FIXTURE_NOT_REAL_BROKER_ACCOUNT"
        else:
            raise V81Error("V81_EVENT_DISPATCH_UNHANDLED")
        records.append({
            "original_event_sha":item["fingerprint"],
            "kind":kind,"at_et":at.isoformat(),
            "available_at_et":available.isoformat(),
            "state_after":status,"cumulative_filled":filled,
            "remaining_quantity":quantity-filled,
            "reason":reason,
        })
    # An unmatched submission, outstanding cancellation, missing broker
    # ACK, or broker timeout remains unsafe even after its original cutoff.
    if status in ("SUBMISSION_UNCONFIRMED","CANCEL_PENDING"):
        unknown=True
    if cutoff>=expires and status not in FINAL and not unknown:
        # Expiration of a DAY order is not proof of broker auto-cancellation.
        unknown=True
        status="UNKNOWN_NEEDS_RECONCILIATION"
        records.append({
            "kind":"DAY_TIME_IN_FORCE_CUTOFF_UNCONFIRMED",
            "at_et":cutoff.isoformat(),"available_at_et":cutoff.isoformat(),
            "state_after":status,
            "cumulative_filled":filled,
            "remaining_quantity":quantity-filled,
            "reason":"EXCHANGE_CLOSE_DOES_NOT_SUPPLY_BROKER_CANCEL_ACK",
        })
    return _signed({
        "contract":CONTRACT,"origin":ORIGIN,
        "intent_sha":order["fingerprint"],
        "broker":order["broker"],
        "client_order_id":order["client_order_id"],
        "broker_order_id_fixture":broker_id,
        "status":status,
        "cumulative_fixture_filled_quantity":filled,
        "remaining_quantity_unverified":quantity-filled,
        "synthetic_fill_proceeds_after_fees":
            str(proceeds.quantize(CENT,rounding=ROUND_HALF_UP)),
        "real_broker_fills_verified":False,
        "actual_broker_orders_submitted":0,
        "historical_broker_cash_credited":None,
        "account_cash_reconciliation_status":"UNKNOWN_NOT_CONNECTED_TO_BROKER",
        "automatic_broker_failover":False,
        "replay_source":"SIGNED_SYNTHETIC_RECEIPTS_NOT_ORIGINAL_BROKER_EXECUTION",
        "needs_broker_reconciliation_before_retry_or_switch":
            unknown or status in ("WORKING","PARTIALLY_FILLED","CANCEL_PENDING"),
        "original_events":records,
    })
