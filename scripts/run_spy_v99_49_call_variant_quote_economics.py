from __future__ import annotations

"""V99 source-linked CALL-only 49-entry x 24-exit historical quote simulation.

Reuses signed V97B as-of stock decisions, completed V98 original quote archives,
V84/V86 bounded quote execution and V90 one-slot $25,000 cash accounting.
No historical news classification, future signal data, provider calls or broker
orders. Missing exact source remains unknown; never fabricated as a zero PnL.
"""

import argparse
from collections import Counter,defaultdict
from datetime import date,datetime,time
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v84_offline_three_family_economics import (
    POLICIES,LAGS,prepare_original_tape,replay,verified as verify84,
)
from packages.simulation.spy_v86_original_option_exit_recheck import (
    DWELLS,recheck,verified as verify86,
)
from packages.simulation.spy_v90_six_family_capital_ledger import (
    simulate as capital_simulate,verified as verify90,
)
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only
from scripts.run_spy_v97b_49_variant_call_source_union_preview import (
    CONTRACT as V97B,BASELINES,params,read as read97b,
)
from scripts.run_spy_v98_historical_call_union_safe_acquisition import (
    CONTRACT as V98,verify_preview,
)

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v99-call-only-source-linked-49-variant-offline-quote-economics-v1"
V98SUMMARY=V98+"-summary-v1"
ORIGINAL="EXACT_ORIGINAL_CALL_SOURCE_ALREADY_ARCHIVED"
NEW="NEW_EXACT_CALL_SOURCE_SCOPE_REQUIRES_SEPARATE_REVIEW"
UNKNOWN="ORIGINAL_PROVIDER_DISPATCH_UNKNOWN_NO_RETRY"
DEFINITIONS=tuple((policy,lag,dwell)
                  for policy in POLICIES for lag in LAGS for dwell in DWELLS)
V99_REQUIRED_COMPLETE_COEFFICIENTS=49*len(DEFINITIONS)
COHORTS=(
    ("2018_full","2018-01-01","2018-12-31"),
    ("2019_full","2019-01-01","2019-12-31"),
    ("2020_SOURCE_PARTIAL","2020-01-01","2020-12-31"),
    ("2021_full","2021-01-01","2021-12-31"),
    ("2022_full","2022-01-01","2022-12-31"),
    ("2023_full","2023-01-01","2023-12-31"),
    ("2024_full","2024-01-01","2024-12-31"),
    ("2025_h2","2025-07-01","2025-12-31"),
    ("2026_janapr","2026-01-01","2026-04-30"),
)

class V99Error(ValueError):
    pass


def signed(d):
    return {**d,"fingerprint":_fingerprint(d)}


def check(d,contract):
    if (not isinstance(d,dict) or d.get("contract")!=contract
            or d.get("fingerprint")!=_fingerprint({
                k:v for k,v in d.items() if k!="fingerprint"})):
        raise V99Error("V99_SIGNED_INPUT_OR_RESULT_ROOT_CHANGED")
    return d


def read(path,contract):
    return check(json.loads(path.read_text(encoding="utf8")),contract)


def write_once(path,doc):
    # Verify all objects serialize BEFORE touching an immutable output path.
    # Do not silently stringify Decimal metadata to disguise broken dates.
    result=signed(doc)
    payload=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n"
    with path.open("x",encoding="utf8") as f:
        f.write(payload);f.flush();os.fsync(f.fileno())
    return result


def source_key(event):
    return (event["session"],event["decision_clock_et"],event["strike"])


def cohort_bounds(name,start,end):
    if (not isinstance(start,str) or not isinstance(end,str)
            or name not in {row[0] for row in COHORTS}):
        raise V99Error("V99_HISTORICAL_PERIOD_BOUNDS_NOT_DATE_STRINGS")
    try:
        first=date.fromisoformat(start)
        last=date.fromisoformat(end)
    except ValueError as exc:
        raise V99Error("V99_HISTORICAL_PERIOD_BOUNDS_INVALID") from exc
    expected=next((row for row in COHORTS if row[0]==name),None)
    if not expected or (start,end)!=(expected[1],expected[2]) or first>last:
        raise V99Error("V99_HISTORICAL_COHORT_BOUNDARY_DRIFT")
    return {"cohort":name,"historical_start":start,"historical_end":end}


