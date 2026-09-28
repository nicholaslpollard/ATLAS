from __future__ import annotations

"""Start or resume the accepted 2021–2025 chain-library campaign; no stock rescan."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.multiyear_chain_campaign_v1 import (
    MultiYearChainCampaignError, run_campaign,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Year-balanced local-cache-first historical chains")
    p.add_argument("--max-new-requests", type=int, default=0,
                   help="0 means a free local preview; positive needs all confirmations")
    p.add_argument("--max-observed-credits", type=int, default=0)
    p.add_argument("--min-remaining-credits", type=int, default=500,
                   help="Explicit minimum provider credits left for later runs (default 500)")
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--authorize-provider-reads", action="store_true")
    p.add_argument("--confirm-paid-starter", action="store_true")
    p.add_argument("--confirm-private-internal-use", action="store_true")
    a = p.parse_args(argv)
    print("ATLAS 2021–2025 Year-Balanced Chain Acquisition / CACHE FIRST", flush=True)
    print("  Original 2022 quotes reused, no stock replay or old cache rescan.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        result = run_campaign(
            settings, max_new_requests=a.max_new_requests,
            max_observed_credits=a.max_observed_credits, workers=a.workers,
            min_remaining_credits=a.min_remaining_credits,
            authorize_provider_reads=a.authorize_provider_reads,
            confirm_paid_starter=a.confirm_paid_starter,
            confirm_private_internal_use=a.confirm_private_internal_use,
            token=os.getenv("MARKETDATA_TOKEN", ""),
            progress=lambda row: print("  " + " ".join(
                f"{k}={v}" for k, v in row.items()), flush=True),
        )
        for key, value in result.items():
            print(f"  {key}: {value}", flush=True)
        print("  Future exact source requests are resumed only when no ambiguous attempt exists.",
              flush=True)
        return 0 if result["status"] in (
            "OFFLINE_PREVIEW", "COMPLETE_ELIGIBLE_SOURCE_WORK",
            "PARTIAL_REQUEST_LIMIT_REACHED", "PARTIAL_OBSERVED_CREDIT_BUDGET",
            "PARTIAL_PROVIDER_CREDIT_FLOOR", "PARTIAL_D_STORAGE_BUDGET",
        ) else 3
    except (MultiYearChainCampaignError, ValueError, RuntimeError, OSError, KeyError,
            TypeError) as exc:
        print(f"MULTIYEAR CHAIN CAMPAIGN STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve original attempts, bodies and receipts; no blind provider retry.",
              flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
