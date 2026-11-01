from __future__ import annotations

"""V95: eight complete-regime comparisons with original 2020 cohort censored.

Reads 2018,2019,2021..2024 full years, 2025 H2, and 2026 Jan-Apr
pre-existing signed V89/V90 evidence. Original 2020 cannot be scored
when any original exact option query has unresolved provenance. Does not fit rules or select winners.
Audits every original parent SHA and excludes censored cash outcomes.
Signed 1,344-row CSV/JSON; the 2020 gap is recorded as CENSORED.
No providers, brokers, live fills or holdout.
"""

import argparse
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from collections import Counter

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v89_six_family_causal_registry import (
    FAMILIES,verified as verified89,signed,
)
from packages.simulation.spy_v90_six_family_capital_ledger import (
    SCOPES,verified as verified90,
)
from packages.simulation.spy_v84_offline_three_family_economics import POLICIES,LAGS
from packages.simulation.spy_v86_original_option_exit_recheck import DWELLS

ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v95-eight-complete-cohorts-2020-censored-matrix-v1"
COHORTS={
    **{f"{year}_full":(f"{year}-01-01",f"{year}-12-31")
       for year in (2018,2019,2021,2022,2023)},
    "2024_full":("2024-01-01","2024-12-31"),
    "2025_h2":("2025-07-01","2025-12-31"),
    "2026_janapr":("2026-01-01","2026-04-30"),
}
FIELDS=[
    "scope","policy","lag_seconds","limit_rest_seconds","cohort",
    "original_sessions","all_six_decisions","source_demands",
    "candidate_opportunities","hypothetical_entries","no_entry_rejections",
    "capacity_conflicts","closed_positions","positive_closed","negative_closed",
    "stressed_quote_pnl_usd","max_flat_to_flat_drawdown_usd",
    "largest_positive_1_usd","largest_positive_2_usd",
    "pnl_excluding_top_two_positive_usd",
    "unresolved_exercise_or_expiry_cash",
    "terminal_equity_if_flat_usd","portfolio_sha",
]


class V95MatrixError(ValueError):
    pass


