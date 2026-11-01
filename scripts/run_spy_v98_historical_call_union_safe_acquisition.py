from __future__ import annotations

"""V98: signed, source-only qualified CALL union, read-only V38 audit and
optional first-time acquisition through V39's ambiguous-dispatch no-retry gate.
No historical options PnL, model selection, paper/live orders, or news signals.
"""

import argparse
from collections import Counter
from contextlib import closing
from datetime import date,datetime,timedelta
import json
import os
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import (
    DB_REL,_unpack,normalize_source_requirement,OnDemandSourceError,
)
from packages.simulation.strategy_options_source_runtime_v39 import (
    resolve_strategy_source_demands,
)
from scripts.run_spy_v97b_49_variant_call_source_union_preview import (
    CONTRACT as V97B,read as read97b,historical_expiry,
)

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v98-qualified-historical-call-source-union-v1"
REQUIREMENT_METHOD="option_history_exact_quote_tape"
EXPECTED_PREVIEW=226
STATUS_NEW="NEW_EXACT_CALL_SOURCE_SCOPE_REQUIRES_SEPARATE_REVIEW"
STATUS_OLD="EXACT_ORIGINAL_CALL_SOURCE_ALREADY_ARCHIVED"
STATUS_UNKNOWN="ORIGINAL_PROVIDER_DISPATCH_UNKNOWN_NO_RETRY"


class V98Error(ValueError):
    pass


def signed(row):
    return {**row,"fingerprint":_fingerprint(row)}


def write_once(path,row):
    result=signed(row)
    with path.open("x",encoding="utf8") as fp:
        json.dump(result,fp,sort_keys=True,indent=2,allow_nan=False)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    return result


def local_cutoff(session,calendar):
    day=date.fromisoformat(session)
    if not historical_expiry(session):
        raise V98Error("HISTORICAL_EXPIRY_BASE_SCHEDULE_NOT_QUALIFIED")
    if day not in calendar.sessions_in_range(day,day):
        raise V98Error("HISTORICAL_XNYS_MARKET_SESSION_ABSENT")
    close=calendar.regular_open_close(day)[1].astimezone(ET)
    if close.date()!=day:
        raise V98Error("HISTORICAL_SESSION_CLOSE_DATE_DRIFT")
    early=close.hour<16
    end=(close-timedelta(minutes=55)).strftime("%H:%M:%S") if early else "15:30:00"
    return end+".000"


def build_requirement(info,calendar):
    if (info["symbol"]!="SPY" or info["right"]!="call"
            or info["source_contract_identity"]!="SPY_0DTE_1S_CALL"
            or info["session"]!=info["expiry"]
            or info["decision_clock_et"] not in ("09:35:01","09:40:01")
            or not isinstance(info["strike"],str)
            or not isinstance(info["strategy_variants"],list)
            or not info["strategy_variants"]
            or info.get("provider_calls")!=0
            or info.get("broker_orders")!=0):
        raise V98Error("V98_HISTORICAL_NEW_CALL_PREVIEW_SCOPE_INVALID")
    start=info["decision_clock_et"]+".000"
    args={
        "symbol":"SPY","date_et":info["session"],"expiration":info["expiry"],
        "strike":info["strike"],"right":"call",
        "start_time_et":start,
        "end_time_et":local_cutoff(info["session"],calendar),
        "interval":"1s",
    }
    normalized=normalize_source_requirement(REQUIREMENT_METHOD,args)
    return {"method":REQUIREMENT_METHOD,"kwargs":normalized["kwargs"],
            "query_id":_fingerprint(normalized),
            "full_normalized_requirement_sha":_fingerprint(normalized)}


def original_event_requirement(event,calendar):
    # Do NOT accept only matching date/strike: the query includes the exact
    # historical source start and early-close end as well as the option right.
    info={
        "symbol":"SPY","session":event["session"],"expiry":event["expiry"],
        "right":"call","strike":event["strike"],
        "decision_clock_et":event["decision_clock_et"],
        "source_contract_identity":"SPY_0DTE_1S_CALL",
        "strategy_variants":[event["trial_id"]],
        "provider_calls":0,"broker_orders":0,
    }
    return build_requirement(info,calendar)


