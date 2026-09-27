from __future__ import annotations

"""Bounded bulk selected-CALL EOD histories for all captured 2022 PIT strikes."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_2022_broad_quote_campaign_v2 import (
    PLAN_REL, WIDE_POLICY, freeze_broad_quote_plan, run_broad_quote_histories,
)
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_candidate_expansion_v1 import (
    _exclusive, _read_object, _require_external,
)
from packages.data.research_storage import ResearchStorageError, inspect_research_storage


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="PIT-frozen complete captured CALL strike envelope: exact historical quote series."
    )
    p.add_argument("--shards-through", type=int, default=15)
    p.add_argument("--max-new-requests", type=int, default=0)
    p.add_argument("--max-observed-credits", type=int, default=2100)
    p.add_argument("--workers", type=int, default=16, help="bounded concurrent network requests (1..24; recommended 16)")
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    a = p.parse_args(argv)
    print("ATLAS 2022 PIT-wide CALL EOD Quote History Campaign V2", flush=True)
    print("  all available prior-session CALL strikes within 8% of each native raw open", flush=True)
    try:
        if a.max_new_requests and not (
            a.authorize_provider_reads and a.confirm_paid_starter and a.confirm_private_internal_use
        ):
            raise CandidateChainCacheError("three paid/provider/private confirmations required")
        if not a.max_new_requests and any((
            a.authorize_provider_reads, a.confirm_paid_starter, a.confirm_private_internal_use
        )):
            raise CandidateChainCacheError("provider confirmation requires positive request budget")
        settings = load_settings(ROOT, "development")
        if a.max_new_requests:
            _require_external(settings)
        plan = freeze_broad_quote_plan(settings, last_shard_inclusive=a.shards_through)
        plan_path = settings.resolved_path(
            f"{PLAN_REL}/through_shard_{a.shards_through:03d}.json"
        )
        if plan_path.exists() or plan_path.is_symlink():
            if _read_object(plan_path) != plan:
                raise CandidateChainCacheError("frozen V2 broad quote plan changed; preserve original")
            action = "REUSED_EXACT_BROAD_QUOTE_PLAN"
        elif a.max_new_requests:
            _exclusive(plan_path, plan)
            if _read_object(plan_path) != plan:
                raise CandidateChainCacheError("new broad quote plan failed read-back")
            action = "WRITTEN_NEW_IMMUTABLE_BROAD_QUOTE_PLAN"
        else:
            action = "READ_ONLY_PREVIEW"
        print(f"  plan: {action} / {plan_path}", flush=True)
        print(f"  policy: {WIDE_POLICY}", flush=True)
        print(f"  source shards: 0..{a.shards_through}; proven source gaps: {len(plan['source_gaps'])}", flush=True)
        print(f"  selected memberships / deduplicated exact OCC histories: "
              f"{plan['selected_candidate_memberships']} / {plan['unique_exact_quote_series']}", flush=True)
        print("  one already-captured monthly expiration per opportunity; alternate expirations NOT acquired", flush=True)
        print(f"  immutable plan fingerprint: {plan['plan_fingerprint']}", flush=True)
        before = inspect_research_storage(settings)
        print(f"  D: before: free={before.disk_free_gib:.3f} GiB; "
              f"candidate_cache={before.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{before.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        report = run_broad_quote_histories(
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
        print(f"  D: after: free={after.disk_free_gib:.3f} GiB; "
              f"candidate_cache={after.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{after.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        print(f"  RESULT: {report['status']}", flush=True)
        print(f"  complete exact histories / exact no-data gaps / pending: "
              f"{report['complete_source_series']} / {report['exact_source_gaps']} / {report['pending']}", flush=True)
        print(f"  new GETs / observed credits: "
              f"{report['new_provider_attempts']} / {report['observed_credits_this_invocation']}", flush=True)
        print(f"  verified original raw quote response bytes: {report['verified_and_new_raw_body_bytes']}", flush=True)
        print(f"  last provider remaining: {report['last_observed_provider_remaining']}", flush=True)
        print(f"  report fingerprint: {report['report_fingerprint']}", flush=True)
        print("  source only, no at-09:35 executable option price, P&L, PAPER/LIVE or broker authority", flush=True)
        return 0
    except (CandidateChainCacheError, ResearchStorageError, OSError,
            ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"BROAD QUOTE CAMPAIGN STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve original plan/intents/receipts; no blanket retries.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
