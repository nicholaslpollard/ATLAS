from __future__ import annotations

"""One bounded command to acquire consecutive immutable 2022 additive chain shards."""

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
from packages.data.marketdata_additive_2022_campaign_v1 import run_additive_campaign
from packages.data.research_storage import ResearchStorageError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Bounded, resumable 2022 historical option-chain campaign on D:.")
    p.add_argument("--start-shard", type=int, default=0)
    p.add_argument("--max-shards", type=int, default=6)
    p.add_argument("--duckdb-threads", type=int, default=4)
    p.add_argument("--max-total-new-requests", type=int, default=0)
    p.add_argument("--max-observed-credits", type=int, default=250)
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    p.add_argument("--classify-exact-no-data", action="store_true")
    a = p.parse_args(argv)
    print("ATLAS Additive 2022 Multi-Shard Historical Option Chain Campaign V1", flush=True)
    print("  D: candidate-chain cache; original 2022 and 2025 pilot receipts unchanged", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        def progress(row: dict) -> None:
            print("  campaign: " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True)
        report = run_additive_campaign(
            settings, start_shard=a.start_shard, max_shards=a.max_shards,
            duckdb_threads=a.duckdb_threads,
            max_total_new_requests=a.max_total_new_requests,
            max_observed_credits=a.max_observed_credits,
            authorize=a.authorize_provider_reads, paid=a.confirm_paid_starter,
            private=a.confirm_private_internal_use,
            classify_no_data=a.classify_exact_no_data, progress=progress,
        )
        print(f"  RESULT: {report['status']}", flush=True)
        print(f"  frozen source shards: {report['total_frozen_shards']}; "
              f"source loads this command: {report['accepted_source_loads_this_run']}", flush=True)
        for row in report["shard_reports"]:
            print(
                f"  shard {row['shard_index']:02d}: complete={row['completed_chains']} "
                f"exact_gaps={row['proven_exact_query_gaps']} pending={row['pending']} "
                f"new_GETs={row['new_provider_attempts']} credits={row['observed_credits']}",
                flush=True,
            )
        print(f"  TOTAL new GETs={report['new_provider_attempts']} "
              f"observed_credits={report['observed_credits']} "
              f"last_remaining={report['last_observed_provider_remaining']}", flush=True)
        print(f"  campaign fingerprint: {report['campaign_fingerprint']}", flush=True)
        print("  no selected option quote/fill/P&L or PAPER/LIVE/broker authority", flush=True)
        return 3 if report["status"] == "PARTIAL_SHARD_REQUIRES_REVIEW" else 0
    except (CandidateChainCacheError, CandidateStockExportError,
            CandidateBatchPlanError, ResearchStorageError,
            OSError, ValueError, TypeError, KeyError) as exc:
        print(f"CAMPAIGN STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve original source/attempt/body/receipt. Do not blindly retry.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
