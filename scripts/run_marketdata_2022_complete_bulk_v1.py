from __future__ import annotations

"""One resume-safe operator command for remaining frozen 2022 monthly CALL corpus."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_2022_complete_bulk_v1 import run_complete_2022_bulk
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_accepted_stock_candidate_export_v1 import CandidateStockExportError
from packages.data.marketdata_candidate_batch_plan_v1 import CandidateBatchPlanError
from packages.data.research_storage import ResearchStorageError, inspect_research_storage


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Resumable original-source 2022 chain + EOD quote corpus.")
    p.add_argument("--max-new-chain-requests", type=int, default=1800)
    p.add_argument("--max-new-quote-requests", type=int, default=6500)
    p.add_argument("--max-total-observed-credits", type=int, default=6400)
    p.add_argument("--initial-chain-workers", type=int, default=8)
    p.add_argument("--max-chain-workers", type=int, default=24)
    p.add_argument("--quote-workers", type=int, default=24)
    p.add_argument("--duckdb-threads", type=int, default=4)
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    a = p.parse_args(argv)
    print("ATLAS Frozen 2022 Bulk: Source Shards 26-70 + Entire Monthly CALL EOD Histories", flush=True)
    print("  Original exact cache resumes; no repeats of 0-25 original paid requests", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        before = inspect_research_storage(settings)
        print(f"  D: before free={before.disk_free_gib:.3f} GiB, "
              f"candidate_cache={before.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{before.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        result = run_complete_2022_bulk(
            settings, max_total_new_chain_requests=a.max_new_chain_requests,
            max_total_new_quote_requests=a.max_new_quote_requests,
            max_total_observed_credits=a.max_total_observed_credits,
            initial_chain_workers=a.initial_chain_workers,
            max_chain_workers=a.max_chain_workers,
            quote_workers=a.quote_workers, duckdb_threads=a.duckdb_threads,
            authorize=a.authorize_provider_reads, paid=a.confirm_paid_starter,
            private=a.confirm_private_internal_use, token=os.getenv("MARKETDATA_TOKEN", ""),
            progress=lambda row: print(
                "  " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True
            ),
        )
        after = inspect_research_storage(settings)
        print(f"  D: after free={after.disk_free_gib:.3f} GiB, "
              f"candidate_cache={after.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{after.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        for key, value in result.items():
            print(f"  {key}: {value}", flush=True)
        return 0 if result["status"] == "COMPLETE_FROZEN_2022_SOURCE_AND_QUOTE_CORPUS" else 3
    except (CandidateChainCacheError, CandidateStockExportError,
            CandidateBatchPlanError, ResearchStorageError, OSError,
            ValueError, TypeError, KeyError) as exc:
        print(f"BULK SOURCE CAMPAIGN STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve original plans, attempts, SHA receipts and full output. No blind paid retry.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
