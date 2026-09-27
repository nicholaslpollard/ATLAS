from __future__ import annotations

"""Acquire exact PIT-selected 2022 CALL EOD quote histories in one bounded campaign."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_additive_2022_shards_v1 import prepare_additive_shard
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object, _require_external
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    PLAN_REL, freeze_quote_plan, run_selected_quote_histories,
)
from packages.data.research_storage import ResearchStorageError, inspect_research_storage


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Global exact-symbol 2022 selected CALL EOD quote histories.")
    p.add_argument("--shards-through", type=int, default=15)
    p.add_argument("--max-new-requests", type=int, default=0)
    p.add_argument("--max-observed-credits", type=int, default=2100)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    a = p.parse_args(argv)
    print("ATLAS 2022 PIT-selected Historical CALL EOD Quote History Campaign V1", flush=True)
    print("  source-bound; 2022 originals and 2025 selected-quote pilot remain unchanged", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if a.max_new_requests:
            _require_external(settings)
        plan = freeze_quote_plan(settings, last_shard_inclusive=a.shards_through)
        plan_path = settings.resolved_path(
            f"{PLAN_REL}/through_shard_{a.shards_through:03d}.json"
        )
        if plan_path.exists() or plan_path.is_symlink():
            if _read_object(plan_path) != plan:
                raise CandidateChainCacheError("frozen selected quote plan changed; never overwrite")
            action = "REUSED_FROZEN_SELECTED_QUOTE_PLAN"
        elif a.max_new_requests:
            _exclusive(plan_path, plan)
            if _read_object(plan_path) != plan:
                raise CandidateChainCacheError("new selected quote plan failed read-back")
            action = "WRITTEN_FROZEN_SELECTED_QUOTE_PLAN"
        else:
            action = "PREVIEW_NO_PLAN_WRITES"
        print(f"  plan: {action} / {plan_path}", flush=True)
        print(f"  frozen source global census: {plan['global_2022_query_keys_fingerprint']}", flush=True)
        print(f"  original input shards: 0..{a.shards_through}; exact source gaps: {len(plan['source_gaps'])}", flush=True)
        print(f"  PIT-selected candidate memberships / distinct quote series: "
              f"{plan['selected_candidate_memberships']} / {plan['unique_exact_quote_series']}", flush=True)
        print(f"  quote query: 2022-01-01 through exact OCC expiration inclusive, once per symbol", flush=True)
        print(f"  plan fingerprint: {plan['plan_fingerprint']}", flush=True)
        before = inspect_research_storage(settings)
        print(f"  D: before: free={before.disk_free_gib:.3f} GiB "
              f"candidate_cache={before.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{before.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        result = run_selected_quote_histories(
            settings, plan, max_new_requests=a.max_new_requests,
            max_observed_credits=a.max_observed_credits, workers=a.workers,
            authorize=a.authorize_provider_reads, paid=a.confirm_paid_starter,
            private=a.confirm_private_internal_use,
            token=os.getenv("MARKETDATA_TOKEN", ""),
            progress=lambda row: print(
                "  quotes: " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True
            ),
        )
        after = inspect_research_storage(settings)
        print(f"  D: after: free={after.disk_free_gib:.3f} GiB "
              f"candidate_cache={after.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{after.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        print(f"  result: {result['status']}", flush=True)
        print(f"  complete histories / exact no-data / pending: "
              f"{result['complete_source_series']} / {result['exact_source_gaps']} / "
              f"{result['pending']}", flush=True)
        print(f"  new GETs / observed credits: "
              f"{result['new_provider_attempts']} / {result['observed_credits_this_invocation']}", flush=True)
        print(f"  original and new raw quote body bytes: {result['verified_and_new_raw_body_bytes']}", flush=True)
        print(f"  last provider remaining: {result['last_observed_provider_remaining']}", flush=True)
        print(f"  report fingerprint: {result['report_fingerprint']}", flush=True)
        print("  historical EOD source-only, no 09:35 option fill or option P&L authority", flush=True)
        return 0
    except (CandidateChainCacheError, ResearchStorageError,
            OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"QUOTE HISTORY CAMPAIGN STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve original chain/quote receipts and attempts; do not blindly retry.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
