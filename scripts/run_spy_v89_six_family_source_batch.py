from __future__ import annotations

"""V89: one SHA-verified stock pass; six independent causal entry hypotheses.

Every market session evaluates all six registered setups, including NO_SIGNAL
and rejected source states. --acquire-options resolves exact 0DTE 1s tapes
cache-first through V39, with original provider receipts persisted to V38.
A hash-chained fsynced progress journal survives interrupted acquisitions.
No broker calls, no outcome lookahead or real-fill claims.
"""

import argparse
from collections import Counter
from datetime import date,datetime,timedelta
from decimal import Decimal,ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import load_settings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    B34_MAX_SAMPLE_DATE,discover_minute_units,_sample_rows,validate_minute_rows,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import normalize_source_requirement
from packages.data.spy_v51_native_minute_orb_inventory import _verify_monthly_unit_with_progress
from packages.simulation.spy_v89_six_family_causal_registry import (
    FAMILIES,CONTRACT as MODEL,evaluate,signed,verified,V89Error,
)
from packages.simulation.strategy_options_source_runtime_v39 import resolve_strategy_source_demands
from scripts.run_spy_v83_three_family_native_source_screen import (
    source_bars,previous_session_close,
)

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v89-six-family-original-source-campaign-v1"


def emit(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",flush=True)


def write_once(path,row):
    doc=signed(row)
    with path.open("x",encoding="utf8") as out:
        json.dump(doc,out,sort_keys=True,indent=2,allow_nan=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    return doc


def exact_demand(decision,stock_sha,*,end_time_et):
    if (not verified(decision) or decision["contract"]!=MODEL
            or decision["status"]!="OPTIONS_CANDIDATE_SOURCE_SELECTION_REQUIRED"
            or decision["source_stock_sha256"]!=stock_sha):
        raise V89Error("V89_NONCAUSAL_OR_UNSIGNED_OPTION_SELECTION")
    at=datetime.fromisoformat(decision["decision_at_et"])
    if at.tzinfo is None or at.astimezone(ET).strftime("%H:%M:%S") + ".000">=end_time_et:
        raise V89Error("V89_SOURCE_CLOCK_AFTER_END")
    day=decision["session"]
    strike=str(Decimal(decision["features"]["last_completed_close"]).quantize(
        Decimal("1"),rounding=ROUND_HALF_UP))
    req=normalize_source_requirement("option_history_exact_quote_tape",{
        "symbol":"SPY","date_et":day,"expiration":day,
        "strike":strike,"right":decision["direction"].lower(),
        "start_time_et":at.astimezone(ET).strftime("%H:%M:%S")+".000",
        "end_time_et":end_time_et,"interval":"1s",
    })
    return signed({
        "contract":CONTRACT+"-exact-source-demand-v1",
        "strategy_decision_sha":decision["fingerprint"],
        "candidate_id":f"SPY_{day}_{decision['strategy_id']}_{decision['direction'].lower()}",
        "purpose":"original_causal_entry_and_exit_quote_tape",
        "selection_at_et":(at-timedelta(seconds=1)).isoformat(),
        "selection_prior_source_sha256":stock_sha,
        "method":req["method"],"kwargs":req["kwargs"],
        "query_id":_fingerprint(req),
        "broker_orders":0,"option_listing_not_independently_proven":True,
    })


def run(start,end,output,*,acquire_options=False,
        discover=discover_minute_units,verify=_verify_monthly_unit_with_progress,
        sample=_sample_rows,validate=validate_minute_rows,
        resolver=resolve_strategy_source_demands,
        settings_factory=load_settings,market=None,reporter=emit):
    if (type(acquire_options) is not bool or start>end or
            end>B34_MAX_SAMPLE_DATE or output.exists() or output.is_symlink()):
        raise V89Error("V89_DATE_OR_IMMUTABLE_OUTPUT_INVALID")
    calendar=market or get_market_calendar("XNYS")
    days=calendar.sessions_in_range(start,end)
    if not days:
        raise V89Error("V89_NO_MARKET_SESSIONS")
    layout=V2Layout.beneath(ROOT/"data")
    units={}
    rows_cache={}
    failures=[]
    records=[]
    demands=[]
    def monthly(day):
        ym=(day.year,day.month)
        if ym not in units:
            reporter(f"STAGE_START V89 verify original SPY stock month={ym}")
            found=discover(layout,target_year=day.year,target_month=day.month,
                           progress=reporter)
            matches=[u for u in found if (u.year,u.month)==ym and "SPY" in u.symbols]
            if len(matches)!=1:
                raise V89Error("V89_ORIGINAL_SPY_MONTH_MISSING_OR_AMBIGUOUS")
            unit=matches[0]
            if not verify(unit,reporter)["accepted"]:
                raise V89Error("V89_ORIGINAL_SPY_MONTH_SHA_INVALID")
            units[ym]=unit
        return units[ym]
    def day_rows(day):
        if day not in rows_cache:
            unit=monthly(day)
            bars=sample(unit.canonical_path,symbol="SPY",session_date=day)
            if bars and not validate(
                    bars,sample_class="SPY_0DTE_ORB_SOURCE_PREVIEW",
                    symbol="SPY",session_date=day)["accepted"]:
                raise V89Error("V89_ORIGINAL_STOCK_SESSION_SEMANTICS_INVALID")
            rows_cache[day]=bars or []
        return rows_cache[day]

    reporter(f"STAGE_START V89 sessions={len(days)} independent_hypotheses={len(FAMILIES)} "
             f"data_acquisition={acquire_options} broker_orders=0")
    output.mkdir(parents=True,exist_ok=False)
    for index,day in enumerate(days,1):
        current=day_rows(day)
        unit=monthly(day)
        priors=calendar.sessions_in_range(day-timedelta(days=10),day-timedelta(days=1))
        prev=priors[-1] if priors else None
        prior=None
        if prev:
            try:
                prior=previous_session_close(day_rows(prev),prev,calendar)
            except (V89Error,ValueError,KeyError) as exc:
                failures.append({"session":day.isoformat(),
                                 "reason":"PRIOR_STOCK_CLOSE_SOURCE_NOT_VERIFIED",
                                 "error_type":type(exc).__name__})
        official=calendar.regular_open_close(day)[1].astimezone(ET)
        if official.date()!=day:
            raise V89Error("V89_OFFICIAL_SESSION_CLOSE_DRIFT")
        early=official.hour<16
        cutoff=((official-timedelta(minutes=55)).strftime("%H:%M:%S")
                if early else "15:30:00")+".000"
        for family,spec in FAMILIES.items():
            try:
                if not current:
                    raise V89Error("V89_ORIGINAL_STOCK_BARS_MISSING")
                stop="09:35:00" if spec["decision"]=="09:35:01" else "09:40:00"
                bars=source_bars(current,day,before=stop)
                prior_kwargs=(
                    {k:prior[k] for k in (
                        "prior_close","prior_close_at_et",
                        "prior_close_available_at_et")}
                    if family=="gap_followthrough_0940" and prior else {}
                )
                if family=="gap_followthrough_0940" and not prior:
                    raise V89Error("V89_PRIOR_CLOSE_UNAVAILABLE")
                decision=evaluate(
                    family,session=day.isoformat(),
                    stock_source_sha=unit.canonical_sha256,bars=bars,
                    market_session_verified=True,**prior_kwargs)
                demand=None
                if decision["status"]=="OPTIONS_CANDIDATE_SOURCE_SELECTION_REQUIRED":
                    demand=exact_demand(decision,unit.canonical_sha256,end_time_et=cutoff)
                    demands.append(demand)
                records.append({
                    "session":day.isoformat(),"strategy":family,
                    "status":"OPTIONS_EXACT_SOURCE_DEMAND_PREPARED" if demand else "NO_SIGNAL",
                    "reason":decision["reason"],
                    "causal_decision":decision,
                    "source_demand_sha":demand["fingerprint"] if demand else None,
                    "stock_source_sha256":unit.canonical_sha256,
                    "official_market_close_at_et":official.isoformat(),
                    "option_source_end_time_et":cutoff if demand else None,
                    "broker_orders":0,
                })
            except (V89Error,KeyError,ValueError,TypeError) as exc:
                records.append({
                    "session":day.isoformat(),"strategy":family,
                    "status":"SOURCE_UNQUALIFIED_NO_TRADE",
                    "reason":str(exc),"causal_decision":None,
                    "source_demand_sha":None,"broker_orders":0,
                })
        if index%25==0 or index==len(days):
            reporter(f"PROGRESS V89 sessions={index}/{len(days)} "
                     f"decisions={len(records)} exact_option_demands={len(demands)}")
    if len(records)!=len(days)*len(FAMILIES):
        raise V89Error("V89_INCOMPLETE_CAUSAL_DECISION_CENSUS")
    by_strategy={f:dict(sorted(Counter(r["status"] for r in records
                                       if r["strategy"]==f).items())) for f in FAMILIES}
    entry=write_once(output/"entry_screen.json",{
        "contract":CONTRACT,"start":start.isoformat(),"end":end.isoformat(),
        "registry":FAMILIES,"registry_sha":_fingerprint(FAMILIES),
        "source_months":[{
            "year":ym[0],"month":ym[1],"unit_id":u.unit_id,
            "original_stock_sha256":u.canonical_sha256,
            "original_raw_bundle_sha256":u.raw_bundle_sha256,
        } for ym,u in sorted(units.items())],
        "sessions":len(days),"cases":records,
        "by_strategy":by_strategy,"source_failures":failures,
        "stock_bars_available_not_intraminute_trade_ticks":True,
        "decision_at_one_second_after_minute_boundary_assumed_available":True,
        "broker_orders":0,"options_not_yet_priced":True,
    })
    plan=write_once(output/"exact_option_source_plan.json",{
        "contract":CONTRACT+"-source-plan-v1",
        "parent_entry_sha":entry["fingerprint"],
        "demands":demands,"requested":len(demands),
        "historical_contract_listing_not_proven":True,
        "provider_calls_allowed_only_when_flagged":acquire_options,
        "broker_orders":0,
    })
    receipt_sha=None
    resolution=None
    if acquire_options and demands:
        completed=[]
        events=[]
        previous=None
        def audit(event,detail):
            nonlocal previous
            record=signed({
                "contract":CONTRACT+"-append-only-source-event-v1",
                "sequence":len(events)+1,"parent_event_sha":previous,
                "event":event,"candidate_id":detail.get("candidate_id"),
                "query_id":detail.get("query_id"),"date_et":detail.get("date_et"),
                "source_status":detail.get("status"),
                "error_type":detail.get("error"),
            })
            with (output/"source_events.jsonl").open("a",encoding="utf8") as handle:
                handle.write(json.dumps(record,sort_keys=True,allow_nan=False)+"\n")
                handle.flush()
                os.fsync(handle.fileno())
            events.append(record)
            previous=record["fingerprint"]
            if event in ("source_done","source_failed","source_blocked"):
                reporter(f"V89_{event.upper()} completed_events={len(events)} "
                         f"date={detail.get('date_et')} status={detail.get('status')}")
        def on_source(item,source):
            completed.append({
                "candidate_id":item["candidate_id"],
                "query_id":source["query_id"],
                "source_sha256":source.get("source_sha256"),
                "status":source["status"],
                "method":item["method"],
                "date_et":item["kwargs"]["date_et"],
            })
        settings=settings_factory(ROOT,"development")
        reporter(f"STAGE_START V89 cache-first exact option sources requirements={len(demands)} "
                 "automated_gets_only_when_cache_miss=True broker_orders=0")
        resolved=resolver(
            settings,"spy_v89_six_distinct_entry_hypotheses_20261101",
            ({"candidate_id":d["candidate_id"],"purpose":d["purpose"],
              "method":d["method"],"kwargs":d["kwargs"]} for d in demands),
            continue_on_error=True,on_source=on_source,on_progress=audit)
        if (resolved.get("contract")!="atlas-strategy-options-data-demand-runtime-v39"
                or resolved.get("source_uses_requested")!=len(demands)):
            raise V89Error("V89_PROVIDER_RESOLUTION_COUNT_DRIFT")
        resolution=signed(resolved)
        receipts=write_once(output/"source_receipts.json",{
            "contract":CONTRACT+"-source-receipts-v1",
            "parent_plan_sha":plan["fingerprint"],
            "original_provider_source_receipts":completed,
            "source_event_count":len(events),
            "last_event_sha":previous,
            "all_original_sources_in_V38_external_archive":True,
            "broker_orders":0,
        })
        receipt_sha=receipts["fingerprint"]
    report=write_once(output/"summary.json",{
        "contract":CONTRACT+"-summary-v1",
        "entry_sha":entry["fingerprint"],"source_plan_sha":plan["fingerprint"],
        "receipt_sha":receipt_sha,
        "source_resolution":resolution,
        "market_sessions":len(days),"hypotheses":len(FAMILIES),
        "considered_decisions":len(records),
        "exact_source_requirements":len(demands),
        "per_family_dispositions":by_strategy,
        "all_required_sources_archived":(
            bool(resolution and resolution.get("status")=="ALL_REQUESTED_SOURCES_PRESENT")
        ),
        "research_only":True,"fills_verified":0,"broker_orders":0,
        "master_holdout_accessed":False,
    })
    reporter(f"COMPLETE V89 considered={len(records)} exact_sources={len(demands)} "
             f"provider_dispatches={(resolution or {}).get('provider_dispatch_attempts',0)} "
             "broker_orders=0")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start",required=True,type=date.fromisoformat)
    p.add_argument("--end",required=True,type=date.fromisoformat)
    p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--acquire-options",action="store_true")
    args=p.parse_args(argv)
    try:
        run(args.start,args.end,args.output_dir,acquire_options=args.acquire_options)
        return 0
    except Exception as exc:
        emit(f"STOP V89 error_type={type(exc).__name__} "
             "historical_sources_or_partial_journals_preserved=True broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
