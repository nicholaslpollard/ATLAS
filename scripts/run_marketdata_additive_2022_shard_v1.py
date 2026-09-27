from __future__ import annotations

"""Additive 2022 accepted DEVELOPMENT chain shard, never reacquiring old query keys."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_accepted_stock_candidate_export_v1 import CandidateStockExportError
from packages.data.marketdata_candidate_batch_plan_v1 import CandidateBatchPlanError
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_candidate_expansion_v1 import run_expansion
from packages.data.marketdata_additive_2022_shards_v1 import prepare_additive_shard
from packages.data.research_storage import ResearchStorageError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Additive, physically noncolliding, accepted 2022 historical EOD chain shard on D:."
    )
    p.add_argument("--shard-index", type=int, default=0)
    p.add_argument("--duckdb-threads", type=int, default=4)
    p.add_argument("--max-total-new-requests", type=int, default=0)
    p.add_argument("--max-observed-credits", type=int, default=60)
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    p.add_argument("--classify-exact-no-data", action="store_true")
    a = p.parse_args(argv)
    print("ATLAS Additive 2022 Accepted Historical Option Chain Shard V1", flush=True)
    try:
        if not 0 <= a.max_total_new_requests <= 50:
            raise CandidateChainCacheError("bounded new provider requests must be 0..50")
        if not 1 <= a.max_observed_credits <= 100:
            raise CandidateChainCacheError("bounded observed credit budget must be 1..100")
        if a.max_total_new_requests and not (
                a.authorize_provider_reads and a.confirm_paid_starter
                and a.confirm_private_internal_use):
            raise CandidateChainCacheError("all explicit paid/provider/private-use confirmations required")
        if not a.max_total_new_requests and any((
                a.authorize_provider_reads, a.confirm_paid_starter,
                a.confirm_private_internal_use, a.classify_exact_no_data)):
            raise CandidateChainCacheError("authorization requires positive provider request cap")
        settings = load_settings(ROOT, "development")
        def progress(item: dict) -> None:
            print("  shard: " + " ".join(f"{k}={v}" for k, v in item.items()), flush=True)
        plan, source, binding, action = prepare_additive_shard(
            settings, shard_index=a.shard_index,
            duckdb_threads=a.duckdb_threads, progress=progress,
        )
        print(f"  source: {action} / {source}", flush=True)
        print(f"  source SHA256: {binding['source_sha256']}", flush=True)
        print(f"  physical new plan fingerprint: {plan['plan_fingerprint']}", flush=True)
        print(f"  selected opportunities: {binding['selected_opportunities']}", flush=True)
        print(f"  shared new chains: {plan['shared_chain_requests']}", flush=True)
        print("  original 2022 exact query keys excluded; original raw receipts untouched", flush=True)
        result = run_expansion(
            settings, plan, source,
            max_total_new_requests=a.max_total_new_requests,
            max_observed_credits=a.max_observed_credits,
            authorize=a.authorize_provider_reads,
            paid=a.confirm_paid_starter,
            private=a.confirm_private_internal_use,
            classify_no_data=a.classify_exact_no_data, progress=progress,
        )
        print(f"  result: {result['status']}", flush=True)
        print(f"  completed chains / exact gaps / pending: "
              f"{result['completed_chains']} / {result['proven_exact_query_gaps']} / {result['pending']}", flush=True)
        print(f"  new provider requests / observed credits: "
              f"{result['new_provider_attempts_this_invocation']} / "
              f"{result['observed_provider_credits_this_invocation']}", flush=True)
        print(f"  reported credits remaining: {result['last_observed_credits_remaining']}", flush=True)
        print(f"  report fingerprint: {result['report_fingerprint']}", flush=True)
        print("  source-only; no historical option fill, P&L, PAPER, LIVE or broker authority", flush=True)
        return 0
    except (CandidateChainCacheError, CandidateStockExportError,
            CandidateBatchPlanError, ResearchStorageError, ValueError,
            OSError, TypeError, KeyError) as exc:
        print(f"ADDITIVE SHARD STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  preserve all original evidence; never blindly retry a paid attempt", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
