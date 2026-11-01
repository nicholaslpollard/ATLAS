from __future__ import annotations

"""V84: offline, SHA-bound V83 SPY 0DTE entry and dynamic-exit quote economics.

Read ONLY V83 signed reports and original option rows from the V38 read-only
cache. No provider calls, broker orders, synthetic fills, or hindsight entry
selection. Journals retain rejected observations, trigger/action marketability,
and censoring; P&L is explicitly a hypothetical BID/ASK reference.
"""

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v84_offline_three_family_economics import (
    LAGS, POLICIES, CONTRACT as MODEL, V84Error,
    prepare_original_tape, replay, signed, verified,
)
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")
CONTRACT = "atlas-v84-original-v83-cache-only-three-family-economics-v1"
V83 = "atlas-v83-original-native-three-entry-family-source-screen-v2"


def emit(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}", flush=True)


def read_signed(path, expected_contract=None):
    if path.is_symlink() or not path.is_file():
        raise V84Error("V84_REPORT_MISSING_OR_UNSAFE")
    item = json.loads(path.read_text(encoding="utf8"))
    if (not verified(item) or
            expected_contract is not None and item.get("contract") != expected_contract):
        raise V84Error("V84_SOURCE_DOCUMENT_SIGNATURE_OR_CONTRACT_CHANGED")
    return item


def write_once(path, record):
    signed_record = signed(record)
    with path.open("x", encoding="utf8") as target:
        json.dump(signed_record, target, sort_keys=True, indent=2, allow_nan=False)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    return signed_record


