from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION
from packages.instruments.reference_rekey import rekey_reference_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-key an existing ATLAS Massive reference snapshot without downloading provider data."
    )
    parser.add_argument("--date", required=True, type=date.fromisoformat, dest="as_of_date")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings(PROJECT_ROOT, "development")
    result = rekey_reference_snapshot(settings, args.as_of_date)

    print("ATLAS Reference Identity Repair")
    print(f"  as-of date:             {result.as_of_date}")
    print(f"  identity contract:      {IDENTITY_CONTRACT_VERSION}")
    print(f"  reference rows:         {result.row_count:,}")
    print(f"  old stable instruments: {result.old_instrument_count:,}")
    print(f"  new stable instruments: {result.new_instrument_count:,}")
    print(f"  rows re-keyed:          {result.changed_row_count:,}")
    print(f"  strong ID changes:      {result.strong_id_changes:,}")
    print("  collision audit:")
    print(
        f"    duplicate ID groups:  {result.old_duplicate_id_groups:,} -> "
        f"{result.new_duplicate_id_groups:,}"
    )
    print(
        f"    multi-ticker groups:  {result.old_multi_ticker_id_groups:,} -> "
        f"{result.new_multi_ticker_id_groups:,}"
    )
    print(f"  snapshot:               {result.path}")
    print("  result:                 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
