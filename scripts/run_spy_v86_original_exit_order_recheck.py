from __future__ import annotations

"""V86 offline source-backed post-trigger exit order recheck and cash sensitivities.

Requires original V83 reports, every V84 SHA-verified journal, and exact
immutable V38 option source cache. Prohibits provider calls and broker orders.
"""

import argparse
from collections import Counter,defaultdict
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.simulation.spy_v84_offline_three_family_economics import prepare_original_tape
from packages.simulation.spy_v85_shared_capital_quote_ledger import (
    SCOPES,simulate,signed as sign85,verified as verify85,
)
from packages.simulation.spy_v86_original_option_exit_recheck import (
    CONTRACT,DWELLS,recheck,signed,verified,V86Error,
)
from scripts.run_spy_v84_offline_three_family_economics import _load_campaign
from scripts.run_spy_v85_shared_capital_quote_portfolios import verify_input
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
REPORT="atlas-v86-source-first-exit-order-recheck-and-cash-stress-v1"


def emit(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",flush=True)


def write_signed(path,doc):
    row=signed(doc)
    with path.open("x",encoding="utf8") as fh:
        json.dump(row,fh,sort_keys=True,indent=2,allow_nan=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    return row


def journal(path,doc):
    payload=(json.dumps(doc,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode("utf8")
    packed=gzip.compress(payload,compresslevel=9,mtime=0)
    with path.open("xb") as fh:
        fh.write(packed)
        fh.flush()
        os.fsync(fh.fileno())
    return hashlib.sha256(packed).hexdigest(),len(packed)


def _v85_trial_compatible(original,result):
    """Re-sign synthetic V84-shaped research inputs without altering originals.

    This is ONLY an alternate shadow order-handling outcome for the same
    original entry. The original V84 journal SHA remains linked in V86.
    """
    copy={k:v for k,v in original.items() if k!="fingerprint"}
    if result["status"]=="NO_ENTRY":
        return sign85(copy)
    if result["status"]!="CLOSED_QUOTE_REFERENCE":
        raise V86Error("V86_UNRESOLVED_OPTION_OUTCOME_CANNOT_ENTER_CASH_LEDGER")
    copy["exit"]={**copy["exit"],
                  "action_at_et":result["exit_action_at_et"],
                  "action_bid":result["exit_bid_reference"],
                  "quote_reference_credit_usd":result["quote_reference_credit_usd"],
                  "reference_pnl":result["quote_reference_pnl_usd"],
                  "pnl_with_2pct_exit_bid_haircut":result[
                      "quote_reference_pnl_2pct_bid_haircut_usd"],
                  "adverse_bid_change_from_trigger_pct":str(
                      (Decimal(result["exit_bid_reference"]) /
                       Decimal(copy["exit"]["trigger_bid"]) - 1) * 100)}
    copy["quote_reference_pnl_usd"]=result["quote_reference_pnl_usd"]
    copy["quote_reference_pnl_2pct_exit_haircut_usd"]=result[
        "quote_reference_pnl_2pct_bid_haircut_usd"]
    copy["v86_post_trigger_recheck_sha"]=result["fingerprint"]
    copy["v86_historical_fill_still_unproven"]=True
    return sign85(copy)


def run(v83dir,v84dir,output,*,settings_factory=load_settings,
        source_reader=_local_cache_only,announce=emit):
    if output.exists() or output.is_symlink():
        raise V86Error("V86_IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    announce("STAGE_START V86 verify V83/V84 SHA chain and original event journals "
             "provider_calls=0 broker_orders=0")
    pre,screen,early,outcomes,trials=verify_input(v83dir,v84dir,announce=announce)
    _,plan,source_summary,demands,receipts=_load_campaign(v83dir)
    if pre["fingerprint"]!=source_summary["fingerprint"]:
        raise V86Error("V86_V83_SOURCE_AND_V84_PARENT_SHA_DIFFER")
    expected_sources=pre["planned_exact_option_demands"]
    if (expected_sources<1 or len(demands)!=expected_sources
            or len(receipts)!=expected_sources
            or len(plan["demands"])!=expected_sources
            or early["candidate_sources"]!=expected_sources):
        raise V86Error("V86_ORIGINAL_SOURCE_CENSUS_CHANGED")
    original_by_qid=defaultdict(list)
    for t in trials:
        original_by_qid[t["source_query_id"]].append(t)
    expected_trials=expected_sources*len(POLICIES)*len(LAGS)
    if (len(trials)!=expected_trials or len(original_by_qid)!=expected_sources
            or any(len(r)!=len(POLICIES)*len(LAGS) for r in original_by_qid.values())):
        raise V86Error("V86_MISSING_ALTERNATIVE_ENTRY_EXIT_TRIALS")
    settings=settings_factory(ROOT,"development")
    announce("STAGE_START V86 read original V38 cache only, recheck 0/3/10/30s "
             "resting limits plus 1s/3s hypothetical cancel/replace; provider_requests=0")
    # Verify every source before creating output: fail closed on a mutated or
    # missing archive, rather than emit a misleading partial cash result.
    inventory={}
    for n,d in enumerate(plan["demands"],1):
        qid=d["query_id"]
        record=source_reader(settings,qid)
        if (not isinstance(record,dict) or record.get("cache_evidence")!="CACHE_HIT"
                or not isinstance(record.get("source"),dict)):
            raise V86Error("V86_ORIGINAL_EXACT_SOURCE_NOT_READABLE")
        source=record["source"]
        if (source.get("source_sha256")!=receipts[qid]["source_sha256"]
                or source.get("query_id")!=qid
                or source.get("exact_requirement")!={"provider":"thetadata",
                     "method":d["method"],"kwargs":d["kwargs"]}):
            raise V86Error("V86_ORIGINAL_SOURCE_SHA_OR_QUERY_IDENTITY_CHANGED")
        contract={k:d["kwargs"][k] for k in
                  ("symbol","date_et","expiration","strike","right")}
        tape=prepare_original_tape(source,contract,d["kwargs"]["date_et"])
        inventory[qid]=(source["source_sha256"],len(tape))
        # Keep just the verified SHA and row count, never 101 full tapes.
        del record,source,tape
        if n%25==0:
            announce(f"PROGRESS V86 original_source_sha_verified={n}/{expected_sources}")
    output.mkdir(parents=True,exist_ok=False)
    (output/"journals").mkdir()
    rows=[]
    variants=defaultdict(list)
    outcomes_by_scope=defaultdict(Counter)
    index=0
    for d in plan["demands"]:
        qid=d["query_id"]
        record=source_reader(settings,qid)
        if not isinstance(record,dict) or record.get("cache_evidence")!="CACHE_HIT":
            raise V86Error("V86_PREVERIFIED_ORIGINAL_SOURCE_MISSING_DURING_REPLAY")
        source=record["source"]
        if (source.get("source_sha256"),len(source.get("source_rows",())))!=inventory[qid]:
            raise V86Error("V86_ORIGINAL_SOURCE_CHANGED_AFTER_PREFLIGHT")
        contract={k:d["kwargs"][k] for k in
                  ("symbol","date_et","expiration","strike","right")}
        tape=prepare_original_tape(source,contract,d["kwargs"]["date_et"])
        for trial in original_by_qid[qid]:
            for dwell in DWELLS:
                result=recheck(trial,source,tape,dwell_seconds=dwell)
                index+=1
                filename=(f"{index:04d}_{trial['session']}_{trial['strategy']}_"
                          f"{trial['policy']}_{trial['lag_seconds']}s_{dwell}s.json.gz")
                digest,size=journal(output/"journals"/filename,result)
                rows.append({
                    "session":trial["session"],
                    "strategy":trial["strategy"],
                    "policy":trial["policy"],"lag_seconds":trial["lag_seconds"],
                    "limit_rest_seconds":dwell,
                    "source_query_id":qid,"original_trial_sha":trial["fingerprint"],
                    "v86_trial_sha":result["fingerprint"],"status":result["status"],
                    "outcome_class":result["outcome_class"],
                    "quote_reference_pnl_usd":result["quote_reference_pnl_usd"],
                    "quote_reference_pnl_2pct_bid_haircut_usd":
                        result["quote_reference_pnl_2pct_bid_haircut_usd"],
                    "journal_path":"journals/"+filename,
                    "journal_gzip_sha256":digest,"journal_gzip_bytes":size,
                    "historical_order_execution_proven":False,
                })
                variants[(dwell,trial["policy"],trial["lag_seconds"])].append(
                    (trial,result))
                outcomes_by_scope[(dwell,trial["policy"],trial["lag_seconds"])][
                    result["outcome_class"]]+=1
        # Only one original options tape remains allocated at a time.
        del record,source,tape
        if len(rows)%400<24:
            announce(f"PROGRESS V86 new_signed_quote_reference_journals={len(rows)}/{expected_trials*len(DWELLS)}")
    if len(rows)!=expected_trials*len(DWELLS) or len(variants)!=len(DWELLS)*len(POLICIES)*len(LAGS):
        raise V86Error("V86_EXPECTED_VARIANTS_NOT_COMPLETE")
    verdicts=[]
    portfolio_ledgers=[]
    for (dwell,policy,lag),pairs in sorted(variants.items()):
        for scope in SCOPES:
            selected=[(orig,r) for orig,r in pairs
                      if scope=="all_families" or orig["strategy"]==scope]
            unresolved=[x for x,r in selected if r["status"]=="UNRESOLVED_POSITION"]
            result=None
            if not unresolved:
                result=simulate([_v85_trial_compatible(o,r) for o,r in selected],
                    scope=scope,policy=policy,lag_seconds=lag,
                    mode="repriced_bid_quote_shadow")
                if not verify85(result):
                    raise V86Error("V86_SHARED_CAPITAL_REPORT_SIGNATURE_INVALID")
                portfolio_ledgers.append({
                    "scope":scope,"policy":policy,"lag_seconds":lag,
                    "limit_rest_seconds":dwell,"signed_original_quote_ledger":result,
                })
            verdicts.append({
                "scope":scope,"policy":policy,"lag_seconds":lag,
                "limit_rest_seconds":dwell,
                "opportunities":len(selected),
                "entry_rejections":sum(r["status"]=="NO_ENTRY" for _,r in selected),
                "original_limit_marketability_at_action":
                    sum(r["outcome_class"]=="ORIGINAL_LIMIT_QUOTE_MARKETABLE" for _,r in selected),
                "later_original_limit_marketable_observations":
                    sum(r["outcome_class"]=="LATER_FIXED_LIMIT_QUOTE_MARKETABLE" for _,r in selected),
                "modeled_repriced_bid_exit_references":
                    sum(r["outcome_class"]=="REPRICED_BID_QUOTE_SHADOW" for _,r in selected),
                "unresolved_exit_actions":len(unresolved),
                "portfolio_cash_ledger_computable":result is not None,
                "conditional_closed_only_quote_pnl_usd":
                    str(sum((Decimal(r["quote_reference_pnl_usd"]) for _,r in selected
                             if r["quote_reference_pnl_usd"] is not None),Decimal(0))),
                "conditional_closed_only_2pct_haircut_pnl_usd":
                    str(sum((Decimal(r["quote_reference_pnl_2pct_bid_haircut_usd"])
                             for _,r in selected if r["quote_reference_pnl_2pct_bid_haircut_usd"] is not None),
                            Decimal(0))),
                "shared_cash_quote_reference_pnl_usd":
                    result["realized_closed_quote_reference_pnl_usd"] if result else None,
                "shared_cash_2pct_exit_haircut_quote_reference_pnl_usd":
                    result["realized_closed_2pct_exit_haircut_pnl_usd"] if result else None,
                "conditional_portfolio_accepted_entries":
                    result["dispositions"].get("HYPOTHETICAL_ENTRY_AT_ACTION_ASK",0) if result else None,
                "conditional_portfolio_capacity_conflicts":
                    result["dispositions"].get("BLOCKED_CAPACITY_POSITION_ALREADY_OPEN",0) if result else None,
                "shared_cash_portfolio_sha":result["fingerprint"] if result else None,
                "remaining_unknown_expiry_or_exercise_cash":bool(unresolved),
                "historical_broker_fills_verified":0,
            })
    r1=write_signed(output/"trial_rechecks.json",{
        "contract":REPORT+"-trial-rechecks-v1",
        "original_v83_sha":pre["fingerprint"],
        "original_v84_sha":early["fingerprint"],
        "trial_rows":rows,"original_option_tapes_read":len(inventory),
        "provider_calls":0,"broker_orders":0,
    })
    full_portfolios=write_signed(output/"portfolio_ledgers.json",{
        "contract":REPORT+"-portfolio-event-ledgers-v1",
        "original_trial_rechecks_sha":r1["fingerprint"],
        "conditional_full_quote_reference_ledgers":portfolio_ledgers,
        "source_linked_quote_events_not_actual_order_fills":True,
    })
    r2=write_signed(output/"portfolio_comparisons.json",{
        "contract":REPORT+"-portfolio-compare-v1",
        "original_trial_rechecks_sha":r1["fingerprint"],
        "full_portfolio_ledgers_sha":full_portfolios["fingerprint"],
        "scenarios":verdicts,
        "unresolved_scenarios_do_not_claim_complete_account_equity":True,
        "synthetic_quote_reference_cannot_establish_fill":True,
    })
    summary=write_signed(output/"summary.json",{
        "contract":REPORT,
        "parent_v83_summary_sha":pre["fingerprint"],
        "parent_v84_summary_sha":early["fingerprint"],
        "trial_rechecks_sha":r1["fingerprint"],
        "portfolio_ledgers_sha":full_portfolios["fingerprint"],
        "portfolio_comparisons_sha":r2["fingerprint"],
        "original_sha_verified_option_tapes":len(inventory),
        "original_sha_verified_v84_trials":len(trials),
        "v86_recheck_journals":len(rows),
        "portfolio_scenarios":len(verdicts),
        "scenario_exit_classes":dict(sorted(Counter(r["outcome_class"] for r in rows).items())),
        "portfolio_scenarios_with_unresolved_exit":
            sum(not r["portfolio_cash_ledger_computable"] for r in verdicts),
        "historical_broker_execution_unproven":True,
        "historical_order_cancel_replace_unproven":True,
        "expiry_or_exercise_settlement_not_inferred":True,
        "in_sample_development_only":True,
        "provider_calls":0,"broker_orders":0,"actual_broker_fills":0,
    })
    announce(f"COMPLETE V86 original_tapes={expected_sources} trials={len(rows)} "
             f"portfolio_scenarios={len(verdicts)} "
             f"unresolved_portfolios={summary['portfolio_scenarios_with_unresolved_exit']} "
             "provider_calls=0 broker_orders=0")
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v83-dir",required=True,type=Path)
    p.add_argument("--v84-dir",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        run(args.v83_dir,args.v84_dir,args.output_dir)
        return 0
    except Exception as exc:
        emit(f"STOP V86 type={type(exc).__name__} reason={str(exc)[:160]} "
             "original_sources_preserved=True provider_calls=0 broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
