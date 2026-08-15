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
    files = provider.list_files(dataset, args.start, args.end)

    print(f"ATLAS Massive history-access probe: {dataset.value}")
    print(f"Range: {args.start} -> {args.end}")
    print(f"Remote files listed: {len(files)}")
    if not files:
        print("No remote files were listed in the requested range.")
        return 2

    if not provider.client.can_read_object(files[-1].remote_key):
        print(f"Newest listed session is not readable: {files[-1].trading_date}")
        print("The current S3 credentials do not have read access to this dataset/range.")
        return 2

    if provider.client.can_read_object(files[0].remote_key):
        first_index = 0
    else:
        low = 0
        high = len(files) - 1
        while low < high:
            mid = (low + high) // 2
            if provider.client.can_read_object(files[mid].remote_key):
                high = mid
            else:
                low = mid + 1
        first_index = low

    first = files[first_index]
    inaccessible = first_index
    readable = len(files) - first_index
    readable_bytes = sum(item.expected_size_bytes or 0 for item in files[first_index:])

    print(f"Earliest readable session: {first.trading_date}")
    print(f"Earlier listed but inaccessible: {inaccessible}")
    print(f"Readable listed sessions: {readable}")
    print(f"Readable provider bytes: {readable_bytes / (1024 ** 3):.2f} GiB")
    if first_index > 0:
        previous = files[first_index - 1]
        previous_readable = provider.client.can_read_object(previous.remote_key)
        print(f"Boundary check previous session: {previous.trading_date} -> {'READABLE' if previous_readable else 'DENIED'}")
        if previous_readable:
            print("WARNING: access is not monotonic at the detected boundary; do not use this result as an automatic cutoff.")
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
