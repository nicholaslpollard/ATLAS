from __future__ import annotations

"""New 2022 EOD scenario-readiness stage; no paid provider reads or option P&L."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_2022_ranked_eod_readiness_v1 import (
    build_ranked_eod_readiness, write_ranked_readiness,
)
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.research_storage import ResearchStorageError


def main() -> int:
    print("ATLAS 2022 Rank-0 CALL: Post-Decision EOD Scenario Readiness V1", flush=True)
    print("  source-only offline transformation; ZERO provider requests; no 09:35 fill or P&L", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        result = build_ranked_eod_readiness(
            settings, progress=lambda row: print(
                "  " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True
            )
        )
        path, action = write_ranked_readiness(settings, result)
        print(f"  status: {result['status']}", flush=True)
        for key in (
            "rank_zero_opportunity_memberships", "unique_rank_zero_quote_histories",
            "no_later_eod_observation", "later_eod_without_two_sided_context",
            "later_two_sided_eod_context_only",
            "later_positive_reported_volume_opportunities",
            "opportunities_with_two_or_more_later_two_sided_context_dates",
            "provider_requests", "original_quote_receipts_modified",
            "readiness_fingerprint",
        ):
            print(f"  {key}: {result[key]}", flush=True)
        print(f"  manifest: {action} / {path}", flush=True)
        print("  Future EOD observations do NOT establish PIT liquidity, intraday fills, adjusted deliverables, or option P&L.", flush=True)
        return 0
    except (CandidateChainCacheError, ResearchStorageError,
            OSError, ValueError, TypeError, KeyError) as exc:
        print(f"RANKED EOD READINESS STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve all original evidence; no paid retry or source reacquisition.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
