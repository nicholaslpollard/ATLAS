from __future__ import annotations

"""V55 immutable append-only event journal: hash-linked quote-replay decisions."""

import hashlib
import json
import os
from pathlib import Path

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_closed_bar_option_replay import CONTRACT as REPLAY_CONTRACT

CONTRACT = "atlas-v55-closed-minute-option-quote-event-journal-v1"
MAX_LINE_BYTES = 256 * 1024


class JournalError(ValueError):
    pass


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",",":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _record(seq, previous, kind, data):
    row={"contract":CONTRACT,"seq":seq,"previous_sha256":previous,
         "event_type":kind,"payload":data}
    row["sha256"]=_hash(row)
    return row


def verify_journal(path):
    if path.is_symlink() or not path.is_file():
        raise JournalError("V55_JOURNAL_MISSING_OR_LINKED")
    previous=None
    count=0
    manifest=None
    close=None
    with path.open("r",encoding="utf-8") as handle:
        for seq,line in enumerate(handle):
            if len(line.encode("utf-8"))>MAX_LINE_BYTES:
                raise JournalError("V55_JOURNAL_EVENT_OVERSIZE")
            try:
                row=json.loads(line)
            except ValueError as exc:
                raise JournalError("V55_JOURNAL_BAD_JSON") from exc
            if (row.get("seq")!=seq or row.get("contract")!=CONTRACT
                    or row.get("previous_sha256")!=previous
                    or row.get("sha256")!=_hash({k:v for k,v in row.items() if k!="sha256"})):
                raise JournalError("V55_JOURNAL_BROKEN_SEQUENCE_OR_SHA")
            if seq==0 and row.get("event_type")=="RUN_MANIFEST":
                manifest=row["payload"]
            elif row.get("event_type")=="RUNTIME_EVENT" and not close:
                if row["payload"].get("index")!=count:
                    raise JournalError("V55_JOURNAL_RUNTIME_EVENT_MISSING")
                count+=1
            elif row.get("event_type")=="RUN_CLOSEOUT" and close is None and seq>0:
                close=row["payload"]
            else:
                raise JournalError("V55_JOURNAL_INVALID_ORDER")
            previous=row["sha256"]
    if (manifest is None or close is None
            or manifest["report_fingerprint"]!=close.get("report_fingerprint")
            or close.get("runtime_event_count")!=count):
        raise JournalError("V55_JOURNAL_TRUNCATED_OR_INCONSISTENT")
    return {"report_fingerprint":manifest["report_fingerprint"],
            "runtime_events":count,"journal_rows":count+2,
            "tip_sha256":previous,"historical_fills":0}


def save_journal(path, report, *, progress=None):
    if (report.get("contract")!=REPLAY_CONTRACT
            or report.get("fingerprint")!=_fingerprint(
                {k:v for k,v in report.items() if k!="fingerprint"})
            or report.get("actual_fills")!=0 or report.get("valid_historical_alpha") is not False):
        raise JournalError("V55_UNQUALIFIED_REPORT_FOR_AUDIT")
    if path.exists() or path.is_symlink():
        raise JournalError("V55_JOURNAL_OUTPUT_EXISTS")
    entries=report.get("events")
    if not isinstance(entries,list) or not entries:
        raise JournalError("V55_JOURNAL_EVENTS_MISSING")
    manifest={"report_fingerprint":report["fingerprint"],
              "source_query_id":report.get("source_query_id"),
              "source_sha256":report.get("source_sha256"),
              "strategy_version":report["strategy_version"],
              "published_tick_strategy_reproduced":False}
    close={"report_fingerprint":report["fingerprint"],
           "runtime_event_count":len(entries),"disposition":report["status"],
           "terminal_equity_if_resolved":report["terminal_equity_if_resolved"]}
    records=[("RUN_MANIFEST",manifest),*[
        ("RUNTIME_EVENT",{"index":i,"event":event}) for i,event in enumerate(entries)],
        ("RUN_CLOSEOUT",close)]
    path.parent.mkdir(parents=True,exist_ok=True)
    prev=None
    milestone=10
    with path.open("xb") as stream:
        for i,(kind,data) in enumerate(records):
            row=_record(i,prev,kind,data)
            blob=(json.dumps(row,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
            if len(blob)>MAX_LINE_BYTES:
                raise JournalError("V55_JOURNAL_EVENT_OVERSIZE")
            stream.write(blob)
            prev=row["sha256"]
            if (i+1)%512==0:
                stream.flush()
                os.fsync(stream.fileno())
            while progress and milestone<=100 and 100*(i+1)>=milestone*len(records):
                progress(f"PROGRESS_{milestone}PCT phase=journal_write"
                         f" completed={i+1}/{len(records)}"
                         f" percent={100*(i+1)/len(records):.1f}")
                milestone+=10
        stream.flush()
        os.fsync(stream.fileno())
    verified=verify_journal(path)
    if verified["report_fingerprint"]!=report["fingerprint"]:
        raise JournalError("V55_JOURNAL_REPORT_FINGERPRINT_DISAGREES")
    return verified
