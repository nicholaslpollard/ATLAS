from __future__ import annotations

"""V100 signed independent V99 49x24 source/ledger audit and chronological selection.

No options price fetching, news feature peeking, simulated future time at the
point of selection, brokerage access, or parameter fitting. This is research
on historical periods already inspected, not true untouched out-of-sample.
"""

import argparse
from collections import Counter
from datetime import date
from decimal import Decimal,InvalidOperation
import gzip
import hashlib
import json
import os
from pathlib import Path

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts.run_spy_v99_49_call_variant_quote_economics import CONTRACT as V99

CONTRACT="atlas-v100-independent-full-v99-audit-and-causal-rolling-policy-v1"
ALL_PERIODS=("2018_full","2019_full","2020_SOURCE_PARTIAL","2021_full",
             "2022_full","2023_full","2024_full","2025_h2","2026_janapr")
DEVELOPMENT=tuple(x for x in ALL_PERIODS if x!="2020_SOURCE_PARTIAL")
SELECTORS=("prior_total","prior_profitable_periods","prior_worst_period")
FIRST_EVALUATION_INDEX=3
MIN_TRAINING_CLOSED_TRADES=10


class V100Error(ValueError):
    pass


def check(obj,contract=None):
    if (not isinstance(obj,dict)
            or obj.get("fingerprint")!=_fingerprint({
                k:v for k,v in obj.items() if k!="fingerprint"})
            or contract is not None and obj.get("contract")!=contract):
        raise V100Error("V100_SHA_OR_CONTRACT_INVALID")
    return obj


def source(path,contract=None):
    return check(json.loads(path.read_text(encoding="utf8")),contract)


def decimal(value):
    try:
        v=Decimal(str(value))
    except (TypeError,ValueError,InvalidOperation) as exc:
        raise V100Error("V100_NON_NUMERIC_CASH") from exc
    if not v.is_finite():
        raise V100Error("V100_NONFINITE_CASH")
    return v


def write_once(path,item):
    obj={**item,"fingerprint":_fingerprint(item)}
    payload=json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+"\n"
    with path.open("x",encoding="utf8") as f:
        f.write(payload);f.flush();os.fsync(f.fileno())
    return obj


def scenario_key(item):
    return (item["trial_id"],item["policy"],item["lag_seconds"],
            item["limit_rest_seconds"])