def cohort(session):
    for name,start,end in COHORTS:
        if start<=session<=end:
            return name
    raise V99Error("V99_PROTECTED_OR_OUT_OF_SCOPE_DATE")


def inspect_v98(v97b_dir,v98_dir,calendar):
    summary,events,plan,qualified=verify_preview(v97b_dir,calendar)
    s=read(v98_dir/"summary.json",V98SUMMARY)
    audit=read(v98_dir/"exact_call_source_union_audit.json",
               V98+"-original-source-read-only-preflight-v1")
    intents=read(v98_dir/"first_dispatch_source_intents.json",
                 V98+"-source-intents-v1")
    results=read(v98_dir/"acquisition_results.json",
                 V98+"-source-results-v1")
    if (s["mode"]!="CACHE_FIRST_SOURCE_ONLY"
            or s["original_V97B_summary_sha"]!=summary["fingerprint"]
            or s["preflight_sha"]!=audit["fingerprint"]
            or s["acquisition_results_sha"]!=results["fingerprint"]
            or audit["original_V97B_events_sha"]!=events["fingerprint"]
            or audit["original_V97B_union_preview_sha"]!=plan["fingerprint"]
            or intents["preflight_sha"]!=audit["fingerprint"]
            or results["original_preflight_sha"]!=audit["fingerprint"]
            or results["dispatch_intents_sha"]!=intents["fingerprint"]
            or s["provider_dispatch_attempts"]!=209
            or s["source_uses_resolved"]!=208
            or s["source_uses_explicit_no_data"]!=1
            or s["source_uses_failed_or_unresolved"]!=0
            or s["broker_orders"]!=0):
        raise V99Error("V99_SOURCE_ACQUISITION_SIGNED_REPORT_MISMATCH")
    old={}
    for ev in events["candidate_events"]:
        if ev["source_coverage_status"]==ORIGINAL:
            qid=ev["original_call_query_id"]
            sha=ev["original_archived_source_sha256"]
            if (not isinstance(qid,str) or len(qid)!=64
                    or not isinstance(sha,str) or len(sha)!=64):
                raise V99Error("V99_ORIGINAL_SOURCE_SHA_OR_QUERY_MISSING")
            if qid in old and old[qid]!=sha:
                raise V99Error("V99_ORIGINAL_SOURCE_FINGERPRINT_CONFLICT")
            old[qid]=sha
    if len(old)!=351:
        raise V99Error("V99_ORIGINAL_DISTINCT_CALL_SHA_CENSUS_DRIFT")

    original_index={q["query_id"]:q for q in qualified}
    cached={}
    preflight=audit["all_distinct_exact_historical_requirements"]
    if (len(preflight)!=226 or len({x["query_id"] for x in preflight})!=226
            or set(x["query_id"] for x in preflight)!=set(original_index)
            or len(intents["eligible_new_query_ids"])!=209):
        raise V99Error("V99_SOURCE_UNION_CENSUS_MISMATCH")
    for item in preflight:
        qid=item["query_id"];expected=original_index[qid]
        if (item["normalized_requirement"]["kwargs"]!=expected["kwargs"]
                or item["normalized_requirement"]["method"]!=expected["method"]):
            raise V99Error("V99_NEW_EXACT_CONTRACT_QUERY_MISMATCH")
        if item["read_only_v38_state"]=="ARCHIVED_SHA_VERIFIED":
            sha=item["read_only_source_sha256"]
            if not isinstance(sha,str) or len(sha)!=64:
                raise V99Error("V99_CACHED_SOURCE_HASH_MISSING")
            cached[qid]=sha
        elif item["read_only_v38_state"]!="NOT_REGISTERED":
            raise V99Error("V99_UNRESOLVED_PRIOR_DISPATCH_IN_NEW_SOURCE_UNION")
    expected_new=set(intents["eligible_new_query_ids"])
    if (len(expected_new)!=209 or len(cached)!=17
            or expected_new!=set(original_index)-set(cached)):
        raise V99Error("V99_FIRST_DISPATCH_SOURCE_INTENTS_CHANGED")
    journal=v98_dir/"source_events.jsonl"
    if not journal.is_file() or journal.is_symlink():
        raise V99Error("V99_ORIGINAL_V98_DISPATCH_JOURNAL_MISSING")
    last=None
    event_count=0
    kinds=Counter()
    observed_queries={"source_started":set(),"provider_dispatch":set(),
                      "source_done":set()}
    with journal.open("r",encoding="utf8") as stream:
        for line in stream:
            row=check(json.loads(line),V98+"-source-event-journal-v1")
            event_count+=1
            if (row["sequence"]!=event_count or row["previous_event_sha"]!=last
                    or row["event"] not in observed_queries
                    or row["query_id"] not in expected_new):
                raise V99Error("V99_ORIGINAL_V98_DISPATCH_EVENT_CHAIN_INVALID")
            observed_queries[row["event"]].add(row["query_id"])
            kinds[row["event"]]+=1
            last=row["fingerprint"]
    if (event_count!=627 or last!=results["source_events_sha_head"]
            or results["source_event_count"]!=event_count
            or any(kinds[x]!=209 or observed_queries[x]!=expected_new
                   for x in observed_queries)):
        raise V99Error("V99_INCOMPLETE_OR_UNTRUSTED_V98_PROVIDER_EVENTS")
    receipts={}
    for row in results["verified_cached_or_fetched_receipts"]:
        qid=row["query_id"]
        if qid in receipts or qid not in expected_new:
            raise V99Error("V99_DUPLICATE_OR_FOREIGN_SOURCE_RECEIPT")
        receipts[qid]=row
    if set(receipts)!=expected_new:
        raise V99Error("V99_MISSING_OR_EXTRA_PROVIDER_RECEIPT")
    no_data=[]
    for qid,item in receipts.items():
        if item["status"]=="FETCHED_AND_ARCHIVED":
            sha=item["source_sha256"]
            if (not isinstance(sha,str) or len(sha)!=64
                    or item["source_row_count"]<=0):
                raise V99Error("V99_NEW_ARCHIVE_SOURCE_BYTES_MISSING")
            cached[qid]=sha
        elif item["status"]=="FETCHED_EXPLICIT_NO_DATA":
            if item["source_sha256"] is not None or item["source_row_count"]!=0:
                raise V99Error("V99_ORIGINAL_EXPLICIT_NO_DATA_CHANGED")
            no_data.append(qid)
        else:
            raise V99Error("V99_UNKNOWN_OR_FAILED_NEW_PROVIDER_STATUS")
    if len(no_data)!=1 or len(cached)!=225:
        raise V99Error("V99_225_NEW_QUALIFIED_SOURCE_CENSUS_CHANGED")
    if set(cached)&set(old):
        raise V99Error("V99_NEW_SOURCE_OVERLAPS_OLD_QUERY")
    resolved={**old,**cached}
    new_lookup={source_key(item):item["query_id"] for item in qualified}
    if len(new_lookup)!=226:
        raise V99Error("V99_NEW_UNION_LOOKUP_DUPLICATE")
    entries=[]
    unknown_seen=set()
    missing_seen=set()
    for ev in events["candidate_events"]:
        state=ev["source_coverage_status"]
        if state==ORIGINAL:
            qid=ev["original_call_query_id"]
        elif state==NEW:
            qid=new_lookup.get(source_key(ev))
            if qid is None:
                raise V99Error("V99_NEW_SOURCE_CASE_NOT_IN_ORIGINAL_PLAN")
        elif state==UNKNOWN:
            qid=ev["original_call_query_id"]
            unknown_seen.add(qid)
        else:
            raise V99Error("V99_UNRECOGNIZED_ORIGINAL_CANDIDATE_STATUS")
        if state!=UNKNOWN and qid not in resolved:
            if qid not in no_data:
                raise V99Error("V99_MISSING_NEVER_QUALIFIED_SOURCE")
            missing_seen.add(qid)
        entries.append({**ev,"exact_original_call_query_id":qid,
                        "qualified_original_source_sha256":resolved.get(qid),
                        "new_source_explicit_no_data":qid in no_data})
    if len(unknown_seen)!=1 or len(missing_seen)!=1 or len(entries)!=2482:
        raise V99Error("V99_ORIGINAL_UNKNOWN_OR_NO_DATA_CASE_COUNT_DRIFT")
    return s,summary,events,entries,resolved,no_data,unknown_seen


