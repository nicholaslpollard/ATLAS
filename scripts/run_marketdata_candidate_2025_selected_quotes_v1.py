from __future__ import annotations

"""One-command operator gate for the frozen 2025 selected EOD CALL sources."""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.research_storage import ResearchStorageError
from packages.data.marketdata_candidate_2025_selected_quote_source_v1 import (
    build_quote_plan, read_accepted_inputs, run_quote_source, write_plan,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-gate bounded selected historical EOD quote-source acquisition."
    )
    parser.add_argument("--authorize-provider-reads", action="store_true")
    parser.add_argument("--confirm-paid-starter", action="store_true")
    parser.add_argument("--confirm-private-internal-use", action="store_true")
    parser.add_argument("--max-new-requests", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(ROOT, "development")
        shortlist, references = read_accepted_inputs(settings)
        plan = build_quote_plan(settings, shortlist, references)
        action, location = write_plan(settings, plan, authorize=args.max_new_requests > 0)
        print("ATLAS 2025 Selected CALL EOD Quote Source V1", flush=True)
        print(f"  frozen shortlist: {plan['shortlist_fingerprint']}", flush=True)
        print(f"  prior reference plan: {plan['reference_plan_fingerprint']}", flush=True)
        print(f"  new quote plan: {plan['plan_fingerprint']}", flush=True)
        print(f"  quote plan: {action} / {location}", flush=True)
        print("  11 exact CALL symbols, decision-date to expiry+1 exclusive; FSLY excluded", flush=True)
        def progress(item: dict) -> None:
            s = item["safe_summary"]
            c = item["rate_limit"]
            print(
                f"  {item['ticker']:<5} HTTP={item['http_status']} "
                f"{item['classification']} rows={s['observed_rows']} "
                f"positive_volume={s['positive_volume_rows']} "
                f"observed_credits={c['consumed']} remaining={c['remaining']}",
                flush=True,
            )
        report = run_quote_source(
            settings, plan, authorize=args.authorize_provider_reads,
            confirm_paid=args.confirm_paid_starter,
            confirm_private_use=args.confirm_private_internal_use,
            max_new_requests=args.max_new_requests,
            token=os.getenv("MARKETDATA_TOKEN", "").strip(),
            progress=progress,
        )
        print(
            f"  result={report['status']} source_series={report['source_series']} "
            f"exact_query_gaps={report['exact_no_data_series']} pending={report['pending']} "
            f"new_GETs={report['new_provider_attempts']} "
            f"observed_credits={report['observed_credits_consumed_this_run']}",
            flush=True,
        )
        print(f"  report fingerprint: {report['report_fingerprint']}", flush=True)
        print("  no option fill/P&L, strategy, PAPER, LIVE or broker authority", flush=True)
        return 0
    except (CandidateChainCacheError, ResearchStorageError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"QUOTE SOURCE GATE STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  preserve original evidence and do not retry blindly", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
