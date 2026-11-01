from __future__ import annotations

"""V97B source-only CALL entry grid; 49 causal variants, no outcome or API data.

Reads V97A original as-of stock feature signatures, not V90 trial outcomes.
Matches existing CALL tape only on same SPY expiry/strike/decision second,
and plans missing distinct scopes once. One ambiguous 2020 quote is never
queued for automatic retry. Does not calculate PnL or certify broker fills.
"""
import argparse
from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import hashlib
import itertools
import json
import os
from pathlib import Path

CONTRACT="atlas-v97b-causal-call-only-entry-grid-source-union-v1"
V97A="atlas-v97a-actual-original-call-source-and-strategy-capability-v1"
FAMILIES=("impulse_0935","acceleration_0940","early_reversal_0940",
          "pullback_resume_0940","gap_followthrough_0940","compression_release_0940")

class V97BError(ValueError):
    pass

def fingerprint(d):
    return hashlib.sha256((json.dumps(d,sort_keys=True,separators=(",",":"),default=str)+"\n").encode()).hexdigest()

def signed(d):
    return {**d,"fingerprint":fingerprint(d)}

def verified(d):
    return isinstance(d,dict) and fingerprint({k:v for k,v in d.items() if k!="fingerprint"})==d.get("fingerprint")

def read(path,contract):
    d=json.loads(path.read_text(encoding="utf8"))
    if not verified(d) or d.get("contract")!=contract:
        raise V97BError("V97B_INPUT_SIGNED_ROOT_INVALID")
    return d

def write_once(path,doc):
    d=signed(doc)
    with path.open("x",encoding="utf8") as f:
        json.dump(d,f,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())
    return d

def params():
    grid={
        "impulse_0935":[(a,) for a in ("0.12","0.16","0.20","0.25")],
        "acceleration_0940":list(itertools.product(("0.06","0.08","0.12"),("0.07","0.09","0.13"))),
        "early_reversal_0940":list(itertools.product(("0.14","0.18","0.22"),("0.10","0.13","0.17"))),
        # Original 09:39 candle direction was not retained in V97A's scalar
        # feature export. Only narrow the original CALL population; never
        # invent new CALLs from incomplete pullback candle evidence.
        "pullback_resume_0940":[(a,b,c) for a in ("0.20","0.25","0.30")
            for b,c in (("0.25","0.70"),("0.30","0.65"),("0.35","0.60"))],
        "gap_followthrough_0940":list(itertools.product(("0.35","0.45","0.55"),("0.06","0.08","0.12"))),
        "compression_release_0940":list(itertools.product(("0.45","0.55","0.65"),("0.15","0.20","0.25"))),
    }
    return [{
        "trial_id":f"V97B-{family}-{i:02d}",
        "strategy":family,
        "parameters":list(values),
        "subset_of_original_call_only":family=="pullback_resume_0940",
        "candidate_source_identity_requires_new_lookup":True,
        "historical_profitability_measured":False,
    } for family,rows in grid.items() for i,values in enumerate(rows)]

BASELINES={
    "impulse_0935":("0.16",),
    "acceleration_0940":("0.08","0.09"),
    "early_reversal_0940":("0.18","0.13"),
    "pullback_resume_0940":("0.20","0.25","0.70"),
    "gap_followthrough_0940":("0.45","0.08"),
    "compression_release_0940":("0.55","0.20"),
}

def historical_expiry(day):
    d=date.fromisoformat(day);w=d.weekday()
    return (w in (2,4) or w==0 and d>=date(2018,2,26)
            or w==1 and d>=date(2022,11,22)
            or w==3 and d>=date(2022,12,1))

def decimal(x):
    try:
        value=Decimal(str(x))
    except (TypeError,ValueError,InvalidOperation) as exc:
        raise V97BError("V97B_INVALID_SOURCE_FEATURE") from exc
    if not value.is_finite():
        raise V97BError("V97B_NONFINITE_SOURCE_FEATURE")
    return value