def source_journal_audit(root,manifest):
    entries=manifest["source_tape_family_journals"]
    if len(entries)!=manifest["total_source_family_journals"]!=630:
        raise V100Error("V100_630_ORIGINAL_TRIAL_JOURNALS_REQUIRED")
    status=Counter()
    cohorts=Counter()
    unique_queries={}
    for ref in entries:
        path=root/ref["relative_path"]
        if not path.is_file() or path.is_symlink():
            raise V100Error("V100_ORIGINAL_GZIP_JOURNAL_MISSING")
        comp=path.read_bytes()
        if (len(comp)!=ref["compressed_bytes"]
                or hashlib.sha256(comp).hexdigest()!=ref["compressed_sha256"]):
            raise V100Error("V100_ORIGINAL_GZIP_BYTES_SHA_INVALID")
        raw=gzip.decompress(comp)
        if len(raw)!=ref["raw_bytes"]:
            raise V100Error("V100_ORIGINAL_JOURNAL_RAW_LENGTH_CHANGED")
        doc=check(json.loads(raw),V99+"-source-linked-quote-trials-v1")
        if (doc["fingerprint"]!=ref["source_trial_sha"]
                or doc["original_source_query_id"]!=ref["query_id"]
                or len(doc["original_24_variant_economic_trials"])!=6
                or doc["provider_requests"]!=0 or doc["broker_orders"]!=0):
            raise V100Error("V100_ORIGINAL_JOURNAL_CASE_PARENT_DRIFT")
        decision=check(doc["original_asof_bullish_derived_decision"])
        demand=check(doc["original_derived_exact_source_demand"])
        if (decision["direction"]!="CALL"
                or demand["strategy_decision_sha"]!=decision["fingerprint"]
                or demand["query_id"]!=doc["original_source_query_id"]
                or doc["original_source_sha256"] is None):
            raise V100Error("V100_HISTORICAL_CALL_CAUSAL_SOURCE_CHANGED")
        qid=doc["original_source_query_id"]
        sha=doc["original_source_sha256"]
        if qid in unique_queries and unique_queries[qid]!=sha:
            raise V100Error("V100_SHARED_SOURCE_QUERY_SHA_CONFLICT")
        unique_queries[qid]=sha
        for group in doc["original_24_variant_economic_trials"]:
            trial=check(group["original_v84_trial"])
            if len(group["original_v86_exit_rechecks"])!=4:
                raise V100Error("V100_V86_EXIT_RECHECK_CENSUS_CHANGED")
            for exit_quote in group["original_v86_exit_rechecks"]:
                check(exit_quote)
                if (exit_quote["original_trial_sha"]!=trial["fingerprint"]
                        or trial["actual_broker_fills"]!=0
                        or exit_quote["actual_broker_fills"]!=0):
                    raise V100Error("V100_ORIGINAL_CAUSAL_EXIT_SHA_CHANGED")
                status[exit_quote["status"]]+=1
        cohorts[ref["cohort"]]+=1
    if len(unique_queries)!=576 or sum(cohorts.values())!=630:
        raise V100Error("V100_ORIGINAL_SOURCE_TAPE_POPULATION_CHANGED")
    return {"archive_sha_checked":len(entries),
            "unique_original_historical_query_id":len(unique_queries),
            "embedded_v84_sha_checked":len(entries)*6,
            "embedded_v86_sha_checked":len(entries)*24,
            "quote_replay_status_counts":dict(sorted(status.items())),
            "original_quote_journals_per_cohort":dict(sorted(cohorts.items()))}