def decision_and_demand(ev,source):
    """Re-sign an explicitly derived bullish decision; preserve original SHA."""
    when=datetime.combine(date.fromisoformat(ev["session"]),
        time.fromisoformat(ev["decision_clock_et"]),ET)
    if (ev["decision_clock_et"] not in ("09:35:01","09:40:01")
            or ev["expiry"]!=ev["session"] or ev["strategy"] is None
            or source["exact_requirement"]["kwargs"]["right"]!="call"
            or source["exact_requirement"]["kwargs"]["strike"]!=ev["strike"]
            or source["exact_requirement"]["kwargs"]["expiration"]!=ev["session"]
            or source["exact_requirement"]["kwargs"]["date_et"]!=ev["session"]
            or source["exact_requirement"]["kwargs"]["start_time_et"]!=(
                ev["decision_clock_et"]+".000")):
        raise V99Error("V99_NONCAUSAL_OR_INCORRECT_DERIVED_CALL_DECISION")
    decision=signed({
        "contract":CONTRACT+"-asof-bullish-derived-decision-v1",
        "strategy_id":ev["strategy"],"session":ev["session"],
        "decision_at_et":when.isoformat(),
        "direction":"CALL",
        "original_asof_v89_decision_sha":ev["original_decision_sha"],
        "original_stock_source_sha256":ev["original_stock_sha256"],
        "selected_strike_from_original_asof_stock":ev["strike"],
        "news_signal_used":False,
        "broker_orders":0,
    })
    req=source["exact_requirement"]
    demand=signed({
        "contract":CONTRACT+"-exact-original-call-source-demand-v1",
        "strategy_decision_sha":decision["fingerprint"],
        "query_id":source["query_id"],"method":req["method"],
        "kwargs":req["kwargs"],
        "provenance_v97b_original_stock_decision_sha":ev["original_decision_sha"],
        "broker_orders":0,
    })
    return decision,demand


