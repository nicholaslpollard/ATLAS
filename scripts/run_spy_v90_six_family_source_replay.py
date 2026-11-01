from __future__ import annotations

"""V90: offline source-linked six-family options quote economics batch.

Read V89 signed source plans/receipts and original V38 cache. For EACH original
source, evaluate all 3 frozen V84 exit policies x 2 entry/exit lags x 4 V86
original limit-rest windows. All 24 source-linked journal variants, even
NO_ENTRY and unresolved, are preserved with per-gzip SHA. Then build 168
signed one-slot capital scenarios: six families plus all-six, 24 each.
Never use original future quotes to select entry or treat quote BID as a fill.
"""

import argparse
from collections import Counter
from datetime import datetime,date
import gzip
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v89_six_family_causal_registry import (
    FAMILIES,CONTRACT as ENTRY_MODEL,verified as verify89,signed,
)
from packages.simulation.spy_v84_offline_three_family_economics import (
    POLICIES,LAGS,prepare_original_tape,replay,verified as verify84,
)
from packages.simulation.spy_v86_original_option_exit_recheck import (
    DWELLS,recheck,verified as verify86,
)
from packages.simulation.spy_v90_six_family_capital_ledger import (
    SCOPES,simulate,verified as verify90,
)
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
V89="atlas-v89-six-family-original-source-campaign-v1"
CONTRACT="atlas-v90-six-new-hypotheses-original-quote-batch-v1"


class V90BatchError(ValueError):
    pass