def verify_every_ledger(root,summary,comparison,manifest,*,full_journals=True):
    if (summary["trial_manifest_sha"]!=manifest["fingerprint"]
            or summary["eight_period_exploratory_comparison_sha"]!=comparison["fingerprint"]
            or summary["total_standalone_and_combined_capital_scenarios"]!=10800
            or summary["signed_source_family_quote_journals"]!=630
            or summary["provider_requests"]!=0 or summary["broker_orders"]!=0
            or summary["source_qualified_distinct_call_tapes"]!=576
            or summary["news_metadata_context_qualified_or_joined"] is not False
            or summary["no_future_2026_master_holdout"] is not True):
        raise V100Error("V100_V99_COMPLETE_SIGNED_ANCESTRY_DRIFT")
    audit=source_journal_audit(root,manifest) if full_journals else {
        "archive_sha_checked":0,
        "detailed_quote_journal_verification_deferred":True,
        "manifest_reported_journals":manifest["total_source_family_journals"],
    }
    cohorts={}
    reconciled=0
    qualified=Counter()
    status=Counter()
    for meta in summary["cohorts"]:
        name=meta["cohort"]
        if name not in ALL_PERIODS or name in cohorts:
            raise V100Error("V100_DUPLICATE_OR_FOREIGN_HISTORICAL_PERIOD")
        doc=source(root/f"{name}_capital_scenarios.json",
                   V99+"-1200-scenarios-cohort-v1")
        if (doc["fingerprint"]!=meta["capital_scenarios_sha"]
                or len(doc["capital_scenarios"])!=1200
                or doc["cohort"]!=name
                or doc["actual_broker_orders"]!=0 or doc["provider_requests"]!=0):
            raise V100Error("V100_ORIGINAL_COHORT_CASH_PARENT_INVALID")
        period={}
        for row in doc["capital_scenarios"]:
            key=scenario_key(row)
            if key in period:
                raise V100Error("V100_DUPLICATE_SCENARIO_IN_PERIOD")
            q=check(row["qualified"],V99+"-scenario-qualified-ledger-v1")
            cash=check(q["original_v90_account_ledger"],
                       "atlas-v90-new-six-family-execution-sober-ledger-v1")
            if (cash["actual_broker_orders"]!=0 or cash["actual_broker_fills"]!=0
                    or cash["lag_seconds"]!=row["lag_seconds"]
                    or cash["limit_rest_seconds"]!=row["limit_rest_seconds"]
                    or cash["policy"]!=row["policy"]):
                raise V100Error("V100_ORIGINAL_V90_CASH_SOURCE_DRIFT")
            flat=q["cash_equity_known"]
            if flat!=(q["source_complete"] and not cash["unresolved_exercise_or_expiry_cash"]):
                raise V100Error("V100_FICTITIOUS_COMPLETE_HISTORICAL_CASH")
            if flat:
                p=decimal(q["original_stressed_quote_pnl_usd_if_complete"])
                month=sum((decimal(v) for v in
                           cash["stressed_month_pnl_usd"].values()),Decimal(0))
                week=sum((decimal(v) for v in
                          cash["stressed_week_pnl_usd"].values()),Decimal(0))
                if (p!=month or p!=week or p!=decimal(cash["ending_stressed_quote_cash_usd"])
                        -decimal(cash["starting_cash_usd"])):
                    raise V100Error("V100_WEEK_MONTH_ACCOUNT_ARITHMETIC_DRIFT")
                qualified[name]+=1
            elif q["original_stressed_quote_pnl_usd_if_complete"] is not None:
                raise V100Error("V100_INCOMPLETE_HISTORY_RECEIVED_PNL")
            period[key]=(row,q,cash)
            reconciled+=1
        if len(period)!=1200 or qualified[name]!=meta["qualified_and_flat_scenarios"]:
            raise V100Error("V100_COHORT_LEDGER_CENSUS_INVALID")
        cohorts[name]=period
        status.update(doc["outcome_counts_for_dedup_source_family"])
    if len(cohorts)!=len(ALL_PERIODS) or reconciled!=10800:
        raise V100Error("V100_HISTORICAL_PERIOD_OR_LEDGER_MISSING")
    cases={}
    for obj in comparison["historical_comparisons"]:
        key=scenario_key(obj)
        if key in cases or len(obj["historical_periods"])!=9:
            raise V100Error("V100_COMPARISON_SCENARIO_OR_HISTORY_DUPLICATE")
        periods={}
        for row in obj["historical_periods"]:
            name=row["cohort"]
            if name in periods or name not in cohorts:
                raise V100Error("V100_INVALID_V99_COMPARISON_COHORT")
            _,q,cash=cohorts[name][key]
            if (row["cash_equity_known"]!=q["cash_equity_known"]
                    or row["source_complete"]!=q["source_complete"]
                    or row["quote_pnl_if_complete_usd"]!=q["original_stressed_quote_pnl_usd_if_complete"]
                    or row["simulated_closed_wins"]!=cash["positive_closed"]
                    or row["simulated_closed_losses"]!=cash["negative_closed"]
                    or row["weekly_stressed_pnl_usd"]!=cash["stressed_week_pnl_usd"]
                    or row["monthly_stressed_pnl_usd"]!=cash["stressed_month_pnl_usd"]):
                raise V100Error("V100_V99_CROSSPERIOD_PARENT_LEDGER_CHANGED")
            periods[name]=row
        if set(periods)!=set(ALL_PERIODS):
            raise V100Error("V100_INCOMPLETE_V99_CROSSPERIOD_HISTORY")
        valid=[periods[year] for year in DEVELOPMENT if periods[year]["cash_equity_known"]]
        if obj["qualified_flat_development_cohorts"]!=len(valid):
            raise V100Error("V100_COMPARISON_QUALIFIED_PERIOD_CENSUS_CHANGED")
        if len(valid)==8:
            total=sum((decimal(x["quote_pnl_if_complete_usd"]) for x in valid),Decimal(0))
            if str(total)!=obj["nominal_eight_period_quote_pnl_usd_if_complete"]:
                raise V100Error("V100_V99_EIGHTPERIOD_PNL_DRIFT")
        elif obj["nominal_eight_period_quote_pnl_usd_if_complete"] is not None:
            raise V100Error("V100_V99_PARTIAL_RESULT_CLAIMED_FULL_PNL")
        cases[key]=periods
    if (len(cases)!=1200 or comparison["comparison_scenario_count"]!=1200
            or comparison["fully_comparable_eight_period_scenarios"]!=1114
            or comparison["positive_in_all_eight_scenarios"]!=0):
        raise V100Error("V100_ORIGINAL_8_PERIOD_POPULATION_CHANGED")
    return cases,{"signed_source_archive_provenance":audit,
                  "account_scenarios_sha_verified":reconciled,
                  "account_scenarios_qualified_by_cohort":dict(sorted(qualified.items())),
                  "V84_V86_dedup_replay_statuses":dict(sorted(status.items())),
                  "crossperiod_scenarios_sha_verified":len(cases)}


