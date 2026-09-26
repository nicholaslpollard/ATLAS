from __future__ import annotations

"""One-command accepted DEVELOPMENT historical chain expansion on secondary D:."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_accepted_stock_candidate_export_v1 import CandidateStockExportError
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_candidate_expansion_v1 import (
    _require_external, prepare_cohort, run_expansion,
)
from packages.data.research_storage import ResearchStorageError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Bounded 2022-2024 selected-stock EOD historical CHAIN acquisition.")
    p.add_argument("--year", type=int, default=2024, choices=(2022, 2023, 2024))
    p.add_argument("--per-month", type=int, default=3, choices=(1, 2, 3))
    p.add_argument("--duckdb-threads", type=int, default=4)
    p.add_argument("--max-total-new-requests", type=int, default=0)
    p.add_argument("--max-observed-credits", type=int, default=100)
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    p.add_argument("--classify-exact-no-data", action="store_true",
                   help="Offline sidecar only for fully verified 404/no_data with reported zero credits; never retry.")
    args = p.parse_args(argv)
    try:
        settings = load_settings(ROOT, "development")
        _require_external(settings)  # Fail before exporter or provider reads if D: is not ready.
        if not 0 <= args.max_total_new_requests <= 50:
            raise CandidateChainCacheError("bounded new request count must be 0..50")
        if not 1 <= args.max_observed_credits <= 100:
            raise CandidateChainCacheError("observed credit cap must be 1..100")
        if args.max_total_new_requests and not (
            args.authorize_provider_reads and args.confirm_paid_starter
            and args.confirm_private_internal_use
        ):
            raise CandidateChainCacheError("explicit paid/private provider authorizations required")
        if not args.max_total_new_requests and any((
            args.authorize_provider_reads, args.confirm_paid_starter,
            args.confirm_private_internal_use, args.classify_exact_no_data,
        )):
            raise CandidateChainCacheError("authorization requires a positive new request count")

        print("ATLAS MarketData Candidate Expansion V1 — D: historical chain acquisition", flush=True)
        print("  accepted native-raw DEVELOPMENT cohort: "
              f"{args.year}, up to {args.per_month} opportunities/month", flush=True)
        plan, source, binding, action = prepare_cohort(
            settings, year=args.year, per_month=args.per_month,
            duckdb_threads=args.duckdb_threads,
        )
        print(f"  cohort: {action} / {binding['cohort_id']}", flush=True)
        print(f"  original stock bundle SHA256: {binding['source_sha256']}", flush=True)
        print(f"  new chain plan fingerprint: {plan['plan_fingerprint']}", flush=True)
        print(f"  accepted source artifact: {source}", flush=True)
        print(f"  planned opportunities / shared historical chains: "
              f"{plan['opportunities']} / {plan['shared_chain_requests']}", flush=True)
        print("  original 2025 pilot untouched; no original paid-call replay", flush=True)

        def progress(status: dict) -> None:
            print("  batch: " + " ".join(f"{k}={v}" for k, v in status.items()), flush=True)

        report = run_expansion(
            settings, plan, source,
            max_total_new_requests=args.max_total_new_requests,
            max_observed_credits=args.max_observed_credits,
            authorize=args.authorize_provider_reads,
            paid=args.confirm_paid_starter,
            private=args.confirm_private_internal_use,
            classify_no_data=args.classify_exact_no_data,
            progress=progress,
        )
        print(f"  result: {report['status']}", flush=True)
        print(f"  complete chains / exact source gaps / pending: "
              f"{report['completed_chains']} / {report['proven_exact_query_gaps']} / {report['pending']}", flush=True)
        print(f"  NEW provider attempts / OBSERVED credits: "
              f"{report['new_provider_attempts_this_invocation']} / "
              f"{report['observed_provider_credits_this_invocation']}", flush=True)
        print(f"  last provider remaining: {report['last_observed_credits_remaining']}", flush=True)
        print(f"  offline 404 sidecar proofs this invocation: {report['new_offline_exact_gap_proofs']}", flush=True)
        print(f"  report fingerprint: {report['report_fingerprint']}", flush=True)
        print("  this expansion acquires chains only; next stage selected quote paths", flush=True)
        print("  no intraday entry, fill, option P&L, promotion, PAPER, LIVE or broker authority", flush=True)
        return 0
    except (CandidateStockExportError, CandidateChainCacheError, ResearchStorageError,
            OSError, ValueError, TypeError, KeyError) as exc:
        print(f"EXPANSION STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  preserve any original attempt/body/receipt; do not blindly rerun paid requests", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
