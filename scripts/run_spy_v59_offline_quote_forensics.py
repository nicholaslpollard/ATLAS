from __future__ import annotations

"""V59: read-only, source-linked forensics of V56 trade/no-trade/exit blockers.

A report + hash journal is verified before reading the original V38 archived
source from SQLite in READ-ONLY mode. No ThetaData SDK methods are invoked and
no broker orders are possible. Never fixes or promotes an invalid quote.
"""

import argparse
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import (
    DB_REL, OnDemandSourceError, _unpack,
)
from packages.simulation.spy_v55_closed_bar_option_replay import (
    _quote, _read_timestamp,
)
from packages.simulation.spy_v55_event_journal import verify_journal

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v59-original-quote-forensic-evidence-v1"
PARENT="atlas-v56-spy-multi-session-closed-bar-quote-account-v1"


class ForensicError(ValueError):
    pass


def log(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",
          flush=True)


def _report(path):
    if path.is_symlink() or not path.is_file():
        raise ForensicError("SOURCE_REPORT_MISSING_OR_SYMLINK")
    doc=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc,dict) or doc.get("fingerprint")!=_fingerprint({
            k:v for k,v in doc.items() if k!="fingerprint"}):
        raise ForensicError("SOURCE_REPORT_FINGERPRINT_INVALID")
    return doc


def _local_cache_only(settings,query_id):
    """Read already archived V38 exact source; never create DB or dispatch GET."""
    if not isinstance(query_id,str) or len(query_id)!=64:
        return {"cache_evidence":"NO_QUERY_ID","source":None}
    db=settings.resolved_path(DB_REL)
    if db.is_symlink() or not db.is_file():
        return {"cache_evidence":"READ_ONLY_SOURCE_INDEX_ABSENT","source":None}
    # URI mode=ro prevents sqlite write locks, table creation and WAL changes.
    try:
        with sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True,
                             timeout=20) as con:
            row=con.execute(
                "SELECT query_id,request_json,state,touched,source_sha,"
                "gzip_sha,stored_path,source_rows FROM sources WHERE query_id=?",
                (query_id,)).fetchone()
    except sqlite3.Error as exc:
        raise ForensicError("READ_ONLY_SOURCE_INDEX_ERROR") from exc
    if row is None:
        return {"cache_evidence":"EXACT_QUERY_NOT_IN_INDEX","source":None}
    request=json.loads(row[1])
    if query_id!=_fingerprint(request):
        raise ForensicError("CACHED_REQUEST_IDENTITY_MISMATCH")
    try:
        cached=_unpack(settings,row,request)
    except (OnDemandSourceError,ValueError,KeyError,TypeError) as exc:
        raise ForensicError("ARCHIVED_SOURCE_VERIFICATION_FAILED") from exc
    return {"cache_evidence":cached["status"],"source":cached}


def _brief_row(row,index,*,day,contract):
    summary={"index":index}
    if not isinstance(row,dict):
        summary["validation"]="NONOBJECT_ROW"
        return summary
    for field in ("timestamp_et","timestamp","datetime","timestamp_utc",
                  "ms_of_day","bid","ask","bid_size","ask_size"):
        if field in row:
            value=row[field]
            summary[field]=value if isinstance(value,(str,int,float,bool,type(None))) else str(type(value).__name__)
    try:
        stamp=_read_timestamp(row,day)
        summary["interpreted_et_clock"]=stamp.isoformat()
    except Exception as exc:
        summary["interpreted_et_clock_error"]=type(exc).__name__+":"+str(exc)
    if contract is not None:
        try:
            _quote(row,day=day,contract=contract)
            summary["validation"]="QUALIFIED"
        except Exception as exc:
            summary["validation"]="UNQUALIFIED"
            summary["validation_reason"]=type(exc).__name__+":"+str(exc)
    return summary