def pick(cases,prior,selector):
    if selector not in SELECTORS or len(prior)<FIRST_EVALUATION_INDEX:
        raise V100Error("V100_PREDECLARED_ROLLING_SELECTOR_INVALID")
    eligible=[]
    for key,periods in cases.items():
        history=[periods[year] for year in prior]
        if any(not row["cash_equity_known"] for row in history):
            continue
        count=sum(row["simulated_closed_wins"]+row["simulated_closed_losses"]
                  for row in history)
        if count<MIN_TRAINING_CLOSED_TRADES:
            continue
        pnl=[decimal(row["quote_pnl_if_complete_usd"]) for row in history]
        total=sum(pnl,Decimal(0))
        positive=sum(x>0 for x in pnl)
        worst=min(pnl)
        if selector=="prior_total":
            score=(total,positive,worst)
        elif selector=="prior_profitable_periods":
            score=(positive,total,worst)
        else:
            score=(worst,total,positive)
        eligible.append((score,key,total,count))
    if not eligible:
        return None,0
    score,key,total,count=max(eligible,key=lambda x:(x[0],x[1]))
    return {"scenario_id":{
                "trial_id":key[0],"policy":key[1],
                "lag_seconds":key[2],"limit_rest_seconds":key[3]},
            "score_in_prior_only_training_periods":list(map(str,score)),
            "training_quote_pnl_usd":str(total),
            "training_closed_positions":count},len(eligible)


def rolling(cases):
    runs={}
    for selector in SELECTORS:
        folds=[]
        pnl_total=Decimal(0)
        censored=[]
        for i in range(FIRST_EVALUATION_INDEX,len(DEVELOPMENT)):
            history=DEVELOPMENT[:i]
            year=DEVELOPMENT[i]
            choice,count=pick(cases,history,selector)
            if choice is None:
                folds.append({"next_period":year,"training_periods":list(history),
                              "status":"ABSTAIN_NO_QUALIFIED_PRIOR_SELECTION",
                              "eligible_prior_candidates":count,"test_quote_pnl_usd":None})
                continue
            key=(choice["scenario_id"]["trial_id"],choice["scenario_id"]["policy"],
                 choice["scenario_id"]["lag_seconds"],
                 choice["scenario_id"]["limit_rest_seconds"])
            held=cases[key][year]
            if held["cash_equity_known"]:
                value=decimal(held["quote_pnl_if_complete_usd"])
                pnl_total+=value
                state="NEXT_PERIOD_COMPLETE_MODEL_QUOTE_RESULT"
                result=str(value)
            else:
                state="NEXT_PERIOD_SOURCE_OR_CASH_CENSORED"
                censored.append(year)
                result=None
            folds.append({
                "next_period":year,
                "training_periods":list(history),
                "eligible_prior_candidates":count,
                "choice":choice,
                "status":state,
                "test_quote_pnl_usd":result,
                "test_closed_wins":held["simulated_closed_wins"] if result is not None else None,
                "test_closed_losses":held["simulated_closed_losses"] if result is not None else None,
            })
        runs[selector]={
            "folds":folds,
            "observed_future_periods":sum(f["test_quote_pnl_usd"] is not None for f in folds),
            "censored_next_periods":censored,
            "nominal_sum_of_observed_later_period_quote_pnl_usd":str(pnl_total),
            "full_five_period_quote_pnl_if_all_qualified":(
                str(pnl_total) if len(censored)==0
                and all(f["test_quote_pnl_usd"] is not None for f in folds)
                else None),
            "not_independent_unseen_holdout_or_live_fills":True,
        }
    return runs