def info(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",flush=True)


def read_signed(path,contract):
    if not path.is_file() or path.is_symlink():
        raise V90BatchError("V90_ORIGINAL_SIGNED_REPORT_MISSING")
    doc=json.loads(path.read_text(encoding="utf8"))
    if not verify89(doc) or doc.get("contract")!=contract:
        raise V90BatchError("V90_ORIGINAL_REPORT_SHA_OR_CONTRACT_INVALID")
    return doc


def once(path,doc):
    item=signed(doc)
    with path.open("x",encoding="utf8") as out:
        json.dump(item,out,sort_keys=True,indent=2,allow_nan=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    return item


def gz_once(path,record):
    raw=(json.dumps(record,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode("utf8")
    packed=gzip.compress(raw,compresslevel=9,mtime=0)
    with path.open("xb") as out:
        out.write(packed)
        out.flush()
        os.fsync(out.fileno())
    return hashlib.sha256(packed).hexdigest(),len(raw),len(packed)


def audit_input(folder):
    entry=read_signed(folder/"entry_screen.json",V89)
    plan=read_signed(folder/"exact_option_source_plan.json",V89+"-source-plan-v1")
    receipts=read_signed(folder/"source_receipts.json",V89+"-source-receipts-v1")
    summary=read_signed(folder/"summary.json",V89+"-summary-v1")
    if (summary["entry_sha"]!=entry["fingerprint"]
            or summary["source_plan_sha"]!=plan["fingerprint"]
            or summary["receipt_sha"]!=receipts["fingerprint"]
            or plan["parent_entry_sha"]!=entry["fingerprint"]
            or receipts["parent_plan_sha"]!=plan["fingerprint"]
            or entry["registry"]!=FAMILIES
            or entry["registry_sha"]!=_fingerprint(FAMILIES)
            or entry["broker_orders"]!=0 or receipts["broker_orders"]!=0
            or summary["broker_orders"]!=0
            or summary["hypotheses"]!=len(FAMILIES)
            or summary["considered_decisions"]!=len(entry["cases"])
            or len(entry["cases"])!=summary["market_sessions"]*len(FAMILIES)
            or not summary["all_required_sources_archived"]):
        raise V90BatchError("V90_ORIGINAL_SOURCE_CENSUS_OR_SHA_CHAIN_DRIFT")
    # Verify the append-only signed acquisition journal, not only a final
    # aggregate provider receipt. A partial/interrupted campaign cannot be
    # silently reinterpreted as a complete historical quote population.
    path=folder/"source_events.jsonl"
    if not path.is_file() or path.is_symlink():
        raise V90BatchError("V90_SIGNED_SOURCE_EVENT_CHAIN_MISSING")
    parent=None
    count=0
    with path.open(encoding="utf8") as src:
        for line in src:
            event=json.loads(line)
            count+=1
            if (not verify89(event)
                    or event["parent_event_sha"]!=parent
                    or event["sequence"]!=count
                    or event["contract"]!=V89+"-append-only-source-event-v1"):
                raise V90BatchError("V90_SOURCE_EVENT_SHA_CHAIN_INVALID")
            parent=event["fingerprint"]
    if (count!=receipts["source_event_count"]
            or parent!=receipts["last_event_sha"]):
        raise V90BatchError("V90_PROVIDER_RECEIPT_EVENT_CHAIN_MISMATCH")
    candidate_map={}
    dates=set()
    for case in entry["cases"]:
        if (case["strategy"] not in FAMILIES or
                case["status"] not in ("NO_SIGNAL","OPTIONS_EXACT_SOURCE_DEMAND_PREPARED",
                                       "SOURCE_UNQUALIFIED_NO_TRADE")):
            raise V90BatchError("V90_UNREGISTERED_OR_MISSING_CANDIDATE_STATUS")
        k=(case["session"],case["strategy"])
        if k in candidate_map:
            raise V90BatchError("V90_DUPLICATE_CAUSAL_DECISION")
        if case["status"]=="SOURCE_UNQUALIFIED_NO_TRADE":
            if case.get("causal_decision") is not None or case.get("source_demand_sha") is not None:
                raise V90BatchError("V90_UNQUALIFIED_STOCK_BECAME_TRADE")
        else:
            if (not verify89(case["causal_decision"])
                    or case["causal_decision"]["strategy_id"]!=case["strategy"]
                    or case["causal_decision"]["session"]!=case["session"]
                    or (case["status"]=="NO_SIGNAL")!=(
                        case["causal_decision"]["direction"] is None)):
                raise V90BatchError("V90_STOCK_DECISION_SHA_OR_STATUS_CHANGED")
        candidate_map[k]=case
        dates.add(case["session"])
    if len(dates)!=summary["market_sessions"]:
        raise V90BatchError("V90_STOCK_SESSION_CENSUS_CHANGED")
    if (len(plan["demands"])!=summary["exact_source_requirements"]
            or len(plan["demands"])!=len(receipts["original_provider_source_receipts"])):
        raise V90BatchError("V90_MISSING_HISTORICAL_OPTION_SOURCE")
    from packages.data.options_on_demand_source_cache_v38 import normalize_source_requirement
    actual={}
    receipts_by_id={}
    for receipt in receipts["original_provider_source_receipts"]:
        cid=receipt["candidate_id"]
        if (cid in receipts_by_id or receipt["status"] not in (
                    "CACHE_HIT","FETCHED_AND_ARCHIVED")
                or not isinstance(receipt["source_sha256"],str)
                or len(receipt["source_sha256"])!=64):
            raise V90BatchError("V90_BAD_ORIGINAL_PROVIDER_RECEIPT")
        receipts_by_id[cid]=receipt
    for demand in plan["demands"]:
        cid=demand["candidate_id"]
        req=normalize_source_requirement(demand["method"],demand["kwargs"])
        k=(demand["kwargs"]["date_et"],cid.split("_",2)[2].rsplit("_",1)[0])
        case=candidate_map.get(k)
        if (not verify89(demand) or cid in actual
                or demand["query_id"]!=_fingerprint(req)
                or not case or not verify89(case["causal_decision"])
                or case["status"]!="OPTIONS_EXACT_SOURCE_DEMAND_PREPARED"
                or case["source_demand_sha"]!=demand["fingerprint"]
                or case["causal_decision"]["fingerprint"]!=demand["strategy_decision_sha"]
                or demand["selection_prior_source_sha256"]!=case["stock_source_sha256"]
                or cid not in receipts_by_id
                or receipts_by_id[cid]["query_id"]!=demand["query_id"]):
            raise V90BatchError("V90_DEMAND_CAUSAL_SOURCE_IDENTITY_INVALID")
        actual[cid]=(case,demand,receipts_by_id[cid])
    if len(actual)!=len(plan["demands"]):
        raise V90BatchError("V90_SOURCE_REQUIREMENTS_INCOMPLETE")
    # Period bounds must never expose protected master holdout.
    if (entry["end"]>"2026-04-30" or
            any(x["session"]<entry["start"] or x["session"]>entry["end"]
                for x in entry["cases"])):
        raise V90BatchError("V90_PROTECTED_MASTER_HOLDOUT_BOUNDARY")
    return entry,plan,receipts,summary,actual


def run(source_dir,out_dir,*,reader=_local_cache_only,
        settings_factory=load_settings,market=None,reporter=info):
    if (not source_dir.is_dir() or source_dir.is_symlink()
            or out_dir.exists() or out_dir.is_symlink()):
        raise V90BatchError("V90_SOURCE_OR_IMMUTABLE_OUTPUT_INVALID")
    entry,plan,receipts,summary,actual=audit_input(source_dir)
    calendar=market or get_market_calendar("XNYS")
    settings=settings_factory(ROOT,"development")
    reporter(f"STAGE_START V90 original_source_count={len(actual)} "
             f"hypotheses={len(FAMILIES)} variants_per_source={len(POLICIES)*len(LAGS)*len(DWELLS)} "
             "provider_calls=0 broker_orders=0")
    out_dir.mkdir(parents=True,exist_ok=False)
    journals=out_dir/"journals"
    journals.mkdir()
    rows=[]
    scenarios={ (p,l,d):[] for p in POLICIES for l in LAGS for d in DWELLS}
    order=sorted(actual.values(),key=lambda x:(
        x[0]["session"],x[1]["candidate_id"]))
    for idx,(case,demand,receipt) in enumerate(order,1):
        day=date.fromisoformat(case["session"])
        if not calendar.is_session(day):
            raise V90BatchError("V90_SOURCE_SESSION_NOT_EXCHANGE_DAY")
        source_evidence=reader(settings,demand["query_id"])
        if (not isinstance(source_evidence,dict) or
                source_evidence.get("cache_evidence")!="CACHE_HIT"):
            raise V90BatchError("V90_READ_ONLY_SOURCE_MISSING")
        source=source_evidence["source"]
        if (source.get("source_sha256")!=receipt["source_sha256"]
                or source.get("query_id")!=demand["query_id"]):
            raise V90BatchError("V90_ORIGINAL_CACHED_SOURCE_SHA_DRIFT")
        option={k:demand["kwargs"][k] for k in (
            "symbol","date_et","expiration","strike","right")}
        tape=prepare_original_tape(source,option,day.isoformat())
        close=calendar.regular_open_close(day)[1]
        decision=case["causal_decision"]
        for policy in POLICIES:
            for lag in LAGS:
                t=replay(decision,demand,source,tape,policy=policy,
                         lag_seconds=lag,market_close_et=close)
                if not verify84(t):
                    raise V90BatchError("V90_V84_RESULT_SHA_INVALID")
                for dwell in DWELLS:
                    if t["status"]=="UNRESOLVED_POSITION":
                        r=signed({
                            "contract":"atlas-v90-original-v84-expiry-censor-v1",
                            "original_trial_sha":t["fingerprint"],
                            "session":t["session"],"strategy":t["strategy"],
                            "policy":policy,"lag_seconds":lag,
                            "limit_rest_seconds":dwell,
                            "status":"UNRESOLVED_POSITION","reason":t["reason"],
                            "quote_reference_pnl_usd":None,
                            "quote_reference_pnl_2pct_bid_haircut_usd":None,
                            "original_source_sha256":receipt["source_sha256"],
                            "actual_broker_fills":0,"provider_requests":0,
                            "exercise_or_expiry_cash_unknown":True,
                        })
                    else:
                        r=recheck(t,source,tape,dwell_seconds=dwell)
                    if not verify86(r):
                        raise V90BatchError("V90_ORIGINAL_EXIT_RECHECK_SIGNATURE_INVALID")
                    name=(f"{idx:05d}_{day}_{case['strategy']}_{policy}"
                          f"_{lag}s_{dwell}s.json.gz")
                    doc=signed({
                        "contract":CONTRACT+"-source-linked-trial-v1",
                        "original_v89_decision_sha":decision["fingerprint"],
                        "original_v89_demand_sha":demand["fingerprint"],
                        "original_v38_source_sha":receipt["source_sha256"],
                        "original_v84_trial":t,
                        "original_v86_exit_recheck":r,
                        "provider_requests":0,"broker_orders":0,
                    })
                    gzsha,rawsize,gzsize=gz_once(journals/name,doc)
                    rows.append({
                        "session":case["session"],"strategy":case["strategy"],
                        "policy":policy,"lag_seconds":lag,
                        "limit_rest_seconds":dwell,
                        "status":r["status"],"reason":r["reason"],
                        "original_query_id":demand["query_id"],
                        "original_source_sha256":receipt["source_sha256"],
                        "entry_trial_sha":t["fingerprint"],
                        "exit_recheck_sha":r["fingerprint"],
                        "journal_sha":doc["fingerprint"],
                        "journal":f"journals/{name}",
                        "gzip_sha256":gzsha,"raw_bytes":rawsize,"gzip_bytes":gzsize,
                        "quote_reference_pnl_2pct_usd":
                            r.get("quote_reference_pnl_2pct_bid_haircut_usd"),
                    })
                    scenarios[(policy,lag,dwell)].append((t,r))
        if idx%25==0 or idx==len(order):
            reporter(f"PROGRESS V90 original_source_tapes_sha_verified={idx}/{len(order)} "
                     f"signed_trial_journals={len(rows)}")
    manifest=once(out_dir/"trial_manifest.json",{
        "contract":CONTRACT+"-original-signed-trial-manifest-v1",
        "parent_v89_summary_sha":summary["fingerprint"],
        "parent_v89_source_receipts_sha":receipts["fingerprint"],
        "trials":rows,"total_journals":len(rows),
        "status_counts":dict(sorted(Counter(x["status"] for x in rows).items())),
        "broker_orders":0,"provider_requests":0,
    })
    ledgers=[]
    for (policy,lag,dwell),pairs in scenarios.items():
        for scope in SCOPES:
            ledger=simulate(pairs,scope=scope,policy=policy,
                            lag_seconds=lag,dwell_seconds=dwell)
            if not verify90(ledger):
                raise V90BatchError("V90_ACCOUNT_LEDGER_SHA_INVALID")
            ledgers.append(ledger)
    books=once(out_dir/"portfolio_ledgers.json",{
        "contract":CONTRACT+"-full-portfolio-ledgers-v1",
        "parent_original_trial_manifest_sha":manifest["fingerprint"],
        "capital_ledger_contract":"atlas-v90-new-six-family-execution-sober-ledger-v1",
        "ledgers":ledgers,"broker_orders":0,
    })
    report=once(out_dir/"summary.json",{
        "contract":CONTRACT,
        "parent_v89_entry_sha":entry["fingerprint"],
        "parent_v89_source_plan_sha":plan["fingerprint"],
        "parent_v89_receipt_sha":receipts["fingerprint"],
        "parent_v89_summary_sha":summary["fingerprint"],
        "source_tapes_verified":len(actual),
        "causal_decisions":len(entry["cases"]),
        "registered_hypotheses":list(FAMILIES),
        "variants_per_source":len(POLICIES)*len(LAGS)*len(DWELLS),
        "signed_quote_trial_journals":len(rows),
        "trial_manifest_sha":manifest["fingerprint"],
        "portfolio_ledgers_sha":books["fingerprint"],
        "portfolio_scenarios":len(ledgers),
        "portfolio_scenarios_with_unresolved_cash":
            sum(x["unresolved_exercise_or_expiry_cash"] for x in ledgers),
        "outcome_counts":dict(sorted(Counter(x["status"] for x in rows).items())),
        "no_trade_or_conflict_decisions_preserved":True,
        "never_optimized_entry_rules_from_outcomes":True,
        "quotes_are_not_real_fills":True,
        "master_holdout_accessed":False,
        "new_provider_requests":0,"broker_orders":0,
    })
    reporter(f"COMPLETE V90 source_tapes={len(actual)} "
             f"signed_quote_journals={len(rows)} "
             f"portfolio_scenarios={len(ledgers)} "
             "provider_calls=0 broker_orders=0")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v89-source-dir",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        run(args.v89_source_dir,args.output_dir)
        return 0
    except Exception as exc:
        info(f"STOP V90 type={type(exc).__name__} "
             "original_source_cache_unmodified=True broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
