from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION
from packages.instruments.reference_rekey import ReferenceIdentityRekeyResult, rekey_reference_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Re-key existing ATLAS Massive reference snapshots from local provider facts only; "
            "no provider download is performed."
        )
    )
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--date", type=date.fromisoformat, dest="as_of_date")
    scope.add_argument(
        "--all-local",
        action="store_true",
        help="Re-key every locally persisted Massive reference snapshot in date order.",
    )
    return parser.parse_args()


def _local_snapshot_dates(paths: MarketDataPaths) -> list[date]:
    sample = paths.reference_snapshot_file(date(2000, 1, 1))
    root = sample.parent.parent
    values: list[date] = []
    for directory in root.glob("date=*"):
        if not directory.is_dir() or not (directory / "part-000.parquet").exists():
            continue
        try:
            values.append(date.fromisoformat(directory.name.removeprefix("date=")))
        except ValueError:
            continue
    return sorted(set(values))


def _print_result(result: ReferenceIdentityRekeyResult, *, indent: str = "") -> None:
    print(f"{indent}as-of date:             {result.as_of_date}")
    print(f"{indent}reference rows:         {result.row_count:,}")
    print(f"{indent}old stable instruments: {result.old_instrument_count:,}")
    print(f"{indent}new stable instruments: {result.new_instrument_count:,}")
    print(f"{indent}rows re-keyed:          {result.changed_row_count:,}")
    print(f"{indent}strong ID changes:      {result.strong_id_changes:,}")
    print(f"{indent}collision audit:")
    print(
        f"{indent}  duplicate ID groups: {result.old_duplicate_id_groups:,} -> "
        f"{result.new_duplicate_id_groups:,}"
    )
    print(
        f"{indent}  multi-ticker groups: {result.old_multi_ticker_id_groups:,} -> "
        f"{result.new_multi_ticker_id_groups:,}"
    )
    print(f"{indent}snapshot:               {result.path}")


def main() -> int:
    args = parse_args()
    settings = load_settings(PROJECT_ROOT, "development")
    paths = MarketDataPaths(settings)

    print("ATLAS Reference Identity Repair")
    print(f"  identity contract: {IDENTITY_CONTRACT_VERSION}")
    print("  provider access:   not used")

    if args.all_local:
        dates = _local_snapshot_dates(paths)
        if not dates:
            raise FileNotFoundError("No local Massive reference snapshots were found")
        print(f"  local snapshots:   {len(dates):,}")
        total_changed = 0
        for index, as_of_date in enumerate(dates, start=1):
            print(f"\n  [{index}/{len(dates)}]")
            result = rekey_reference_snapshot(settings, as_of_date)
            total_changed += result.changed_row_count
            _print_result(result, indent="    ")
        print("\nATLAS reference identity repair result")
        print(f"  snapshots repaired: {len(dates):,}")
        print(f"  total rows re-keyed: {total_changed:,}")
        print("  result:              PASS")
        return 0

    result = rekey_reference_snapshot(settings, args.as_of_date)
    _print_result(result, indent="  ")
    print("  result:                 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