def run(v99_dir,out_dir,*,verify_journals=True,reporter=print):
    if (not v99_dir.is_dir() or out_dir.exists()
            or out_dir.is_symlink()):
        raise V100Error("V100_ORIGINAL_DIRECTORY_OR_NEW_OUTPUT_INVALID")
    summary=source(v99_dir/"summary.json",V99)
    matrix=source(v99_dir/"eight_period_exploratory_matrix.json",
                  V99+"-eight-period-account-robustness-v1")
    manifest=source(v99_dir/"trial_archive_manifest.json",
                    V99+"-signed-trial-archive-manifest-v1")
    cases,audit=verify_every_ledger(v99_dir,summary,matrix,manifest,
                                    full_journals=verify_journals)
    trials=rolling(cases)
    out_dir.mkdir(parents=True,exist_ok=False)
    study=write_once(out_dir/"prior_only_rolling_selection.json",{
        "contract":CONTRACT+"-full-chronological-prior-only-selection-v1",
        "original_V99_summary_sha":summary["fingerprint"],
        "original_V99_comparison_sha":matrix["fingerprint"],
        "historical_order_without_censored_2020":list(DEVELOPMENT),
        "minimum_completed_prior_periods":FIRST_EVALUATION_INDEX,
        "minimum_prior_closed_trades":MIN_TRAINING_CLOSED_TRADES,
        "predeclared_selectors":list(SELECTORS),
        "selectors":trials,
        "original_2020_censored_never_used_to_fit_or_score":True,
        "prior_train_sliced_before_test_period":True,
        "originally_explored_historical_periods_not_new_master_holdout":True,
        "historical_option_quotes_not_verified_broker_fills":True,
        "provider_requests":0,"broker_orders":0,
    })
    report=write_once(out_dir/"summary.json",{
        "contract":CONTRACT,
        "original_V99_summary_sha":summary["fingerprint"],
        "original_V99_trial_manifest_sha":manifest["fingerprint"],
        "original_V99_eightperiod_matrix_sha":matrix["fingerprint"],
        "rolling_experiment_sha":study["fingerprint"],
        "independent_source_and_cash_audit":audit,
        "source_qualified_eightperiod_scenarios":1114,
        "positive_in_all_eight_scenarios":0,
        "note_nominal_positive_scenarios_do_not_prove_tradable_alpha":True,
        "rolling_selection_pnl_by_selector":{
            selector:data["full_five_period_quote_pnl_if_all_qualified"]
            for selector,data in trials.items()},
        "historical_news_joined":False,
        "original_protected_2026_master_holdout_unaccessed":True,
        "source_bytes_read_only":True,
        "provider_requests":0,"broker_orders":0,
    })
    reporter("V100 COMPLETE original V99 signed source/account audit "
             f"ledgers={audit['account_scenarios_sha_verified']} "
             f"crossperiod={audit['crossperiod_scenarios_sha_verified']} "
             f"journal_sha={audit['signed_source_archive_provenance']['archive_sha_checked']} "
             "provider_calls=0 broker_orders=0")
    for selector,data in trials.items():
        reporter(f"V100 PRIOR_ONLY {selector} "
                 f"next_periods={data['observed_future_periods']} "
                 f"observed_quote_pnl={data['nominal_sum_of_observed_later_period_quote_pnl_usd']} "
                 f"complete_quote_pnl={data['full_five_period_quote_pnl_if_all_qualified']}")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v99-dir",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--skip-full-journal-sha",action="store_true")
    args=p.parse_args(argv)
    try:
        run(args.v99_dir,args.output_dir,
            verify_journals=not args.skip_full_journal_sha)
        return 0
    except (OSError,ValueError,TypeError,KeyError,EOFError) as exc:
        print(f"STOP V100 {type(exc).__name__} detail={str(exc)[:200]} "
              "provider_calls=0 broker_orders=0",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
