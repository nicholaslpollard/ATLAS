from __future__ import annotations

"""V77: source-first monthly exact options acquisition plus registered V76 exit tests.

Run an entire multi-month evaluation from one operator command. Source reads
are read-through, persist exact receipts, and never silently skip misses.
The completed offline option exits are quote references, not broker fills.
"""

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts.run_spy_v73_xnys_calendar_source_first import run as run_v73
from scripts.run_spy_v76_registered_exit_benchmark import run as run_v76, POLICIES
from scripts.run_spy_v74_original_dynamic_exit_cohort import signed_file
from scripts.run_spy_v76_registered_exit_benchmark import V69

ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v77-multi-month-exact-source-plus-exit-benchmark-v1"


def announce(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",
          flush=True)


def signature(document):
    return {**document,"fingerprint":_fingerprint(document)}


def write_new(path,doc):
    value=signature(doc)
    with path.open("x",encoding="utf8") as out:
        json.dump(value,out,indent=2,sort_keys=True,allow_nan=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    return value


def month_starts(start,end):
    if (start>end or start.day!=1 or end.day!=1):
        raise ValueError("V77_MONTH_RANGE_INVALID")
    result=[]
    year,month=start.year,start.month
    while date(year,month,1)<=end:
        result.append(date(year,month,1))
        if month==12:
            year+=1
            month=1
        else:month+=1
    return result


def run(start,end,output_dir,*,source_run=run_v73,
        benchmark_run=run_v76,emit=announce):
    months=month_starts(start,end)
    if not months or output_dir.exists() or output_dir.is_symlink():
        raise ValueError("V77_IMMUTABLE_OUTPUT_OR_EMPTY_RANGE")
    emit(f"STAGE_START V77 prepare multi-month roster {start}/{end} "
         "provider=OPTIONAL_THETADATA_READ_ONLY broker_orders=0")
    output_dir.mkdir(parents=True,exist_ok=False)
    emit(f"START V77 months={len(months)} policy_families={len(POLICIES)} "
         "lags=1s,3s original_stock_and_options=VERIFIED_ON_DEMAND "
         "manual_provider_confirmation_not_required=True broker_orders=0 "
         "no_runtime_call_cap=True")
    complete=0
    milestone=10
    month_reports=[]
    for first in months:
        ym=f"{first.year:04d}{first.month:02d}"
        if first.month==12:
            last=date(first.year,12,31)
        else:
            last=date.fromordinal(date(first.year,first.month+1,1).toordinal()-1)
        source_dir=output_dir/f"{ym}_v73_original_sources"
        variants_dir=output_dir/f"{ym}_v76_registered_exit_variants"
        status="UNKNOWN"
        error_class=None
        source_sha=None
        exit_sha=None
        dispatches=None
        monthly_option_cache_hits=None
        requested=None
        explicit_no_data=None
        describe=None
        emit(f"STAGE_START V77 month={ym} source_first dates={first}/{last} "
             "monthly_original_SHA=MANDATORY exact_options=ON_MISS "
             "broker_orders=0")
        try:
            sources=source_run(first,last,source_dir)
            if (sources.get("fingerprint")!=_fingerprint({
                    k:v for k,v in sources.items() if k!="fingerprint"
                }) or sources.get("broker_orders")!=0):
                raise ValueError("V77_ORIGINAL_SOURCE_SUMMARY_SIGNATURE_INVALID")
            source_sha=sources["fingerprint"]
            if sources["chunks"]!=1 or len(sources["chunk_summaries"])!=1:
                raise ValueError("V77_EXPECTED_ONE_SOURCE_CHUNK_PER_MONTH")
            chunk=sources["chunk_summaries"][0]
            if chunk.get("status") not in (
                "SOURCE_CHECKED_AND_REPLAYED",
                "SOURCE_COORDINATION_BLOCKED",
                "POST_ACQUISITION_REPLAY_UNVERIFIED",
            ):
                status="ORIGINAL_STOCK_OR_SOURCE_BLOCKED"
            elif chunk["status"]!="SOURCE_CHECKED_AND_REPLAYED":
                status="ORIGINAL_STOCK_OR_SOURCE_BLOCKED"
            else:
                emit(f"STAGE_START V77 month={ym} verify signed provider source receipt")
                receipt=signed_file(source_dir/"chunk_0001.sources.json",V69)
                sr=receipt["runtime_source_receipt"]
                dispatches=sr["provider_dispatch_attempts"]
                monthly_option_cache_hits=sr["persisted_cache_hits"]
                requested=sr["source_uses_requested"]
                explicit_no_data=sr["source_uses_explicit_no_data"]
                emit(f"STAGE_PASS V77 month={ym} source_requirements={requested} "
                     f"provider_dispatches={dispatches} cache_hits={monthly_option_cache_hits} "
                     f"source_explicit_no_data={explicit_no_data}")
                emit(f"STAGE_START V77 month={ym} V76 all_variants "
                     "cache=READ_ONLY broker_orders=0")
                results=benchmark_run(source_dir,variants_dir,
                                      expected_parent_sha=source_sha)
                if (results.get("fingerprint")!=_fingerprint({
                        k:v for k,v in results.items() if k!="fingerprint"
                    }) or results.get("provider_calls")!=0
                        or results.get("broker_orders")!=0):
                    raise ValueError("V77_EXIT_MATRIX_SIGNATURE_OR_AUTHORITY_INVALID")
                exit_sha=results["fingerprint"]
                describe=[{
                    "policy":r["name"],"lag_seconds":r["lag_seconds"],
                    "closed_trade_count":r["closed_trade_count"],
                    "modeled_closed_trade_pnl":r["modeled_closed_trade_pnl"],
                    "source_or_exit_unresolved_dates":r["unresolved_days"],
                } for r in results["policies"]]
                status=("EXIT_MATRIX_WITH_UNRESOLVED_EVIDENCE"
                        if any(r["unresolved_days"] for r in results["policies"])
                        else "EXIT_MATRIX_ALL_QUOTE_CASES_RESOLVED")
        except Exception as exc:
            status="MONTH_EXECUTION_OR_SOURCE_BLOCKED"
            error_class=type(exc).__name__
            emit(f"STAGE_BLOCKED V77 month={ym} error_type={error_class} "
                 "source_receipts_preserved=True "
                 "other_months_continue=True broker_orders=0")
        record={
            "month":ym,"start":first.isoformat(),"end":last.isoformat(),
            "source_report_dir":str(source_dir),
            "source_summary_fingerprint":source_sha,
            "source_uses_requested":requested,
            "provider_dispatch_attempts":dispatches,
            "persisted_cache_hits":monthly_option_cache_hits,
            "explicit_no_data_requirements":explicit_no_data,
            "exit_matrix_dir":str(variants_dir) if exit_sha else None,
            "exit_matrix_fingerprint":exit_sha,
            "status":status,"error_class":error_class,
            "policy_quote_reference_economics":describe,
            "real_broker_fills":0,
        }
        month_reports.append(record)
        write_new(output_dir/f"month_{ym}.receipt.json",record)
        complete+=1
        while milestone<=100 and complete*100>=milestone*len(months):
            emit(f"PROGRESS_{milestone}PCT V77 months_completed={complete}/{len(months)} "
                 f"latest={ym} status={status} provider_requests=ORIGINAL_RECEIPTS "
                 "broker_orders=0")
            milestone+=10
    blocked=[r for r in month_reports if r["status"]!="EXIT_MATRIX_ALL_QUOTE_CASES_RESOLVED"]
    aggregate={}
    for name in POLICIES:
        for lag in (1,3):
            matches=[p for m in month_reports
                     for p in (m["policy_quote_reference_economics"] or [])
                     if p["policy"]==name and p["lag_seconds"]==lag]
            from decimal import Decimal
            aggregate[f"{name}_{lag}s"]={
                "evaluated_months":len(matches),
                "closed_trades":sum(x["closed_trade_count"] for x in matches),
                "sum_of_closed_subset_quote_pnl_not_portfolio_equity":
                    str(sum(Decimal(x["modeled_closed_trade_pnl"]) for x in matches)),
                "unresolved_months":[m["month"] for m in month_reports
                                     if m["status"]!="EXIT_MATRIX_ALL_QUOTE_CASES_RESOLVED"],
            }
    final=write_new(output_dir/"summary.json",{
        "contract":CONTRACT,
        "status":"COMPLETE_ALL_MONTHS_QUOTE_REFERENCE_ONLY"
                 if not blocked else "COMPLETE_WITH_EXPLICIT_MONTH_BLOCKERS",
        "start_month":start.isoformat(),"end_month":end.isoformat(),
        "months_requested":len(months),"months_processed":complete,
        "research_policy_registry_sha":_fingerprint(POLICIES),
        "months":month_reports,
        "aggregate_of_closed_trade_subset_not_true_account_cash":aggregate,
        "blocked_months":[r["month"] for r in blocked],
        "no_silent_skips":True,
        "real_option_broker_fills":0,
        "broker_orders":0,
        "provider_dispatches_in_confirmed_month_receipts":sum(
            r["provider_dispatch_attempts"] or 0 for r in month_reports),
        "provider_requests_unknown_for_blocked_stages":any(
            r["provider_dispatch_attempts"] is None for r in month_reports),
        "provider_requests_detail":"EXACT_ORIGINAL_V73_V69_SIGNED_SOURCE_RECEIPTS",
        "future_period_not_promoted_as_unseen_holdout":True,
        "cash_censored_on_any_unresolved_month":True,
        "historical_profitability_proven":False,
    })
    emit(f"COMPLETE V77 months={complete}/{len(months)} "
         f"blocked={len(blocked)} output={output_dir/'summary.json'} "
         "broker_orders=0 original_source_receipts_preserved=True")
    return final


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start-month",type=lambda x:date.fromisoformat(x+"-01"),required=True)
    p.add_argument("--end-month",type=lambda x:date.fromisoformat(x+"-01"),required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        run(a.start_month,a.end_month,a.output_dir)
        return 0
    except Exception as exc:
        announce(f"STOPPED V77 error_type={type(exc).__name__} "
                 "provider_calls=UNKNOWN_IF_STAGES_RAN broker_orders=0 "
                 "original_receipts_preserved=True")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
