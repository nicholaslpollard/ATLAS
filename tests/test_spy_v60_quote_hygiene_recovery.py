from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from scripts.run_spy_v60_quote_hygiene_recovery import (
    RecoveryError,_sanitize_quote_tape,
)


def sample_row(sec,bid,ask,*,size=8):
    return {
        "timestamp_et":f"2025-06-13T09:59:{sec:02d}-04:00",
        "symbol":"SPY","expiration":"2025-06-13",
        "strike":"598","right":"put",
        "bid":str(bid),"ask":str(ask),"bid_size":size,"ask_size":12,
    }


def fixtures(*,bad_bid="1.05",bad_ask="1.60"):
    src=[
        sample_row(1,"1.16","1.18"),
        sample_row(2,"1.16","1.18"),
        sample_row(3,bad_bid,bad_ask,size=2),
        sample_row(4,"1.39","1.60",size=2),
        sample_row(5,"1.41","1.43",size=4),
    ]
    right={"symbol":"SPY","date_et":"2025-06-13",
           "expiration":"2025-06-13","strike":"598","right":"put"}
    signal={"session":"2025-06-13","selected_contract":right}
    original={
        "session":"2025-06-13","signal":signal,
        "source_sha256":"a"*64,"source_query_id":"b"*64,
        "starting_cash":"25000.00",
        "events":[
            {"type":"ORDER_ACTION_QUOTE_REFERENCE",
             "action":{"timestamp_et":"2025-06-13T09:59:02-04:00",
                       "ask":"1.18"}},
            {"type":"MODELED_ENTRY_QUOTE_REFERENCE",
             "qty":2,"ask":"1.18"},
        ],
    }
    source={
        "source_sha256":original["source_sha256"],
        "query_id":original["source_query_id"],
        "status":"CACHE_HIT",
        "exact_requirement":{
            "method":"option_history_exact_quote_tape",
            "kwargs":{**right,"interval":"1s"},
        },
        "source_rows":tuple(src),
    }
    return source,original


def test_isolated_spread_only_skipped_as_explicit_shadow_and_raw_unchanged():
    src,original=fixtures()
    accepted=_sanitize_quote_tape(src,original)
    assert accepted["original_row_count"]==5
    assert accepted["retained_row_count"]==4
    assert accepted["original_row_index_map"]==[0,1,3,4]
    assert accepted["skipped"][0]["raw_source_row_index"]==2
    assert accepted["skipped"][0]["never_modeled_as_a_fill"] is True
    assert accepted["max_qualified_observation_gap_seconds"]==2
    assert len(src["source_rows"])==5
    assert accepted["source"]["source_rows"][2]["bid"]=="1.39"
    assert accepted["source_was_never_modified"] is True


def test_invalid_bid_crossing_stop_cannot_be_skipped():
    src,original=fixtures(bad_bid=".50",bad_ask="1.60")
    with pytest.raises(RecoveryError,match="V60_AMBIGUOUS_FIXED_EXIT_ON_BAD_SPREAD"):
        _sanitize_quote_tape(src,original)


def test_bad_quote_during_buy_action_rejected_even_if_other_side_good():
    src,original=fixtures()
    src["source_rows"]=tuple([src["source_rows"][0],
        sample_row(2,"0.70","1.18"),*src["source_rows"][2:]])
    with pytest.raises(RecoveryError,match="V60_INVALID_PREENTRY_OR_ACTION_QUOTE"):
        _sanitize_quote_tape(src,original)


def test_original_query_and_hash_not_mutable():
    src,original=fixtures()
    src["source_sha256"]="c"*64
    with pytest.raises(RecoveryError,match="V60_EXACT_SOURCE_SHA_OR_QUERY_MISMATCH"):
        _sanitize_quote_tape(src,original)
