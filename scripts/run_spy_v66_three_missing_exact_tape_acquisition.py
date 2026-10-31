from __future__ import annotations

"""V66 exact missing three SPY option tapes: bounded, audited, no retries.

Source-only. Verify V65 June 9-20 signed report; select only its three
registered missing exact source IDs. Read V38 SQLite mode=ro before EACH
source. If absent, create an immutable, fsynced dispatch intent before
calling V38's existing read-through source archive. Never repeat a
FAILED_RETRYABLE / IN_FLIGHT / unknown-state exact query. On first failure,
write a censored summary and stop; caller can audit/recover only via verified
original receipts. No equity reconstruction, no broker orders.
"""

import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import time
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import (
    normalize_source_requirement,read_through_historical_options,
)
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only
from scripts.run_spy_v65_full_june_offline_simulator_readiness import (
    _lookup_source_receipt,
)

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v66-june-2025-three-exact-missing-spy-options-source-acquisition-v1"
V65="atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1"
V65_SHA="26f6cd1ce497f08094f9001b56f60a600d0d547ab786e528912546eb7039486c"
SCOPE={
    "2025-06-16":{
        "query":"669d16e1df78897005e93cf81de93ba929bea7a7eb8e0f95c0bdab8ae8e0dbea",
        "strike":"602","right":"call","decision":"2025-06-16T09:42:01-04:00",
    },
    "2025-06-18":{
        "query":"23b8b0b6bf2e178568b9e5d52b8b7a5f9fe0df8b87b06ec3ca348191b8621bd4",
        "strike":"599","right":"call","decision":"2025-06-18T09:48:01-04:00",
    },
    "2025-06-20":{
        "query":"20113f0f56ec7c7476f73d467f6b567e31a4d8e5c479e4f379bf657548c98b5c",
        "strike":"599","right":"call","decision":"2025-06-20T09:38:01-04:00",
    },
}


class V66Error(ValueError):
    pass


