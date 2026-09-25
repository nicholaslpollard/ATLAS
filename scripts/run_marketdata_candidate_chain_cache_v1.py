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
        return 3

    print("ATLAS MarketData Candidate Chain Cache V1")
    print(f"  status: {report['status']}")
    print(f"  plan fingerprint: {report['plan_fingerprint']}")
    print(f"  storage mode: {report['storage_mode']}")
    print(f"  verified stock source files: {len(report['verified_stock_source_sha256'])}")
    print(f"  planned shared chains: {report['planned_chain_requests']}")
    print(f"  verified existing receipts: {report['reused']}")
    print(f"  new complete receipts: {report['new_complete']}")
    print(f"  provider reads: {report['provider_reads']}")
    print(f"  pending: {report['pending']}")
    print("  option quote-series reads: 0")
    print("  broker reads/writes: 0")
    print("  historical option execution/P&L authority: false")
    print(f"  report fingerprint: {report['report_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
