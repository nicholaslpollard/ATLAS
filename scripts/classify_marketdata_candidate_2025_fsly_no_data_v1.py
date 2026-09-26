from __future__ import annotations

"""Explicit offline disposition of the immutable 2025 FSLY 404/no_data.

No provider import, credentials, network, existing-cache overwrite or plan
modification. Creates only a separately fingerprinted, exclusive source-gap
sidecar when explicitly authorized, then independently previews the cohort.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, record_exact_query_no_data,
    run_candidate_chain_cache,
)
from scripts.run_marketdata_candidate_2025_pilot import (
    FSLY_NO_DATA_REQUEST_ID, TOTAL_REQUESTS, _assert_preview, preflight,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exact FSLY 404/no_data evidence; preview by default, zero provider calls."
    )
    parser.add_argument(
        "--authorize-exact-no-data-record", action="store_true",
        help="Explicitly create immutable exact-query source-gap sidecar; never retry or rewrite response."
    )
    args = parser.parse_args(argv)
    try:
        settings = load_settings(ROOT, "development")
        plan, source = preflight(settings)
        if len(plan["requests"]) != TOTAL_REQUESTS:
            raise CandidateChainCacheError("pilot cohort size mismatch")
        original = plan["requests"][5]
        if (original["ticker"] != "FSLY"
                or original["request_identity"] != FSLY_NO_DATA_REQUEST_ID):
            raise CandidateChainCacheError("frozen FSLY request identity mismatch")
        result = record_exact_query_no_data(
            settings, plan, FSLY_NO_DATA_REQUEST_ID,
            authorize_offline_classification=args.authorize_exact_no_data_record,
        )
        proof = result["proof"]
        print("ATLAS MarketData 2025 FSLY Exact-Query No-Data Disposition")
        print(f"  exact source verified: {source}")
        print(f"  action: {result['action']}")
        print(f"  frozen request: {original['ticker']} {original['params']}")
        print(f"  http status / provider s: {proof['http_status']} / {proof['provider_payload_status']}")
        print(f"  row count: {proof['row_count']}")
        print(f"  raw body hash: {proof['body_sha256']}")
        print(f"  original receipt fingerprint: {proof['original_receipt_fingerprint']}")
        print(f"  provider-reported consumed credits: {proof['provider_credits_consumed_reported']}")
        print(f"  last remaining: {proof['provider_credits_remaining_reported']}")
        print(f"  proof fingerprint: {proof['proof_fingerprint']}")
        if args.authorize_exact_no_data_record:
            preview = run_candidate_chain_cache(settings, plan)
            _assert_preview(preview)
            if (preview.get("no_data_verified") != 1 or preview["pending"] != 6
                    or preview["reused"] != 5 or preview["provider_reads"] != 0):
                raise CandidateChainCacheError(
                    "post-disposition physical cohort preview differs; preserve evidence"
                )
            print("  physical cohort: 5 complete / 1 exact-query no-data / 6 pending")
        print("  provider calls: 0; credits spent this invocation: 0")
        print("  original raw body, receipt, attempt and frozen plan unchanged")
        print("  exact-query source coverage only; no broader contract absence or option P&L authority")
        return 0
    except (OSError, ValueError, CandidateChainCacheError, TypeError) as exc:
        print(f"OFFLINE DISPOSITION BLOCKED: {type(exc).__name__}: {exc}", flush=True)
        print("  preserve original evidence and do not replay FSLY", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