def info(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",flush=True)


def signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def write_once(path,payload):
    """Immutable report/intent, flush to disk before any external call."""
    raw=(json.dumps(payload,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()
    with path.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def input_sessions(path,*,expected_report_fingerprint=V65_SHA):
    if path.is_symlink() or not path.is_file():
        raise V66Error("V66_V65_ORIGINAL_REPORT_MISSING")
    report=json.loads(path.read_text(encoding="utf8"))
    digest=report.get("fingerprint")
    if digest!=_fingerprint({k:v for k,v in report.items()
                            if k!="fingerprint"}):
        raise V66Error("V66_V65_FINGERPRINT_CHANGED")
    if (report.get("contract")!=V65 or digest!=expected_report_fingerprint
            or report.get("start")!="2025-06-09"
            or report.get("end")!="2025-06-20"
            or report.get("weekdays_in_calendar_scope")!=10
            or report.get("provider_requests")!=0
            or report.get("broker_orders")!=0
            or len(report.get("session_reports",[]))!=10):
        raise V66Error("V66_FROZEN_V65_REPORT_IDENTITY_INVALID")
    by_day={x["session"]:x for x in report["session_reports"]}
    if len(by_day)!=10:
        raise V66Error("V66_DUPLICATE_V65_SESSION")
    result=[]
    for day,expected in sorted(SCOPE.items()):
        row=by_day[day]
        receipt=row.get("exact_option_receipt")
        selected=row.get("selected_contract")
        req=row.get("exact_option_requirement")
        if (row.get("signal_status")!="COMPLETED_BAR_BREAKOUT_DEVELOPMENT"
                or row.get("signal_decision_at_et")!=expected["decision"]
                or row.get("standalone_replay_disposition")!="NO_ENTRY"
                or row.get("standalone_replay_censor_reason")!="OPTION_SOURCE_MISSING_OR_UNQUALIFIED"
                or not isinstance(receipt,dict)
                or receipt.get("state")!="NOT_REGISTERED"
                or receipt.get("query_id")!=expected["query"]
                or not isinstance(selected,dict)
                or selected.get("right")!=expected["right"]
                or selected.get("strike")!=expected["strike"]
                or selected.get("date_et")!=day
                or selected.get("expiration")!=day
                or selected.get("symbol")!="SPY"
                or not isinstance(req,dict)
                or req.get("method")!="option_history_exact_quote_tape"):
            raise V66Error("V66_MISSING_DAY_FROZEN_REQUIREMENT_CHANGED")
        normalized=normalize_source_requirement(req["method"],req["kwargs"])
        if (normalized!=req or _fingerprint(normalized)!=expected["query"]):
            raise V66Error("V66_FROZEN_QUERY_FINGERPRINT_CHANGED")
        result.append({"session":day,"query_id":expected["query"],
                       "source_requirement":normalized,
                       "v65_session_fingerprint":row["fingerprint"],
                       "decision_at_et":expected["decision"]})
    return digest,result


def dispatch(v65_report,outdir,*,setting_fn=load_settings,
             receipt_reader=None,cache_get=_local_cache_only,
             source_get=read_through_historical_options,
             expected_report_fingerprint=V65_SHA,emit=info):
    if outdir.exists() or outdir.is_symlink():
        raise V66Error("V66_IMMUTABLE_OUTPUT_DIRECTORY_EXISTS")
    parent,requests=input_sessions(v65_report,
                                   expected_report_fingerprint=expected_report_fingerprint)
    settings=setting_fn(ROOT,"development")
    outdir.mkdir(parents=True,exist_ok=False)
    emitted=[]
    state="COMPLETE_SOURCE_CENSUS"
    emit(f"START V66 frozen_parent={parent[:12]} candidates={len(requests)}"
         " read_through_on_verified_new_scope_only=True"
         " duplicate_or_ambiguous_request_retry=False broker_orders=0")
    for idx,scope in enumerate(requests,1):
        day=scope["session"]
        requirement=scope["source_requirement"]
        query_id=scope["query_id"]
        inspect=_lookup_source_receipt(settings,requirement,reader=receipt_reader)
        if inspect["query_id"]!=query_id:
            raise V66Error("V66_V38_READONLY_QUERY_IDENTITY_CHANGED")
        emit(f"STAGE_START day={day} index={idx}/{len(requests)}"
             f" exact_query={query_id} prior_state={inspect['state']}")
        item={
            "session":day,"query_id":query_id,"exact_requirement":requirement,
            "v65_session_fingerprint":scope["v65_session_fingerprint"],
            "decision_at_et":scope["decision_at_et"],
            "preflight_cache_receipt":inspect,
            "result":None,"source_sha256":None,"rows":None,
            "duration_seconds":None,
            "broker_orders":0,
        }
        if inspect["state"] in ("FAILED_RETRYABLE","IN_FLIGHT"):
            item["result"]="ABSTAIN_AMBIGUOUS_PRIOR_DISPATCH_NO_RETRY"
            state="COMPLETE_WITH_BLOCKED_SOURCES"
            emitted.append(item)
            emit(f"BLOCKED V66 query={query_id} state={inspect['state']}"
                 " same_request_retry_prohibited=True"
                 " continue_with_distinct_demands=True")
            write_once(outdir/f"scope_{idx:02d}_{day}.json",signed(item))
            continue
        if inspect["state"]=="NO_DATA_EXPLICIT":
            item["result"]="CACHED_EXPLICIT_NO_DATA"
            emitted.append(item)
            write_once(outdir/f"scope_{idx:02d}_{day}.json",signed(item))
            continue
        if inspect["state"]=="ARCHIVED":
            verified=cache_get(settings,query_id)
            source=verified.get("source")
            if (verified.get("cache_evidence")!="CACHE_HIT"
                    or not isinstance(source,dict)
                    or source.get("query_id")!=query_id
                    or source.get("exact_requirement")!=requirement
                    or source.get("source_sha256")!=inspect["archive_sha256"]):
                raise V66Error("V66_ORIGINAL_ARCHIVED_SOURCE_SHA_INVALID")
            item["result"]="ORIGINAL_ARCHIVE_VERIFIED_REUSED"
            item["source_sha256"]=source["source_sha256"]
            item["rows"]=len(source["source_rows"])
            emitted.append(item)
            write_once(outdir/f"scope_{idx:02d}_{day}.json",signed(item))
            emit(f"STAGE_PASS cache_verified day={day} rows={item['rows']}"
                 " requests=0")
            continue
        if inspect["state"]!="NOT_REGISTERED":
            raise V66Error("V66_UNRECOGNIZED_V38_PRECALL_STATE")
        # An fsynced, immutable dispatch intent is persisted BEFORE the new
        # provider attempt. Another run's preflight refuses failed/inflight.
        intent=signed({
            "contract":CONTRACT,"session":day,"query_id":query_id,
            "exact_requirement":requirement,
            "status":"RESERVED_INTENT_BEFORE_ONE_POSSIBLE_PROVIDER_DISPATCH",
            "pre_dispatch_receipt_state":inspect["state"],
            "automatic_same_query_retry":False,
            "broker_orders":0,
        })
        write_once(outdir/f"intent_{idx:02d}_{day}.json",intent)
        began=time.monotonic()
        try:
            response=source_get(settings,requirement["method"],
                                dict(requirement["kwargs"]))
            if (not isinstance(response,dict)
                    or response.get("query_id")!=query_id
                    or response.get("exact_requirement")!=requirement):
                raise V66Error("V66_V38_PROVIDER_SOURCE_IDENTITY_CHANGED")
            status=response.get("status")
            if status in ("FETCHED_AND_ARCHIVED","CACHE_HIT"):
                verified=cache_get(settings,query_id)
                source=verified.get("source")
                if (verified.get("cache_evidence")!="CACHE_HIT"
                        or not isinstance(source,dict)
                        or source.get("query_id")!=query_id
                        or source.get("exact_requirement")!=requirement
                        or source.get("source_sha256")!=response["source_sha256"]):
                    raise V66Error("V66_V38_NEW_SOURCE_ARCHIVE_SHA_INVALID")
                item["result"]="SOURCE_ARCHIVED_AND_REVERIFIED"
                item["source_sha256"]=source["source_sha256"]
                item["rows"]=len(source["source_rows"])
            elif status in ("FETCHED_EXPLICIT_NO_DATA","CACHED_EXPLICIT_NO_DATA"):
                item["result"]="SOURCE_EXPLICIT_NO_DATA"
                item["rows"]=0
            else:
                raise V66Error("V66_V38_SOURCE_STATUS_UNVERIFIED")
            item["duration_seconds"]=round(time.monotonic()-began,3)
            emit(f"STAGE_PASS day={day} source={item['result']}"
                 f" rows={item['rows']} elapsed={item['duration_seconds']}s")
        except Exception as exc:
            item["duration_seconds"]=round(time.monotonic()-began,3)
            item["result"]="STOPPED_SOURCE_FAILURE_DISPATCH_OUTCOME_UNKNOWN"
            item["exception_type_only"]=type(exc).__name__
            state="COMPLETE_WITH_BLOCKED_SOURCES"
            emit(f"STAGE_BLOCKED day={day} error_class={type(exc).__name__}"
                 " provider_reached_unknown=True no_same_query_retry=True"
                 " remaining_independent_sources_continue=True")
            emitted.append(item)
            write_once(outdir/f"scope_{idx:02d}_{day}.json",signed(item))
            continue
        emitted.append(item)
        write_once(outdir/f"scope_{idx:02d}_{day}.json",signed(item))
    counts=dict(sorted(Counter(x["result"] for x in emitted).items()))
    doc=signed({
        "contract":CONTRACT,"status":state,
        "frozen_v65_report_fingerprint":parent,
        "selected_days":list(SCOPE),
        "candidate_exact_source_scopes":len(requests),
        "completed_scopes":len(emitted),
        "per_scope":emitted,"result_counts":counts,
        "remaining_not_attempted":[x["session"] for x in requests[len(emitted):]],
        "new_provider_request_count_upper_bound":sum(
            x["preflight_cache_receipt"]["state"]=="NOT_REGISTERED"
            for x in emitted),
        "actual_provider_dispatch_receipt":"UNKNOWN_IF_FAILED_OR_TIMED_OUT",
        "no_ambiguous_same_query_retries":True,
        "no_global_source_count_or_strategy_universe_limit":True,
        "independent_missing_sources_continue_after_failure":True,
        "source_only":True,"broker_orders":0,"historical_broker_fills":0,
        "cash_account_updated":False,"cumulative_account_not_simulated":True,
        "historical_profitability_validated":False,
    })
    write_once(outdir/"summary.json",doc)
    emit(f"COMPLETE V66 status={state} completed={len(emitted)}/{len(requests)}"
         f" counts={counts} report={outdir/'summary.json'}"
         " broker_orders=0")
    return doc


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v65-report",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        doc=dispatch(a.v65_report,a.output_dir)
        return 0 if doc["status"]=="COMPLETE_SOURCE_CENSUS" else 2
    except Exception as exc:
        info(f"STOPPED V66 exception_type={type(exc).__name__}"
             " no_automatic_retry=True broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
