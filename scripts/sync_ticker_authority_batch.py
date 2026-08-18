from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.ticker_authority_batch import (
    TICKER_AUTHORITY_BATCH_DEFAULT_LIMIT,
    TICKER_AUTHORITY_BATCH_MAX_ERRORS,
    TickerAuthorityBatch,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sequentially enrich a bounded Gate 9 ticker-identity batch using "
            "Composite-FIGI Massive ticker events."
        )
    )
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument(
        "--limit",
        type=int,
        default=TICKER_AUTHORITY_BATCH_DEFAULT_LIMIT,
        help=f"Maximum new provider candidates to attempt (default {TICKER_AUTHORITY_BATCH_DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=TICKER_AUTHORITY_BATCH_MAX_ERRORS,
        help=f"Stop after this many provider errors (default {TICKER_AUTHORITY_BATCH_MAX_ERRORS}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = TickerAuthorityBatch(load_settings(PROJECT_ROOT, "development")).run(
        args.as_of,
        limit=args.limit,
        max_errors=args.max_errors,
    )

    print("ATLAS Phase 9 Ticker Authority Batch")
    print(f"  contract:                         {report.contract_version}")
    print(f"  as-of session:                    {report.as_of_date}")
    print(f"  requested batch limit:            {report.requested_limit:,}")
    print(f"  provider candidates before:       {report.candidate_count_before:,}")
    print(f"  attempted:                        {report.attempted_count:,}")
    print(f"  synced:                           {report.synced_count:,}")
    print(f"  skipped/cached:                   {report.skipped_count:,}")
    print(f"  provider errors:                  {report.provider_error_count:,}")
    print(f"  authoritative results:            {report.authoritative_result_count:,}")
    print(f"  ticker-change events returned:    {report.event_count_total:,}")
    print(f"  instruments with events:          {report.with_events_count:,}")
    print(f"  instruments with zero events:     {report.zero_events_count:,}")
    print("  authority resolution:")
    print(f"    resolved intervals before       {report.resolved_interval_count_before:,}")
    print(f"    resolved intervals after        {report.resolved_interval_count_after:,}")
    print(f"    resolution gain                 {report.resolution_gain:+,}")
    print(f"    unresolved + Composite FIGI     {report.unresolved_with_composite_figi_after:,}")
    print(f"    new sync candidates remaining   {report.provider_sync_candidates_after:,}")
    print(f"  stopped on error budget:          {str(report.stopped_on_error_budget).upper()}")
    print("  outcomes:")
    for item in report.outcomes:
        if item["status"] == "PROVIDER_ERROR":
            print(
                f"    {item['ticker']:<12} PROVIDER_ERROR  "
                f"figi={item['composite_figi']}  {item['error']}"
            )
        else:
            print(
                f"    {item['ticker']:<12} {item['status']:<8} "
                f"authority={str(item['continuity_authority']).lower():<5} "
                f"events={item['event_count']} figi={item['composite_figi']}"
            )
    print(f"  wall time:                        {report.wall_seconds:.3f}s")
    print(f"  report:                           {Path(report.report_path).resolve()}")
    print("  result:                           BATCH COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