def write_gzip_once(path, record):
    raw = (json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf8")
    packed = gzip.compress(raw, compresslevel=9, mtime=0)
    with path.open("xb") as dest:
        dest.write(packed)
        dest.flush()
        os.fsync(dest.fileno())
    return hashlib.sha256(packed).hexdigest(), len(raw), len(packed)


def _load_campaign(folder):
    entry = read_signed(folder/"entry_screen.json", V83)
    plan = read_signed(folder/"option_source_plan.json", V83+"-exact-source-plan-v1")
    receipts = read_signed(folder/"source_receipts.json", V83+"-source-receipts-v1")
    summary = read_signed(folder/"summary.json", V83+"-summary-v1")
    if (summary["entry_screen_sha"] != entry["fingerprint"]
            or summary["option_source_plan_sha"] != plan["fingerprint"]
            or summary["source_receipt_report_sha"] != receipts["fingerprint"]
            or plan["entry_screen_sha"] != entry["fingerprint"]
            or receipts["option_source_plan_sha"] != plan["fingerprint"]
            or len(entry["cases"]) != summary["family_cases"]
            or len(plan["demands"]) != summary["planned_exact_option_demands"]
            or len(plan["demands"]) != len(receipts["original_provider_source_receipts"])
            or receipts["source_use_requested"] != len(plan["demands"])
            or summary["broker_orders"] != 0
            or not summary["option_selection_and_trade_execution_not_qualified"]):
        raise V84Error("V84_V83_LINEAGE_OR_DENOMINATOR_INVALID")
    if summary["source_resolution"] is None or summary["source_resolution"]["status"] != "ALL_REQUESTED_SOURCES_PRESENT":
        raise V84Error("V84_ORIGINAL_ACQUISITION_NOT_COMPLETE")
    all_cases = entry["cases"]
    candidates = {x["source_demand_sha"]: x for x in all_cases
                  if x["status"] == "OPTIONS_EXACT_SOURCE_DEMAND_PREPARED"}
    if len(candidates) != len(plan["demands"]) or None in candidates:
        raise V84Error("V84_ENTRY_TO_SOURCE_BINDING_MISMATCH")
    demand_by_qid = {}
    candidate_ids = set()
    for demand in plan["demands"]:
        if (not verified(demand) or demand["fingerprint"] not in candidates
                or demand["query_id"] != _fingerprint({
                    "provider":"thetadata","method":demand["method"],"kwargs":demand["kwargs"]})):
            raise V84Error("V84_ORIGINAL_EXACT_SOURCE_DEMAND_CHANGED")
        source_case = candidates[demand["fingerprint"]]
        if (not verified(source_case["causal_decision"])
                or source_case["causal_decision"]["fingerprint"] != demand["strategy_decision_sha"]
                or demand["candidate_id"] in candidate_ids):
            # candidate_id is deliberately unique per signal, but V39 query
            # identity is the true immutable archive/cache key.
            raise V84Error("V84_ORIGINAL_ENTRY_SOURCE_IDENTITY_CHANGED")
        if demand["query_id"] in demand_by_qid:
            raise V84Error("V84_DUPLICATE_EXACT_QUERY_ID")
        candidate_ids.add(demand["candidate_id"])
        demand_by_qid[demand["query_id"]] = (source_case, demand)
    receipt_by_qid = {}
    for receipt in receipts["original_provider_source_receipts"]:
        qid = receipt["query_id"]
        if (qid in receipt_by_qid or qid not in demand_by_qid
                or receipt["status"] not in ("FETCHED_AND_ARCHIVED","CACHE_HIT")
                or not isinstance(receipt.get("source_sha256"), str)
                or len(receipt["source_sha256"]) != 64
                or receipt["candidate_id"] != demand_by_qid[qid][1]["candidate_id"]):
            raise V84Error("V84_ORIGINAL_SOURCE_RECEIPT_CHANGED")
        receipt_by_qid[qid] = receipt
    if set(receipt_by_qid) != set(demand_by_qid):
        raise V84Error("V84_MISSING_OPTION_SOURCE_RECEIPT")
    return entry, plan, summary, demand_by_qid, receipt_by_qid


def run(campaign_dir, output_dir, *, source_reader=_local_cache_only,
        settings_factory=load_settings, calendar=None, reporter=emit):
    if (campaign_dir.is_symlink() or not campaign_dir.is_dir()
            or output_dir.exists() or output_dir.is_symlink()):
        raise V84Error("V84_CAMPAIGN_OR_IMMUTABLE_OUTPUT_INVALID")
    entry, plan, prior, demands, receipts = _load_campaign(campaign_dir)
    # Only this previously declared, later calendar period receives an
    # explicit temporal-validation label. All 2025 development journal
    # metadata and experiment rules are byte-for-byte unchanged.
    temporal_validation = (
        entry.get("start") == "2026-01-01"
        and entry.get("end") == "2026-04-30"
    )
    market = calendar or get_market_calendar("XNYS")
    settings = settings_factory(ROOT, "development")
    ordered = list(plan["demands"])
    reporter(f"STAGE_START V84 read-only original option archives requirements={len(ordered)} "
             f"policies={len(POLICIES)} action_lags={LAGS} "
             "provider_requests=0 broker_orders=0")
    output_dir.mkdir(parents=True, exist_ok=False)
    journals = output_dir/"journals"
    journals.mkdir()
    trials = []
    milestones = 10
    for i, d in enumerate(ordered, 1):
        case, demand = demands[d["query_id"]]
        rec = receipts[d["query_id"]]
        decision = case["causal_decision"]
        day = date.fromisoformat(case["session"])
        if not market.is_session(day):
            raise V84Error("V84_NON_MARKET_DAY_WITH_OPTION_SOURCE")
        _, close = market.regular_open_close(day)
        source_evidence = source_reader(settings, demand["query_id"])
        if (not isinstance(source_evidence, dict)
                or source_evidence.get("cache_evidence") != "CACHE_HIT"
                or not isinstance(source_evidence.get("source"), dict)):
            raise V84Error("V84_ORIGINAL_SOURCE_NOT_IN_READ_ONLY_CACHE")
        source = source_evidence["source"]
        if (source.get("source_sha256") != rec["source_sha256"]
                or source.get("query_id") != demand["query_id"]):
            raise V84Error("V84_CACHED_ARCHIVE_SOURCE_SHA_DRIFT")
        contract = {k:demand["kwargs"][k] for k in
                    ("symbol","date_et","expiration","strike","right")}
        original = prepare_original_tape(source, contract, day.isoformat())
        for policy in POLICIES:
            for lag in LAGS:
                result = replay(decision, demand, source, original, policy=policy,
                                lag_seconds=lag, market_close_et=close)
                if temporal_validation:
                    # Annotate a validation-only research trial without
                    # changing entry, quote, stop, latency or exit economics.
                    result = signed({
                        **{k:v for k,v in result.items() if k != "fingerprint"},
                        "in_sample_development_only":False,
                        "temporal_validation_not_protected_master_holdout":True,
                    })
                path = f"{i:04d}_{day.isoformat()}_{decision['strategy_id']}_{policy}_{lag}s.json.gz"
                sha, raw_bytes, compressed_bytes = write_gzip_once(journals/path, result)
                exit_data = result.get("exit")
                trials.append({
                    "session":day.isoformat(), "strategy":decision["strategy_id"],
                    "policy":policy, "lag_seconds":lag,
                    "status":result["status"], "reason":result["reason"],
                    "source_query_id":demand["query_id"],
                    "source_sha256":rec["source_sha256"],
                    "trial_fingerprint":result["fingerprint"],
                    "journal":f"journals/{path}", "journal_gzip_sha256":sha,
                    "journal_raw_bytes":raw_bytes, "journal_gzip_bytes":compressed_bytes,
                    "entry_qty":result["entry_qty"],
                    "entry_debit_usd":result["entry_debit_usd"],
                    "quote_reference_pnl_usd":result["quote_reference_pnl_usd"],
                    "quote_reference_pnl_2pct_exit_haircut_usd":
                        result["quote_reference_pnl_2pct_exit_haircut_usd"],
                    "original_trigger_limit_marketable_at_action":
                        exit_data["original_trigger_limit_marketable_at_action"] if exit_data else None,
                    "actual_fills":0,
                })
        while milestones <= 100 and i*100 >= milestones*len(ordered):
            reporter(f"PROGRESS_{milestones}PCT V84 candidate_sources={i}/{len(ordered)} "
                     f"last_day={day} modeled_variants={len(trials)}")
            milestones += 10

    grouping = defaultdict(list)
    for row in trials:
        for level,key in (
            ("overall","ALL"),
            ("month",row["session"][:7]),
            ("week",date.fromisoformat(row["session"]).isocalendar().week),
            ("year",row["session"][:4]),
        ):
            grouping[(row["strategy"],row["policy"],row["lag_seconds"],level,str(key))].append(row)
    economics=[]
    for (family,policy,lag,level,period),values in sorted(grouping.items()):
        closed = [x for x in values if x["status"]=="CLOSED_QUOTE_REFERENCE"]
        gains = sum((Decimal(x["quote_reference_pnl_usd"]) for x in closed),Decimal("0"))
        stress = sum((Decimal(x["quote_reference_pnl_2pct_exit_haircut_usd"]) for x in closed),Decimal("0"))
        marketable = [x for x in closed if x["original_trigger_limit_marketable_at_action"] is True]
        marketable_gains = sum((Decimal(x["quote_reference_pnl_usd"]) for x in marketable),Decimal("0"))
        marketable_stress = sum((Decimal(x["quote_reference_pnl_2pct_exit_haircut_usd"]) for x in marketable),Decimal("0"))
        economics.append({
            "strategy":family, "policy":policy, "lag_seconds":lag,
            "window_kind":level,"window":period,
            "cases":len(values),"closed_quote_reference_cases":len(closed),
            "closed_original_trigger_limit_marketable_cases":len(marketable),
            "closed_original_trigger_limit_unmarketable_cases":len(closed)-len(marketable),
            "original_limit_marketable_subset_reference_pnl_usd":str(marketable_gains),
            "original_limit_marketable_subset_2pct_haircut_pnl_usd":str(marketable_stress),
            "no_entry":sum(x["status"]=="NO_ENTRY" for x in values),
            "unresolved_positions":sum(x["status"]=="UNRESOLVED_POSITION" for x in values),
            "quote_reference_closed_only_pnl_usd":str(gains),
            "quote_reference_closed_only_2pct_haircut_pnl_usd":str(stress),
            "incomplete_outcomes_excluded_from_pnl":len(values)!=len(closed),
            "cash_portfolio_pnl_not_proven":True,
        })
    candidate_report = write_once(output_dir/"candidate_outcomes.json",{
        "contract":CONTRACT+"-candidate-outcomes-v1",
        "parent_v83_summary_sha":prior["fingerprint"],
        "trials":trials,"all_trial_count":len(trials),
        "broker_orders":0,"provider_requests":0,
    })
    economics_report = write_once(output_dir/"window_economics.json",{
        "contract":CONTRACT+"-windows-v1","parent_candidate_outcomes_sha":candidate_report["fingerprint"],
        "window_rows":economics, "closed_only_not_true_portfolio_pnl":True,
        "in_sample_development_only":not temporal_validation,
        "temporal_validation_not_protected_master_holdout":temporal_validation,
    })
    report = write_once(output_dir/"summary.json",{
        "contract":CONTRACT,"parent_v83_summary_sha":prior["fingerprint"],
        "parent_v83_entry_sha":entry["fingerprint"],
        "parent_v83_option_plan_sha":plan["fingerprint"],
        "candidate_outcomes_sha":candidate_report["fingerprint"],
        "window_economics_sha":economics_report["fingerprint"],
        "strategy_counts":dict(sorted(Counter(x["strategy"] for x in
                entry["cases"] if x["status"]=="OPTIONS_EXACT_SOURCE_DEMAND_PREPARED").items())),
        "candidate_sources":len(ordered),"trial_count":len(trials),
        "status_counts":dict(sorted(Counter(t["status"] for t in trials).items())),
        "exit_trigger_limit_unmarketable_cases":
            sum(x["status"]=="CLOSED_QUOTE_REFERENCE" and
                x["original_trigger_limit_marketable_at_action"] is False for x in trials),
        "simulated_cash_portfolio_ledger":False,
        "quotes_not_real_fills":True,"no_autoexercise_assumptions":True,
        "no_future_prices_used_to_enter":True,
        "scenario_results_not_proven_profitability":True,
        "in_sample_development_only":not temporal_validation,
        "temporal_validation_not_protected_master_holdout":temporal_validation,
        "actual_broker_fills":0,"broker_orders":0,"provider_requests":0,
    })
    reporter(f"COMPLETE V84 candidates={len(ordered)} trials={len(trials)} "
             f"status={report['status_counts']} provider_requests=0 broker_orders=0")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--campaign-dir",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        run(args.campaign_dir,args.output_dir)
        return 0
    except Exception as exc:
        emit(f"STOP V84 reason_type={type(exc).__name__} "
             "provider_requests=0 broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
