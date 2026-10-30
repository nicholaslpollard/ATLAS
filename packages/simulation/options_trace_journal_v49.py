from __future__ import annotations

"""Durable append-only, self-verifying V49 OFFLINE opportunity-event journal.

Stores one fully attributable record for each evaluated opportunity (including
no-trade). Original source blobs are referenced by SHA in the event payload, not
duplicated. This is a research audit, NOT an order/response event gateway.
"""

import json
import os
from pathlib import Path

from packages.simulation.options_opportunity_trace_v49 import (
    CONTRACT as TRACE_CONTRACT, fingerprint, TraceError,
)

JOURNAL_CONTRACT = "atlas-sim-option-opportunity-append-only-journal-v49"


def _event(seq: int, prev_sha: str | None, kind: str, event_id: str, payload: dict) -> dict:
    record = {
        "contract": JOURNAL_CONTRACT,
        "seq": seq,
        "previous_record_sha256": prev_sha,
        "event_id": event_id,
        "event_type": kind,
        "payload": payload,
    }
    record["record_sha256"] = fingerprint(record)
    return record


def create_journal(path: Path, trace: dict) -> dict:
    if (trace.get("contract") != TRACE_CONTRACT or
            trace.get("fingerprint") != fingerprint({k:v for k,v in trace.items() if k != "fingerprint"})):
        raise TraceError("V49_JOURNAL_SOURCE_TRACE_NOT_VERIFIED")
    opportunities = trace.get("opportunities")
    if not isinstance(opportunities, list) or len(opportunities) != 361:
        raise TraceError("V49_JOURNAL_EXPECTED_361_CANDIDATES")
    ids = [c["opportunity_id"] for c in opportunities]
    if len(ids) != len(set(ids)):
        raise TraceError("V49_JOURNAL_DUPLICATE_OPPORTUNITY_ID")
    if path.is_symlink() or path.exists():
        raise TraceError("V49_JOURNAL_PATH_MUST_BE_NEW")
    path.parent.mkdir(parents=True, exist_ok=True)
    prev = None
    events = [
        ("RUN_MANIFEST", "V49:RUN_MANIFEST", {
            "trace_contract": TRACE_CONTRACT,
            "trace_fingerprint": trace["fingerprint"],
            "input_report_fingerprints": trace["input_report_fingerprints"],
            "original_one_second_rule_unchanged": True,
            "three_second_policy_is_diagnostic_only": True,
            "not_historical_execution": True,
            "provider_calls": 0,
        }),
        *[("OPPORTUNITY_EVALUATED", c["opportunity_id"], c) for c in opportunities],
        ("OFFLINE_AUDIT_CLOSEOUT", "V49:OFFLINE_AUDIT_CLOSEOUT", {
            "trace_fingerprint": trace["fingerprint"],
            "opportunity_events_written": len(opportunities),
            "historical_fills_claimed": 0,
            "missing_original_preselection_abstention_ids": 50,
        }),
    ]
    with path.open("xb") as f:
        for i,(kind,event_id,payload) in enumerate(events):
            row = _event(i,prev,kind,event_id,payload)
            encoded=(json.dumps(row,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")
            if len(encoded) > 128*1024:
                raise TraceError("V49_JOURNAL_EVENT_OVERSIZED")
            f.write(encoded)
            f.flush()
            os.fsync(f.fileno())
            prev=row["record_sha256"]
    verified = verify_journal(path)
    if verified["trace_fingerprint"] != trace["fingerprint"]:
        raise TraceError("V49_JOURNAL_REPLAY_MISMATCH")
    return verified


def verify_journal(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise TraceError("V49_JOURNAL_INPUT_INVALID")
    prev=None
    seen=set()
    run=None
    count=0
    last=None
    with path.open("rt",encoding="utf-8") as f:
        for seq,line in enumerate(f):
            if len(line) > 128*1024:
                raise TraceError("V49_JOURNAL_EVENT_OVERSIZED")
            try:
                event=json.loads(line)
            except (ValueError,TypeError) as exc:
                raise TraceError("V49_JOURNAL_INVALID_RECORD") from exc
            observed=event.get("record_sha256")
            if (event.get("contract") != JOURNAL_CONTRACT or
                    event.get("seq") != seq or event.get("previous_record_sha256") != prev or
                    observed != fingerprint({k:v for k,v in event.items() if k != "record_sha256"}) or
                    event.get("event_id") in seen):
                raise TraceError("V49_JOURNAL_CHAIN_OR_UNIQUE_ID_BROKEN")
            seen.add(event["event_id"])
            kind=event["event_type"]
            if seq==0:
                if kind!="RUN_MANIFEST":
                    raise TraceError("V49_JOURNAL_MANIFEST_MISSING")
                run=event["payload"]["trace_fingerprint"]
            elif kind=="OPPORTUNITY_EVALUATED":
                if last=="OFFLINE_AUDIT_CLOSEOUT":
                    raise TraceError("V49_JOURNAL_OPPORTUNITY_AFTER_CLOSEOUT")
                count+=1
            elif kind=="OFFLINE_AUDIT_CLOSEOUT":
                if count!=361 or event["payload"]["trace_fingerprint"]!=run or event["payload"]["opportunity_events_written"]!=count:
                    raise TraceError("V49_JOURNAL_CLOSEOUT_COUNT_DRIFT")
            else:
                raise TraceError("V49_JOURNAL_UNRECOGNIZED_EVENT_TYPE")
            prev=observed
            last=kind
    if last!="OFFLINE_AUDIT_CLOSEOUT" or count!=361:
        raise TraceError("V49_JOURNAL_INCOMPLETE")
    return {
        "journal_contract": JOURNAL_CONTRACT,
        "trace_fingerprint": run,
        "opportunity_events": count,
        "total_records": count+2,
        "final_record_sha256": prev,
        "original_source_archive_promotion": False,
    }
