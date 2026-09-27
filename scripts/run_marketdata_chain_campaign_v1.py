from __future__ import annotations

"""Bounded multi-year historical EOD option-CHAIN campaign on external D:."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_accepted_stock_candidate_export_v1 import CandidateStockExportError
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_chain_campaign_v1 import run_chain_campaign
from packages.data.research_storage import ResearchStorageError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Source-bound D: historical option chain campaign.")
    p.add_argument("--years", type=int, nargs="+", default=[2024, 2023, 2022])
    p.add_argument("--per-month", type=int, default=3)
    p.add_argument("--duckdb-threads", type=int, default=4)
    p.add_argument("--max-total-new-requests", type=int, default=0)
    p.add_argument("--max-observed-credits", type=int, default=80)
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    p.add_argument("--classify-exact-no-data", action="store_true",
                   help="Only independently verified exact 404/no_data with zero reported credits.")
    args = p.parse_args(argv)
    try:
        print("ATLAS Historical Options Chain Campaign V1 — D: secondary acquisition", flush=True)
        print(f"  year order: {', '.join(str(x) for x in args.years)}", flush=True)
        print("  original 2025 pilot/quote receipts are excluded; no original paid-call replay", flush=True)
        settings = load_settings(ROOT, "development")
        def progress(item: dict) -> None:
            print("  campaign: " + " ".join(f"{k}={v}" for k, v in item.items()), flush=True)
        result = run_chain_campaign(
            settings, years=tuple(args.years), per_month=args.per_month,
            duckdb_threads=args.duckdb_threads,
            max_total_new_requests=args.max_total_new_requests,
            max_observed_credits=args.max_observed_credits,
            authorize=args.authorize_provider_reads,
            paid=args.confirm_paid_starter,
            private=args.confirm_private_internal_use,
            classify_no_data=args.classify_exact_no_data, progress=progress,
        )
        print(f"  campaign result: {result['status']}", flush=True)
        for row in result["year_reports"]:
            print(
                f"  {row['year']}: {row['status']} "
                f"completed={row['completed_chains']} exact_gaps={row['proven_exact_query_gaps']} "
                f"pending={row['pending']} new_GETs={row['new_provider_attempts_this_invocation']} "
                f"observed_credits={row['observed_provider_credits_this_invocation']}",
                flush=True,
            )
        print(f"  TOTAL new GETs / observed credits: "
              f"{result['new_provider_attempts']} / {result['observed_credits']}", flush=True)
        print(f"  completed years: {result['completed_years']}", flush=True)
        print(f"  campaign fingerprint: {result['campaign_fingerprint']}", flush=True)
        print("  chain acquisition only; selected quote histories and option simulator are distinct next stages", flush=True)
        print("  no option intraday entry/fill/P&L, promotion, PAPER, LIVE or broker authority", flush=True)
        if result["status"] == "PARTIAL_COHORT_REQUIRES_REVIEW":
            return 3
        return 0
    except (CandidateChainCacheError, CandidateStockExportError,
            ResearchStorageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"CAMPAIGN STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  preserve original provider intents/bodies/receipts and per-plan checkpoints; do not blindly retry", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
