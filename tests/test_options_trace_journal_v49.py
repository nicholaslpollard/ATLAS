from __future__ import annotations

import copy
import json

import pytest

from packages.simulation.options_opportunity_trace_v49 import (
    CONTRACT, fingerprint, TraceError,
)
from packages.simulation.options_trace_journal_v49 import (
    create_journal, verify_journal,
)


def trace_fixture():
    rows=[]
    for i in range(361):
        rows.append({
            "opportunity_id": f"SPY:2018-01-{i:03d}:SIMULATION_DIAGNOSTIC",
            "date_et": f"2018-01-{i:03d}",
            "decision_reason_codes": ["NO_SOURCE" if i%2 else "HYPOTHETICAL_LONG"],
            "morning_open_interest_and_provenance": None,
            "simulator_disposition": "NO_HISTORICAL_TRADE_AUTHORIZED_HYPOTHETICAL_LONG" if i%2==0
            else "NO_ENTRY_HYPOTHETICAL_ABSTAIN_OR_SOURCE_BLOCK",
            "broker_fills": None,
            "realized_strategy_pnl": None,
        })
    result={
        "contract":CONTRACT,
        "opportunities":rows,
        "input_report_fingerprints":{"v45":"a"*64,"v46":"b"*64,"v47":"c"*64},
    }
    result["fingerprint"]=fingerprint(result)
    return result


def test_immutable_361_opportunity_journal_complete_and_hash_verifiable(tmp_path):
    path=tmp_path/"simulator_opportunities.jsonl"
    trace=trace_fixture()
    saved=create_journal(path,trace)
    assert saved["total_records"]==363
    assert saved["opportunity_events"]==361
    assert saved["trace_fingerprint"]==trace["fingerprint"]
    assert verify_journal(path)==saved
    lines=path.read_text().splitlines()
    assert json.loads(lines[0])["event_type"]=="RUN_MANIFEST"
    assert json.loads(lines[-1])["event_type"]=="OFFLINE_AUDIT_CLOSEOUT"
    assert json.loads(lines[2])["payload"]["decision_reason_codes"]==["NO_SOURCE"]
    with pytest.raises(TraceError,match="MUST_BE_NEW"):
        create_journal(path,trace)


def test_changed_event_or_truncated_journal_fail_closed(tmp_path):
    trace=trace_fixture()
    path=tmp_path/"one.jsonl"
    create_journal(path,trace)
    entries=path.read_text().splitlines()
    bad=copy.deepcopy(json.loads(entries[5]))
    bad["payload"]["decision_reason_codes"]=["FAKE_PROFITABLE"]
    entries[5]=json.dumps(bad)
    path.write_text("\n".join(entries)+"\n")
    with pytest.raises(TraceError,match="CHAIN"):
        verify_journal(path)
    path2=tmp_path/"two.jsonl"
    create_journal(path2,trace)
    path2.write_text("\n".join(path2.read_text().splitlines()[:-1])+"\n")
    with pytest.raises(TraceError,match="INCOMPLETE"):
        verify_journal(path2)


def test_falsified_input_fingerprint_or_duplicate_opportunity_refused(tmp_path):
    trace=trace_fixture()
    changed=copy.deepcopy(trace)
    changed["opportunities"][0]["broker_fills"]=[{"fake":"fill"}]
    with pytest.raises(TraceError,match="NOT_VERIFIED"):
        create_journal(tmp_path/"bad.jsonl",changed)
    dup=trace_fixture()
    dup["opportunities"][2]["opportunity_id"]=dup["opportunities"][1]["opportunity_id"]
    dup["fingerprint"]=fingerprint({k:v for k,v in dup.items() if k!="fingerprint"})
    with pytest.raises(TraceError,match="DUPLICATE"):
        create_journal(tmp_path/"dup.jsonl",dup)
