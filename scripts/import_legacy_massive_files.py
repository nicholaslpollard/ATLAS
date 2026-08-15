from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ingestion.legacy_import import LegacyFlatFileImporter
from packages.providers.massive.normalizer import parse_stock_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import existing Massive CSV.gz files into ATLAS provider storage.")
    parser.add_argument("--source", required=True, type=Path, help="Directory recursively containing Massive YYYY-MM-DD.csv.gz files")
    parser.add_argument("--dataset", required=True, help="day|daily|1d or minute|1m")
    parser.add_argument("--start", type=date.fromisoformat, default=None)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    parser.add_argument("--replace-existing", action="store_true", help="Replace an existing ATLAS provider file when content differs.")
    parser.add_argument("--max-files", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(PROJECT_ROOT)
    dataset = parse_stock_dataset(args.dataset)
    result = LegacyFlatFileImporter(settings).import_tree(
        args.source,
        dataset,
        start_date=args.start,
        end_date=args.end,
        replace_existing=args.replace_existing,
        max_files=args.max_files,
    )
    print(f"Legacy Massive import: {dataset.value}")
    print(f"  discovered: {result.discovered_files}")
    print(f"  imported:   {result.imported_files}")
    print(f"  skipped:    {result.skipped_files}")
    print(f"  invalid:    {result.invalid_files}")
    if result.invalid_paths:
        print("Invalid source files:")
        for path in result.invalid_paths[:20]:
            print(f"  - {path}")
    return 2 if result.invalid_files else 0


if __name__ == "__main__":
    raise SystemExit(main())
