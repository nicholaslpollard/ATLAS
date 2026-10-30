from __future__ import annotations

from copy import deepcopy

from scripts.run_spy_v52_exact_intraday_quote_canary import summarize_source


def source():
    return {
        "exact_requirement":{"method":"option_history_exact_quote_tape",
                             "kwargs":{"symbol":"SPY","strike":"604",
                                       "date_et":"2025-06-09","expiration":"2025-06-09",
                                       "right":"call","interval":"1s",
                                       "start_time_et":"09:35:00.000",
                                       "end_time_et":"09:37:00.000"}},
        "source_rows":(
            {"timestamp":"2025-06-09T09:35:30-04:00","bid":1.00,"ask":1.10,
             "bid_size":8,"ask_size":5,"symbol":"SPY",
             "expiration":"2025-06-09","strike":604,"right":"call"},
            {"timestamp":"2025-06-09T09:36:11-04:00","bid":1.04,"ask":1.13,
             "bid_size":10,"ask_size":6,"symbol":"SPY",
             "expiration":"2025-06-09","strike":604,"right":"call"},
        ),
        "status":"FETCHED_AND_ARCHIVED",
        "query_id":"a"*64,"source_sha256":"b"*64,
    }


def test_canary_retains_provenance_and_sample_but_not_pnl():
    a=summarize_source(source(),strike="604",right="call",session="2025-06-09")
    assert a["rows"]==2
    assert a["source_query_id"]=="a"*64
    assert a["contract_identity_conflict_count"]==0
    assert a["per_row_contract_identity_provable"] is True
    assert a["historical_fill_verified"] is False
    assert a["independent_historical_publication_verified"] is False
    assert a["historical_strategy_pnl"] is None
    assert len(a["preview_first_three_rows"])==2
    assert "timestamp" in a["source_row_field_names"]
    assert a["fingerprint"]


def test_wrong_contract_is_visible_not_silently_counted():
    r=source()
    r["source_rows"]=(dict(r["source_rows"][0],right="put"),)
    a=summarize_source(r,strike="604",right="call",session="2025-06-09")
    assert a["contract_identity_conflict_count"]==1
    assert a["contract_identity_conflicts"][0]["field"]=="right"
    assert a["historical_fill_verified"] is False


def test_missing_per_row_identity_remains_unproven():
    r=source()
    r["source_rows"]=tuple({k:v for k,v in row.items() if k not in ("symbol","expiration","right","strike")} for row in r["source_rows"])
    a=summarize_source(r,strike="604",right="call",session="2025-06-09")
    assert a["per_row_contract_identity_provable"] is False
    assert a["contract_identity_conflict_count"]==0
    assert a["source_sha256"]=="b"*64
    assert a["historical_fill_verified"] is False
