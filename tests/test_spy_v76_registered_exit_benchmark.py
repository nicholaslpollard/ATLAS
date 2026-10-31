from __future__ import annotations

from datetime import date
from decimal import Decimal
import json

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation import spy_v74_dynamic_sell_to_close_shadow as v74
from scripts import run_spy_v76_registered_exit_benchmark as v76


def _quote(second,bid,ask,size=9):
    return {"timestamp_et":f"2025-06-04T09:36:{second:02d}-04:00",
            "bid":bid,"ask":ask,"bid_size":size,"ask_size":size}


def _case():
    day="2025-06-04"
    contract={"symbol":"SPY","date_et":day,"expiration":day,
              "strike":"598","right":"call"}
    req={"provider":"thetadata","method":"option_history_exact_quote_tape",
         "kwargs":{**contract,"interval":"1s"}}
    qid=_fingerprint(req)
    debit="402.60"
    trade=v74.signed({"session":day,"status":"UNRESOLVED_POSITION",
                       "actual_fills":0,
                       "policy":{"lag_seconds":1,"max_adverse_pct":"1"},
                       "source_query_id":qid,"source_sha256":"f"*64,
                       "entry_debit":debit,
                       "events":[{"type":"MODELED_ENTRY_QUOTE_REFERENCE",
                                  "at_et":day+"T09:36:02-04:00",
                                  "ask":"1","qty":4,
                                  "debit_plus_entry_fees":debit}]})
    parent=v74.signed({"session":day,"selected_contract":contract,
                       "exact_option_requirement":req,
                       "exact_option_receipt":{"state":"ARCHIVED",
                                               "query_id":qid,
                                               "archive_sha256":"f"*64},
                       "standalone_replay_report":trade})
    tape={"status":"CACHE_HIT","source_sha256":"f"*64,
          "query_id":qid,"exact_requirement":req,
          "source_rows":[_quote(2,"0.99","1.00"),
                         _quote(3,"0.70","0.72"),
                         _quote(4,"0.66","0.68"),
                         _quote(5,"0.61","0.63"),
                         _quote(6,"0.57","0.60")]}
    return parent,tape


def test_v76_registered_fast_risk_stop_triggers_while_v74_default_holds():
    original,tape=_case()
    default=v74.replay(original,tape)
    fast=v74.replay(original,tape,
                    **v76.POLICIES["fast_25_40"])
    assert default["status"]=="UNRESOLVED_POSITION"
    assert fast["status"]=="CLOSED_QUOTE_REFERENCE"
    assert fast["reason"]=="REGISTERED_VARIANT_STOP"
    assert fast["exit_bid"]=="0.66"
    assert fast["exit_at_et"].endswith("09:36:04-04:00")
    assert fast["trade_net_pnl"]=="-141.20"
    assert fast["actual_broker_fills"]==0


def test_same_unchanged_v74_baseline_output():
    original,tape=_case()
    baseline=v74.replay(original,tape)
    candidate=v74.replay(original,tape,**v76.POLICIES["v74_control"])
    assert baseline==candidate
    assert baseline["fingerprint"]==candidate["fingerprint"]


def test_policy_registry_frozen_and_invalid_parameters_blocked():
    assert set(v76.POLICIES)=={
        "v74_control","defensive_25_75","balanced_35_100",
        "fast_25_40","runner_35_150"
    }
    assert v76.LAGS==(1,3)
    original,tape=_case()
    with pytest.raises(v74.V74Error,match="UNREGISTERED_PREDECLARED"):
        v74.replay(original,tape,stop_loss_option_pct="-10")
    with pytest.raises(v74.V74Error,match="UNREGISTERED_PREDECLARED"):
        v74.replay(original,tape,take_profit_option_pct="200")


def test_v76_source_chain_and_event_proof_no_broker_calls(tmp_path):
    parent,tape=_case()
    root=tmp_path/"source"
    root.mkdir()
    src=v74.signed({
        **{k:v for k,v in parent.items() if k!="fingerprint"},
        "signal_fingerprint":"a"*64,
        "native_minute_source_sha256":"b"*64,
        "standalone_replay_disposition":"UNRESOLVED_POSITION",
    })
    before_row=v74.signed({
        **{k:v for k,v in src.items() if k!="fingerprint"},
    })
    pre=v74.signed({"contract":v76.V65,"session_reports":[before_row],
                    "provider_requests":0,"broker_orders":0})
    after=v74.signed({"contract":v76.V65,"session_reports":[src],
                      "provider_requests":0,"broker_orders":0})
    resolver={"source_uses_requested":1,"provider_dispatch_attempts":0}
    ch=v74.signed({"contract":v76.V69,
                   "original_v65_preflight_sha":pre["fingerprint"],
                   "original_v65_post_source_sha":after["fingerprint"],
                   "source_resolution":resolver})
    sr=v74.signed({"contract":v76.V69,
                   "original_preflight_sha":pre["fingerprint"],
                   "runtime_source_receipt":resolver})
    summary=v74.signed({"contract":v76.V69,
                         "chunks":1,"broker_orders":0,
                         "start":"2025-06-04","end":"2025-06-04",
                         "chunk_summaries":[{"fingerprint":ch["fingerprint"]}]})
    for name,doc in {
        "summary.json":summary,
        "chunk_0001.summary.json":ch,
        "chunk_0001.preflight.json":pre,
        "chunk_0001.replay.json":after,
        "chunk_0001.sources.json":sr,
    }.items():
        (root/name).write_text(json.dumps(doc),encoding="utf8")
    read=[]
    def cache(_settings,qid):
        read.append(qid)
        return {"cache_evidence":"CACHE_HIT","source":tape}
    logs=[]
    out=v76.run(root,tmp_path/"out",
                expected_parent_sha=summary["fingerprint"],
                settings_factory=lambda *a: object(),
                source_reader=cache,emit_event=logs.append)
    assert len(read)==1
    assert len(out["policies"])==10
    assert out["provider_calls"]==out["broker_orders"]==0
    assert out["policies"][0]["closed_trade_count"] in (0,1)
    assert len(list((tmp_path/"out").glob("*.json.gz")))==10
    assert logs[0].startswith("STAGE_START V76")
    assert any(x.startswith("PROGRESS_10PCT") for x in logs)
    assert logs[-1].startswith("COMPLETE V76")
    assert out["original_v69_sha"]==summary["fingerprint"]
    assert out["out_of_sample_perf_proven"] is False


def test_immutable_rejects_preexisting_output_without_source_activity(tmp_path):
    out=tmp_path/"existing"
    out.mkdir()
    with pytest.raises(ValueError,match="OUTPUT_ALREADY_EXISTS"):
        v76.run(tmp_path/"source",out,expected_parent_sha="a"*64,
                source_reader=lambda *a:pytest.fail("forbidden"),
                emit_event=lambda msg:None)
