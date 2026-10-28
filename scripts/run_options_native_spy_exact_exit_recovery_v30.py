from __future__ import annotations

"""V30 shared-auth ThetaData exact SPY option exit ORIGINAL SOURCE recovery.

Preview makes ZERO provider calls. --run intentionally performs paid historical
option GETs at fixed 10:00 dated exact contract identities from an immutable
V29 report. No broker, trading, historical fill or account simulation.
A single SDK login creates four clients for source-only batches.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.options_native_spy_exact_exit_source_campaign_v30 import (
    load_exact_exit_plan, preview_exact_exit_campaign, run_exact_exit_campaign,
)

DEFAULT_PLAN = Path("data/research/spy_one_pair_exact_exit_demand_v29.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--run", action="store_true",
                        help="Perform real paid ThetaData historical exact-contract quote GETs")
    parser.add_argument("--max-calls", type=int, default=None,
                        help="Optional absolute per-run paid request cap; default all missing")
    parser.add_argument("--progress-every", type=int, default=50)
    parser.add_argument("--adaptive-recovery", action="store_true",
                        help="After one ambiguous four-query batch, leave its IDs uncertain, "
                             "restart SDK authentication and use 16 new single-query "
                             "batches before returning to four workers; stop at two failures")
    args = parser.parse_args(argv)
    print("ATLAS V30 SPY EXACT CONTRACT SHARED-AUTH SOURCE RECOVERY", flush=True)
    print(
        "  mode=" + (
            "PAID_EXACT_OPTION_SOURCE_ONLY" if args.run
            else "OFFLINE_IMMUTABLE_RECEIPT_PREVIEW"
        ), flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        plan = load_exact_exit_plan(args.plan)
        preview = preview_exact_exit_campaign(settings, plan)
        print(
            f"  missing_right_requests={preview['total_exact_right_requests']}"
            f" unattempted={preview['remaining_unattempted']}"
            f" states={preview['states']}"
            f" source_plan_fp={plan['fingerprint']}",
            flush=True,
        )
        if not args.run:
            print("  COMPLETE: PREVIEW_ONLY provider_requests=0 broker_requests=0", flush=True)
            return 0
        def progress(item):
            print(
                f"  PROGRESS: calls={item['calls']}"
                f" archives={item['archives']}"
                f" no_data={item['explicit_no_data']}"
                f" provider_faults={item['provider_faults']}"
                f" invalid_archives={item['invalid_archives']}"
                f" last_date={item['last_date']}",
                flush=True,
            )
        done = run_exact_exit_campaign(
            settings, plan,
            max_calls=args.max_calls,
            progress=progress,
            progress_every=args.progress_every,
            adaptive_recovery=args.adaptive_recovery,
        )
        print(
            f"  dispatched={done['provider_requests_this_run']}"
            f" archived={done['archived_this_run']}"
            f" no_data={done['no_data_this_run']}"
            f" provider_failures={done['provider_failures_this_run']}"
            f" invalid_archives={done['invalid_archives_this_run']}"
            f" full_storage_audits={done['storage_audits_this_run']}"
            f" ambiguous_batches={done['ambiguous_batch_failures_this_run']}"
            f" uncertain_new={done['ambiguous_query_ids_preserved_this_run']}"
            f" ambiguous_error_class={done['last_ambiguous_error_type']}"
            f" ambiguous_category={done['last_ambiguous_failure_category']}"
            f" single_fallback={done['adaptive_single_query_fallback_activated']}"
            f" stop={done['stop_reason']}", flush=True,
        )
        print(f"  remaining={done['remaining']} states={done['states']}", flush=True)
        print("  COMPLETE: SOURCE_ONLY simulator_ready=False broker_requests=0", flush=True)
        return 0 if done["stop_reason"] in {
            "ALL_ELIGIBLE_EXACT_RIGHT_QUERIES_SCANNED", "CALL_LIMIT_REACHED",
        } else 2
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__ + ": " + str(exc)[:400],
            flush=True,
        )
        print("  NEVER re-request a started or terminal exact query ID automatically.", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
