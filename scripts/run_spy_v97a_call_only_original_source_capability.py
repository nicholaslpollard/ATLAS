from __future__ import annotations

"""V97A: signed offline CALL-only strategy / source / news-readiness census.

No ThetaData SDK, provider, broker, SQLite modifications, raw quote GET,
P&L evaluation or strategy tuning. All original V89 decisions and SHA-linked
source receipts are preserved. This inventories genuine CALL source
availability before a large 2026 V97 historical CALL-only causal experiment.
"""

import argparse
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path
import json
import os
import re

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v89_six_family_causal_registry import (
    FAMILIES,verified as verified_decision,
)
from scripts.run_spy_v89_six_family_source_batch import CONTRACT as V89
from scripts.run_spy_v90_six_family_source_replay import read_signed

ROOT=Path(__file__).resolve().parents[1]
CONTRACT="atlas-v97a-actual-original-call-source-and-strategy-capability-v1"
COHORTS={
    "2018_full":("2018-01-01","2018-12-31","spy_v93_v89_six_families_2018_full_*"),
    "2019_full":("2019-01-01","2019-12-31","spy_v93_v89_six_families_2019_full_*"),
    "2020_full_SOURCE_INCOMPLETE":("2020-01-01","2020-12-31","spy_v93_v89_six_families_2020_full_*"),
    "2021_full":("2021-01-01","2021-12-31","spy_v95_v89_six_families_2021_full_*"),
    "2022_full":("2022-01-01","2022-12-31","spy_v95_v89_six_families_2022_full_*"),
    "2023_full":("2023-01-01","2023-12-31","spy_v95_v89_six_families_2023_full_*"),
    "2024_full":("2024-01-01","2024-12-31","spy_v89_six_new_families_2024_full_*"),
    "2025_h2":("2025-07-01","2025-12-31","spy_v89_six_new_families_2025_h2_*"),
    "2026_janapr":("2026-01-01","2026-04-30","spy_v89_six_new_families_2026_janapr_*"),
}
NEUTRAL={"NO_SIGNAL","SOURCE_UNQUALIFIED_NO_TRADE",
         "OPTION_0DTE_BASE_SCHEDULE_UNQUALIFIED_NO_TRADE"}
COMPLETE={"CACHE_HIT","FETCHED_AND_ARCHIVED"}
NEWS_START=date(2021,1,1)
NEWS_END=date(2026,9,19)


class V97AError(ValueError):
    pass


def signed(x):
    return {**x,"fingerprint":_fingerprint(x)}


def verify(x):
    return (isinstance(x,dict)
            and x.get("fingerprint")==_fingerprint({
                k:v for k,v in x.items() if k!="fingerprint"}))


def write_once(path,doc):
    result=signed(doc)
    with path.open("x",encoding="utf8") as fp:
        json.dump(result,fp,indent=2,sort_keys=True,allow_nan=False)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    return result


def code_census(root):
    base=root/"packages"/"strategies"
    names=sorted(base.rglob("*.py")) if base.is_dir() else []
    nonempty=[f for f in names if f.stat().st_size>0]
    src=(base/"reference_library.py").read_text(encoding="utf8")
    registry=(base/"registry.py").read_text(encoding="utf8")
    reference_ids=re.findall(r'strategy_id="([^"]+)"',src)
    rule_ids=re.findall(r'_rule\(\s*"([^"]+)"',registry)
    if len(reference_ids)!=9 or len(rule_ids)!=8:
        raise V97AError("ORIGINAL_REFERENCE_STRATEGY_REGISTRY_CENSUS_CHANGED")
    return {
        "python_files":len(names),
        "empty_placeholders":len(names)-len(nonempty),
        "nonempty_including_infrastructure":len(nonempty),
        "reference_daily_stock_rule_ids":reference_ids,
        "generic_daily_strategy_registry_ids":rule_ids,
        "original_V89_stock_to_options_strategy_ids":list(FAMILIES),
        "generic_stock_implementations_are_not_executable_CALL_trades":True,
        "outside_V89_strategies_option_adapter_is_not_yet_qualified":True,
    }