def verify_preview(directory,calendar):
    summary=read97b(directory/"summary.json",V97B)
    events=read97b(directory/"call_only_candidate_source_coverage.json",
                   V97B+"-all-variant-causes-v1")
    plan=read97b(directory/"new_exact_call_source_union_preview.json",
                 V97B+"-missing-source-union-preview-v1")
    if (summary["candidate_coverage_sha"]!=events["fingerprint"]
            or summary["new_source_union_preview_sha"]!=plan["fingerprint"]
            or summary["input_v97a_summary_sha"]!=events["input_v97a_summary_sha"]
            or summary["input_v97a_considerations_sha"]!=events["input_v97a_considerations_sha"]
            or plan["original_candidate_coverage_sha"]!=events["fingerprint"]
            or summary["preregistered_entry_variants"]!=49
            or summary["candidate_variant_occurrences"]!=2482
            or summary["new_exact_distinct_call_scopes_to_review"]!=EXPECTED_PREVIEW
            or summary["original_distinct_unknown_exact_call_scopes"]!=1
            or len(plan["union_new_source_scopes"])!=EXPECTED_PREVIEW
            or summary["provider_requests"]!=0 or summary["broker_orders"]!=0
            or events["provider_requests"]!=0 or events["broker_orders"]!=0
            or plan["provider_requests"]!=0 or plan["broker_orders"]!=0
            or plan["no_paid_provider_dispatch_authorized"] is not True):
        raise V98Error("V98_UNSIGNED_OR_MUTATED_V97B_PREVIEW_ANCESTRY")
    distinct={}
    events_new={}
    old_ids={}
    unknown_ids={}
    event_counts=Counter()
    for ev in events["candidate_events"]:
        status=ev["source_coverage_status"]
        if status not in (STATUS_NEW,STATUS_OLD,STATUS_UNKNOWN):
            raise V98Error("V98_UNKNOWN_PREVIEW_CANDIDATE_STATUS")
        req=original_event_requirement(ev,calendar)
        qid=req["query_id"]
        event_counts[status]+=1
        k=(ev["session"],ev["decision_clock_et"],ev["strike"])
        if status==STATUS_NEW:
            events_new.setdefault(k,set()).add(ev["trial_id"])
            if ev["original_call_query_id"] is not None:
                raise V98Error("V98_NEW_SCOPE_RELABELED_AS_ORIGINAL_SOURCE")
        else:
            if req["query_id"]!=ev["original_call_query_id"]:
                raise V98Error("V98_EXACT_ORIGINAL_QUERY_IDENTITY_OR_EARLY_CLOSE_DRIFT")
            if status==STATUS_OLD:
                if not isinstance(ev["original_archived_source_sha256"],str):
                    raise V98Error("V98_ORIGINAL_ARCHIVED_SHA_MISSING")
                previous=old_ids.setdefault(qid,ev["original_archived_source_sha256"])
                if previous!=ev["original_archived_source_sha256"]:
                    raise V98Error("V98_ORIGINAL_ARCHIVED_SHA_CONFLICT")
            else:
                if ev["original_archived_source_sha256"] is not None:
                    raise V98Error("V98_ORIGINAL_UNKNOWN_SOURCE_CANNOT_HAVE_SHA")
                unknown_ids[qid]=True
    if (event_counts!={STATUS_NEW:426,STATUS_OLD:2053,STATUS_UNKNOWN:3}
            or len(old_ids)!=351 or len(unknown_ids)!=1
            or set(old_ids)&set(unknown_ids)):
        raise V98Error("V98_ORIGINAL_EVENT_AND_QUERY_CENSUS_CHANGED")
    for item in plan["union_new_source_scopes"]:
        k=(item["session"],item["decision_clock_et"],item["strike"])
        if k in distinct or k not in events_new or (
            set(item["strategy_variants"])!=events_new[k]
        ):
            raise V98Error("V98_SOURCE_PLAN_NOT_MATCHED_TO_ORIGINAL_VARIANT_EVENTS")
        req=build_requirement(item,calendar)
        qid=req["query_id"]
        if qid in old_ids or qid in unknown_ids:
            raise V98Error("V98_UNSAFE_SOURCE_OVERLAP_WITH_ORIGINAL_OR_UNKNOWN_DISPATCH")
        distinct[k]={**item,**req}
    if set(distinct)!=set(events_new) or len(distinct)!=EXPECTED_PREVIEW:
        raise V98Error("V98_MISSING_NEW_SOURCE_EVENT_SCOPE")
    if len({d["query_id"] for d in distinct.values()})!=EXPECTED_PREVIEW:
        raise V98Error("V98_DUPLICATE_EXACT_PROVIDER_QUERY_ID")
    return summary,events,plan,sorted(distinct.values(),
        key=lambda d:(d["session"],d["decision_clock_et"],d["strike"]))


