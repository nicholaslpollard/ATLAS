from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation import spy_v74_dynamic_sell_to_close_shadow as v74


def case(rows,*,status="UNRESOLVED_POSITION",quantity=4,entry_ask="1.00"):
    day="2025-06-04"
    contract={"symbol":"SPY","date_et":day,
              "expiration":day,"strike":"598","right":"call"}
    request={"provider":"thetadata","method":"option_history_exact_quote_tape",
             "kwargs":{**contract,"interval":"1s"}}
    qid=_fingerprint(request)
    debit=str(v74.money(quantity*(Decimal(entry_ask)*100+Decimal(".65"))))
    trade=v74.signed({
        "session":day,"status":status,"actual_fills":0,
        "policy":{"lag_seconds":1,"max_adverse_pct":"1"},
        "source_query_id":qid,"source_sha256":"f"*64,
        "entry_debit":debit,
        "events":[{"type":"MODELED_ENTRY_QUOTE_REFERENCE",
                   "at_et":day+"T09:36:02-04:00",
                   "qty":quantity,"ask":entry_ask,
                   "debit_plus_entry_fees":debit}],
    })
    parent=v74.signed({
        "session":day,"selected_contract":contract,
        "exact_option_receipt":{"state":"ARCHIVED",
                                "query_id":qid,"archive_sha256":"f"*64},
        "exact_option_requirement":request,
        "standalone_replay_report":trade,
    })
    source={"status":"CACHE_HIT","source_sha256":"f"*64,
            "exact_requirement":request,"query_id":qid,
            "source_rows":tuple(rows)}
    return parent,source


def q(seconds,bid,ask,*,size=8):
    return {"timestamp_et":f"2025-06-04T09:36:{seconds:02d}-04:00",
            "bid":str(bid),"ask":str(ask),
            "bid_size":size,"ask_size":size}


def test_trailing_exit_is_acted_one_second_later_not_at_future_peak():
    parent,source=case([
        q(2,"0.99","1.00"),
        q(3,"1.00","1.01"),
        q(4,"1.25","1.26"),
        q(5,"1.10","1.11"),
        q(6,"1.02","1.03"),
        q(7,"0.90","0.92"),
    ])
    result=v74.replay(parent,source)
    assert result["status"]=="CLOSED_QUOTE_REFERENCE"
    assert result["reason"]=="CAUSAL_TRAILING_PROFIT"
    assert result["exit_at_et"].endswith("09:36:07-04:00")
    assert result["exit_bid"]=="0.90"
    assert result["trade_net_pnl"]=="-45.20"
    assert result["actual_broker_fills"]==0
    assert len([x for x in result["events"] if x["type"]=="EXIT_INTENT"])==1
    assert result["events"][-1]["type"]=="MODELED_SELL_TO_CLOSE_BID_REFERENCE"


def test_bad_wide_quote_never_becomes_exit_then_later_stop_action_worse_price():
    parent,source=case([
        q(2,"0.99","1.00"),
        q(3,"0.90","1.30"),
        q(4,"0.90","0.92"),
        q(5,"0.45","0.46"),
        q(6,"0.42","0.43"),
    ])
    result=v74.replay(parent,source)
    assert result["status"]=="CLOSED_QUOTE_REFERENCE"
    assert result["reason"]=="BASELINE_STOP"
    assert result["exit_at_et"].endswith("09:36:06-04:00")
    assert result["exit_bid"]=="0.42"
    assert result["trade_net_pnl"]=="-237.20"
    assert any(x["type"]=="QUOTE_REJECTED_HELD_NOT_CASH" for x in result["events"])


def test_liquidity_defers_reference_sale_without_inventing_partial_fill():
    parent,source=case([
        q(2,"0.99","1.00"),
        q(3,"0.40","0.42"),
        q(4,"0.39","0.41",size=2),
        q(5,"0.37","0.39",size=10),
    ])
    result=v74.replay(parent,source)
    assert result["status"]=="CLOSED_QUOTE_REFERENCE"
    assert result["exit_bid"]=="0.37"
    assert any(x["type"]=="PENDING_EXIT_INSUFFICIENT_DISPLAYED_SIZE"
               and x["partial_fill_not_assumed"] for x in result["events"])


def test_prolonged_bad_quotes_censor_without_assuming_zero_value():
    parent,source=case([
        q(2,"0.99","1.00"),q(3,"0.90","1.25"),
        {"timestamp_et":"2025-06-04T09:36:35-04:00",
         "bid":"0.9","ask":"1.25","bid_size":2,"ask_size":4},
    ])
    result=v74.replay(parent,source)
    assert result["status"]=="UNRESOLVED_POSITION"
    assert result["exit_credit"] is None
    assert result["cash_balance_after_if_unresolved"] is None


def test_wrong_original_sha_never_reads_future_tape_as_valid():
    parent,source=case([q(2,"0.99","1.00"),q(3,"0.4","0.42")])
    source["source_sha256"]="0"*64
    with pytest.raises(v74.V74Error,match="EXACT_ORIGINAL_SOURCE_SHA"):
        v74.replay(parent,source)


def test_variant_restrictions_keep_no_arbitrary_assumptions():
    parent,source=case([q(2,"0.99","1.00"),q(3,"0.4","0.42")])
    with pytest.raises(v74.V74Error,match="UNREGISTERED"):
        v74.replay(parent,source,action_lag_seconds=0)
    with pytest.raises(v74.V74Error,match="UNREGISTERED"):
        v74.replay(parent,source,broker="unknown")