def censored_exit(trial,dwell):
    return signed({
        "contract":"atlas-v90-original-v84-expiry-censor-v1",
        "original_trial_sha":trial["fingerprint"],
        "session":trial["session"],"strategy":trial["strategy"],
        "policy":trial["policy"],"lag_seconds":trial["lag_seconds"],
        "limit_rest_seconds":dwell,
        "status":"UNRESOLVED_POSITION","reason":trial["reason"],
        "quote_reference_pnl_usd":None,
        "quote_reference_pnl_2pct_bid_haircut_usd":None,
        "original_source_sha256":trial["source_sha256"],
        "actual_broker_fills":0,"provider_requests":0,
        "exercise_or_expiry_cash_unknown":True,
    })


def gzip_evidence(path,doc):
    result=signed(doc)
    raw=(json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()
    comp=gzip.compress(raw,compresslevel=6,mtime=0)
    with path.open("xb") as f:
        f.write(comp);f.flush();os.fsync(f.fileno())
    return {"relative_path":"journals/"+path.name,
            "source_trial_sha":result["fingerprint"],
            "compressed_sha256":hashlib.sha256(comp).hexdigest(),
            "compressed_bytes":len(comp),"raw_bytes":len(raw)}


def exact_ledger(pairs,*,scope,policy,lag,dwell,missing):
    ledger=capital_simulate(pairs,scope=scope,policy=policy,
                            lag_seconds=lag,dwell_seconds=dwell)
    if not verify90(ledger) or ledger["actual_broker_orders"]!=0:
        raise V99Error("V99_ORIGINAL_V90_ACCOUNT_LEDGER_NOT_VERIFIED")
    return signed({
        "contract":CONTRACT+"-scenario-qualified-ledger-v1",
        "source_complete":len(missing)==0,
        "unqualified_causal_candidate_sources":missing,
        "original_v90_account_ledger":ledger,
        "original_stressed_quote_pnl_usd_if_complete":(
            ledger["closed_trade_stressed_quote_pnl_usd"]
            if not missing and not ledger["unresolved_exercise_or_expiry_cash"]
            else None),
        "cash_equity_known":not missing and not ledger["unresolved_exercise_or_expiry_cash"],
        "not_a_broker_fill_or_proven_profitable_strategy":True,
        "historical_news_joined":False,
    })


def run(v97b_dir,v98_dir,out_dir,*,source_reader=_local_cache_only,
        settings_factory=load_settings,calendar=None,reporter=print):
    if out_dir.exists() or out_dir.is_symlink():
        raise V99Error("V99_OUTPUT_ALREADY_EXISTS")
    calendar=calendar or get_market_calendar("XNYS")
    v98,original,root,events,available,no_data,unknown=inspect_v98(
        v97b_dir,v98_dir,calendar)
    variants=root["variant_results"]
    ids={x["trial_id"]:x for x in variants}
    grid=params()
    if (len(ids)!=49 or set(ids)!={x["trial_id"] for x in grid}
            or any(ids[x["trial_id"]]["parameters"]!=x["parameters"]
                   for x in grid)):
        raise V99Error("V99_49_REGISTERED_ENTRY_PARAMETERS_CHANGED")
    baseline={}
    for v in grid:
        if tuple(v["parameters"])==BASELINES[v["strategy"]]:
            if v["strategy"] in baseline:
                raise V99Error("V99_DUPLICATE_BASELINE_STRATEGY")
            baseline[v["strategy"]]=v["trial_id"]
    if len(baseline)!=6 or len(DEFINITIONS)!=24:
        raise V99Error("V99_FROZEN_RISK_AND_BASELINE_CONFIGURATION_CHANGED")

    by_cohort=defaultdict(list)
    for ev in events:
        if ev["trial_id"] not in ids or ids[ev["trial_id"]]["strategy"]!=ev["strategy"]:
            raise V99Error("V99_EVENT_TRIAL_ID_OR_STRATEGY_CHANGED")
        if ev["session"]>"2026-04-30":
            raise V99Error("V99_PROTECTED_MASTER_HOLDOUT_REQUESTED")
        by_cohort[cohort(ev["session"])].append(ev)

    settings=settings_factory(ROOT,"development")
    out_dir.mkdir(parents=True,exist_ok=False)
    (out_dir/"journals").mkdir()
    cohort_rows=[]
    all_journals=[]
    total_books=0
    total_unique_source_family=0
    missing_total=Counter()
    scenario_history=defaultdict(list)
    for name,start,end in COHORTS:
        cohort_events=by_cohort[name]
        grouped=defaultdict(list)
        missing_by_variant=defaultdict(list)
        for ev in cohort_events:
            qid=ev["exact_original_call_query_id"]
            if ev["qualified_original_source_sha256"] is None:
                reason=("PRIOR_PROVIDER_DISPATCH_UNCERTAIN_NO_RETRY"
                        if qid in unknown else "PROVIDER_EXPLICIT_NO_DATA")
                missing_by_variant[ev["trial_id"]].append({
                    "session":ev["session"],"original_query_id":qid,
                    "source_reason":reason,
                    "original_stock_decision_sha":ev["original_decision_sha"],
                })
                missing_total[reason]+=1
                continue
            key=(qid,ev["strategy"],ev["original_decision_sha"])
            grouped[key].append(ev)
        pair_map=defaultdict(list)
        outcome_counts=Counter()
        for index,(key,candidates) in enumerate(sorted(grouped.items()),1):
            qid,family,original_decision_sha=key
            original_sha=available[qid]
            evidence=source_reader(settings,qid)
            if (evidence.get("cache_evidence")!="CACHE_HIT"
                    or not isinstance(evidence.get("source"),dict)):
                raise V99Error("V99_LOCAL_SHA_ORIGINAL_CALL_ARCHIVE_UNAVAILABLE")
            source=evidence["source"]
            if (source["query_id"]!=qid or source["source_sha256"]!=original_sha
                    or source["status"]!="CACHE_HIT"):
                raise V99Error("V99_HISTORICAL_ORIGINAL_SOURCE_SHA_CHANGED")
            pivot=candidates[0]
            if any(ev["session"]!=pivot["session"]
                   or ev["decision_clock_et"]!=pivot["decision_clock_et"]
                   or ev["strike"]!=pivot["strike"]
                   or ev["original_stock_sha256"]!=pivot["original_stock_sha256"]
                   or ev["original_decision_sha"]!=pivot["original_decision_sha"]
                   for ev in candidates):
                raise V99Error("V99_UNSAFE_SOURCE_ECONOMIC_REPLAY_REUSE")
            decision,demand=decision_and_demand(pivot,source)
            selected={k:demand["kwargs"][k] for k in
                      ("symbol","date_et","expiration","strike","right")}
            tape=prepare_original_tape(source,selected,pivot["session"])
            close=calendar.regular_open_close(
                date.fromisoformat(pivot["session"]))[1]
            outcome_rows=[]
            for policy in POLICIES:
                for lag in LAGS:
                    trial=replay(decision,demand,source,tape,policy=policy,
                                 lag_seconds=lag,market_close_et=close)
                    if not verify84(trial):
                        raise V99Error("V99_V84_TRIAL_SIGNATURE_CHANGED")
                    exits=[]
                    for dwell in DWELLS:
                        exit_quote=(censored_exit(trial,dwell)
                            if trial["status"]=="UNRESOLVED_POSITION"
                            else recheck(trial,source,tape,dwell_seconds=dwell))
                        if not verify86(exit_quote):
                            raise V99Error("V99_V86_EXIT_SIGNATURE_CHANGED")
                        exits.append(exit_quote)
                        outcome_counts[exit_quote["status"]]+=1
                        for ev in candidates:
                            pair_map[(ev["trial_id"],policy,lag,dwell)].append(
                                (trial,exit_quote))
                    outcome_rows.append({"original_v84_trial":trial,
                                         "original_v86_exit_rechecks":exits})
            journal=gzip_evidence(
                out_dir/"journals"/f"{name}_{index:05d}_{qid[:20]}_{family}.json.gz",{
                "contract":CONTRACT+"-source-linked-quote-trials-v1",
                "original_v97b_candidate_event_count":len(candidates),
                "variant_trial_ids":sorted({x["trial_id"] for x in candidates}),
                "original_v97b_stock_decision_sha":original_decision_sha,
                "original_source_query_id":qid,
                "original_source_sha256":original_sha,
                "original_asof_bullish_derived_decision":decision,
                "original_derived_exact_source_demand":demand,
                "source_quote_rows":len(tape),
                "original_24_variant_economic_trials":outcome_rows,
                "historical_news_used":False,
                "provider_requests":0,"broker_orders":0,
            })
            all_journals.append({**journal,"cohort":name,"query_id":qid,
                                  "family":family,"candidate_count":len(candidates)})
            if index%25==0 or index==len(grouped):
                reporter(f"V99 {name} source_family_tapes={index}/{len(grouped)} "
                         f"original_sha_journals={len(all_journals)} "
                         "provider_calls=0 broker_orders=0")
        ledger_rows=[]
        for variant in grid:
            trial_id=variant["trial_id"];family=variant["strategy"]
            missing=missing_by_variant[trial_id]
            for policy,lag,dwell in DEFINITIONS:
                result=exact_ledger(
                    pair_map[(trial_id,policy,lag,dwell)],
                    scope=family,policy=policy,lag=lag,dwell=dwell,
                    missing=missing)
                ledger_rows.append({"trial_id":trial_id,"strategy":family,
                    "policy":policy,"lag_seconds":lag,"limit_rest_seconds":dwell,
                    "qualified":result})
        for policy,lag,dwell in DEFINITIONS:
            baseline_pairs=[]
            missing=[]
            for family,trial_id in baseline.items():
                baseline_pairs.extend(pair_map[(trial_id,policy,lag,dwell)])
                missing.extend(missing_by_variant[trial_id])
            result=exact_ledger(baseline_pairs,scope="all_six_new_families",
                                policy=policy,lag=lag,dwell=dwell,missing=missing)
            ledger_rows.append({"trial_id":"V99_BASELINE_ALL_SIX_CALL_ONLY",
                "strategy":"combined_six_frozen_baselines",
                "policy":policy,"lag_seconds":lag,"limit_rest_seconds":dwell,
                "qualified":result})
        if len(ledger_rows)!=50*24:
            raise V99Error("V99_EXPECTED_1200_CAPITAL_SCENARIOS_PER_COHORT")
        for row in ledger_rows:
            result=row["qualified"]
            book=result["original_v90_account_ledger"]
            if result["cash_equity_known"]:
                pnl=Decimal(result["original_stressed_quote_pnl_usd_if_complete"])
                months=sum((Decimal(x) for x in
                            book["stressed_month_pnl_usd"].values()),Decimal("0"))
                weeks=sum((Decimal(x) for x in
                           book["stressed_week_pnl_usd"].values()),Decimal("0"))
                cash_end=Decimal(book["ending_stressed_quote_cash_usd"])
                cash_start=Decimal(book["starting_cash_usd"])
                if months!=pnl or weeks!=pnl or cash_end-cash_start!=pnl:
                    raise V99Error("V99_WEEK_MONTH_CASH_LEDGER_ARITHMETIC_DRIFT")
            k=(row["trial_id"],row["policy"],row["lag_seconds"],
               row["limit_rest_seconds"])
            scenario_history[k].append({
                "cohort":name,
                "quote_pnl_if_complete_usd":row["qualified"][
                    "original_stressed_quote_pnl_usd_if_complete"],
                "source_complete":row["qualified"]["source_complete"],
                "cash_equity_known":row["qualified"]["cash_equity_known"],
                "simulated_closed_wins":row["qualified"][
                    "original_v90_account_ledger"]["positive_closed"],
                "simulated_closed_losses":row["qualified"][
                    "original_v90_account_ledger"]["negative_closed"],
                "monthly_stressed_pnl_usd":row["qualified"][
                    "original_v90_account_ledger"]["stressed_month_pnl_usd"],
                "weekly_stressed_pnl_usd":row["qualified"][
                    "original_v90_account_ledger"]["stressed_week_pnl_usd"],
            })
        books=write_once(out_dir/f"{name}_capital_scenarios.json",{
            "contract":CONTRACT+"-1200-scenarios-cohort-v1",
            **cohort_bounds(name,start,end),
            "source_family_tape_groups":len(grouped),
            "candidate_occurrences":len(cohort_events),
            "source_unknown_candidate_occurrences":sum(
                len(x) for x in missing_by_variant.values()),
            "source_quality":"2020_ORIGINAL_COHORT_INCOMPLETE"
                if name=="2020_SOURCE_PARTIAL" else "PER_SCENARIO_QUALIFIED_ONLY",
            "outcome_counts_for_dedup_source_family":dict(sorted(outcome_counts.items())),
            "capital_scenarios":ledger_rows,
            "news_as_of_features_joined":False,
            "actual_broker_orders":0,"provider_requests":0,
        })
        cohort_rows.append({
            "cohort":name,"capital_scenarios_sha":books["fingerprint"],
            "capital_scenario_count":len(ledger_rows),
            "candidate_occurrences":len(cohort_events),
            "source_unknown_candidate_occurrences":sum(
                len(x) for x in missing_by_variant.values()),
            "qualified_and_flat_scenarios":sum(
                row["qualified"]["cash_equity_known"] for row in ledger_rows),
            "source_tapes_distinct_family_count":len(grouped),
        })
        total_books+=len(ledger_rows)
        total_unique_source_family+=len(grouped)
        reporter(f"V99 PERIOD_COMPLETE {name} ledgers={len(ledger_rows)} "
                 f"qualified_flat={cohort_rows[-1]['qualified_and_flat_scenarios']} "
                 f"source_unknown_candidates={cohort_rows[-1]['source_unknown_candidate_occurrences']}")
    if len(scenario_history)!=50*24 or total_books!=9*50*24:
        raise V99Error("V99_COMPLETE_HISTORY_SCENARIO_GRID_NOT_RECTANGULAR")
    historical_comparison=[]
    for (trial_id,policy,lag,dwell),history in sorted(scenario_history.items()):
        if len(history)!=9 or len({h["cohort"] for h in history})!=9:
            raise V99Error("V99_DUPLICATE_OR_MISSING_HISTORICAL_COHORT")
        development=[h for h in history if h["cohort"]!="2020_SOURCE_PARTIAL"]
        complete=[h for h in development if h["cash_equity_known"]]
        if any(h["quote_pnl_if_complete_usd"] is None for h in complete):
            raise V99Error("V99_CASH_COMPLETE_SCENARIO_WITH_NULL_PNL")
        positive=sum(Decimal(h["quote_pnl_if_complete_usd"])>0 for h in complete)
        monthly=[Decimal(pnl) for h in complete
                 for pnl in h["monthly_stressed_pnl_usd"].values()]
        weekly=[Decimal(pnl) for h in complete
                for pnl in h["weekly_stressed_pnl_usd"].values()]
        nominal=sum((Decimal(h["quote_pnl_if_complete_usd"]) for h in complete),
                    Decimal("0"))
        historical_comparison.append({
            "trial_id":trial_id,"policy":policy,
            "lag_seconds":lag,"limit_rest_seconds":dwell,
            "historical_periods":history,
            "expected_eight_source_complete_cohorts":8,
            "qualified_flat_development_cohorts":len(complete),
            "unqualified_or_cash_unresolved_development_cohorts":
                [h["cohort"] for h in development if not h["cash_equity_known"]],
            "positive_qualified_development_cohorts":positive,
            "positive_in_all_eight_if_full_coverage":(
                len(complete)==8 and positive==8),
            "nominal_partial_quote_pnl_usd":str(nominal),
            "nominal_eight_period_quote_pnl_usd_if_complete":(
                str(nominal) if len(complete)==8 else None),
            "positive_completed_months":sum(x>0 for x in monthly),
            "negative_completed_months":sum(x<0 for x in monthly),
            "positive_completed_weeks":sum(x>0 for x in weekly),
            "negative_completed_weeks":sum(x<0 for x in weekly),
            "original_2020_source_cohort_excluded_from_eight_period_gate":True,
            "in_sample_exploratory_not_independent_validation":True,
        })
    comparison=write_once(out_dir/"eight_period_exploratory_matrix.json",{
        "contract":CONTRACT+"-eight-period-account-robustness-v1",
        "original_v98_source_sha":v98["fingerprint"],
        "comparison_scenario_count":len(historical_comparison),
        "historical_comparisons":historical_comparison,
        "fully_comparable_eight_period_scenarios":sum(
            h["qualified_flat_development_cohorts"]==8
            for h in historical_comparison),
        "positive_in_all_eight_scenarios":sum(
            h["positive_in_all_eight_if_full_coverage"]
            for h in historical_comparison),
        "2020_partial_source_omitted_from_eight_period_profit_gate":True,
        "not_a_compounded_return_or_out_of_sample_alpha_proof":True,
        "provider_calls":0,"broker_orders":0,
    })
    manifest=write_once(out_dir/"trial_archive_manifest.json",{
        "contract":CONTRACT+"-signed-trial-archive-manifest-v1",
        "original_V97B_signed_summary_sha":original["fingerprint"],
        "original_V98_signed_summary_sha":v98["fingerprint"],
        "source_tape_family_journals":all_journals,
        "total_source_family_journals":len(all_journals),
        "provider_requests":0,"broker_orders":0,
    })
    report=write_once(out_dir/"summary.json",{
        "contract":CONTRACT,
        "original_V97B_summary_sha":original["fingerprint"],
        "original_V97B_candidate_root_sha":root["fingerprint"],
        "original_V98_summary_sha":v98["fingerprint"],
        "trial_manifest_sha":manifest["fingerprint"],
        "eight_period_exploratory_comparison_sha":comparison["fingerprint"],
        "fully_comparable_eight_period_scenarios":comparison[
            "fully_comparable_eight_period_scenarios"],
        "positive_in_all_eight_qualified_scenarios":comparison[
            "positive_in_all_eight_scenarios"],
        "cohorts":cohort_rows,
        "preregistered_call_entry_variants":49,
        "preregistered_risk_execution_variants":24,
        "separate_baseline_combination_per_cohort":24,
        "total_standalone_and_combined_capital_scenarios":total_books,
        "signed_source_family_quote_journals":len(all_journals),
        "source_qualified_distinct_call_tapes":len(available),
        "new_V98_explicit_no_data_query_id":no_data[0],
        "original_unknown_query_id":next(iter(unknown)),
        "missing_candidate_occurrence_reasons":dict(sorted(missing_total.items())),
        "news_metadata_context_qualified_or_joined":False,
        "no_future_2026_master_holdout":True,
        "in_sample_exploratory_only":True,
        "quote_reference_not_verified_broker_fills":True,
        "source_data_read_only":True,
        "provider_requests":0,"broker_orders":0,
    })
    reporter(f"V99 COMPLETE 49 entry x 24 exit/latency quote scenarios "
             f"capital_ledgers={total_books} source_family_journals={len(all_journals)} "
             f"eight_period_fully_comparable={comparison['fully_comparable_eight_period_scenarios']} "
             f"positive_in_all_eight={comparison['positive_in_all_eight_scenarios']} "
             "providers=0 broker_orders=0 asof_news_join=NOT_RUN")
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v97b-dir",type=Path,required=True)
    parser.add_argument("--v98-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        run(args.v97b_dir,args.v98_dir,args.output_dir)
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print(f"STOP V99 error={type(exc).__name__} reason={str(exc)[:220]} "
              "no_new_provider_calls=True broker_orders=0",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