def bullish(family,row,p):
    f=row["as_of_stock_feature_values"]
    if f is None:
        return False
    v=lambda key:decimal(f[key])
    x=list(map(decimal,p))
    if family=="impulse_0935":
        return v("first_leg_pct")>=x[0]
    if family=="acceleration_0940":
        return (v("first_leg_pct")>=x[0]
                and v("second_leg_pct")>=x[1]
                and v("second_leg_pct")>=v("first_leg_pct"))
    if family=="early_reversal_0940":
        return v("first_leg_pct")<=-x[0] and v("second_leg_pct")>=x[1]
    if family=="pullback_resume_0940":
        return (row["original_side"]=="CALL"
                and v("first_leg_pct")>=x[0]
                and x[1]<=v("retracement_fraction")<=x[2])
    if family=="gap_followthrough_0940":
        return v("gap_pct")>=x[0] and v("followthrough_pct")>=x[1]
    if family=="compression_release_0940":
        return (v("compression_ratio")<=x[0]
                and v("close_location_fraction")>=1-x[1]
                and v("last_completed_close")>v("opening_price"))
    raise V97BError("V97B_UNREGISTERED_FAMILY")

def source_key(row):
    if row["decision_at_et"] is None:
        return None
    f=row["as_of_stock_feature_values"]
    if f is None:
        return None
    strike=decimal(f["last_completed_close"]).quantize(
        Decimal("1"),rounding=ROUND_HALF_UP)
    if strike<=0:
        raise V97BError("V97B_NONPOSITIVE_CONTRACT_STRIKE")
    # A 09:35 full tape could theoretically cover 09:40, but only accept
    # exact same source start before independent physical archive time audit.
    return (row["session"],row["decision_at_et"].split("T",1)[1][:8],str(strike))

def validated_inputs(root):
    summary=read(root/"summary.json",V97A)
    a=read(root/"original_call_source_considerations.json",
           V97A+"-all-original-decision-considerations-v1")
    if (summary["original_all_considerations_sha"]!=a["fingerprint"]
        or len(a["decisions"])!=11826 or summary["original_six_family_considerations"]!=11826
        or summary["original_CALL_sources_archived"]!=376 or summary["original_CALL_sources_unresolved"]!=1
        or summary["original_PUT_sources_not_eligible_for_CALL_only"]!=334
        or summary["historical_complete_source_cohorts"]!=8
        or summary["historical_original_cohort_count"]!=9
        or summary["provider_requests"]!=0 or summary["broker_orders"]!=0
        or a["provider_calls"]!=0 or a["broker_orders"]!=0):
        raise V97BError("V97B_V97A_SOURCE_CENSUS_OR_ROOT_DRIFT")
    return summary,a

