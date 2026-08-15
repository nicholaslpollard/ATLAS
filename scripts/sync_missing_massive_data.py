from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.market_ingestion.flat_file_service import FlatFileIngestionService
from packages.core.settings import load_settings
from packages.providers.massive.normalizer import parse_stock_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Incrementally synchronize Massive stock aggregate Flat Files.")
    parser.add_argument("--dataset", required=True, help="minute|1m|day|daily|1d")
    parser.add_argument("--start", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Build and print the plan without downloading.")
    parser.add_argument("--max-files", type=int, default=None, help="Safety cap on files downloaded in this run.")
    parser.add_argument("--verify-existing-hashes", action="store_true", help="Re-hash already-complete files while planning.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(PROJECT_ROOT)
    dataset = parse_stock_dataset(args.dataset)
    service = FlatFileIngestionService(settings)
    plan = service.plan(dataset, args.start, args.end, verify_existing_hashes=args.verify_existing_hashes)

    print(f"ATLAS Massive sync plan: {dataset.value}")
    print(f"Range: {args.start} -> {args.end}")
    print(f"Exchange sessions expected: {len(plan.expected_sessions)}")
    print(f"Remote files available: {len(plan.available_remote_sessions)}")
    print(f"Already complete: {plan.already_complete}")
    print(f"Planned downloads: {plan.planned_count}")
    if plan.unavailable_remote_sessions:
        print("Provider files not yet available for sessions:")
        for session in plan.unavailable_remote_sessions:
            print(f"  - {session}")

    for item in plan.items[:20]:
        print(f"  {item.descriptor.trading_date}  {item.descriptor.remote_key}  ->  {item.local_path}")
    if len(plan.items) > 20:
        print(f"  ... {len(plan.items) - 20} more")

    if args.dry_run or not plan.items:
        return 0

    service.sync(
        dataset,
        args.start,
        args.end,
        max_files=args.max_files,
        verify_existing_hashes=args.verify_existing_hashes,
    )
    print("Sync complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
