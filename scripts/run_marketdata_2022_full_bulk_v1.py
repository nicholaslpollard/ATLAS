from __future__ import annotations

"""One resumable 2022 source+CALL EOD backfill; existing exact caches own every GET."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_2022_full_bulk_v1 import run_full_bulk
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_candidate_batch_plan_v1 import CandidateBatchPlanError
from packages.data.marketdata_accepted_stock_candidate_export_v1 import CandidateStockExportError
from packages.data.research_storage import ResearchStorageError, inspect_research_storage


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Full 2022 additive PIT monthly CALL chain + exact EOD histories, local-first."
    )
    p.add_argument("--max-new-requests", type=int, default=12000)
    p.add_argument("--max-total-observed-credits", type=int, default=8000)
    p.add_argument("--max-credit-windows", type=int, default=2)
    p.add_argument("--chain-workers", type=int, default=4)
    p.add_argument("--quote-workers", type=int, default=16)
    p.add_argument("--duckdb-threads", type=int, default=4)
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    a = p.parse_args(argv)
    print("ATLAS Full 2022 Additive PIT Monthly CALL Historical EOD Bulk Acquisition", flush=True)
    print("  source shards 26..70; every earlier 0..25 original body/receipt reused", flush=True)
    print("  original 2022 three/month pilot and 2023..2025 are separate source contracts", flush=True)
    print("  source-only EOD, not executable 09:35 option quote, return or PAPER/LIVE authority", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        before = inspect_research_storage(settings)
        print(f"  D: before free={before.disk_free_gib:.3f} GiB; "
              f"candidate_cache={before.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{before.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        result = run_full_bulk(
            settings, max_new_requests=a.max_new_requests,
            max_total_observed_credits=a.max_total_observed_credits,
            max_credit_windows=a.max_credit_windows,
            initial_chain_workers=a.chain_workers,
            initial_quote_workers=a.quote_workers,
            duckdb_threads=a.duckdb_threads,
            authorize=a.authorize_provider_reads, paid=a.confirm_paid_starter,
            private=a.confirm_private_internal_use, token=os.getenv("MARKETDATA_TOKEN", ""),
            progress=lambda event: print(
                "  " + " ".join(f"{key}={value}" for key, value in event.items()),
                flush=True,
            ),
        )
        after = inspect_research_storage(settings)
        print(f"  D: after free={after.disk_free_gib:.3f} GiB; "
              f"candidate_cache={after.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{after.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        for key, value in result.items():
            print(f"  {key}: {value}", flush=True)
        return 0 if result["status"] == "COMPLETE_SOURCE_ONLY" else 3
    except (CandidateChainCacheError, CandidateBatchPlanError,
            CandidateStockExportError, ResearchStorageError,
            OSError, ValueError, TypeError, KeyError) as exc:
        print(f"FULL BULK STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Original intents/receipts/sidecars preserved. Never blanket-retry ambiguous work.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