def read_original_cohort(folder,key,start,end):
    if not folder.is_dir() or folder.is_symlink():
        raise V97AError("ORIGINAL_V89_DIRECTORY_NOT_AVAILABLE")
    entry=read_signed(folder/"entry_screen.json",V89)
    plan=read_signed(folder/"exact_option_source_plan.json",V89+"-source-plan-v1")
    rec=read_signed(folder/"source_receipts.json",V89+"-source-receipts-v1")
    summary=read_signed(folder/"summary.json",V89+"-summary-v1")
    if (entry["start"]!=start or entry["end"]!=end
            or entry["registry"]!=FAMILIES
            or entry["registry_sha"]!=_fingerprint(FAMILIES)
            or len(entry["cases"])!=entry["sessions"]*len(FAMILIES)
            or plan["parent_entry_sha"]!=entry["fingerprint"]
            or rec["parent_plan_sha"]!=plan["fingerprint"]
            or summary["entry_sha"]!=entry["fingerprint"]
            or summary["source_plan_sha"]!=plan["fingerprint"]
            or summary["receipt_sha"]!=rec["fingerprint"]
            or len(plan["demands"])!=summary["exact_source_requirements"]
            or summary["broker_orders"]!=0 or rec["broker_orders"]!=0):
        raise V97AError("ORIGINAL_V89_COHORT_ROOT_MISMATCH")
    receipts={}
    for item in rec["original_provider_source_receipts"]:
        cid=item["candidate_id"]
        if (cid in receipts or item["status"] not in COMPLETE
                or len(item["source_sha256"])!=64):
            raise V97AError("ORIGINAL_V89_RECEIPT_INVALID_OR_DUPLICATE")
        receipts[cid]=item
    demands={}
    for d in plan["demands"]:
        if (d["candidate_id"] in demands or not verify(d)
                or d["kwargs"]["symbol"]!="SPY"
                or d["kwargs"]["date_et"]!=d["kwargs"]["expiration"]
                or d["kwargs"]["interval"]!="1s"
                or d["kwargs"]["right"] not in ("call","put")
                or d["method"]!="option_history_exact_quote_tape"):
            raise V97AError("ORIGINAL_V89_EXACT_OPTION_DEMAND_CHANGED")
        demands[d["candidate_id"]]=d
    if not set(receipts).issubset(demands):
        raise V97AError("ORIGINAL_V89_SOURCE_NOT_DEMANDED")
    cases=[]
    all_candidates=set()
    for case in entry["cases"]:
        decision=case["causal_decision"]
        no_source_decision=decision is None
        if no_source_decision:
            # V89 intentionally logs a null causal decision when a necessary
            # original *past* bar is unavailable. Keep this consideration and
            # its original no-trade reason, never create a synthetic signal.
            if (case["status"]!="SOURCE_UNQUALIFIED_NO_TRADE"
                    or case["reason"] not in (
                        "V89_PRIOR_CLOSE_UNAVAILABLE",
                        "V89_EXACT_CLOSED_MINUTES_REQUIRED")
                    or case.get("source_demand_sha") is not None
                    or case.get("stock_source_sha256") is not None
                    or case["strategy"] not in FAMILIES
                    or not start<=case["session"]<=end):
                raise V97AError("ORIGINAL_NULL_DECISION_SOURCE_REJECTION_INVALID")
        elif (case["session"]!=decision["session"]
                or case["strategy"]!=decision["strategy_id"]
                or case["strategy"] not in FAMILIES
                or not verified_decision(decision)):
            raise V97AError("ORIGINAL_CAUSAL_STOCK_DECISION_SHA_INVALID")
        signal=case["status"]=="OPTIONS_EXACT_SOURCE_DEMAND_PREPARED"
        if case["status"] not in NEUTRAL and not signal:
            raise V97AError("UNEXPECTED_ORIGINAL_ENTRY_STATUS")
        d=None;src=None
        if signal:
            direction=decision["direction"]
            if direction not in ("CALL","PUT"):
                raise V97AError("ORIGINAL_OPTION_SIGNAL_SIDE_MISMATCH")
            cid=f"SPY_{case['session']}_{case['strategy']}_{direction.lower()}"
            d=demands.get(cid)
            if (not d or cid in all_candidates
                    or d["fingerprint"]!=case["source_demand_sha"]
                    or d["strategy_decision_sha"]!=decision["fingerprint"]
                    or d["selection_prior_source_sha256"]!=case["stock_source_sha256"]
                    or d["kwargs"]["right"]!=direction.lower()):
                raise V97AError("ORIGINAL_CALL_OR_PUT_SOURCE_IDENTITY_CHANGED")
            src=receipts.get(cid)
            if src and src["query_id"]!=d["query_id"]:
                raise V97AError("ORIGINAL_CALL_OR_PUT_RECEIPT_QUERY_CHANGED")
            all_candidates.add(cid)
        elif case["source_demand_sha"] is not None:
            raise V97AError("ORIGINAL_NONTRADE_SHOULD_NOT_HAVE_SOURCE")
        when=date.fromisoformat(case["session"])
        news=("PIT_NEWS_METADATA_SOURCE_WINDOW_AWAITING_SHA_CHECK"
              if NEWS_START<=when<=NEWS_END
              else "PIT_NEWS_UNAVAILABLE_OR_OUTSIDE_ACCEPTED_SCOPE")
        cases.append({
            "cohort":key,"session":case["session"],
            "strategy":case["strategy"],
            "original_decision_sha":decision["fingerprint"] if decision else None,
            "original_stock_sha256":case.get("stock_source_sha256"),
            "original_signal_status":case["status"],
            "original_reason":case["reason"],
            "decision_at_et":decision["decision_at_et"] if decision else None,
            "original_side":decision["direction"] if decision else None,
            "as_of_stock_feature_values":decision["features"] if decision else None,
            "source_unqualified_null_original_decision":no_source_decision,
            "exact_option_query_id":d["query_id"] if d else None,
            "original_demand_sha":d["fingerprint"] if d else None,
            "CALL_only_source_status":(
                "ORIGINAL_STOCK_SOURCE_UNQUALIFIED_NO_CAUSAL_DECISION"
                if no_source_decision else
                ("CALL_VERIFIED_ORIGINAL_ARCHIVE" if src
                 else "CALL_ORIGINAL_SOURCE_UNRESOLVED")
                if d and d["kwargs"]["right"]=="call" else
                ("PUT_EXCLUDED_FROM_CALL_ONLY" if d else
                 "NO_ORIGINAL_EXECUTABLE_OPTION_DEMAND")
            ),
            "call_original_source_sha256":(
                src["source_sha256"] if src and d
                and d["kwargs"]["right"]=="call" else None
            ),
            "original_call_strike":(
                d["kwargs"]["strike"] if d and
                d["kwargs"]["right"]=="call" else None),
            "original_call_expiry":(
                d["kwargs"]["expiration"] if d and
                d["kwargs"]["right"]=="call" else None),
            "predecision_news_status":news,
            "news_event_counts":None,
            "historical_broker_fill_verified":False,
            "option_quote_prices_loaded_by_V97A":False,
        })
    if set(demands)!=all_candidates:
        raise V97AError("ORIGINAL_SOURCE_DEMAND_NOT_MATCHED_TO_CAUSAL_DECISION")
    if len(cases)!=entry["sessions"]*6:
        raise V97AError("ORIGINAL_SOURCE_DECISION_CENSUS_SHORT")
    lineage={
        "cohort":key,"start":start,"end":end,
        "V89_folder":folder.name,
        "entry_sha":entry["fingerprint"],
        "source_plan_sha":plan["fingerprint"],
        "receipt_sha":rec["fingerprint"],
        "summary_sha":summary["fingerprint"],
        "original_sessions":entry["sessions"],
        "original_six_family_considerations":len(cases),
        "exact_original_source_demands":len(demands),
        "archived_exact_source_receipts":len(receipts),
        "original_source_fully_complete":len(demands)==len(receipts),
        "CALL_original_demands":sum(d["kwargs"]["right"]=="call" for d in demands.values()),
        "CALL_original_receipts":sum(d["kwargs"]["right"]=="call"
                                     for c,d in demands.items() if c in receipts),
        "PUT_demands_excluded_from_CALL_replay":sum(
            d["kwargs"]["right"]=="put" for d in demands.values()),
        "source_unqualified_null_decision_considerations":sum(
            x["source_unqualified_null_original_decision"] for x in cases),
        "historical_quote_execution_not_proven":True,
    }
    return cases,lineage