def _focus_event(report):
    events=report.get("events") or []
    reason=report.get("censor_reason")
    rejection_names={
        "UNQUALIFIED_EXIT_QUOTE_PATH":"EXIT_SOURCE_REJECTION",
        "SOURCE_OBSERVATION_CLOCK_UNQUALIFIED":"SOURCE_CLOCK_REJECTION",
        "FIRST_ORDER_QUOTE_NOT_ELIGIBLE":"ENTRY_QUOTE_REJECTION",
        "ACTION_QUOTE_NOT_ELIGIBLE":"ACTION_QUOTE_REJECTION",
        "QUOTE_PATH_GAP_OVER_60_SECONDS":"EXIT_REVIEW",
        "EXIT_BID_SIZE_INSUFFICIENT":"EXIT_REVIEW",
        "TIME_EXIT_BID_SIZE_INSUFFICIENT":"EXIT_REVIEW",
    }
    typ=rejection_names.get(reason)
    found=[(i,e) for i,e in enumerate(events) if e.get("type")==typ] if typ else []
    if reason=="QUOTE_PATH_GAP_OVER_60_SECONDS":
        found=[(i,e) for i,e in found
               if Decimal(str(e.get("observed_gap_seconds",0)))>60]
    if reason=="EXIT_BID_SIZE_INSUFFICIENT":
        found=[(i,e) for i,e in found if e.get("reason")!="HOLD"]
    if reason=="TIME_EXIT_BID_SIZE_INSUFFICIENT":
        # The last hold quote became the time-exit quote.
        found=[(i,e) for i,e in found]
    if not found:
        for name in ("EXIT_SOURCE_REJECTION","ACTION_QUOTE_REJECTION",
                     "ENTRY_QUOTE_REJECTION","SOURCE_CLOCK_REJECTION"):
            other=[(i,e) for i,e in enumerate(events) if e.get("type")==name]
            if other:
                found=other
                break
    if found:
        index,ev=found[-1] if reason=="TIME_EXIT_BID_SIZE_INSUFFICIENT" else found[0]
        return {
            "event_index":index,"event_type":ev.get("type"),
            "source_row_index":ev.get("row"),
            "at_et":ev.get("at_et") or (ev.get("quote") or {}).get("timestamp_et"),
            "reason":ev.get("reason"),"observed_gap_seconds":ev.get("observed_gap_seconds"),
            "quote":ev.get("quote"),
        }
    return None


def _source_summary(source,day,contract,focus_row):
    rows=source["source_rows"]
    counts=Counter()
    first=None
    last=None
    largest_gap=0.0
    largest_gap_row=None
    first_invalid=None
    for i,row in enumerate(rows):
        try:
            stamp=_read_timestamp(row,day)
            if last is not None:
                delta=(stamp-last).total_seconds()
                if delta>largest_gap:
                    largest_gap=delta
                    largest_gap_row=i
                if delta<=0:
                    counts["NONINCREASING_SOURCE_CLOCK"]+=1
            last=stamp
            if first is None:
                first=stamp
        except Exception:
            counts["BAD_SOURCE_CLOCK"]+=1
        if contract is not None:
            try:
                _quote(row,day=day,contract=contract)
                counts["QUALIFIED_QUOTES"]+=1
            except Exception as exc:
                code=type(exc).__name__+":"+str(exc)
                counts[code]+=1
                if first_invalid is None:
                    first_invalid={"index":i,"validation_error":code}
    context=[]
    if type(focus_row) is int and 0<=focus_row<len(rows):
        for idx in range(max(0,focus_row-2),min(len(rows),focus_row+3)):
            context.append(_brief_row(rows[idx],idx,day=day,contract=contract))
    return {
        "original_source_rows":len(rows),
        "source_first_clock":first.isoformat() if first else None,
        "source_last_clock":last.isoformat() if last else None,
        "max_observation_gap_seconds":largest_gap,
        "max_observation_gap_ends_at_index":largest_gap_row,
        "quality_class_counts":dict(sorted(counts.items())),
        "first_invalid_quote":first_invalid,
        "focus_quote_neighborhood":context,
        "raw_quotes_retained_in_original_source_only":True,
        "audit_looks_forward_to_find_errors_not_for_causal_decisions":True,
    }


