from __future__ import annotations

from datetime import datetime

import pytest

from packages.simulation import spy_v81_broker_neutral_option_order_lifecycle as v81


def order():
    return v81.intent(
        broker="webull",client_order_id="atlas-v81-test-A",
        option_contract={"symbol":"SPY","expiration":"2025-08-20","strike":"635","right":"call"},
        original_quote_event_sha="a"*64,
        quantity=4,limit_price="2.20",
        created_at_et="2025-08-20T09:53:44-04:00",
        expires_at_et="2025-08-20T15:05:00-04:00",
    )


def event(num,kind,second,**kwargs):
    return v81.event(
        event_id=f"v81-e{num}",kind=kind,
        at_et=f"2025-08-20T09:53:{second:02d}-04:00",
        available_at_et=f"2025-08-20T09:53:{second:02d}-04:00",
        broker="webull",client_order_id="atlas-v81-test-A",
        **kwargs,
    )


def ack():
    return event(2,"BROKER_ACK",46,broker_order_id="broker-order-1")


def start():
    return [event(1,"SUBMIT_REQUESTED",45),ack()]


def test_partial_then_final_requires_broker_ack_and_limit_protection():
    seq=start()+[
        event(3,"PARTIAL_FILL",47,broker_order_id="broker-order-1",
              cumulative_filled=2,fill_price="2.21"),
        event(4,"FINAL_FILL",48,broker_order_id="broker-order-1",
              cumulative_filled=4,fill_price="2.23"),
    ]
    result=v81.replay(order(),seq,as_of_et="2025-08-20T09:53:49-04:00")
    assert result["status"]=="FILLED"
    assert result["cumulative_fixture_filled_quantity"]==4
    assert result["remaining_quantity_unverified"]==0
    assert result["synthetic_fill_proceeds_after_fees"]=="885.40"
    assert result["historical_broker_cash_credited"] is None
    assert result["real_broker_fills_verified"] is False
    assert result["actual_broker_orders_submitted"]==0
    assert result["needs_broker_reconciliation_before_retry_or_switch"] is False


def test_quote_and_request_without_ack_never_imply_fills():
    seq=[
        event(0,"QUOTE_OBSERVED",44,bid="2.79",ask="2.81",bid_size=9),
        event(1,"SUBMIT_REQUESTED",45),
    ]
    result=v81.replay(order(),seq,as_of_et="2025-08-20T09:53:49-04:00")
    assert result["status"]=="SUBMISSION_UNCONFIRMED"
    assert result["cumulative_fixture_filled_quantity"]==0
    assert result["needs_broker_reconciliation_before_retry_or_switch"] is True


def test_cancel_request_is_not_cancellation_ack():
    seq=start()+[event(3,"CANCEL_REQUESTED",47,broker_order_id="broker-order-1")]
    pending=v81.replay(order(),seq,as_of_et="2025-08-20T09:53:48-04:00")
    assert pending["status"]=="CANCEL_PENDING"
    assert pending["needs_broker_reconciliation_before_retry_or_switch"] is True
    closed=v81.replay(order(),seq+[event(4,"CANCEL_ACK",49,
                            broker_order_id="broker-order-1")],
                      as_of_et="2025-08-20T09:53:49-04:00")
    assert closed["status"]=="CANCELLED"
    assert closed["remaining_quantity_unverified"]==4


def test_partial_fill_before_cancel_ack_remains_known_synthetic_liability():
    seq=start()+[
        event(3,"PARTIAL_FILL",47,broker_order_id="broker-order-1",
              cumulative_filled=1,fill_price="2.20"),
        event(4,"CANCEL_REQUESTED",48,broker_order_id="broker-order-1"),
        event(5,"CANCEL_ACK",49,broker_order_id="broker-order-1"),
    ]
    doc=v81.replay(order(),seq,as_of_et="2025-08-20T09:53:50-04:00")
    assert doc["status"]=="CANCELLED"
    assert doc["cumulative_fixture_filled_quantity"]==1
    assert doc["remaining_quantity_unverified"]==3
    assert doc["historical_broker_cash_credited"] is None


def test_uncertain_timeout_forbids_retry_switch_until_reconciled():
    seq=[event(1,"SUBMIT_REQUESTED",45),event(2,"BROKER_TIMEOUT",47)]
    blocked=v81.replay(order(),seq,as_of_et="2025-08-20T09:53:48-04:00")
    assert blocked["status"]=="UNKNOWN_NEEDS_RECONCILIATION"
    assert blocked["needs_broker_reconciliation_before_retry_or_switch"]
    completed=v81.replay(order(),seq+[
        event(3,"BROKER_RECONCILIATION",49,broker_order_id="broker-order-1",
              cumulative_filled=0,resolved_status="CANCELLED"),
    ],as_of_et="2025-08-20T09:53:49-04:00")
    assert completed["status"]=="CANCELLED"
    assert completed["actual_broker_orders_submitted"]==0


def test_reconciliation_cannot_invent_missing_fill_price():
    seq=[event(1,"SUBMIT_REQUESTED",45),event(2,"BROKER_TIMEOUT",47),
         event(3,"BROKER_RECONCILIATION",49,broker_order_id="broker-order-1",
               cumulative_filled=3,resolved_status="WORKING")]
    with pytest.raises(v81.V81Error,match="MISSING_FILL_PRICE"):
        v81.replay(order(),seq,as_of_et="2025-08-20T09:53:49-04:00")


