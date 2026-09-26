from __future__ import annotations

"""Acquire exact historical reference dossiers; no chain re-acquisition."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_candidate_2025_exact_reference_v1 import (
    MIN_REQUEST_INTERVAL_SECONDS, build_exact_reference_plan,
    read_accepted_shortlist, run_reference_dossiers, write_reference_plan,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exact PIT Massive reference dossiers, zero-network default.")
    parser.add_argument("--authorize-reference-reads", action="store_true")
    parser.add_argument("--confirm-development-reference-only", action="store_true")
    parser.add_argument("--max-new-requests", type=int, default=0)
    args = parser.parse_args(argv)
    if args.max_new_requests and not (
        args.authorize_reference_reads and args.confirm_development_reference_only
    ):
        print("REFERENCE GATE BLOCKED: network reads require both explicit flags")
        return 3
    try:
        settings = load_settings(ROOT, "development")
        plan = build_exact_reference_plan(read_accepted_shortlist(settings))
        action, path = write_reference_plan(settings, plan)
        preview = run_reference_dossiers(settings, plan)
        print("ATLAS 2025 Exact Historical Contract Reference Dossiers V1")
        print(f"  frozen shortlist: {plan['shortlist_fingerprint']}")
        print(f"  plan fingerprint: {plan['plan_fingerprint']}")
        print(f"  plan action: {action}; private manifest: {path}")
        print(f"  reusable original reference receipts: {preview['previous_receipts_reused']}")
        print(f"  pending exact reference requests: {preview['pending']}; FSLY excluded")
        print(f"  minimum pacing: {MIN_REQUEST_INTERVAL_SECONDS:.1f}s, one worker; no retries")
        if not args.max_new_requests:
            print("  no provider reads authorized; preview only")
            return 0
        report = run_reference_dossiers(
            settings, plan, authorize_provider_reads=True,
            confirm_reference_only=args.confirm_development_reference_only,
            max_new_requests=args.max_new_requests,
            api_key=os.getenv(settings.massive.credentials.api_key_env, "").strip(),
        )
        for item in report["results"]:
            if item["status"] == "PENDING_NEVER_ATTEMPTED":
                print(f"  {item['ticker']:<5} {item['option_symbol']} PENDING_NEVER_ATTEMPTED")
                continue
            terms = item["safe_terms"]
            print(
                f"  {item['ticker']:<5} {item['option_symbol']} HTTP={item['http_status']} "
                f"{item['status']} shares={terms['shares_per_contract']} "
                f"style={terms['exercise_style']} extras={terms['additional_underlyings']}"
            )
        print(f"  result: {report['status']}; new GET starts: {report['new_provider_attempts_this_run']}")
        print(f"  remaining: {report['pending']}; report fingerprint: {report['report_fingerprint']}")
        print("  historical deliverable verified: 0; executable contracts: 0; option P&L: none")
        return 0
    except (OSError, ValueError, TypeError, KeyError, CandidateChainCacheError) as exc:
        print(f"REFERENCE GATE STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  preserve original raw, attempt and receipt; no automatic retry", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
