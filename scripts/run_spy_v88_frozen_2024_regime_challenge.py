from __future__ import annotations

"""V88: frozen full-year 2024 SPY historical-regime challenge, offline only.

The full program is *only* V84 -> V85 -> V86 with unchanged prices, latency,
entry registry, stops, quantity, fees, cash and exit-marketability rules.
This is earlier history, NOT forward validation and NOT the protected 2026 holdout.
Input V83 original source acquisition must be complete and SHA signed.
NO provider calls, NO brokerage orders, NO unseen date-range substitution.
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v82_causal_entry_family_registry import REGISTRY
from packages.simulation.spy_v84_offline_three_family_economics import (
    LAGS, POLICIES, V84Error,
)
from packages.simulation.spy_v85_shared_capital_quote_ledger import SCOPES
from packages.simulation.spy_v86_original_option_exit_recheck import DWELLS
from scripts.run_spy_v84_offline_three_family_economics import (
    _load_campaign, run as run_v84,
    read_signed, signed, verified,
)
from scripts.run_spy_v85_shared_capital_quote_portfolios import run as run_v85
from scripts.run_spy_v86_original_exit_order_recheck import run as run_v86

ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v88-frozen-full-year-2024-historical-regime-challenge-v1"
START="2024-01-01"
END="2024-12-31"
EXPECTED_SESSIONS=252
EXPECTED_FAMILY_DECISIONS=756
EXPECTED_SOURCES=207
PRIMARY={
    "scope":"failed_breakout_fade_0940",
    "policy":"balanced_35_100",
    "lag_seconds":3,
    "limit_rest_seconds":10,
}
PREVIOUS_DEVELOPMENT_ONLY={
    "2025_h2_development_primary_2pct_bid_haircut_usd":"971.68",
    "2026_janapr_later_period_primary_2pct_bid_haircut_usd":"883.70",
    "same_frozen_policy":"failed_breakout_fade_0940 balanced_35_100 lag=3 rest=10",
    "both_references_unverified_historical_fills":True,
}
EXPECTED_ORIGINAL_SHAS={
    "entry":"f24ecbcc9c7a7c3f22200048b33a8631daeb2121b6ec0b3bc9283b997818f32e",
    "plan":"6d81364b40587d69361241fb1c6b955a0ed19e578e1dd88c6c23e88909dfaf41",
    "receipts":"fdf9ebfc10583febb53b9199fd7b257a2e5615140d80b26fa66e473511f04db3",
    "summary":"c08008c476cdd90eb8fee33749af2c3b64780e4ce4c1098f3bd317caa967d1d9",
}
PROTECTED_MASTER_HOLDOUT=("2026-05-12","2026-08-11")


class V88Error(ValueError):
    pass


def info(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",flush=True)


def _signed_once(path,row):
    payload=signed(row)
    with path.open("x",encoding="utf8") as f:
        json.dump(payload,f,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return payload


def preflight(campaign):
    if not campaign.is_dir() or campaign.is_symlink():
        raise V88Error("V88_ORIGINAL_ACQUISITION_DIRECTORY_NOT_AVAILABLE")
    entry,plan,pre,demands,receipts=_load_campaign(campaign)
    # Original V83 evidence signed roots independently audited from user ZIP.
    if (entry.get("fingerprint")!=EXPECTED_ORIGINAL_SHAS["entry"]
            or plan.get("fingerprint")!=EXPECTED_ORIGINAL_SHAS["plan"]
            or pre.get("fingerprint")!=EXPECTED_ORIGINAL_SHAS["summary"]
            or pre.get("source_receipt_report_sha")!=EXPECTED_ORIGINAL_SHAS["receipts"]):
        raise V88Error("V88_FROZEN_ORIGINAL_SOURCE_MANIFEST_SHA_CHANGED")
    if (entry.get("start")!=START or entry.get("end")!=END
            or pre.get("sessions")!=EXPECTED_SESSIONS
            or len(entry.get("cases",[]))!=EXPECTED_FAMILY_DECISIONS
            or len(plan.get("demands",[]))!=EXPECTED_SOURCES
            or len(receipts)!=EXPECTED_SOURCES
            or pre.get("source_resolution",{}).get("status")!="ALL_REQUESTED_SOURCES_PRESENT"
            or entry.get("families")!=REGISTRY
            or entry.get("registry_sha")!=_fingerprint(REGISTRY)
            or entry.get("xnys_sessions")!=EXPECTED_SESSIONS
            or pre.get("entry_dispositions",{}).get(
                "OPTIONS_EXACT_SOURCE_DEMAND_PREPARED")!=EXPECTED_SOURCES
            or pre.get("entry_dispositions",{}).get("NO_SIGNAL")!=549
            or pre.get("actual_fills")!=0 or pre.get("broker_orders")!=0
            or entry.get("actual_broker_orders")!=0):
        raise V88Error("V88_FROZEN_2024_REGIME_SOURCE_OR_FAMILY_CENSUS_MISMATCH")
    if len(POLICIES)!=3 or LAGS!=(1,3) or DWELLS!=(0,3,10,30):
        raise V88Error("V88_FROZEN_EXECUTION_EXPERIMENT_VARIANTS_CHANGED")
    if any(x.get("session","")<START or x.get("session","")>END
           for x in entry["cases"]):
        raise V88Error("V88_HISTORICAL_CASE_OUTSIDE_FROZEN_WINDOW")
    if any(x["kwargs"]["date_et"]<START or x["kwargs"]["date_et"]>END
           for x in plan["demands"]):
        raise V88Error("V88_ORIGINAL_OPTION_REQUEST_OUTSIDE_FROZEN_WINDOW")
    return entry,pre


def run(campaign,output,*,v84_runner=run_v84,
        v85_runner=run_v85,v86_runner=run_v86,
        announce=info):
    if output.exists() or output.is_symlink():
        raise V88Error("V88_OUTPUT_ALREADY_EXISTS_AND_IMMUTABLE")
    entry,original=preflight(campaign)
    announce(f"STAGE_PASS V88 original {EXPECTED_SESSIONS} XNYS sessions, "
             f"{EXPECTED_FAMILY_DECISIONS} independent strategy decisions "
             f"and {EXPECTED_SOURCES} signed exact option source receipts")
    announce("FROZEN_PRIMARY failed_breakout_fade_0940 balanced_35_100 "
             "action_lag=3s limit_rest=10s fee_and_2pct_haircut=FROM_V84 "
             "protected_2026_master_holdout=UNTOUCHED")
    output.mkdir(parents=True,exist_ok=False)
    v84_dir=output/"v84"
    v85_dir=output/"v85"
    v86_dir=output/"v86"

    announce("STAGE_START V88 original-source 2024 V84 economics provider_calls=0")
    early=v84_runner(campaign,v84_dir)
    if (not verified(early) or early.get("candidate_sources")!=EXPECTED_SOURCES
            or early.get("trial_count")!=EXPECTED_SOURCES*len(POLICIES)*len(LAGS)
            or early.get("parent_v83_summary_sha")!=original["fingerprint"]
            or early.get("provider_requests")!=0 or early.get("broker_orders")!=0):
        raise V88Error("V88_V84_ORIGINAL_SOURCE_CENSUS_OR_SIGNATURE_INVALID")

    announce("STAGE_START V88 2024 V85 chronological shared-capital ledgers "
             "provider_calls=0 broker_orders=0")
    shared=v85_runner(campaign,v84_dir,v85_dir)
    if (not verified(shared)
            or shared.get("original_signed_option_candidates")!=EXPECTED_SOURCES
            or shared.get("original_sha_verified_trial_journals")!=EXPECTED_SOURCES*6
            or shared.get("portfolio_scenarios")!=len(SCOPES)*len(POLICIES)*len(LAGS)*2
            or shared.get("provider_requests")!=0 or shared.get("broker_orders")!=0):
        raise V88Error("V88_V85_ORIGINAL_CASH_PORTFOLIOS_INCOMPLETE")

    announce("STAGE_START V88 2024 V86 0/3/10/30-second source-based exits "
             "provider_calls=0 broker_orders=0")
    order=v86_runner(campaign,v84_dir,v86_dir)
    if (not verified(order)
            or order.get("original_sha_verified_option_tapes")!=EXPECTED_SOURCES
            or order.get("original_sha_verified_v84_trials")!=EXPECTED_SOURCES*6
            or order.get("v86_recheck_journals")!=EXPECTED_SOURCES*6*len(DWELLS)
            or order.get("portfolio_scenarios")!=len(SCOPES)*len(POLICIES)*len(LAGS)*len(DWELLS)
            or order.get("provider_calls")!=0 or order.get("broker_orders")!=0):
        raise V88Error("V88_V86_OPTION_EXIT_QUOTE_RECHECK_INCOMPLETE")
    compare=read_signed(v86_dir/"portfolio_comparisons.json",
        "atlas-v86-source-first-exit-order-recheck-and-cash-stress-v1-portfolio-compare-v1")
    if compare["fingerprint"]!=order["portfolio_comparisons_sha"]:
        raise V88Error("V88_PORTFOLIO_COMPARISON_SOURCE_SHA_DRIFT")
    matches=[x for x in compare["scenarios"] if all(
        x.get(k)==v for k,v in PRIMARY.items())]
    if len(matches)!=1:
        raise V88Error("V88_PREDECLARED_PRIMARY_NOT_EXACTLY_ONE")
    primary=matches[0]
    if (primary.get("historical_broker_fills_verified")!=0
            or (primary.get("portfolio_cash_ledger_computable")
                and primary.get("shared_cash_2pct_exit_haircut_quote_reference_pnl_usd") is None)):
        raise V88Error("V88_PRIMARY_RESULT_UNVERIFIED")
    # Do not fill in censored or incomplete outcomes. Primary is never
    # reselected after examining alternate-family or alternate-lag results.
    result=_signed_once(output/"regime_challenge_summary.json",{
        "contract":CONTRACT,
        "frozen_source_start":START,
        "frozen_source_end":END,
        "protected_master_holdout_start":PROTECTED_MASTER_HOLDOUT[0],
        "protected_master_holdout_end":PROTECTED_MASTER_HOLDOUT[1],
        "master_holdout_accessed":False,
        "not_an_untouched_master_holdout":True,
        "historical_regime_challenge_not_forward_validation":True,
        "source_campaign_full_year_2024_original_sha_pinned":True,
        "legacy_v84_v86_in_sample_flag_describes_original_development_code":True,
        "original_v83_entry_sha":entry["fingerprint"],
        "original_v83_summary_sha":original["fingerprint"],
        "verified_v84_summary_sha":early["fingerprint"],
        "verified_v85_summary_sha":shared["fingerprint"],
        "verified_v86_summary_sha":order["fingerprint"],
        "verified_v86_comparison_sha":compare["fingerprint"],
        "original_xnys_sessions":EXPECTED_SESSIONS,
        "original_family_decisions":EXPECTED_FAMILY_DECISIONS,
        "original_exact_option_sources":EXPECTED_SOURCES,
        "v84_original_signed_trials":EXPECTED_SOURCES*6,
        "v86_source_linked_order_rechecks":EXPECTED_SOURCES*6*len(DWELLS),
        "primary_preregistered_configuration":PRIMARY,
        "primary_result":primary,
        "primary_quote_reference_pnl_usd":primary.get("shared_cash_quote_reference_pnl_usd"),
        "primary_2pct_haircut_quote_reference_pnl_usd":
            primary.get("shared_cash_2pct_exit_haircut_quote_reference_pnl_usd"),
        "primary_unresolved_exit_actions":primary.get("unresolved_exit_actions"),
        "prior_evidence_frozen_before_2024_scoring":PREVIOUS_DEVELOPMENT_ONLY,
        "actual_broker_fills_verified":0,
        "historical_marketability_not_proven_fill":True,
        "exercise_expiry_cash_if_unresolved_unknown":True,
        "cash_reference_not_realized_account_profit":True,
        "strategy_not_promoted":True,
        "provider_requests":0,
        "broker_orders":0,
    })
    announce(f"COMPLETE V88 source_signals={EXPECTED_SOURCES} "
             f"quote_trials={EXPECTED_SOURCES*6} original_exit_rechecks={EXPECTED_SOURCES*24} "
             f"primary_2pct_reference_pnl_usd={result['primary_2pct_haircut_quote_reference_pnl_usd']} "
             "broker_orders=0 provider_calls=0")
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v83-campaign-dir",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        run(args.v83_campaign_dir,args.output_dir)
        return 0
    except Exception as exc:
        info(f"STOP V88 type={type(exc).__name__} reason={str(exc)[:160]} "
             "source_writes=0 broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
