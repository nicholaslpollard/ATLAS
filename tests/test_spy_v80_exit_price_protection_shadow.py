from __future__ import annotations

from datetime import datetime
import gzip
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from packages.simulation.spy_v80_exit_price_protection_shadow import (
    V80Error, evaluate, _signed,
)
from scripts import run_spy_v80_signed_exit_price_protection as v80


def original(case_date="2025-07-02",*,trigger="1.24",action="1.19",
             lag=1,status="CLOSED_QUOTE_REFERENCE"):
    trigger_at=f"{case_date}T10:00:01-04:00"
    action_at=f"{case_date}T10:00:{1+lag:02d}-04:00"
    entry={"type":"ORIGINAL_ENTRY_REUSED","qty":3,
           "at_et":f"{case_date}T09:35:01-04:00",
           "debit_plus_fees":"301.95"}
    events=[entry,{
        "type":"EXIT_INTENT","trigger_at_et":trigger_at,
        "reference_bid":trigger,"earliest_action":action_at,
    }]
    if status=="CLOSED_QUOTE_REFERENCE":
        events.append({
            "type":"MODELED_SELL_TO_CLOSE_BID_REFERENCE",
            "at_et":action_at,"qty":3,
            "observed_bid":action,"observed_bid_size":8,
            "actual_broker_fill":False,"limit_order_fill_guaranteed":False,
        })
    price=str((float(action)*300-1.95-301.95))
    inner=_signed({
        "parent_v65_sha":"a"*64,
        "original_option_archive_sha256":"b"*64,
        "selected_contract":{"symbol":"SPY"},
        "actual_broker_fills":0,"provider_requests":0,
        "status":status,
        "trade_net_pnl":price if status=="CLOSED_QUOTE_REFERENCE" else None,
        "events":events,
    })
    return _signed({
        "contract":"atlas-v76-preregistered-multi-exit-causal-quote-research-v1",
        "session":case_date,
        "policy":"runner_35_150",
        "lag_seconds":lag,
        "parent_v65_sha":"a"*64,
        "original_source_sha256":"b"*64,
        "status":status,
        "reason":"REGISTERED_VARIANT_STOP",
        "trade_net_pnl":inner["trade_net_pnl"],
        "broker_orders":0,"provider_calls":0,
        "v74_inner_quote_shadow_report":inner,
    })


def test_original_sell_limit_bid_below_trigger_demands_explicit_reprice():
    doc=original()
    block=evaluate(doc,max_adverse_pct="1")
    assert block["status"]=="ADVERSE_DRIFT_OUTSIDE_PRICE_PROTECTION"
    assert block["original_trigger_limit_marketable_at_action_quote"] is False
    assert block["actual_broker_fills"]==0 and block["credited_cash_from_shadow"] is None
    assert block["adverse_bid_drift_pct"]=="4.0323"
    permissive=evaluate(doc,max_adverse_pct="2")
    assert permissive["status"]=="ADVERSE_DRIFT_OUTSIDE_PRICE_PROTECTION"
    assert permissive["fingerprint"]!=block["fingerprint"]
    within=evaluate(original(action="1.23"),max_adverse_pct="1")
    assert within["status"]=="ADVERSE_REPRICE_ALLOWED_NOT_EXECUTED"
    assert within["fresh_broker_acknowledgment_needed"] is True


def test_better_bid_is_trigger_limit_marketable_quote_not_fill():
    result=evaluate(original(action="1.25"),broker="alpaca",max_adverse_pct="0")
    assert result["status"]=="ORIGINAL_TRIGGER_LIMIT_MARKETABLE_QUOTE_ONLY"
    assert result["original_trigger_limit_marketable_at_action_quote"] is True
    assert result["actual_broker_order_submitted"] is False
    assert result["broker_expiry_exercise_outcome_unknown"] is True


def test_missing_original_quote_never_books_cash():
    result=evaluate(original(status="UNRESOLVED_POSITION"))
    assert result["status"]=="ORIGINAL_EXIT_UNRESOLVED_NO_CASH"
    assert result["credited_cash_from_shadow"] is None
    assert result["actual_broker_fills"]==0


def test_signed_lineage_and_latency_must_not_be_bypassed():
    doc=original()
    altered=dict(doc)
    altered["trade_net_pnl"]="99999"
    with pytest.raises(V80Error,match="ORIGINAL_EXIT_REPORT_INVALID"):
        evaluate(altered)
    inner=doc["v74_inner_quote_shadow_report"]
    invalid=_signed({**{k:v for k,v in inner.items() if k!="fingerprint"},
                     "actual_broker_fills":1})
    changed=_signed({**{k:v for k,v in doc.items() if k!="fingerprint"},
                     "v74_inner_quote_shadow_report":invalid})
    with pytest.raises(V80Error,match="NO_FILL_CONTRACT"):
        evaluate(changed)
    with pytest.raises(V80Error,match="UNREGISTERED"):
        evaluate(doc,max_adverse_pct="5")
    with pytest.raises(V80Error,match="UNREGISTERED"):
        evaluate(doc,broker="auto-failover")


def test_action_cannot_be_before_registered_action_delay():
    doc=original(lag=3)
    changed_inner=doc["v74_inner_quote_shadow_report"]
    changed_events=list(changed_inner["events"])
    changed_events[2]={**changed_events[2],
                       "at_et":"2025-07-02T10:00:02-04:00"}
    changed_inner=_signed({**{k:v for k,v in changed_inner.items() if k!="fingerprint"},
                           "events":changed_events})
    changed=_signed({**{k:v for k,v in doc.items() if k!="fingerprint"},
                     "v74_inner_quote_shadow_report":changed_inner})
    with pytest.raises(V80Error,match="NOT_CAUSAL"):
        evaluate(changed)


def test_signed_input_zip_preflight_never_proceeds_if_missing(tmp_path):
    existing=tmp_path/"already"
    existing.mkdir()
    with pytest.raises(ValueError,match="IMMUTABLE_OUTPUT"):
        v80.run(tmp_path/"missing.zip",existing,callback=lambda _:None)
