from __future__ import annotations

"""Local zero-network closeout for the accepted 2025 MarketData candidate pilot."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_candidate_2025_source_closeout_v1 import (
    build_source_closeout, write_local_closeout,
)
from scripts.run_marketdata_candidate_2025_pilot import SOURCE_SHA256, preflight

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independently close out immutable source-only receipts; zero provider calls."
    )
    parser.add_argument(
        "--write-local-closeout", action="store_true",
        help="Exclusive local D:-bound metadata manifest write; never overwrite raw provider evidence.",
    )
    args = parser.parse_args(argv)
    try:
        settings = load_settings(ROOT, "development")
        plan, source = preflight(settings)
        report = build_source_closeout(settings, plan, source_sha256=SOURCE_SHA256)
        action, output_path = write_local_closeout(
            settings, report, authorize_local_write=args.write_local_closeout,
        )
    except (OSError, ValueError, TypeError, CandidateChainCacheError) as exc:
        print(f"SOURCE CLOSEOUT BLOCKED: {type(exc).__name__}: {exc}", flush=True)
        print("  zero provider calls; preserve all original receipts and proof sidecars", flush=True)
        return 3
    print("ATLAS MarketData Accepted 2025 Candidate Source Closeout V1")
    print(f"  accepted stock source: {source}")
    print(f"  plan fingerprint: {report['plan_fingerprint']}")
    print(f"  status: {report['status']}")
    print(f"  verified complete chains: {report['verified_complete_chains']}")
    print(f"  FSLY exact-query no-data: {report['exact_query_no_data']}")
    print(f"  remaining requests: {report['pending']}")
    print(f"  reported credits across complete original receipts: {report['provider_reported_credits_consumed_by_complete_receipts']}")
    for row in report["requests"]:
        desc = (
            f"call={row['observed_call_rows']} put={row['observed_put_rows']}"
            if row["status"] == "REUSED_VERIFIED" else "frozen exact-query source gap"
        )
        print(f"  {row['ticker']:<5} {row['status']} rows={row['row_count']} {desc}")
    print(f"  closeout fingerprint: {report['closeout_fingerprint']}")
    print(f"  local action: {action}")
    print(f"  local output path: {output_path}")
    print("  provider reads: 0; new credits: 0; no quote, contract selection or option-P&L authority")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
