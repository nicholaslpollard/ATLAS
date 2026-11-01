from __future__ import annotations

"""V95 forensic census of original 2020 May-01 ambiguous V89 requests.

NO provider, ThetaData, broker, SQLite mutation or source re-dispatch.
All input original V89 signed reports are immutable. Verify each original
progress event SHA chain and exact original demand/receipt identity, then
probe only unresolved query IDs against the original V38 cache in read-only
SQLite mode. Output a signed complete original-demand census. Missing
sources are UNKNOWN, never zero-value trades or optional ignored dates.
"""

import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import normalize_source_requirement
from packages.simulation.spy_v89_six_family_causal_registry import FAMILIES,signed,verified
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only
from scripts.run_spy_v90_six_family_source_replay import read_signed,V89

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v95-2020-original-source-read-only-reconciliation-v1"


class V95Error(ValueError):
    pass


def write_once(path,body):
    obj=signed(body)
    with path.open("x",encoding="utf8") as out:
        json.dump(obj,out,sort_keys=True,indent=2,allow_nan=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    return obj


def audit_2020(source_dir,output,*,settings_factory=load_settings,
               cache_reader=_local_cache_only,reporter=print):
    if (not source_dir.is_dir() or source_dir.is_symlink()
            or output.exists() or output.is_symlink()):
        raise V95Error("V95_ORIGINAL_SOURCE_DIRECTORY_OR_IMMUTABLE_OUTPUT_INVALID")
    entry=read_signed(source_dir/"entry_screen.json",V89)
    plan=read_signed(source_dir/"exact_option_source_plan.json",V89+"-source-plan-v1")
    receipts=read_signed(source_dir/"source_receipts.json",V89+"-source-receipts-v1")
    summary=read_signed(source_dir/"summary.json",V89+"-summary-v1")
    if (entry["start"]!="2020-01-01" or entry["end"]!="2020-12-31"
            or entry["registry"]!=FAMILIES
            or entry["registry_sha"]!=_fingerprint(FAMILIES)
            or len(entry["cases"])!=entry["sessions"]*len(FAMILIES)
            or plan["parent_entry_sha"]!=entry["fingerprint"]
            or receipts["parent_plan_sha"]!=plan["fingerprint"]
            or summary["entry_sha"]!=entry["fingerprint"]
            or summary["source_plan_sha"]!=plan["fingerprint"]
            or summary["receipt_sha"]!=receipts["fingerprint"]
            or summary["source_resolution"]["source_uses_requested"]!=len(plan["demands"])
            or summary["exact_source_requirements"]!=len(plan["demands"])
            or summary["all_required_sources_archived"] is not False
            or summary["broker_orders"]!=0
            or receipts["broker_orders"]!=0):
        raise V95Error("V95_ORIGINAL_2020_SOURCE_ROOTS_OR_QUALIFICATION_CHANGED")
    eventfile=source_dir/"source_events.jsonl"
    if not eventfile.is_file() or eventfile.is_symlink():
        raise V95Error("V95_ORIGINAL_APPEND_ONLY_SOURCE_EVENTS_MISSING")
    terminal={}
    events=[]
    previous=None
    with eventfile.open("r",encoding="utf8") as inp:
        for line in inp:
            event=json.loads(line)
            if (not verified(event)
                    or event.get("sequence")!=len(events)+1
                    or event.get("parent_event_sha")!=previous
                    or event.get("contract")!=V89+"-append-only-source-event-v1"):
                raise V95Error("V95_ORIGINAL_SOURCE_EVENT_SHA_CHAIN_INVALID")
            events.append(event)
            previous=event["fingerprint"]
            if event["event"] in ("source_done","source_failed","source_blocked"):
                cid=event["candidate_id"]
                if cid in terminal:
                    raise V95Error("V95_MULTIPLE_TERMINAL_EVENTS_FOR_ONE_ORIGINAL_CANDIDATE")
                terminal[cid]=event
    if (len(events)!=receipts["source_event_count"]
            or previous!=receipts["last_event_sha"]):
        raise V95Error("V95_ORIGINAL_EVENT_SHA_HEAD_DRIFT")
    used={}
    for receipt in receipts["original_provider_source_receipts"]:
        cid=receipt["candidate_id"]
        if (cid in used or receipt["status"] not in ("CACHE_HIT","FETCHED_AND_ARCHIVED")
                or len(receipt.get("source_sha256") or "")!=64):
            raise V95Error("V95_ORIGINAL_COMPLETE_SOURCE_RECEIPT_INVALID")
        used[cid]=receipt
    demands={}
    for d in plan["demands"]:
        cid=d["candidate_id"]
        normalized=normalize_source_requirement(d["method"],d["kwargs"])
        if (not verified(d) or cid in demands
                or d["query_id"]!=_fingerprint(normalized)
                or (d["kwargs"]["date_et"][:4]!="2020")
                or cid not in terminal
                or terminal[cid]["query_id"]!=d["query_id"]):
            raise V95Error("V95_ORIGINAL_OPTION_DEMAND_IDENTITY_CHANGED")
        demands[cid]=d
    if set(used)-set(demands) or set(terminal)!=set(demands):
        raise V95Error("V95_ORIGINAL_DEMAND_RECEIPT_OR_EVENT_CENSUS_INCOMPLETE")
    settings=settings_factory(ROOT,"development")
    result=[]
    for cid,d in demands.items():
        t=terminal[cid]
        completed=used.get(cid)
        if completed:
            if (t["event"]!="source_done"
                    or t["source_status"]!=completed["status"]
                    or completed["query_id"]!=d["query_id"]):
                raise V95Error("V95_ORIGINAL_COMPLETION_DISAGREES_WITH_EVENT")
            status="ORIGINAL_SIGNED_ARCHIVED_RECEIPT"
            new_sha=completed["source_sha256"]
            evidence="ORIGINAL_VERIFIED_RECEIPT"
        else:
            if (t["event"] not in ("source_failed","source_blocked")
                    or t["source_status"] not in (
                        "SOURCE_DISPATCH_OUTCOME_UNKNOWN",
                        "SOURCE_RECONCILIATION_REQUIRED",
                        "SOURCE_ACQUISITION_REVIEW_REQUIRED")):
                raise V95Error("V95_UNEXPECTED_ORIGINAL_UNRESOLVED_SOURCE_CLASS")
            # Never pass unresolved request to read_through_historical_options:
            # that method can change FAILED_RETRYABLE to IN_FLIGHT and
            # re-dispatch a previously attempted source.
            try:
                cached=cache_reader(settings,d["query_id"])
                evidence=cached.get("cache_evidence","NO_CACHE_EVIDENCE")
                source=cached.get("source")
                new_sha=source.get("source_sha256") if source else None
                status=("READ_ONLY_VERIFIED_V38_ARCHIVE_PRESENT"
                        if evidence=="CACHE_HIT" and len(new_sha or "")==64
                        else "UNRESOLVED_ORIGINAL_PROVIDER_OUTCOME")
            except Exception as exc:
                evidence="CACHE_READ_ONLY_VERIFICATION_ERROR"
                new_sha=None
                status="UNRESOLVED_ORIGINAL_PROVIDER_OUTCOME"
                err=type(exc).__name__
                reporter(f"V95 unresolved original cache read exception_type={err} "
                         f"date={d['kwargs']['date_et']}; no retry")
        result.append({
            "candidate_id":cid,"query_id":d["query_id"],
            "original_demand_sha":d["fingerprint"],
            "session":d["kwargs"]["date_et"],
            "strategy":cid.split("_",2)[2].rsplit("_",1)[0],
            "original_event_sha":t["fingerprint"],
            "original_terminal_status":t["source_status"],
            "reconciliation_status":status,
            "read_only_v38_cache_evidence":evidence,
            "original_or_verified_cache_source_sha256":new_sha,
            "provider_retries":0,"broker_orders":0,
        })
    if len(result)!=len(plan["demands"]):
        raise V95Error("V95_INCOMPLETE_ORIGINAL_2020_CENSUS")
    counts=dict(sorted(Counter(x["reconciliation_status"] for x in result).items()))
    unresolved=[x for x in result if x["reconciliation_status"]=="UNRESOLVED_ORIGINAL_PROVIDER_OUTCOME"]
    output.mkdir(parents=True,exist_ok=False)
    forensic=write_once(output/"source_census.json",{
        "contract":CONTRACT+"-source-census-v1",
        "original_entry_sha":entry["fingerprint"],
        "original_plan_sha":plan["fingerprint"],
        "original_receipts_sha":receipts["fingerprint"],
        "original_summary_sha":summary["fingerprint"],
        "original_event_chain_sha":receipts["last_event_sha"],
        "original_source_demands":len(plan["demands"]),
        "source_dispositions":result,
        "source_counts":counts,
        "unresolved_candidate_ids":[x["candidate_id"] for x in unresolved],
        "source_recovery_was_read_only":True,
        "all_original_source_data_qualified":not unresolved,
        "unknown_2020_quote_pnl_censored":bool(unresolved),
        "never_use_missing_data_as_zero_or_no_signal":True,
        "provider_requests":0,"broker_orders":0,
    })
    summary_report=write_once(output/"summary.json",{
        "contract":CONTRACT,
        "original_2020_v89_summary_sha":summary["fingerprint"],
        "source_census_sha":forensic["fingerprint"],
        "original_source_requirements":len(result),
        "original_signed_complete_receipts":len(used),
        "extra_original_source_requirements_read_only_archived":
            counts.get("READ_ONLY_VERIFIED_V38_ARCHIVE_PRESENT",0),
        "unresolved_2020_source_requirements":len(unresolved),
        "eligible_for_complete_2020_full_year_quote_pnl":not unresolved,
        "2020_status":"COMPLETE_SOURCE_RECONCILED_OFFLINE" if not unresolved
                      else "INCOMPLETE_PNL_UNKNOWABLE_UNTIL_SOURCE_RECONCILIATION",
        "protected_holdout_accessed":False,
        "provider_requests":0,"broker_orders":0,
    })
    reporter(f"V95_2020_READ_ONLY source_demands={len(result)} "
             f"signed_complete={len(used)} "
             f"new_verified_cached={counts.get('READ_ONLY_VERIFIED_V38_ARCHIVE_PRESENT',0)} "
             f"unresolved={len(unresolved)} provider_calls=0 broker_orders=0")
    return summary_report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-2020-v89-dir",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        audit_2020(args.original_2020_v89_dir,args.output_dir)
        return 0
    except Exception as exc:
        print(f"STOP V95 2020 FORENSIC type={type(exc).__name__} "
              "provider_gets=0 broker_orders=0",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
