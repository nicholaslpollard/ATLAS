from __future__ import annotations

"""Inspect *actual frozen* 09:35 CALL and 10:00 SPY CALL/PUT quote demand.

Default: build the calendar-derived SPY pilot only, provider-free/read-only.
--candidate-plan loads the existing 9,455-query frozen ThetaData candidate
source-plan receipt and composes both independent research branches.
--write-manifest *with* --candidate-plan makes one immutable, non-authorizing
source-demand snapshot. NO V7/V8 reservations, provider calls or backtests.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_frozen_research_demand_v1 import (
    build_frozen_research_demand,
    load_candidate_source_plan,
    write_frozen_demand_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-plan", type=Path,
        help="Exact frozen 9,455-query candidate source-plan path on D:",
    )
    parser.add_argument(
        "--write-manifest", action="store_true",
        help="Opt in to immutable two-branch manifest; no provider requests",
    )
    args = parser.parse_args(argv)
    if args.write_manifest and not args.candidate_plan:
        parser.error("--write-manifest requires an explicit --candidate-plan")
    print("ATLAS EXACT HISTORICAL OPTIONS SOURCE DEMAND V9", flush=True)
    print(
        "  ZERO API calls, reservations, acquisition, simulation, "
        "source scanning or strategy outcomes", flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        candidate = (
            load_candidate_source_plan(settings, args.candidate_plan)
            if args.candidate_plan else None
        )
        report = build_frozen_research_demand(candidate)
        print(
            "  status=" + report["status"] +
            f" native_spy_requests={report['frozen_pilot_quote_queries']}" +
            f" candidate_0935_requests={report['frozen_candidate_quote_queries']}" +
            f" total={report['source_request_count']}", flush=True,
        )
        print(
            f"  origins={report['origin_counts']} "
            f"years={report['year_counts']}", flush=True,
        )
        print(
            f"  0935_anchor_requests={report['frozen_candidate_qualification_anchors']} "
            f"at_time_adapter_ready={report['at_time_provider_adapter_ready']}",
            flush=True,
        )
        for row in report["requests"][:8]:
            print(
                f"  priority={row['priority']} date={row['date_et']} "
                f"symbol={row['symbol']} clock={row['decision_clock_et']} "
                f"right={row['right']} anchor={row['qualification_anchor']} "
                f"state=EXACT_AT_TIME_ADAPTER_UNAVAILABLE "
                f"query_id={row['query_id'][:16]}",
                flush=True,
            )
        print(f"  manifest_fingerprint={report['manifest_fingerprint']}",
              flush=True)
        if args.write_manifest:
            path, new = write_frozen_demand_manifest(settings, report)
            print(
                f"  full_source_manifest={path} "
                f"action={'WRITTEN_IMMUTABLE' if new else 'VERIFIED_REUSED'}",
                flush=True,
            )
        else:
            print("  READ_ONLY no manifest written", flush=True)
        print(
            "  COMPLETE: EXACT_AT_TIME_SOURCE_DEMAND_NOT_HOURLY "
            "provider_requests=0 reservations=0 simulations_run=0 "
            "paid_authority=False", flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"  BLOCKED: {type(exc).__name__}: {exc}", flush=True,
        )
        print(
            "  No provider fallback, reservation or simulation permitted.",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
