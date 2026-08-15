from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.instruments.registry import InstrumentRegistryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync a point-in-time Massive stock reference snapshot into ATLAS.")
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="Point-in-time snapshot date YYYY-MM-DD")
    parser.add_argument("--active-only", action="store_true", help="Do not request inactive/delisted tickers for the date.")
    parser.add_argument("--force", action="store_true", help="Refresh the snapshot even when it already exists.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(PROJECT_ROOT)
    result = InstrumentRegistryStore(settings).sync_snapshot(
        args.date,
        include_inactive=not args.active_only,
        force=args.force,
    )
    state = "SKIPPED (already current)" if result.skipped else "SYNCED"
    print(f"ATLAS instrument reference {args.date}: {state}")
    print(f"  rows:              {result.row_count:,}")
    print(f"  instruments:       {result.instrument_count:,}")
    print(f"  strong identities: {result.strong_identity_count:,}")
    print(f"  medium identities: {result.medium_identity_count:,}")
    print(f"  fallback identities:{result.fallback_identity_count:,}")
    print(f"  snapshot:          {result.path}")
    print(f"  registry:          {settings.resolved_path(settings.data.paths.derived) / 'reference' / 'instruments' / 'registry.parquet'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
