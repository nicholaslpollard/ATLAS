from __future__ import annotations

"""V19 SPY weekly straddle exact 10:00 next-five-session EXIT source campaign.

Default: offline verified existing archive preview; no provider calls or files.
--run: explicitly acquire remaining 1570 distinct frozen exit quote sources
through up to four account-wide ThetaData Standard Python library workers.
Reuses all 411 pre-existing entry query identities (including the separately
retained 2025 one), does not re-download, overwrite or promote them.
Read-only original quote diagnostics only; no simulator or option fills.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    PINNED_MANIFEST_FINGERPRINT,
)
from packages.data.options_native_exit_source_campaign_v1 import (
    SpyExitSourceError, preview_exit_campaign, run_exit_campaign,
)

DEFAULT_MANIFEST = Path(
    "data/options/manifests/hybrid_exact_at_time_research_demand_v1_"
    + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
)
DEFAULT_CANDIDATE = Path(
    "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
    "acc9525a2930fe39.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--run", action="store_true",
                        help="Opt in to real paid exit data acquisition")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-calls", type=int,
                        help="Optional maximum provider calls across all workers")
    parser.add_argument("--progress-every", type=int, default=50)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 4:
        parser.error("ThetaData Standard permits workers in 1..4")
    if args.max_calls is not None and (
        args.max_calls < 1 or not args.run
    ):
        parser.error("--max-calls requires --run and a positive integer")
    if args.progress_every <= 0:
        parser.error("--progress-every must be positive")
    print("ATLAS FROZEN SPY FIVE-SESSION EXIT SOURCES V19", flush=True)
    print(
        "  mode=" + ("PAID_RESUMABLE_EXIT_SOURCE_ACQUISITION" if args.run
                  else "READ_ONLY_DEDUPLICATED_EXIT_DEMAND_PREVIEW"),
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        before = preview_exit_campaign(
            settings, args.manifest, args.candidate_plan,
        )
        print(
            f"  exit_uses={before['exit_review_uses']}"
            f" reused_entry_request_ids={before['reused_original_entry_queries']}"
            f" new_distinct_exit_scopes={before['additional_distinct_exit_requests']}"
            f" remaining={before['remaining_unattempted']}"
            f" states={before['exit_source_states']}",
            flush=True,
        )
        print(
            f"  storage_safe={before['shared_storage_safe']}"
            f" safe_headroom_gib={before['safe_available_bytes']/1024**3:.3f}"
            f" plan_fp={before['plan_fingerprint']}", flush=True,
        )
        if not args.run:
            print(
                "  COMPLETE: provider_requests=0 original_sources_untouched=True"
                " simulator_ready=False fills_run=0",
                flush=True,
            )
            return 0
        print(f"  active_worker_limit={args.workers}", flush=True)
        result = run_exit_campaign(
            settings, args.manifest, args.candidate_plan,
            workers=args.workers, max_calls=args.max_calls,
            progress_every=args.progress_every,
            progress=lambda event: print(
                f"  PROGRESS: calls={event['calls']}"
                f" archives={event['archived']}"
                f" over_dte={event['over_dte']}"
                f" last_date={event['date_et']}"
                f" query_id={event['query_id']}"
                f" state={event['state']}",
                flush=True,
            ),
        )
        print(
            f"  dispatched={result['provider_calls_this_run']}"
            f" completed={result['completed_provider_calls_this_run']}"
            f" archives={result['archives_this_run']}"
            f" out_dte={result['outside_dte_archives_this_run']}"
            f" invalid_archives={result['invalid_archives_this_run']}"
            f" full_storage_audits={result['full_storage_audits_this_run']}"
            f" stop={result['stop_reason']}",
            flush=True,
        )
        after = preview_exit_campaign(
            settings, args.manifest, args.candidate_plan,
        )
        print(
            f"  remaining={after['remaining_unattempted']}"
            f" final_states={after['exit_source_states']}"
            f" preview_fp={after['fingerprint']}", flush=True,
        )
        print(
            "  COMPLETE: source_only=True simulator_ready=False"
            " protected_outcomes_read=0 simulations_run=0", flush=True,
        )
        return 0 if result["stop_reason"] in {
            "ALL_NEW_EXIT_SCOPES_SCANNED",
            "OPTIONAL_GLOBAL_CALL_LIMIT_REACHED",
        } else 4
    except SpyExitSourceError as exc:
        # All explicit V19 error strings are locally-defined invariant
        # constants. No external SDK payload/credentials are disclosed.
        print(f"  BLOCKED: SpyExitSourceError code={exc}"
              " no_source_promotion=True", flush=True)
        return 3
    except Exception as exc:
        print("  BLOCKED: " + type(exc).__name__
              + " no_source_promotion=True", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