def read_only_v38_state(settings,items):
    settings.assert_external_storage_binding("options")
    db=settings.resolved_path(DB_REL)
    if db.is_symlink() or not db.is_file():
        raise V98Error("V98_ORIGINAL_V38_SOURCE_INDEX_NOT_PRESENT")
    output=[]
    with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",
                                 uri=True,timeout=30)) as conn:
        for item in items:
            expected=normalize_source_requirement(
                item["method"],item["kwargs"])
            qid=_fingerprint(expected)
            if qid!=item["query_id"]:
                raise V98Error("V98_CANONICAL_CALL_QUERY_ID_DRIFT")
            row=conn.execute(
                "SELECT query_id,request_json,state,touched,source_sha,"
                "gzip_sha,stored_path,source_rows FROM sources WHERE query_id=?",
                (qid,)).fetchone()
            status="NOT_REGISTERED"
            sha=None
            if row:
                if row[1]!=json.dumps(expected,sort_keys=True,separators=(",",":")):
                    raise V98Error("V98_V38_REQUEST_IDENTITY_DRIFT")
                if row[2]=="ARCHIVED":
                    cached=_unpack(settings,row,expected)
                    if cached["status"]!="CACHE_HIT":
                        raise V98Error("V98_CACHED_SOURCE_NOT_SHA_VERIFIED")
                    status="ARCHIVED_SHA_VERIFIED"
                    sha=cached["source_sha256"]
                elif row[2]=="NO_DATA_EXPLICIT":
                    cached=_unpack(settings,row,expected)
                    if cached["status"]!="CACHED_EXPLICIT_NO_DATA":
                        raise V98Error("V98_EXPLICIT_NO_DATA_STATE_CONFLICT")
                    status="EXPLICIT_NO_DATA"
                elif row[2] in ("FAILED_RETRYABLE","IN_FLIGHT"):
                    status="BLOCKED_POSSIBLY_DISPATCHED_NO_AUTO_RETRY"
                else:
                    raise V98Error("V98_UNRECOGNIZED_V38_SOURCE_STATE")
            output.append({
                "query_id":qid,"date_et":item["session"],
                "decision_clock_et":item["decision_clock_et"],
                "strike":item["strike"],"right":"call",
                "normalized_requirement":expected,
                "original_variant_ids":item["strategy_variants"],
                "read_only_v38_state":status,
                "read_only_source_sha256":sha,
                "new_request_eligible_for_first_dispatch":status=="NOT_REGISTERED",
                "query_retry_automatically_authorized":False,
            })
    return output