def compute(summary,a):
    rows=a["decisions"]
    original={};unknown={}
    for row in rows:
        if row["strategy"] not in FAMILIES:
            raise V97BError("V97B_UNKNOWN_ORIGINAL_STRATEGY")
        status=row["CALL_only_source_status"]
        if status in ("CALL_VERIFIED_ORIGINAL_ARCHIVE","CALL_ORIGINAL_SOURCE_UNRESOLVED"):
            k=source_key(row)
            if not k or not historical_expiry(row["session"]):
                raise V97BError("V97B_ORIGINAL_CALL_NO_HISTORICAL_EXPIRY")
            if row["original_call_strike"]!=k[2] or row["original_call_expiry"]!=k[0]:
                raise V97BError("V97B_ORIGINAL_CALL_STRIKE_OR_EXPIRY_DRIFT")
            qid=row["exact_option_query_id"];sha=row["call_original_source_sha256"]
            if not isinstance(qid,str) or len(qid)!=64:
                raise V97BError("V97B_INVALID_ORIGINAL_QUERY_ID")
            if status=="CALL_VERIFIED_ORIGINAL_ARCHIVE":
                if not isinstance(sha,str) or len(sha)!=64:
                    raise V97BError("V97B_INVALID_ARCHIVED_SOURCE_SHA")
                previous=original.setdefault(k,{"source_query_id":qid,"source_sha256":sha})
                if previous!={"source_query_id":qid,"source_sha256":sha}:
                    raise V97BError("V97B_CONFLICTING_EXACT_CALL_QUERY_SOURCE")
            else:
                if sha is not None:
                    raise V97BError("V97B_UNKNOWN_SOURCE_HAS_ARCHIVED_SHA")
                previous=unknown.setdefault(k,{"source_query_id":qid,"source_sha256":None})
                if previous["source_query_id"]!=qid:
                    raise V97BError("V97B_CONFLICTING_UNKNOWN_QUERY")
    if set(original)&set(unknown):
        raise V97BError("V97B_CONFLICTING_UNKNOWN_AND_ARCHIVED_SCOPE")
    families={family:[r for r in rows if r["strategy"]==family] for family in FAMILIES}
    variants=params()
    events=[];scope_demand={};result_variants=[];statuses=Counter()
    base_errors=[]
    for family in FAMILIES:
        for row in families[family]:
            if row["original_signal_status"]=="SOURCE_UNQUALIFIED_NO_TRADE":
                continue
            isoriginal=row["original_side"]=="CALL"
            if isoriginal!=bullish(family,row,BASELINES[family]):
                base_errors.append((family,row["session"]))
    if base_errors:
        raise V97BError(f"V97B_FROZEN_BASELINE_FEATURE_REPRODUCTION_MISMATCH:{base_errors[:3]}")
    for variant in variants:
        family=variant["strategy"];per=Counter()
        for row in families[family]:
            if row["source_unqualified_null_original_decision"]:
                per["SOURCE_UNQUALIFIED_NO_DECISION"]+=1
                continue
            if not historical_expiry(row["session"]):
                per["NO_HISTORIC_SAME_DAY_LISTING"]+=1
                continue
            if not bullish(family,row,variant["parameters"]):
                per["NO_BULLISH_CALL_SIGNAL"]+=1
                continue
            key=source_key(row)
            if key is None:
                raise V97BError("V97B_NEW_SIGNAL_NO_DECISION_OR_CONTRACT")
            if key in original:
                label="EXACT_ORIGINAL_CALL_SOURCE_ALREADY_ARCHIVED"
                source=original[key]
            elif key in unknown:
                label="ORIGINAL_PROVIDER_DISPATCH_UNKNOWN_NO_RETRY"
                source=unknown[key]
            else:
                label="NEW_EXACT_CALL_SOURCE_SCOPE_REQUIRES_SEPARATE_REVIEW"
                source=None
                req=scope_demand.setdefault(key,{
                    "symbol":"SPY","session":key[0],"expiry":key[0],
                    "strike":key[2],"right":"call","decision_clock_et":key[1],
                    "source_contract_identity":"SPY_0DTE_1S_CALL",
                    "provider_request_constructed_or_dispatched":False,
                    "strategy_variants":set(),
                })
                req["strategy_variants"].add(variant["trial_id"])
            per[label]+=1;statuses[label]+=1
            if family=="gap_followthrough_0940":
                quality="PRIOR_CLOSE_PUBLICATION_NOT_INDEPENDENTLY_PROVEN"
            elif family=="pullback_resume_0940":
                quality="ORIGINAL_CALL_SUBSET_ONLY_NO_NEW_CANDLE_INFERENCE"
            else:
                quality="CAUSAL_STOCK_FEATURE_ASOF_ASSERTED_ORIGINAL_V89"
            events.append({
                "trial_id":variant["trial_id"],"strategy":family,
                "session":key[0],"decision_clock_et":key[1],
                "strike":key[2],"expiry":key[0],
                "original_decision_sha":row["original_decision_sha"],
                "original_stock_sha256":row["original_stock_sha256"],
                "source_coverage_status":label,
                "original_call_query_id":source["source_query_id"] if source else None,
                "original_archived_source_sha256":source["source_sha256"] if source else None,
                "stock_decision_quality":quality,
                "point_in_time_news_context":row["predecision_news_status"],
                "point_in_time_news_counts_qualified":False,
                "historical_quote_fills_known":False,
                "profitability_computed":False,
            })
        if sum(per.values())!=len(families[family]):
            raise V97BError("V97B_VARIANT_DISPOSITION_CENSUS_INCOMPLETE")
        result_variants.append({**variant,
            "stock_considerations":len(families[family]),
            "candidate_source_coverage":dict(sorted(per.items())),
            "original_replay_ready_pnl":False,
        })
    new_requirements=[
        {**{k:v for k,v in info.items() if k!="strategy_variants"},
         "strategy_variants":sorted(info["strategy_variants"]),
         "provider_calls":0,"broker_orders":0}
        for _,info in sorted(scope_demand.items())
    ]
    if len(variants)!=49 or len(events)!=sum(statuses.values()):
        raise V97BError("V97B_VARIANT_SIZE_MISMATCH")
    return (variants,result_variants,events,new_requirements,
            dict(sorted(statuses.items())),len(original),len(unknown))

