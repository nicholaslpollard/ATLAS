from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.data_maintenance.historical_build_service import HistoricalBuildService
from packages.core.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resumably build the ATLAS historical market-data lake.")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--download-missing", action="store_true", help="Use Phase 2 to download provider sessions that are missing.")
    parser.add_argument("--no-materialize", action="store_true", help="Only download/audit; do not run Phase 3 materialization.")
    parser.add_argument("--max-download-files", type=int, default=None)
    parser.add_argument("--max-sessions", type=int, default=None, help="Safety cap on readable exchange sessions processed this run.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on the first materialization error instead of recording it and continuing.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = HistoricalBuildService(load_settings(PROJECT_ROOT)).run(
        args.start,
        args.end,
        download_missing=args.download_missing,
        materialize=not args.no_materialize,
        max_download_files=args.max_download_files,
        max_sessions=args.max_sessions,
        continue_on_error=not args.fail_fast,
    )
    print("ATLAS Historical Build")
    print(f"Requested range:          {result.start_date} -> {result.end_date}")
    if result.effective_start_date is not None and result.effective_end_date is not None:
        print(f"Effective build range:    {result.effective_start_date} -> {result.effective_end_date}")
    print(f"Exchange sessions requested: {result.sessions_requested}")
    print(f"Readable sessions processed: {result.sessions_processed}")
    print(f"Entitlement-skipped sessions:{result.inaccessible_sessions_skipped}")
    print(f"Daily downloads planned:     {result.daily_downloads_planned}")
    print(f"Minute downloads planned:    {result.minute_downloads_planned}")
    print(f"Materialized units:           {result.materialized_sessions}")
    print(f"Skipped current units:        {result.skipped_materializations}")
    print(f"Failures:                     {len(result.failures)}")
    print(f"Elapsed seconds:              {result.elapsed_seconds:.2f}")
    if result.failures:
        print("Failures:")
        for key, message in list(result.failures.items())[:20]:
            print(f"  {key}: {message}")
    return 2 if result.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
