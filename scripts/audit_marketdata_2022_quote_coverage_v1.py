from __future__ import annotations

"""Audit saved PIT-wide exact historical quote series locally. No provider token/read."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_2022_quote_coverage_audit_v1 import audit_frozen_quote_coverage
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.research_storage import ResearchStorageError, inspect_research_storage


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read-only 2022 saved CALL quote source coverage.")
    p.add_argument("--shards-through", type=int, default=15)
    a = p.parse_args(argv)
    print("ATLAS Original 2022 Historical CALL Quote Source Coverage Audit", flush=True)
    print("  local D: evidence only; zero provider requests and no new raw/receipt writes", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        report = audit_frozen_quote_coverage(settings, last_shard_inclusive=a.shards_through)
        for key, value in report.items():
            print(f"  {key}: {value}", flush=True)
        storage = inspect_research_storage(settings)
        print(f"  D: free: {storage.disk_free_gib:.3f} GiB", flush=True)
        print(f"  D: options_candidate_cache: "
              f"{storage.category_usage_gib['options_candidate_cache']:.3f}/"
              f"{storage.category_quota_gib['options_candidate_cache']:.3f} GiB", flush=True)
        return 0 if report["status"] == "COMPLETE_SOURCE_ONLY" else 3
    except (CandidateChainCacheError, ResearchStorageError,
            OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"QUOTE AUDIT STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve original plan/intents/receipts. No automatic paid retry.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
