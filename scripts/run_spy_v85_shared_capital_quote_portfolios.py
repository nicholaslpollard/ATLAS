from __future__ import annotations

"""V85: original-source-linked shared-capital quote-reference simulator.

Reads previously completed V83 and V84 evidence and *all* 606 original
compressed journals with SHA verification. Absolutely no ThetaData GET,
broker order, implied fill, missing-source healing or future-price selection.
"""

import argparse
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v85_shared_capital_quote_ledger import (
    CONTRACT, MODES, SCOPES, V85Error, signed, verified, simulate,
)
from packages.simulation.spy_v84_offline_three_family_economics import (
    CONTRACT as V84_MODEL, POLICIES, LAGS,
)

ET=ZoneInfo("America/New_York")
V83="atlas-v83-original-native-three-entry-family-source-screen-v2"
V84="atlas-v84-original-v83-cache-only-three-family-economics-v1"
SHA_LEN=64


def log(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",flush=True)


def _doc(path,contract):
    if not path.is_file() or path.is_symlink():
        raise V85Error("V85_SIGNED_SOURCE_FILE_NOT_FOUND")
    item=json.loads(path.read_text(encoding="utf8"))
    if not verified(item) or item.get("contract")!=contract:
        raise V85Error("V85_SIGNED_SOURCE_DOCUMENT_MISMATCH")
    return item


def _write_once(path,item):
    out=signed(item)
    with path.open("x",encoding="utf8") as f:
        json.dump(out,f,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return out


def verify_input(v83dir,v84dir,*,announce=log):
    if (not v83dir.is_dir() or not v84dir.is_dir()
            or v83dir.is_symlink() or v84dir.is_symlink()):
        raise V85Error("V85_ORIGINAL_CAMPAIGN_DIRECTORY_MISSING")
    pre=_doc(v83dir/"summary.json",V83+"-summary-v1")
    screen=_doc(v83dir/"entry_screen.json",V83)
    early=_doc(v84dir/"summary.json",V84)
    outcomes=_doc(v84dir/"candidate_outcomes.json",V84+"-candidate-outcomes-v1")
    windows=_doc(v84dir/"window_economics.json",V84+"-windows-v1")
    if (pre["entry_screen_sha"]!=screen["fingerprint"]
            or early["parent_v83_summary_sha"]!=pre["fingerprint"]
            or early["parent_v83_entry_sha"]!=screen["fingerprint"]
            or early["candidate_outcomes_sha"]!=outcomes["fingerprint"]
            or early["window_economics_sha"]!=windows["fingerprint"]
            or outcomes["parent_v83_summary_sha"]!=pre["fingerprint"]
            or windows["parent_candidate_outcomes_sha"]!=outcomes["fingerprint"]
            or pre["planned_exact_option_demands"]!=early["candidate_sources"]
            or early["candidate_sources"]!=101
            or early["trial_count"]!=len(outcomes["trials"])
            or early["trial_count"]!=606
            or len(screen["cases"])!=pre["family_cases"]
            or pre["family_cases"]!=384
            or early["provider_requests"]!=0 or early["broker_orders"]!=0
            or pre["broker_orders"]!=0 or early["actual_broker_fills"]!=0):
        raise V85Error("V85_V83_V84_PARENT_CHAIN_OR_ACCOUNT_AUTHORITY_DRIFT")
    selected=[x for x in screen["cases"] if x["status"]=="OPTIONS_EXACT_SOURCE_DEMAND_PREPARED"]
    no_signal=[x for x in screen["cases"] if x["status"]=="NO_SIGNAL"]
    if len(selected)!=101 or len(no_signal)!=283:
        raise V85Error("V85_ORIGINAL_ENTRY_OPPORTUNITY_DENOMINATOR_DRIFT")
    original_ids={(x["session"],x["strategy"]) for x in selected}
    if len(original_ids)!=101:
        raise V85Error("V85_DUPLICATE_ORIGINAL_STRATEGY_OPPORTUNITY")
    announces_every=60
    trials=[]
    keys=set()
    for n,item in enumerate(outcomes["trials"],1):
        rel=item["journal"]
        if (not isinstance(rel,str) or not rel.startswith("journals/")
                or not rel.endswith(".json.gz")
                or "/" in rel[len("journals/"):]
                or "\\" in rel or ".." in rel):
            raise V85Error("V85_JOURNAL_PATH_UNSAFE")
        src=v84dir/rel
        if not src.is_file() or src.is_symlink():
            raise V85Error("V85_JOURNAL_MISSING_OR_SYMLINK")
        packed=src.read_bytes()
        if (hashlib.sha256(packed).hexdigest()!=item["journal_gzip_sha256"]
                or len(packed)!=item["journal_gzip_bytes"]):
            raise V85Error("V85_ORIGINAL_JOURNAL_GZIP_SHA_CHANGED")
        try:
            raw=gzip.decompress(packed)
            j=json.loads(raw)
        except (gzip.BadGzipFile,ValueError,EOFError,UnicodeError) as exc:
            raise V85Error("V85_JOURNAL_GZIP_OR_JSON_INVALID") from exc
        if (len(raw)!=item["journal_raw_bytes"]
                or not verified(j)
                or j["fingerprint"]!=item["trial_fingerprint"]
                or j["contract"]!=V84_MODEL
                or j["source_query_id"]!=item["source_query_id"]
                or j["source_sha256"]!=item["source_sha256"]
                or j["session"]!=item["session"]
                or j["strategy"]!=item["strategy"]
                or j["policy"]!=item["policy"]
                or j["lag_seconds"]!=item["lag_seconds"]
                or j["status"]!=item["status"]
                or j["quote_reference_pnl_usd"]!=item["quote_reference_pnl_usd"]
                or j["quote_reference_pnl_2pct_exit_haircut_usd"]!=
                    item["quote_reference_pnl_2pct_exit_haircut_usd"]
                or j["actual_broker_fills"]!=0 or j["provider_requests"]!=0
                or not j["observed_ask_bid_not_broker_fills"]
                or (j["session"],j["strategy"]) not in original_ids):
            raise V85Error("V85_ORIGINAL_V84_TRIAL_LINEAGE_OR_CASH_CHANGED")
        key=(j["session"],j["strategy"],j["policy"],j["lag_seconds"])
        if key in keys or j["policy"] not in POLICIES or j["lag_seconds"] not in LAGS:
            raise V85Error("V85_DUPLICATE_OR_UNREGISTERED_V84_TRIAL")
        keys.add(key)
        trials.append(j)
        if n%announces_every==0:
            announce(f"PROGRESS V85 verified_journals={n}/{len(outcomes['trials'])}")
    expected={
        (session,strategy,policy,lag)
        for session,strategy in original_ids
        for policy in POLICIES for lag in LAGS
    }
    if keys!=expected:
        raise V85Error("V85_NOT_ALL_101_ORIGINAL_SIGNALS_6_VARIANTS_PRESENT")
    return pre,screen,early,outcomes,trials


def run(v83dir,v84dir,output,*,announce=log):
    if output.exists() or output.is_symlink():
        raise V85Error("V85_IMMUTABLE_OUTPUT_EXISTS")
    announce("STAGE_START V85 immutable V83/V84 evidence SHA audit "
             "provider_calls=0 broker_orders=0")
    pre,screen,early,outcomes,trials=verify_input(v83dir,v84dir,announce=announce)
    announce("STAGE_PASS V85 original signatures and 606 compressed event journals")
    output.mkdir(parents=True,exist_ok=False)
    portfolio_runs=[]
    progress=10
    total=len(SCOPES)*len(POLICIES)*len(LAGS)*len(MODES)
    for scope in SCOPES:
        for policy in POLICIES:
            for lag in LAGS:
                for mode in MODES:
                    result=simulate(trials,scope=scope,policy=policy,
                                    lag_seconds=lag,mode=mode)
                    portfolio_runs.append(result)
                    if len(portfolio_runs)*100>=progress*total:
                        announce(f"PROGRESS_{progress}PCT V85 portfolios={len(portfolio_runs)}/{total}")
                        progress+=10
    full=_write_once(output/"portfolio_ledgers.json",{
        "contract":CONTRACT+"-full-event-ledgers-v1",
        "original_v83_summary_sha":pre["fingerprint"],
        "original_v84_summary_sha":early["fingerprint"],
        "original_v84_outcomes_sha":outcomes["fingerprint"],
        "portfolios":portfolio_runs,
        "historical_execution_fills_proven":False,
        "provider_requests":0,"broker_orders":0,
    })
    rows=[]
    for r in portfolio_runs:
        rows.append({
            "scope":r["scope"],"policy":r["policy"],"lag_seconds":r["lag_seconds"],
            "mode":r["execution_reference_mode"],
            "opportunities":r["candidate_opportunities"],
            "original_entries_rejected":r["dispositions"].get("ORIGINAL_NO_ENTRY",0),
            "accepted_reference_entries":r["dispositions"].get(
                "HYPOTHETICAL_ENTRY_AT_ACTION_ASK",0),
            "capacity_conflicts":r["dispositions"].get(
                "BLOCKED_CAPACITY_POSITION_ALREADY_OPEN",0),
            "cash_conflicts":r["dispositions"].get(
                "BLOCKED_INSUFFICIENT_SHARED_CASH",0),
            "closed_quote_reference_exits":r["dispositions"].get(
                "MODELED_EXIT_CREDIT_REFERENCE",0),
            "unmarketable_limit_unresolved":r["dispositions"].get(
                "UNRESOLVED_ORIGINAL_LIMIT",0),
            "quote_reference_cash_pnl_usd":
                r["realized_closed_quote_reference_pnl_usd"],
            "two_pct_exit_haircut_reference_cash_pnl_usd":
                r["realized_closed_2pct_exit_haircut_pnl_usd"],
            "terminal_cash_only_usd":r["ending_cash_reference_usd"],
            "terminal_equity_if_flat_usd":r["terminal_equity_if_flat_usd"],
            "terminal_equity_2pct_haircut_if_flat_usd":
                r["terminal_equity_2pct_haircut_if_flat_usd"],
            "unknown_expiry_cash_or_exercise":
                r["unresolved_exercise_or_expiry_cash"],
            "closed_only_monthly":r["realized_by_month"],
            "closed_only_weekly":r["realized_by_week"],
            "closed_only_annual":r["realized_by_year"],
            "two_pct_haircut_monthly":r["realized_2pct_haircut_by_month"],
            "two_pct_haircut_weekly":r["realized_2pct_haircut_by_week"],
            "two_pct_haircut_annual":r["realized_2pct_haircut_by_year"],
            "max_flat_to_flat_drawdown_usd":r["max_flat_to_flat_drawdown_usd"],
            "portfolio_journal_sha":r["fingerprint"],
            "historical_broker_fills":0,
        })
    view=_write_once(output/"portfolio_comparisons.json",{
        "contract":CONTRACT+"-comparison-v1",
        "portfolios_sha":full["fingerprint"],
        "results":rows,"all_results_are_derived_from_original_fixed_V83_signals":True,
        "net_exercise_or_expiry_equity_not_assumed":True,
        "cash_balance_not_live_broker_cash":True,
        "price_reference_not_actual_fills":True,
    })
    summary=_write_once(output/"summary.json",{
        "contract":CONTRACT,
        "v83_summary_sha":pre["fingerprint"],
        "v84_summary_sha":early["fingerprint"],
        "v84_candidate_outcomes_sha":outcomes["fingerprint"],
        "full_portfolio_ledger_sha":full["fingerprint"],
        "portfolio_comparisons_sha":view["fingerprint"],
        "original_spy_sessions":pre["sessions"],
        "all_original_strategy_decisions":len(screen["cases"]),
        "original_no_signal_decisions":sum(x["status"]=="NO_SIGNAL" for x in screen["cases"]),
        "original_signed_option_candidates":101,
        "original_sha_verified_trial_journals":len(trials),
        "portfolio_scenarios":len(portfolio_runs),
        "one_position_max_concurrent":True,
        "starting_cash_usd":"25000.00",
        "cash_portfolio_reference_not_live_fills":True,
        "fixed_limit_nonmarketability_censored_without_fake_expiry_settlement":True,
        "all_cash_and_approval_scenarios_experimental_not_promoted":True,
        "provider_requests":0,"broker_orders":0,"actual_fills":0,
    })
    announce(f"COMPLETE V85 scenarios={len(portfolio_runs)} "
             "original_journals_verified=606 source_gets=0 broker_orders=0")
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
        log(f"STOP V85 exception_type={type(exc).__name__} "
            "original_sources_preserved=True provider_requests=0 broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
