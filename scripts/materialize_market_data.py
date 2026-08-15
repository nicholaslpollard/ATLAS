from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.data_maintenance.materialization_service import MaterializationService
from packages.core.enums import DatasetType
from packages.core.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize Massive provider files into ATLAS canonical/derived Parquet.")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--dataset", choices=["minute", "day", "both"], default="both")
    parser.add_argument("--force", action="store_true", help="Rebuild even when the source hash is already complete.")
    parser.add_argument("--max-sessions", type=int, default=None, help="Safety cap for development runs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(PROJECT_ROOT)
    datasets = {
        "minute": [DatasetType.STOCK_MINUTE_AGGREGATES],
        "day": [DatasetType.STOCK_DAILY_AGGREGATES],
        "both": [DatasetType.STOCK_DAILY_AGGREGATES, DatasetType.STOCK_MINUTE_AGGREGATES],
    }[args.dataset]
    results = MaterializationService(settings).run_range(
        args.start, args.end, datasets, force=args.force, max_sessions=args.max_sessions
    )
    if not results:
        print("No local provider files matched the requested range/datasets.")
        return 0

    for result in results:
        action = "SKIPPED (already current)" if result.skipped else "MATERIALIZED"
        print(f"{result.trading_date} {result.dataset.value}: {action}")
        print(f"  source rows:    {result.source_rows:,}")
        print(f"  canonical rows: {result.canonical_rows:,}")
        print(f"  quality:        {result.quality_status.value}")
        print(f"  canonical:      {result.canonical_path}")
        if result.quarantined_symbols:
            print(f"  quarantined:    {', '.join(result.quarantined_symbols)}")
        for tf, count in result.derived_rows.items():
            print(f"  derived {tf.value}: {count:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