def run(root,output,*,reporter=print):
    research=root/"data"/"research"
    if (not research.is_dir() or not (root/"packages"/"strategies").is_dir()
            or output.exists() or output.is_symlink()):
        raise V97AError("V97A_RESEARCH_ROOT_OR_IMMUTABLE_OUTPUT_INVALID")
    # No general historical report glob and no access to the protected holdout.
    cases=[]
    lineage=[]
    for key,(start,end,pattern) in COHORTS.items():
        matches=[p for p in research.glob(pattern)
                 if p.is_dir() and not p.is_symlink()
                 and (p/"summary.json").is_file()]
        if len(matches)!=1:
            raise V97AError(f"V97A_ORIGINAL_COHORT_NOT_UNIQUE:{key}")
        try:
            subset,parent=read_original_cohort(matches[0],key,start,end)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            raise V97AError(
                f"V97A_COHORT_SOURCE_AUDIT_FAILED:{key}:"
                f"{type(exc).__name__}:{str(exc)[:160]}"
            ) from exc
        cases.extend(subset);lineage.append(parent)
        reporter(f"V97A {key}: sessions={parent['original_sessions']} "
                 f"CALL_archived={parent['CALL_original_receipts']}/"
                 f"{parent['CALL_original_demands']} "
                 f"PUT_excluded={parent['PUT_demands_excluded_from_CALL_replay']} "
                 "providers=0 broker_orders=0")
    status=Counter(x["CALL_only_source_status"] for x in cases)
    by_strategy={
        family:{
            "stock_considerations":sum(x["strategy"]==family for x in cases),
            "call_sources_archived":sum(x["strategy"]==family and
                x["CALL_only_source_status"]=="CALL_VERIFIED_ORIGINAL_ARCHIVE"
                for x in cases),
            "call_source_unknown":sum(x["strategy"]==family and
                x["CALL_only_source_status"]=="CALL_ORIGINAL_SOURCE_UNRESOLVED"
                for x in cases),
            "put_sources_excluded":sum(x["strategy"]==family and
                x["CALL_only_source_status"]=="PUT_EXCLUDED_FROM_CALL_ONLY"
                for x in cases),
        } for family in FAMILIES
    }
    output.mkdir(parents=True,exist_ok=False)
    full=write_once(output/"original_call_source_considerations.json",{
        "contract":CONTRACT+"-all-original-decision-considerations-v1",
        "original_source_cohorts":lineage,
        "decisions":cases,
        "historical_news_used_to_decide_any_trade":False,
        "stock_features_as_of_source_claim_retained_from_V89":True,
        "protected_master_2026_may_aug_unaccessed":True,
        "provider_calls":0,"broker_orders":0,
    })
    summary=write_once(output/"summary.json",{
        "contract":CONTRACT,
        "original_all_considerations_sha":full["fingerprint"],
        "actual_code_capability_census":code_census(root),
        "historical_original_cohort_count":len(lineage),
        "historical_complete_source_cohorts":sum(
            c["original_source_fully_complete"] for c in lineage),
        "historical_incomplete_source_cohorts":[
            c["cohort"] for c in lineage if not c["original_source_fully_complete"]],
        "original_six_family_considerations":len(cases),
        "original_unique_candidate_CALL_source_count":
            status["CALL_VERIFIED_ORIGINAL_ARCHIVE"]+
            status["CALL_ORIGINAL_SOURCE_UNRESOLVED"],
        "original_CALL_sources_archived":status["CALL_VERIFIED_ORIGINAL_ARCHIVE"],
        "original_CALL_sources_unresolved":status["CALL_ORIGINAL_SOURCE_UNRESOLVED"],
        "original_PUT_sources_not_eligible_for_CALL_only":
            status["PUT_EXCLUDED_FROM_CALL_ONLY"],
        "no_signal_or_no_demand_considerations":
            status["NO_ORIGINAL_EXECUTABLE_OPTION_DEMAND"],
        "original_stock_source_unqualified_null_decision_considerations":
            status["ORIGINAL_STOCK_SOURCE_UNQUALIFIED_NO_CAUSAL_DECISION"],
        "per_family_source_capabilities":by_strategy,
        "distinct_qualifying_call_query_ids":len({
            x["exact_option_query_id"] for x in cases
            if x["CALL_only_source_status"]=="CALL_VERIFIED_ORIGINAL_ARCHIVE"
        }),
        "news_metadata_effective_availability_not_yet_joined":True,
        "news_current_accepted_source_period_from":"2021-01-01",
        "news_historical_coverage_before_2021":"UNAVAILABLE",
        "actual_historical_option_fill_or_pnl_recomputed":False,
        "missing_new_rule_or_parameter_call_tapes_require_separate_source_union":True,
        "protected_master_holdout_accessed":False,
        "provider_requests":0,"broker_orders":0,
    })
    reporter("V97A COMPLETE offline CALL-only original-source census "
             f"archived={summary['original_CALL_sources_archived']} "
             f"unknown={summary['original_CALL_sources_unresolved']} "
             f"excluded_put={summary['original_PUT_sources_not_eligible_for_CALL_only']} "
             f"total_stock_considerations={len(cases)} "
             "provider_calls=0 broker_orders=0")
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        run(args.root,args.output_dir)
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print(f"STOP V97A source census error_type={type(exc).__name__} "
              f"reason={str(exc)[:240]} "
              "provider_calls=0 broker_orders=0",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
