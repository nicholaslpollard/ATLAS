from __future__ import annotations

"""One bounded paid command for new original 2022 chains and their quote histories."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_2022_coordinated_chain_quote_v1 import run_coordinated_batch
from packages.data.marketdata_accepted_stock_candidate_export_v1 import CandidateStockExportError
from packages.data.marketdata_candidate_batch_plan_v1 import CandidateBatchPlanError
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.research_storage import ResearchStorageError, inspect_research_storage


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Exact 2022 source shards then wide CALL histories on D:.")
    p.add_argument("--start-shard", type=int, default=16)
    p.add_argument("--shards", type=int, default=10)
    p.add_argument("--max-new-chain-requests", type=int, default=400)
    p.add_argument("--max-new-quote-requests", type=int, default=3000)
    p.add_argument("--max-total-observed-credits", type=int, default=3500)
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--duckdb-threads", type=int, default=4)
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    a = p.parse_args(argv)
    print("ATLAS 2022 Coordinated Chain + Full Captured CALL Quote History V1", flush=True)
    print("  original exact chain source first, then deduplicated EOD contract history", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        before = inspect_research_storage(settings)
        print(f"  D: before free={before.disk_free_gib:.3f} GiB, "
              f"candidate_cache={before.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{before.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        report = run_coordinated_batch(
            settings, start_shard=a.start_shard, shard_count=a.shards,
            max_new_chain_requests=a.max_new_chain_requests,
            max_new_quote_requests=a.max_new_quote_requests,
            max_total_observed_credits=a.max_total_observed_credits,
            workers=a.workers, duckdb_threads=a.duckdb_threads,
            authorize=a.authorize_provider_reads, paid=a.confirm_paid_starter,
            private=a.confirm_private_internal_use,
            token=os.getenv("MARKETDATA_TOKEN", ""),
            progress=lambda row: print(
                "  " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True
            ),
        )
        after = inspect_research_storage(settings)
        print(f"  D: after free={after.disk_free_gib:.3f} GiB, "
              f"candidate_cache={after.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{after.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        for k, value in report.items():
            print(f"  {k}: {value}", flush=True)
        print("  source-only EOD, not original at-09:35 executable option pricing", flush=True)
        return 0 if report["status"] == "COMPLETE_CHAIN_AND_QUOTE_RANGE" else 3
    except (CandidateChainCacheError, CandidateStockExportError,
            CandidateBatchPlanError, ResearchStorageError,
            OSError, ValueError, TypeError, KeyError) as exc:
        print(f"COORDINATED CAMPAIGN STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Original paid attempts and receipts are retained. No blind retries.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