def run(preview_dir,output,*,acquire=False,
        settings_factory=load_settings,
        resolver=resolve_strategy_source_demands,
        calendar=None,reporter=print):
    if (type(acquire) is not bool or output.exists() or output.is_symlink()):
        raise V98Error("V98_MUTABLE_OUTPUT_OR_ACQUISITION_MODE_INVALID")
    calendar=calendar or get_market_calendar("XNYS")
    summary,events,original,distinct=verify_preview(preview_dir,calendar)
    settings=settings_factory(ROOT,"development")
    read_states=read_only_v38_state(settings,distinct)
    intended={r["query_id"] for r in distinct}
    observed=[r["query_id"] for r in read_states]
    if (len(read_states)!=len(distinct) or len(set(observed))!=len(observed)
            or set(observed)!=intended):
        raise V98Error("V98_READ_ONLY_QUERY_ID_CENSUS_INCOMPLETE_OR_MUTATED")
    counts=dict(sorted(Counter(x["read_only_v38_state"]
                               for x in read_states).items()))
    output.mkdir(parents=True,exist_ok=False)
    snapshot=write_once(output/"exact_call_source_union_audit.json",{
        "contract":CONTRACT+"-original-source-read-only-preflight-v1",
        "original_V97B_summary_sha":summary["fingerprint"],
        "original_V97B_events_sha":events["fingerprint"],
        "original_V97B_union_preview_sha":original["fingerprint"],
        "all_distinct_exact_historical_requirements":read_states,
        "source_states":counts,
        "prior_2020_ambiguous_original_query_blocked":True,
        "historical_exchange_contract_listing_not_independently_proven":True,
        "source_preflight_did_not_use_future_outcomes":True,
        "provider_calls":0,"broker_orders":0,
    })
    candidate=[r for r in read_states
               if r["read_only_v38_state"]=="NOT_REGISTERED"]
    reporter(f"V98 ORIGINAL READ-ONLY preflight unique_scopes={len(read_states)} "
             f"cached_sha={counts.get('ARCHIVED_SHA_VERIFIED',0)} "
             f"fresh={len(candidate)} "
             f"prior_uncertain={counts.get('BLOCKED_POSSIBLY_DISPATCHED_NO_AUTO_RETRY',0)} "
             f"explicit_no_data={counts.get('EXPLICIT_NO_DATA',0)} "
             "provider_calls=0 broker_orders=0")
    if not acquire:
        return write_once(output/"summary.json",{
            "contract":CONTRACT+"-summary-v1",
            "mode":"READ_ONLY_NO_NEW_PROVIDER_CALLS",
            "original_V97B_summary_sha":summary["fingerprint"],
            "preflight_sha":snapshot["fingerprint"],
            "source_states":counts,
            "fresh_first_dispatched_source_candidates":len(candidate),
            "simulator_pnl_not_calculated":True,
            "provider_dispatch_attempts":0,"broker_orders":0,
        })
    # V39 uses its own query-index transactions and blocks FAILED_RETRYABLE and
    # IN_FLIGHT regardless of 10-minute lease age. Our original signed plan
    # and append-only journal predate any possible GET.
    progress=[]
    previous=None
    def audit(event,detail):
        nonlocal previous
        obj=signed({
            "contract":CONTRACT+"-source-event-journal-v1",
            "sequence":len(progress)+1,
            "previous_event_sha":previous,
            "event":event,
            "candidate_id":detail.get("candidate_id"),
            "query_id":detail.get("query_id"),
            "date_et":detail.get("date_et"),
            "source_status":detail.get("status"),
            "error_type":detail.get("error"),
        })
        with (output/"source_events.jsonl").open("a",encoding="utf8") as f:
            f.write(json.dumps(obj,sort_keys=True)+"\n")
            f.flush();os.fsync(f.fileno())
        progress.append(obj)
        previous=obj["fingerprint"]
        if event in ("source_done","source_failed","source_blocked"):
            reporter(f"V98_SOURCE_{event.upper()} date={detail.get('date_et')} "
                     f"status={detail.get('status')} count={len(progress)}")
    receipts=[]
    def on_source(item,source):
        receipts.append({
            "candidate_id":item["candidate_id"],
            "query_id":source["query_id"],
            "source_sha256":source.get("source_sha256"),
            "status":source["status"],
            "source_row_count":len(source["source_rows"]),
        })
    source_intents=write_once(output/"first_dispatch_source_intents.json",{
        "contract":CONTRACT+"-source-intents-v1",
        "preflight_sha":snapshot["fingerprint"],
        "eligible_new_query_ids":[r["query_id"] for r in candidate],
        "blocked_prior_dispatches_not_in_queue":True,
        "cache_first_or_new_dispatch":True,
        "broker_orders":0,
    })
    def demands():
        for row in candidate:
            yield {
                "candidate_id":"V98_"+row["query_id"][:32],
                "purpose":"frozen_call_source_union_entry_exit",
                "method":row["normalized_requirement"]["method"],
                "kwargs":row["normalized_requirement"]["kwargs"],
            }
    outcome=resolver(
        settings,"spy_v98_call_only_entry_union_20261101",demands(),
        continue_on_error=True,on_source=on_source,on_progress=audit)
    if (outcome.get("contract")!="atlas-strategy-options-data-demand-runtime-v39"
            or outcome.get("source_uses_requested")!=len(candidate)):
        raise V98Error("V98_V39_SOURCE_RESOLUTION_CENSUS_CHANGED")
    result=write_once(output/"acquisition_results.json",{
        "contract":CONTRACT+"-source-results-v1",
        "original_preflight_sha":snapshot["fingerprint"],
        "dispatch_intents_sha":source_intents["fingerprint"],
        "runtime_source_result":outcome,
        "verified_cached_or_fetched_receipts":receipts,
        "source_events_sha_head":previous,
        "source_event_count":len(progress),
        "no_broker_orders":True,
        "no_simulated_pnl_or_trades":True,
    })
    return write_once(output/"summary.json",{
        "contract":CONTRACT+"-summary-v1","mode":"CACHE_FIRST_SOURCE_ONLY",
        "original_V97B_summary_sha":summary["fingerprint"],
        "preflight_sha":snapshot["fingerprint"],
        "acquisition_results_sha":result["fingerprint"],
        "source_states":counts,
        "fresh_first_dispatched_source_candidates":len(candidate),
        "provider_dispatch_attempts":outcome["provider_dispatch_attempts"],
        "source_uses_resolved":outcome["source_uses_resolved"],
        "source_uses_explicit_no_data":outcome["source_uses_explicit_no_data"],
        "source_uses_failed_or_unresolved":outcome["source_uses_failed_or_unresolved"],
        "simulator_pnl_not_calculated":True,
        "original_source_and_2020_unknowns_unmodified":True,
        "broker_orders":0,
    })


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v97b-dir",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--acquire-new",action="store_true")
    a=p.parse_args(argv)
    try:
        result=run(a.v97b_dir,a.output_dir,acquire=a.acquire_new)
        print(f"COMPLETE V98 mode={result['mode']} "
              f"fresh_first_dispatch={result['fresh_first_dispatched_source_candidates']} "
              f"provider_dispatch_attempts={result['provider_dispatch_attempts']} "
              "broker_orders=0 simulator_pnl=NOT_RUN",flush=True)
        return 0
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error) as exc:
        print(f"STOP V98 type={type(exc).__name__} reason={str(exc)[:160]} "
              "broker_orders=0 no_automatic_ambiguous_query_retry=True",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
