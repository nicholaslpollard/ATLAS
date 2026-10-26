from __future__ import annotations

"""V16 one-command SPY pilot acquisition, index and readiness integration.

Default: read-only coverage and required next-session exit source inventory.
--run: acquire ALL remaining frozen SPY weekly 10:00 quote requests only,
then build SHA-linked original-row indexes and report real pilot blockers.
--max-calls N optionally bounds *this run*, not the lifetime campaign.

No confirmation prompts; only already-authorized market-data API calls.
The 9,455 separate 09:35 CALL-candidate requests are NEVER acquired here.
A provider/archival failure stops the current campaign and remains
idempotently receipted. No quote is promoted to a true executable chain;
no equity P&L, broker activity, trading, protected outcomes or simulation.
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
from packages.data.hybrid_options_derived_dte_index_v1 import (
    build_dte_reference_indices,
)
from packages.data.hybrid_options_unattended_campaign_v1 import (
    run_campaign,
)
from packages.data.hybrid_options_parallel_campaign_v1 import run_parallel_campaign
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    SPY_ORIGIN, NativePilotAcceleratedReadinessError,
    review_native_pilot_acquisition_readiness,
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
                        help="Collect remaining SPY pilot entry sources unattended")
    parser.add_argument("--max-calls", type=int,
                        help="Optional per-run cap; no campaign lifetime cap")
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--workers", type=int, default=1,
                        help="1 sequential (default); 2-4 parallel Standard slots")
    args = parser.parse_args(argv)
    if args.max_calls is not None and (args.max_calls < 1 or not args.run):
        parser.error("--max-calls must be positive and requires --run")
    if args.progress_every < 1:
        parser.error("--progress-every must be positive")
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")
    print("ATLAS SPY PILOT BULK ACQUISITION AND READINESS V16", flush=True)
    print(
        "  mode=" + ("UNATTENDED_SPY_411_ENTRY_SOURCES_THEN_INDEX"
                  if args.run else "READ_ONLY_FROZEN_ENTRY_EXIT_COVERAGE")
        + " typed_authorizations=0", flush=True,
    )
    phase = "ENTRY_COVERAGE_PREFLIGHT"
    try:
        settings = load_settings(ROOT, "development")
        before = review_native_pilot_acquisition_readiness(
            settings, args.manifest, args.candidate_plan,
            with_quote_geometry=False,
        )
        print(
            f"  frozen_weekly_spy_entries={before['entry_required']}"
            f" saved_v12={before['entry_covered_v12_sources']}"
            f" saved_external={before['separately_saved_2025_spy_diagnostic']}"
            f" remaining={before['entry_outstanding_unattempted']}",
            flush=True,
        )
        print(
            f"  five_session_exit_uses={before['exit_review_uses']}"
            f" additional_unique_exit_query_scopes="
            f"{before['additional_distinct_exit_review_queries']}",
            flush=True,
        )
        result = None
        if args.run:
            print(f"  acquisition_workers={args.workers}", flush=True)
            phase = "SPY_SOURCE_ACQUISITION"
            acquire = (run_parallel_campaign if args.workers > 1
                       else run_campaign)
            result = acquire(
                settings, args.manifest, args.candidate_plan,
                **({"workers": args.workers} if args.workers > 1 else {}),
                max_calls=args.max_calls,
                progress_every=args.progress_every,
                allowed_origin=SPY_ORIGIN,
                progress=lambda event: print(
                    f"  PROGRESS: calls={event['completed_calls']}"
                    f" archives={event['archived']}"
                    f" out_dte={event['out_of_dte']}"
                    f" session={event['last_date']}"
                    f" last_id={event['last_request_id']}"
                    f" status={event['state']}",
                    flush=True,
                ),
            )
            print(
                f"  acquisition_calls={result['provider_calls_this_run']}"
                f" archives={result['archives_written_this_run']}"
                f" out_dte={result['out_of_dte_archives_this_run']}"
                f" invalid_archives={result['invalid_schema_archives_this_run']}"
                f" stop={result['stop_reason']}",
                flush=True,
            )
            # This is LOCAL-only source-linked index metadata. Complete
            # original quotes remain on the D: archive, never overwritten.
            phase = "SOURCE_INDEX_VERIFICATION"
            derived = build_dte_reference_indices(
                settings, args.manifest, args.candidate_plan,
                write_indexes=True,
            )
            print(
                f"  indexed_sources={derived['original_archives_scanned']}"
                f" referenced_0_45_dte_rows={derived['in_requested_dte_references']}"
                f" new_sidecars={derived['new_immutable_indices']}",
                flush=True,
            )
        phase = "FINAL_SOURCE_READINESS"
        after = review_native_pilot_acquisition_readiness(
            settings, args.manifest, args.candidate_plan,
            with_quote_geometry=True,
        )
        print(
            f"  final_saved_v12={after['entry_covered_v12_sources']}"
            f" unattempted_spy_entries={after['entry_outstanding_unattempted']}"
            f" research_native_dte_30_45={after['pilot_quote_diagnostics']}"
            f" entry_states={after['entry_states']}",
            flush=True,
        )
        print(
            f"  missing_exits={after['additional_distinct_exit_review_queries']}"
            f" simulator_blockers={len(after['remaining_simulator_blockers'])}"
            f" source_report_fp={after['fingerprint']}",
            flush=True,
        )
        print(
            "  COMPLETE: source_collection_only=True"
            " simulator_ready=False simulations_run=0"
            " protected_outcomes_read=0",
            flush=True,
        )
        if result is not None and result["stop_reason"] not in {
            "FULL_FROZEN_MANIFEST_SCANNED",
            "OPTIONAL_RUN_REQUEST_LIMIT_REACHED",
        }:
            return 4
        return 0
    except NativePilotAcceleratedReadinessError as exc:
        # This exception uses local fixed diagnostic codes only; do not
        # print arbitrary SDK/provider exceptions, source rows, or secrets.
        print(
            f"  BLOCKED: NativePilotAcceleratedReadinessError phase={phase}"
            f" code={exc} no_simulation=True no_source_promotion=True",
            flush=True,
        )
        return 3
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + f" phase={phase}"
            + " no_simulation=True no_source_promotion=True",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
