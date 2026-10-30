from __future__ import annotations

"""Persist V50 modeled option-pair replay as immutable hash-chained event evidence.

Events are already chronological as emitted by runtime; journal preserves every
decision, rejected candidate, quote review, modeled event and unresolved mark.
This does NOT authorize provider/broker actions or establish real fills.
"""

import json
import os
from pathlib import Path

from packages.simulation.options_opportunity_trace_v49 import fingerprint
from packages.simulation.options_pair_chronological_runtime_v50 import (
    CONTRACT as SIMULATOR_CONTRACT, PairReplayError,
)

CONTRACT="atlas-options-pair-chronological-audit-journal-v50"
EVENT_BYTE_CEILING=256*1024


def _signed(seq: int, previous: str | None, typ: str, payload: dict) -> dict:
    rec={"contract":CONTRACT,"seq":seq,"previous_sha256":previous,
         "event_type":typ,"payload":payload}
    rec["sha256"]=fingerprint(rec)
    return rec


def verify_runtime_journal(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise PairReplayError("V50_JOURNAL_FILE_UNAVAILABLE")
    prev=None
    events=0
    manifest=None
    closeout=None
    saw_closeout=False
    with path.open("rt",encoding="utf-8") as f:
        for seq,line in enumerate(f):
            if len(line.encode("utf-8"))>EVENT_BYTE_CEILING:
                raise PairReplayError("V50_OVERSIZED_JOURNAL_RECORD")
            try:
                rec=json.loads(line)
            except (TypeError,ValueError) as exc:
                raise PairReplayError("V50_INVALID_JOURNAL_JSON") from exc
            observed=rec.get("sha256")
            if (rec.get("contract")!=CONTRACT or rec.get("seq")!=seq
                    or rec.get("previous_sha256")!=prev
                    or observed!=fingerprint({k:v for k,v in rec.items() if k!="sha256"})):
                raise PairReplayError("V50_JOURNAL_SEQUENCE_OR_DIGEST_INVALID")
            typ=rec.get("event_type")
            if seq==0:
                if typ!="RUN_MANIFEST":
                    raise PairReplayError("V50_RUN_MANIFEST_REQUIRED_FIRST")
                manifest=rec["payload"]
            elif typ=="RUN_CLOSEOUT":
                if saw_closeout:
                    raise PairReplayError("V50_DUPLICATE_CLOSEOUT")
                closeout=rec["payload"]
                saw_closeout=True
            elif typ=="RUNTIME_EVENT" and not saw_closeout:
                if rec["payload"].get("seq")!=events:
                    raise PairReplayError("V50_RUNTIME_EVENT_SEQUENCE_INVALID")
                events+=1
            else:
                raise PairReplayError("V50_UNKNOWN_EVENT_OR_POST_CLOSEOUT")
            prev=observed
    if (manifest is None or closeout is None
            or events!=closeout.get("events_logged")
            or manifest.get("simulation_fingerprint")!=closeout.get("simulation_fingerprint")
            or closeout.get("terminal_equity_if_fully_resolved")
                !=manifest.get("terminal_equity_if_fully_resolved")):
        raise PairReplayError("V50_TRUNCATED_OR_MISMATCHED_JOURNAL")
    return {
        "contract":CONTRACT,"runtime_events":events,
        "total_journal_records":events+2,
        "simulation_fingerprint":manifest["simulation_fingerprint"],
        "final_record_sha256":prev,
        "historical_fills_claimed":0,
    }


def save_runtime_journal(path: Path, replay: dict) -> dict:
    if (not isinstance(replay,dict)
            or replay.get("contract")!=SIMULATOR_CONTRACT
            or replay.get("fingerprint")!=fingerprint(
                {k:v for k,v in replay.items() if k!="fingerprint"})
            or replay.get("broker_orders_or_fills")!=0
            or replay.get("strategy_pnl_validated") is not False):
        raise PairReplayError("V50_UNVERIFIED_SIMULATION_RESULT")
    if path.is_symlink() or path.exists():
        raise PairReplayError("V50_JOURNAL_ALREADY_EXISTS")
    events=replay.get("events")
    if not isinstance(events,list):
        raise PairReplayError("V50_EVENTS_MISSING")
    payloads=[
        ("RUN_MANIFEST",{
            "runtime_contract":SIMULATOR_CONTRACT,
            "simulation_fingerprint":replay["fingerprint"],
            "policy":replay["policy"],
            "opportunities_evaluated":replay["opportunities_evaluated"],
            "terminal_equity_if_fully_resolved":replay["terminal_equity_if_fully_resolved"],
            "no_historical_fills":True,
        }),
        *[("RUNTIME_EVENT",ev) for ev in events],
        ("RUN_CLOSEOUT",{
            "simulation_fingerprint":replay["fingerprint"],
            "events_logged":len(events),
            "modeled_quote_reference_entries":replay["modeled_quote_reference_entries"],
            "modeled_quote_reference_exits":replay["modeled_quote_reference_exits"],
            "terminal_equity_if_fully_resolved":replay["terminal_equity_if_fully_resolved"],
            "unresolved_position_id":replay["open_unresolved_position_id"],
        }),
    ]
    path.parent.mkdir(parents=True,exist_ok=True)
    prev=None
    with path.open("xb") as f:
        for seq,(typ,payload) in enumerate(payloads):
            record=_signed(seq,prev,typ,payload)
            line=(json.dumps(record,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
            if len(line)>EVENT_BYTE_CEILING:
                raise PairReplayError("V50_OVERSIZED_JOURNAL_RECORD")
            f.write(line)
            if (seq+1)%64==0:
                f.flush()
                os.fsync(f.fileno())
            prev=record["sha256"]
        f.flush()
        os.fsync(f.fileno())
    checked=verify_runtime_journal(path)
    if checked["simulation_fingerprint"]!=replay["fingerprint"]:
        raise PairReplayError("V50_JOURNAL_VERIFICATION_FAILED")
    return checked