def info(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",flush=True)


def read(path,expected):
    if path.is_symlink() or not path.is_file():
        raise V95MatrixError("V95_MATRIX_ORIGINAL_SIGNED_DOCUMENT_MISSING")
    item=json.loads(path.read_text(encoding="utf8"))
    if not verified89(item) or item["contract"]!=expected:
        raise V95MatrixError("V95_MATRIX_ORIGINAL_SIGNED_DOCUMENT_CHANGED")
    return item


def write_once(path,doc):
    item=signed(doc)
    with path.open("x",encoding="utf8") as out:
        json.dump(item,out,sort_keys=True,indent=2,allow_nan=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    return item


def run(inputs,out_dir,*,v93_preflight_dir,v95_2020_reconciliation_dir):
    gap=read(v95_2020_reconciliation_dir/"summary.json",
        "atlas-v95-2020-original-source-read-only-reconciliation-v1")
    source_gap=read(v95_2020_reconciliation_dir/"source_census.json",
        "atlas-v95-2020-original-source-read-only-reconciliation-v1-source-census-v1")
    if (gap["source_census_sha"]!=source_gap["fingerprint"]
            or gap["original_2020_v89_summary_sha"]!=source_gap["original_summary_sha"]
            or gap["unresolved_2020_source_requirements"]<1
            or gap["eligible_for_complete_2020_full_year_quote_pnl"] is not False
            or gap["provider_requests"]!=0 or gap["broker_orders"]!=0
            or source_gap["original_source_demands"]!=len(source_gap["source_dispositions"])
            or source_gap["unknown_2020_quote_pnl_censored"] is not True):
        raise V95MatrixError("V95_MATRIX_2020_CENSOR_OR_ORIGINAL_SOURCE_SHA_INVALID")
    preflight=read(v93_preflight_dir/"preflight.json",
        "atlas-v93-frozen-original-source-preflight-2018-through-2023-v1")
    if (preflight["original_v92_inventory_sha"]!=
            "e19d03c45847e48b536d6eab16331aa752ae296b525484693cc210e63528f0e9"
            or len(preflight["month_source_observations"])!=72
            or preflight["full_source_months_sha_reverified"]!=72
            or preflight["broker_orders"]!=0 or preflight["provider_calls"]!=0):
        raise V95MatrixError("V95_MATRIX_ORIGINAL_2018_2023_SOURCE_PREFLIGHT_MISMATCH")
    validated_months={(x["year"],x["month"]):x
                      for x in preflight["month_source_observations"]}
    if (len(validated_months)!=72
            or set(validated_months)!={(y,m)
                                        for y in range(2018,2024)
                                        for m in range(1,13)}):
        raise V95MatrixError("V95_MATRIX_ORIGINAL_MONTH_SOURCE_COVERAGE_CHANGED")
    if out_dir.exists() or out_dir.is_symlink() or set(inputs)!=set(COHORTS):
        raise V95MatrixError("V95_MATRIX_COHORT_SET_OR_IMMUTABLE_OUTPUT_INVALID")
    portfolio_by_cohort={}
    evidence=[]
    for cohort,(start,end) in COHORTS.items():
        v89dir,v90dir=inputs[cohort]
        entry=read(v89dir/"entry_screen.json",
                   "atlas-v89-six-family-original-source-campaign-v1")
        pre=read(v89dir/"summary.json",
                 "atlas-v89-six-family-original-source-campaign-v1-summary-v1")
        v90=read(v90dir/"summary.json",
                 "atlas-v90-six-new-hypotheses-original-quote-batch-v1")
        books=read(v90dir/"portfolio_ledgers.json",
                   "atlas-v90-six-new-hypotheses-original-quote-batch-v1-full-portfolio-ledgers-v1")
        manifest=read(v90dir/"trial_manifest.json",
                      "atlas-v90-six-new-hypotheses-original-quote-batch-v1-original-signed-trial-manifest-v1")
        if cohort.endswith("_full") and int(cohort[:4])<=2023:
            registered={(x["year"],x["month"]):x for x in entry["source_months"]}
            expected={(y,m):v for (y,m),v in validated_months.items()
                      if y==int(cohort[:4])}
            previous_year=int(cohort[:4])-1
            # The V89 previous-close feature may legitimately consult the
            # preceding December for the first January session; that month
            # is explicitly outside the frozen 12-month performance cohort.
            allowed=set(expected)|{(previous_year,12)}
            if (not set(expected).issubset(registered)
                    or not set(registered).issubset(allowed)
                    or len(entry["source_months"])!=len(registered)
                    or any(registered[k]["unit_id"]!=expected[k]["unit_id"]
                           or registered[k]["original_stock_sha256"]!=
                              expected[k]["canonical_sha256"]
                           or registered[k]["original_raw_bundle_sha256"]!=
                              expected[k]["raw_bundle_sha256"]
                           for k in expected)):
                raise V95MatrixError("V95_MATRIX_SOURCE_MONTH_SHA_NOT_EQUAL_TO_FROZEN_V93")
        if (entry["start"]!=start or entry["end"]!=end
                or entry["registry"]!=FAMILIES
                or entry["registry_sha"]!=_fingerprint(FAMILIES)
                or pre["entry_sha"]!=entry["fingerprint"]
                or pre["source_resolution"]["status"]!="ALL_REQUESTED_SOURCES_PRESENT"
                or pre["all_required_sources_archived"] is not True
                or pre["market_sessions"]!=entry["sessions"]
                or pre["considered_decisions"]!=len(entry["cases"])
                or pre["considered_decisions"]!=pre["market_sessions"]*len(FAMILIES)
                or v90["parent_v89_entry_sha"]!=entry["fingerprint"]
                or v90["parent_v89_summary_sha"]!=pre["fingerprint"]
                or v90["trial_manifest_sha"]!=manifest["fingerprint"]
                or v90["portfolio_ledgers_sha"]!=books["fingerprint"]
                or books["parent_original_trial_manifest_sha"]!=manifest["fingerprint"]
                or manifest["parent_v89_summary_sha"]!=pre["fingerprint"]
                or v90["signed_quote_trial_journals"]!=pre["exact_source_requirements"]*24
                or manifest["total_journals"]!=v90["signed_quote_trial_journals"]
                or books.get("broker_orders")!=0
                or v90["broker_orders"]!=0
                or len(books["ledgers"])!=len(SCOPES)*len(POLICIES)*len(LAGS)*len(DWELLS)):
            raise V95MatrixError("V95_MATRIX_EVIDENCE_LINEAGE_OR_DENOMINATOR_INVALID")
        keymap={}
        for ledger in books["ledgers"]:
            if not verified90(ledger) or ledger["actual_broker_orders"]!=0:
                raise V95MatrixError("V95_MATRIX_ORIGINAL_CAPITAL_LEDGER_SHA_INVALID")
            key=(ledger["scope"],ledger["policy"],
                 ledger["lag_seconds"],ledger["limit_rest_seconds"])
            if key in keymap:
                raise V95MatrixError("V95_MATRIX_DUPLICATE_EXECUTION_SCENARIO")
            keymap[key]=ledger
        if len(keymap)!=len(books["ledgers"]):
            raise V95MatrixError("V95_MATRIX_PORTFOLIO_SCENARIO_MISSING")
        portfolio_by_cohort[cohort]=keymap
        evidence.append({
            "cohort":cohort,"start":start,"end":end,
            "v89_entry_sha":entry["fingerprint"],
            "v89_summary_sha":pre["fingerprint"],
            "v90_summary_sha":v90["fingerprint"],
            "v90_manifest_sha":manifest["fingerprint"],
            "v90_portfolios_sha":books["fingerprint"],
            "original_market_sessions":pre["market_sessions"],
            "all_six_decisions":pre["considered_decisions"],
            "original_exact_option_sources":pre["exact_source_requirements"],
            "source_rejections_and_no_signals":pre["per_family_dispositions"],
            "original_source_sha_verified_by_workstation_not_in_zip":True,
        })
    rows=[]
    completed_positive_all_cohorts=0
    complete_triples=0
    for scope in SCOPES:
        for policy in POLICIES:
            for lag in LAGS:
                for dwell in DWELLS:
                    key=(scope,policy,lag,dwell)
                    triple=[]
                    for cohort in COHORTS:
                        ledger=portfolio_by_cohort[cohort].get(key)
                        if ledger is None:
                            raise V95MatrixError("V95_MATRIX_FROZEN_CONFIG_MISSING_FROM_COHORT")
                        dispositions=ledger["dispositions"]
                        flat=not ledger["unresolved_exercise_or_expiry_cash"]
                        triple.append(ledger)
                        cohort_info=next(x for x in evidence if x["cohort"]==cohort)
                        rows.append({
                            "scope":scope,"policy":policy,
                            "lag_seconds":lag,"limit_rest_seconds":dwell,
                            "cohort":cohort,
                            "original_sessions":cohort_info["original_market_sessions"],
                            "all_six_decisions":cohort_info["all_six_decisions"],
                            "source_demands":cohort_info["original_exact_option_sources"],
                            "candidate_opportunities":ledger["original_opportunities"],
                            "hypothetical_entries":dispositions.get("HYPOTHETICAL_ENTRY_ASK_DEBIT",0),
                            "no_entry_rejections":dispositions.get("NO_ENTRY_REJECTED",0),
                            "capacity_conflicts":dispositions.get("BLOCKED_SHARED_CAPITAL_POSITION_BUSY",0),
                            "closed_positions":dispositions.get("CLOSED_HYPOTHETICAL_QUOTE_EXIT",0),
                            "positive_closed":ledger["positive_closed"],
                            "negative_closed":ledger["negative_closed"],
                            "stressed_quote_pnl_usd":ledger["closed_trade_stressed_quote_pnl_usd"] if flat else None,
                            "max_flat_to_flat_drawdown_usd":ledger["flat_to_flat_max_stressed_drawdown_usd"],
                            "largest_positive_1_usd":ledger["largest_positive_1_stressed_quote_usd"],
                            "largest_positive_2_usd":ledger["largest_positive_2_stressed_quote_usd"],
                            "pnl_excluding_top_two_positive_usd":(
                                ledger["pnl_excluding_top_two_positive_quote_outcomes_usd"] if flat else None),
                            "unresolved_exercise_or_expiry_cash":not flat,
                            "terminal_equity_if_flat_usd":ledger["terminal_equity_known_if_flat_usd"],
                            "portfolio_sha":ledger["fingerprint"],
                        })
                    if all(not x["unresolved_exercise_or_expiry_cash"] for x in triple):
                        complete_triples+=1
                        if all(Decimal(x["closed_trade_stressed_quote_pnl_usd"])>0 for x in triple):
                            completed_positive_all_cohorts+=1
    if len(rows)!=len(SCOPES)*len(POLICIES)*len(LAGS)*len(DWELLS)*len(COHORTS):
        raise V95MatrixError("V95_MATRIX_INCOMPLETE_CROSS_COHORT_MATRIX")
    out_dir.mkdir(parents=True,exist_ok=False)
    matrix=write_once(out_dir/"full_matrix.json",{
        "contract":CONTRACT+"-full-matrix-v1",
        "parent_evidence_shas":evidence,"rows":rows,
        "original_v93_preflight_sha":preflight["fingerprint"],
        "original_v95_2020_reconciliation_sha":gap["fingerprint"],
        "original_v95_2020_source_census_sha":source_gap["fingerprint"],
        "2020_cohort_excluded_due_unresolved_exact_option_sources":True,
        "2020_missing_query_count":gap["unresolved_2020_source_requirements"],
        "2020_original_hypothetical_pnl_usd":None,
        "never_treat_unknown_exercise_cash_as_zero":True,
        "no_strategy_selected_by_matrix":True,
        "broker_orders":0,
    })
    csv_path=out_dir/"full_matrix.csv"
    with csv_path.open("x",encoding="utf8",newline="") as out:
        writer=csv.DictWriter(out,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        out.flush()
        os.fsync(out.fileno())
    csv_sha=hashlib.sha256(csv_path.read_bytes()).hexdigest()
    summary=write_once(out_dir/"summary.json",{
        "contract":CONTRACT,
        "matrix_sha":matrix["fingerprint"],
        "matrix_csv_sha256":csv_sha,
        "cohorts":evidence,
        "original_v93_preflight_sha":preflight["fingerprint"],
        "original_v95_2020_reconciliation_sha":gap["fingerprint"],
        "original_v95_2020_source_census_sha":source_gap["fingerprint"],
        "2020_cohort_excluded_due_unresolved_exact_option_sources":True,
        "2020_missing_query_count":gap["unresolved_2020_source_requirements"],
        "2020_original_hypothetical_pnl_usd":None,
        "distinct_historical_cohort_count":len(COHORTS),
        "hypothesis_families":list(FAMILIES),
        "account_scopes":list(SCOPES),
        "variants_per_scope":len(POLICIES)*len(LAGS)*len(DWELLS),
        "cross_cohort_configurations":len(SCOPES)*len(POLICIES)*len(LAGS)*len(DWELLS),
        "total_comparison_rows":len(rows),
        "complete_eight_cohort_configurations":complete_triples,
        "diagnostic_positive_in_all_eight_cohorts":completed_positive_all_cohorts,
        "posthoc_variant_selection_prohibited":True,
        "no_claim_of_independent_trading_profit":True,
        "protected_2026_master_holdout_accessed":False,
        "broker_orders":0,"provider_requests":0,
    })
    info(f"COMPLETE V95 MATRIX matrix_rows={len(rows)} "
         f"complete_eight_cohort_configs={complete_triples} "
         f"positive_all_eight_diagnostic={completed_positive_all_cohorts} "
         "broker_orders=0 provider_calls=0")
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v93-preflight-dir",type=Path,required=True)
    p.add_argument("--v95-2020-reconciliation-dir",type=Path,required=True)
    for cohort in COHORTS:
        p.add_argument(f"--v89-{cohort.replace('_','-')}",type=Path,required=True)
        p.add_argument(f"--v90-{cohort.replace('_','-')}",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        inputs={
            cohort:(
                getattr(args,f"v89_{cohort}"),
                getattr(args,f"v90_{cohort}"),
            )
            for cohort in COHORTS
        }
        run(inputs,args.output_dir,v93_preflight_dir=args.v93_preflight_dir,
            v95_2020_reconciliation_dir=args.v95_2020_reconciliation_dir)
        return 0
    except Exception as exc:
        info(f"STOP V95 MATRIX type={type(exc).__name__} "
             "broker_orders=0 provider_calls=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