def investigate(cohort_dir,output,*,dates=None,cache_reader=None,
                verify=verify_journal,emit=log,settings_factory=load_settings):
    emit("START V59 offline_forensics no_provider_calls=True no_broker_orders=True"
         f" cohort={cohort_dir}")
    if output.exists() or output.is_symlink():
        raise ForensicError("IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    parent=_report(cohort_dir/"summary.json")
    if parent.get("contract")!=PARENT:
        raise ForensicError("EXPECTED_V56_PARENT_CONTRACT")
    selected=set(dates or ())
    if selected and any(len(d)!=10 or d[4]!="-"
                        for d in selected):
        raise ForensicError("DATE_FORMAT_INVALID")
    days=parent.get("sessions")
    if not isinstance(days,list) or not days:
        raise ForensicError("MISSING_PARENT_DAY_ROWS")
    result=[]
    settings=None
    for meta in days:
        name=meta["session"]
        if selected and name not in selected:
            continue
        emit(f"STAGE_START verify_day name={name}")
        report=_report(cohort_dir/f"{name}.json")
        if (report["fingerprint"]!=meta["report_fingerprint"]
                or report.get("session")!=name
                or report.get("status")!=meta.get("status")):
            raise ForensicError("DAY_REPORT_DISAGREES_WITH_PARENT")
        j=verify(cohort_dir/f"{name}.jsonl")
        if (j["report_fingerprint"]!=report["fingerprint"]
                or j["tip_sha256"]!=meta["event_journal_tip"]):
            raise ForensicError("DAY_CHAIN_RECEIPT_DISAGREES_WITH_PARENT")
        reason=report.get("censor_reason")
        focus=_focus_event(report)
        stamp=date.fromisoformat(name)
        r={
            "session":name,"status":report["status"],
            "censor_reason":reason,"signal_status":report["signal"]["signal_status"],
            "selected_contract":report["signal"]["selected_contract"],
            "decision_at_et":report["signal"]["decision_at_et"],
            "source_status":report.get("source_status"),
            "source_query_id":report.get("source_query_id"),
            "source_sha256":report.get("source_sha256"),
            "modeled_entry_debit":report.get("entry_debit"),
            "modeled_exit_credit":report.get("exit_credit"),
            "modeled_net_pnl":report.get("trade_net_pnl"),
            "terminal_equity_if_resolved":report.get("terminal_equity_if_resolved"),
            "journal_tip_sha256":j["tip_sha256"],
            "journal_events":j["runtime_events"],
            "source_report_fingerprint":report["fingerprint"],
            "event_type_counts":dict(sorted(Counter(
                e.get("type","UNKNOWN") for e in report["events"]).items())),
            "focus_event":focus,
            "quote_archive_evidence":"NOT_REQUESTED",
            "quote_quality_audit":None,
            "no_provider_requests":True,"actual_broker_fills":0,
        }
        if report.get("source_query_id"):
            emit(f"STAGE_START verify_cached_option_archive name={name}"
                 " mode=READ_ONLY_NO_GET")
            if cache_reader is None:
                if settings is None:
                    settings=settings_factory(ROOT,"development")
                cached=_local_cache_only(settings,report["source_query_id"])
            else:
                cached=cache_reader(report["source_query_id"])
            r["quote_archive_evidence"]=cached["cache_evidence"]
            source=cached.get("source")
            if source is not None:
                if (source.get("query_id")!=report["source_query_id"]
                        or source.get("source_sha256")!=report.get("source_sha256")):
                    raise ForensicError("CACHED_SOURCE_AND_DAY_REPORT_SHA_MISMATCH")
                requirement=source.get("exact_requirement") or {}
                kwargs=requirement.get("kwargs") or {}
                requested=report["signal"]["selected_contract"]
                if (requirement.get("method")!="option_history_exact_quote_tape"
                        or requested is None
                        or any(str(kwargs.get(k))!=str(v)
                               for k,v in requested.items())):
                    raise ForensicError("ORIGINAL_SOURCE_CONTRACT_IDENTITY_CHANGED")
                index=focus.get("source_row_index") if focus else None
                r["quote_quality_audit"]=_source_summary(
                    source,stamp,requested,index)
                emit(f"STAGE_PASS verified_cached_option_archive"
                     f" day={name} rows={r['quote_quality_audit']['original_source_rows']}"
                     f" qualified={r['quote_quality_audit']['quality_class_counts'].get('QUALIFIED_QUOTES',0)}")
            else:
                emit(f"STAGE_PASS missing_cached_option_archive"
                     f" day={name} state={cached['cache_evidence']}")
        emit(f"STAGE_PASS forensic_day day={name}"
             f" status={r['status']} reason={reason}"
             f" focus={focus['event_type'] if focus else None}"
             f" source={r['quote_archive_evidence']}")
        result.append(r)
    if selected-set(x["session"] for x in result):
        raise ForensicError("REQUESTED_DATE_MISSING_FROM_V56_COHORT")
    doc={
        "contract":CONTRACT,"v56_account_fingerprint":parent["fingerprint"],
        "v56_account_status":parent.get("account_status"),
        "v56_account_blocker":parent.get("blocker"),
        "original_expected_weekdays":parent.get("calendar_weekday_sessions_expected"),
        "original_evaluated_days":len(days),
        "selected_days":len(result),"dates":result,
        "source_read_only":True,"provider_requests":0,"broker_requests":0,
        "sources_not_modified":True,
        "invalid_quote_not_silently_substituted":True,
        "zero_new_profit_or_loss_assignments":True,
        "research_not_validated_alpha":True,
    }
    doc["fingerprint"]=_fingerprint(doc)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as f:
        json.dump(doc,f,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n")
    emit(f"COMPLETE V59 output={output}"
         f" classified_days={len(result)} read_only=True broker_orders=0")
    return doc


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--dates",nargs="*",default=None)
    args=parser.parse_args(argv)
    try:
        doc=investigate(args.cohort_dir,args.output,dates=args.dates)
        for d in doc["dates"]:
            print(f"FORENSIC date={d['session']} status={d['status']}"
                  f" censor_reason={d['censor_reason']}"
                  f" focus_row={(d['focus_event'] or {}).get('source_row_index')}"
                  f" archive={d['quote_archive_evidence']}"
                  f" class_counts={(d['quote_quality_audit'] or {}).get('quality_class_counts')}",
                  flush=True)
        return 0
    except Exception as exc:
        log(f"STOPPED V59 type={type(exc).__name__}"
            " no_provider_requests=True archived_sources_unchanged=True")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