def test_limit_order_never_fills_below_existing_sell_limit():
    seq=start()+[event(3,"PARTIAL_FILL",47,broker_order_id="broker-order-1",
                       cumulative_filled=1,fill_price="2.19")]
    with pytest.raises(v81.V81Error,match="SELL_LIMIT"):
        v81.replay(order(),seq,as_of_et="2025-08-20T09:53:48-04:00")


def test_no_automatic_order_expiry_or_exercise_assumption():
    seq=start()
    document=v81.replay(order(),seq,as_of_et="2025-08-20T16:00:00-04:00")
    assert document["status"]=="UNKNOWN_NEEDS_RECONCILIATION"
    assert document["needs_broker_reconciliation_before_retry_or_switch"]
    assert document["historical_broker_cash_credited"] is None


def test_order_identity_tampering_or_duplicate_event_fails():
    original=order()
    fake={**original,"quantity":1000}
    with pytest.raises(v81.V81Error,match="INTENT_INVALID"):
        v81.replay(fake,[],as_of_et="2025-08-20T09:53:49-04:00")
    e=start()[0]
    with pytest.raises(v81.V81Error,match="EVENT_IDENTITY"):
        v81.replay(original,[e,e],as_of_et="2025-08-20T09:53:49-04:00")


def test_event_available_after_replay_clock_rejected():
    bad=v81.event(event_id="late",kind="SUBMIT_REQUESTED",
                  at_et="2025-08-20T09:53:45-04:00",
                  available_at_et="2025-08-20T09:53:50-04:00",
                  broker="webull",client_order_id="atlas-v81-test-A")
    with pytest.raises(v81.V81Error,match="CAUSAL_CLOCK"):
        v81.replay(order(),[bad],as_of_et="2025-08-20T09:53:49-04:00")


def test_accidental_broker_swap_fails_same_order():
    seq=start()+[v81.event(
        event_id="bad",kind="BROKER_TIMEOUT",
        at_et="2025-08-20T09:53:47-04:00",
        available_at_et="2025-08-20T09:53:47-04:00",
        broker="alpaca",client_order_id="atlas-v81-test-A",
    )]
    with pytest.raises(v81.V81Error,match="EVENT_IDENTITY"):
        v81.replay(order(),seq,as_of_et="2025-08-20T09:53:49-04:00")


def test_unknown_reconciliation_preserves_known_partial_exposure():
    seq=start()+[
        event(3,"PARTIAL_FILL",47,broker_order_id="broker-order-1",
              cumulative_filled=2,fill_price="2.25"),
        event(4,"BROKER_TIMEOUT",48,broker_order_id="broker-order-1"),
        event(5,"BROKER_RECONCILIATION",49,broker_order_id="broker-order-1",
              cumulative_filled=2,resolved_status="WORKING"),
    ]
    result=v81.replay(order(),seq,as_of_et="2025-08-20T09:53:49-04:00")
    assert result["status"]=="PARTIALLY_FILLED"
    assert result["cumulative_fixture_filled_quantity"]==2
    assert result["remaining_quantity_unverified"]==2
    assert result["needs_broker_reconciliation_before_retry_or_switch"] is True
    assert result["historical_broker_cash_credited"] is None


def test_partial_fills_during_cancel_pending_do_not_clear_cancel_request():
    seq=start()+[
        event(3,"CANCEL_REQUESTED",47,broker_order_id="broker-order-1"),
        event(4,"PARTIAL_FILL",48,broker_order_id="broker-order-1",
              cumulative_filled=1,fill_price="2.21"),
    ]
    still_pending=v81.replay(
        order(),seq,as_of_et="2025-08-20T09:53:48-04:00")
    assert still_pending["status"]=="CANCEL_PENDING"
    assert still_pending["remaining_quantity_unverified"]==3
    assert still_pending["needs_broker_reconciliation_before_retry_or_switch"] is True
    cancelled=v81.replay(
        order(),seq+[event(5,"CANCEL_ACK",49,broker_order_id="broker-order-1")],
        as_of_et="2025-08-20T09:53:49-04:00")
    assert cancelled["status"]=="CANCELLED"
    assert cancelled["cumulative_fixture_filled_quantity"]==1
    assert cancelled["historical_broker_cash_credited"] is None


def test_later_available_ack_cannot_authorize_earlier_received_fill():
    delayed_ack=v81.event(
        event_id="late-ack",kind="BROKER_ACK",
        at_et="2025-08-20T09:53:46-04:00",
        available_at_et="2025-08-20T09:53:52-04:00",
        broker="webull",client_order_id="atlas-v81-test-A",
        broker_order_id="broker-order-1",
    )
    alleged_fill=event(
        3,"PARTIAL_FILL",47,broker_order_id="broker-order-1",
        cumulative_filled=1,fill_price="2.21")
    with pytest.raises(v81.V81Error,match="CAUSAL_CLOCK"):
        v81.replay(order(),[start()[0],delayed_ack,alleged_fill],
                   as_of_et="2025-08-20T09:53:53-04:00")
