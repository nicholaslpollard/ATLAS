from __future__ import annotations

"""One paid, resumable original-2022 historical options bulk acquisition command."""

import argparse
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_2022_bulk_acquisition_v1 import run_bulk_2022
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_accepted_stock_candidate_export_v1 import CandidateStockExportError
from packages.data.marketdata_candidate_batch_plan_v1 import CandidateBatchPlanError
from packages.data.research_storage import ResearchStorageError, inspect_research_storage


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Resumable 2022 complete additive PIT CALL EOD corpus on D:, no duplicate paid GETs."
    )
    p.add_argument("--max-new-chain-requests", type=int, default=1800)
    p.add_argument("--max-new-quote-requests", type=int, default=6000)
    p.add_argument("--max-total-observed-credits", type=int, default=6300)
    p.add_argument("--source-workers", type=int, default=4)
    p.add_argument("--source-worker-ceiling", type=int, default=8)
    p.add_argument("--quote-workers", type=int, default=16)
    p.add_argument("--quote-worker-ceiling", type=int, default=24)
    p.add_argument("--duckdb-threads", type=int, default=4)
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    a = p.parse_args(argv)
    print("ATLAS Local-First 2022 Historical Options Bulk V1", flush=True)
    print("  26..70: prefreeze PIT chain source once, bounded parallel source requests, "
          "then exact full-history CALL quotes (prior 0..25 reused)", flush=True)
    print("  credit limit is observed-charge stopping TARGET, not a monetary guarantee", flush=True)
    print("  no new provider attempt if original intent is ambiguous", flush=True)
    lock: Path | None = None
    fd: int | None = None
    owns_lock = False
    output_lock = threading.Lock()
    try:
        settings = load_settings(ROOT, "development")
        before = inspect_research_storage(settings)
        print(f"  D: before: free={before.disk_free_gib:.3f} GiB, "
              f"candidate_cache={before.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{before.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        lock = settings.resolved_path("data/options/manifests/marketdata_bulk_2022_active_v1.lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            owns_lock = True
        except FileExistsError as exc:
            raise CandidateChainCacheError(
                "bulk acquisition lock exists; inspect original workstation process/receipts before cleanup"
            ) from exc
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = None
            stream.write(f"pid={os.getpid()}\ncontract=atlas-marketdata-2022-bulk-local-first-v1\n")
            stream.flush()
            os.fsync(stream.fileno())

        def emit(row: dict[str, object]) -> None:
            with output_lock:
                print("  " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True)

        report = run_bulk_2022(
            settings,
            max_new_chain_requests=a.max_new_chain_requests,
            max_new_quote_requests=a.max_new_quote_requests,
            max_total_observed_credits=a.max_total_observed_credits,
            source_workers=a.source_workers,
            source_worker_ceiling=a.source_worker_ceiling,
            quote_workers=a.quote_workers,
            quote_worker_ceiling=a.quote_worker_ceiling,
            duckdb_threads=a.duckdb_threads,
            authorize=a.authorize_provider_reads,
            paid=a.confirm_paid_starter,
            private=a.confirm_private_internal_use,
            token=os.getenv("MARKETDATA_TOKEN", ""),
            progress=emit,
        )
        after = inspect_research_storage(settings)
        print(f"  D: after: free={after.disk_free_gib:.3f} GiB, "
              f"candidate_cache={after.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{after.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        for key, value in report.items():
            print(f"  {key}: {value}", flush=True)
        return 0 if report["status"] == "COMPLETE_2022_ADDITIVE_CHAINS_AND_QUOTE_SERIES" else 3
    except (CandidateChainCacheError, CandidateStockExportError,
            CandidateBatchPlanError, ResearchStorageError,
            OSError, ValueError, TypeError, KeyError) as exc:
        print(f"BULK ORIGINAL SOURCE STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve original source/intent/receipt/gap evidence. No blind retry.", flush=True)
        return 3
    finally:
        if fd is not None:
            os.close(fd)
        if owns_lock and lock is not None and lock.is_file():
            lock.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
