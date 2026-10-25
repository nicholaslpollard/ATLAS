from __future__ import annotations

"""V16 offline SPY historical source/exit demand and simulator gap report.

Never downloads option quotes, assumes executable prices, reads protected
performance or runs a strategy. Use the existing no-prompt resumable
V12 downloader for larger batches; use this afterward to quantify which
original 411 SPY weekly entry clocks and exit-review sessions are missing.
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
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    review_native_pilot_acquisition_readiness,
)

DEFAULT_MANIFEST = Path(
    "data/options/manifests/hybrid_exact_at_time_research_demand_v1_"
    + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
)
DEFAULT_SOURCE = Path(
    "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
    "acc9525a2930fe39.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--coverage-only", action="store_true",
        help="Inspect all frozen entry/exit query scopes without requiring new V14 indexes",
    )
    args = parser.parse_args(argv)
    print("ATLAS SPY NATIVE PILOT ACQUISITION AND SIMULATOR GAPS V16", flush=True)
    print(
        "  mode=" + ("SOURCE_COVERAGE_NO_QUOTE_GEOMETRY"
                  if args.coverage_only else "SOURCE_AND_QUOTE_RESEARCH_READINESS")
        + " provider_requests=0 broker_requests=0 outcome_reads=0",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        report = review_native_pilot_acquisition_readiness(
            settings, args.manifest, args.candidate_plan,
            with_quote_geometry=not args.coverage_only,
        )
        print(
            f"  exact_spy_entry_clocks={report['entry_required']}"
            f" archived_v12={report['entry_covered_v12_sources']}"
            f" existing_spy_2025_diagnostic={report['separately_saved_2025_spy_diagnostic']}"
            f" not_attempted={report['entry_outstanding_unattempted']}"
            f" states={report['entry_states']}",
            flush=True,
        )
        print(
            f"  five_session_exit_review_uses={report['exit_review_uses']}"
            f" unique_exit_dates={report['distinct_exit_review_queries']}"
            f" exit_scope_overlap_with_411_entries="
            f"{report['exit_queries_reusing_frozen_entry_scope']}"
            f" additional_exit_scopes={report['additional_distinct_exit_review_queries']}",
            flush=True,
        )
        print(
            "  pilot_dte=30..45"
            " quote_age_max_seconds=30"
            " call_put_skew_max_seconds=1"
            f" observed_diagnostics={report['pilot_quote_diagnostics']}",
            flush=True,
        )
        print(
            "  simulator_blockers=" + ",".join(
                report["remaining_simulator_blockers"]
            ),
            flush=True,
        )
        print(f"  report_fingerprint={report['fingerprint']}", flush=True)
        print(
            "  COMPLETE: provider_requests=0 files_written=0"
            " historic_fill_authority=False simulator_ready=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + " provider_requests=0 files_written=0",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
