from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError,
    run_candidate_chain_cache,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bounded historical MarketData EOD chain cache; preview by default. "
            "Does not select options, fetch quote histories, or simulate P&L."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--max-new-requests", type=int, default=0)
    parser.add_argument("--stock-source-file", type=Path, action="append", default=[], help="Exact accepted DEVELOPMENT stock artifact(s) whose SHA values appear in the plan; mandatory for live reads.")
    parser.add_argument("--authorize-provider-reads", action="store_true")
    parser.add_argument("--confirm-paid-starter", action="store_true")
    parser.add_argument("--confirm-private-internal-use", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        settings = load_settings(PROJECT_ROOT, "development")
        report = run_candidate_chain_cache(
            settings, plan,
            max_new_requests=args.max_new_requests,
            authorize_provider_reads=args.authorize_provider_reads,
            confirm_paid_starter=args.confirm_paid_starter,
            confirm_private_internal_use=args.confirm_private_internal_use,
            stock_source_files=tuple(args.stock_source_file),
        )
    except (OSError, ValueError, CandidateChainCacheError) as exc:
        print(f"CANDIDATE CHAIN CACHE BLOCKED: {type(exc).__name__}: {exc}", flush=True)
        if isinstance(locals().get("plan"), dict):
            fingerprint = plan.get("plan_fingerprint")
            if isinstance(fingerprint, str) and len(fingerprint) == 64:
                print(
                    "  inspect any checkpoint at: "
                    f"data/options/manifests/marketdata_candidate_chain_cache_v1_{fingerprint[:16]}.json",
                    flush=True,
                )
        print("  do not automatically replay an ambiguous provider attempt", flush=True)
        return 3

    print("ATLAS MarketData Candidate Chain Cache V1")
    print(f"  status: {report['status']}")
    print(f"  plan fingerprint: {report['plan_fingerprint']}")
    print(f"  storage mode: {report['storage_mode']}")
    print(f"  verified stock source files: {len(report['verified_stock_source_sha256'])}")
    print(f"  planned stock opportunities: {report['planned_opportunities']}")
    print(f"  planned shared chains: {report['planned_chain_requests']}")
    print(f"  shared-chain dedup savings: {report['planned_opportunities'] - report['planned_chain_requests']}")
    print(f"  verified existing receipts: {report['reused']}")
    print(f"  new complete receipts: {report['new_complete']}")
    print(f"  exact-query source gaps verified: {report['no_data_verified']}")
    print(f"  provider read attempts: {report['provider_reads']}")
    print(f"  credits consumed observed this invocation: {report['observed_credits_consumed_this_run']}")
    print(f"  credit consumption uncertain: {report['credits_unknown_after_failed_request']}")
    print(f"  provider credits remaining last observed: {report['last_observed_provider_credits_remaining']}")
    print(f"  verified reused bytes: {report['verified_reused_bytes']:,}")
    print(f"  separately verified no-data raw bytes: {report['verified_no_data_bytes']:,}")
    print(f"  new raw bytes: {report['new_raw_bytes']:,}")
    print(f"  quarantined responses: {report['quarantined']}")
    print(f"  elapsed seconds: {report['elapsed_seconds']:.1f}")
    if report.get("processed_per_second") is not None:
        print(f"  processed requests/second: {report['processed_per_second']}")
    if report.get("estimated_remaining_seconds") is not None:
        print(f"  rough remaining seconds: {report['estimated_remaining_seconds']}")
    if report.get("latest_report_path"):
        print(f"  checkpoint: {report['latest_report_path']}")
        print(f"  archived run report: {report['run_report_path']}")
    print(f"  pending: {report['pending']}")
    print("  option quote-series reads: 0")
    print("  broker reads/writes: 0")
    print("  historical option execution/P&L authority: false")
    print(f"  report fingerprint: {report['report_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
