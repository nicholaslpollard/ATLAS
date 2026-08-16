from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.providers.massive.flat_files import MassiveFlatFileProvider
from packages.providers.massive.normalizer import parse_stock_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find the earliest Massive flat-file session readable under the current S3 subscription."
    )
    parser.add_argument("--dataset", required=True, help="minute|1m|day|daily|1d")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(PROJECT_ROOT)
    dataset = parse_stock_dataset(args.dataset)
    provider = MassiveFlatFileProvider(settings)
    first, inaccessible, listed = provider.first_readable_file(dataset, args.start, args.end)

    print(f"ATLAS Massive history-access probe: {dataset.value}")
    print(f"Range: {args.start} -> {args.end}")
    print(f"Remote files listed: {listed}")
    if listed == 0:
        print("No remote files were listed in the requested range.")
        return 2
    if first is None:
        print("No listed session in the requested range is readable under the current S3 subscription.")
        return 2

    files = provider.list_files(dataset, first.trading_date, args.end)
    readable_bytes = sum(item.expected_size_bytes or 0 for item in files)
    print(f"Earliest readable session: {first.trading_date}")
    if inaccessible:
        print(f"Earlier listed but inaccessible: {inaccessible}")
    print(f"Readable listed sessions: {listed - inaccessible}")
    print(f"Readable provider bytes: {readable_bytes / (1024 ** 3):.2f} GiB")
    if inaccessible:
        previous_files = provider.list_files(dataset, args.start, first.trading_date)
        previous = [item for item in previous_files if item.trading_date < first.trading_date]
        if previous:
            boundary = previous[-1]
            print(f"Boundary check previous session: {boundary.trading_date} -> DENIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