def run(root,output,reporter=print):
    if output.exists() or output.is_symlink() or not root.is_dir():
        raise V97BError("V97B_OUTPUT_OR_V97A_DIRECTORY_INVALID")
    summary,a=validated_inputs(root)
    variants,variant_rows,events,req,stats,archived,unknown=compute(summary,a)
    output.mkdir(parents=True,exist_ok=False)
    ev=write_once(output/"call_only_candidate_source_coverage.json",{
        "contract":CONTRACT+"-all-variant-causes-v1",
        "input_v97a_summary_sha":summary["fingerprint"],
        "input_v97a_considerations_sha":a["fingerprint"],
        "variant_results":variant_rows,"candidate_events":events,
        "original_V89_baseline_reproduced_from_asof_features":True,
        "protected_2026_master_holdout_unaccessed":True,
        "provider_requests":0,"broker_orders":0,"modeled_trades":0,
    })
    plan=write_once(output/"new_exact_call_source_union_preview.json",{
        "contract":CONTRACT+"-missing-source-union-preview-v1",
        "original_candidate_coverage_sha":ev["fingerprint"],
        "union_new_source_scopes":req,
        "exact_V38_provider_request_not_constructed":True,
        "historical_SPY_expiry_listing_not_independently_confirmed":True,
        "no_paid_provider_dispatch_authorized":True,
        "original_unknown_requests_must_never_be_retried_automatically":True,
        "provider_requests":0,"broker_orders":0,
    })
    result=write_once(output/"summary.json",{
        "contract":CONTRACT,
        "input_v97a_summary_sha":summary["fingerprint"],
        "input_v97a_considerations_sha":a["fingerprint"],
        "candidate_coverage_sha":ev["fingerprint"],
        "new_source_union_preview_sha":plan["fingerprint"],
        "preregistered_entry_variants":len(variants),
        "candidate_variant_occurrences":len(events),
        "candidate_source_dispositions":stats,
        "new_exact_distinct_call_scopes_to_review":len(req),
        "original_distinct_archived_exact_call_scopes":archived,
        "original_distinct_unknown_exact_call_scopes":unknown,
        "existing_24_risk_execution_variants_per_candidate":24,
        "conceptual_entry_x_original_exit_variant_combinations":len(variants)*24,
        "point_in_time_news_integration_status":"NOT_JOINED_NA_NOT_ZERO",
        "all_variants_have_hypothetical_pnl":False,
        "protected_master_holdout_accessed":False,
        "provider_requests":0,"broker_orders":0,
    })
    reporter("COMPLETE V97B offline CALL-only causal entry preview "
             f"variants={result['preregistered_entry_variants']} "
             f"candidate_occurrences={result['candidate_variant_occurrences']} "
             f"reused_original_scopes={result['original_distinct_archived_exact_call_scopes']} "
             f"new_unique_scopes={result['new_exact_distinct_call_scopes_to_review']} "
             f"unknown_scopes={result['original_distinct_unknown_exact_call_scopes']} "
             "provider_calls=0 broker_orders=0")
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v97a-dir",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        run(args.v97a_dir,args.output_dir)
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print(f"STOP V97B type={type(exc).__name__} reason={str(exc)[:200]} "
              "provider_calls=0 broker_orders=0",flush=True)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
