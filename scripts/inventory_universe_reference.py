from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.universe.metadata import UniverseReferenceInventory


def _date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory real Phase 4 reference metadata before Phase 7 eligibility is locked."
    )
    parser.add_argument("--date", required=True, type=_date, dest="as_of_date")
    parser.add_argument("--duplicate-examples", type=int, default=25)
    parser.add_argument("--samples-per-security-type", type=int, default=3)
    return parser


def _print_distribution(name: str, rows: list[dict[str, object]]) -> None:
    print(f"  {name}:")
    for row in rows:
        value = row["value"] if row["value"] is not None else "<NULL>"
        print(f"    {str(value):<18} {int(row['row_count']):>8,}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.duplicate_examples < 0:
        raise ValueError("--duplicate-examples must be >= 0")
    if args.samples_per_security_type < 0:
        raise ValueError("--samples-per-security-type must be >= 0")

    report = UniverseReferenceInventory(load_settings(PROJECT_ROOT)).inspect(
        args.as_of_date,
        duplicate_example_limit=args.duplicate_examples,
        samples_per_security_type=args.samples_per_security_type,
    )

    duplicate = report["duplicate_identity"]
    missing = report["missing"]
    distributions = report["distributions"]

    print("ATLAS Phase 7 Reference Universe Inventory")
    print(f"  as-of date:          {report['as_of_date']}")
    print(f"  reference rows:      {report['row_count']:,}")
    print(f"  stable instruments:  {report['instrument_count']:,}")
    print(f"  repeated ID rows:    {report['repeated_identity_rows']:,}")
    print(f"  inactive rows:       {report['inactive_rows']:,}")
    print(f"  delisted timestamps: {report['rows_with_delisted_timestamp']:,}")
    print("  missing metadata:")
    for key in ("instrument_id", "ticker", "market", "locale", "security_type", "primary_exchange"):
        print(f"    {key:<18} {missing[key]:>8,}")

    print("Duplicate stable-identity audit")
    print(f"  duplicate groups:              {duplicate['groups']:,}")
    print(f"  rows in duplicate groups:      {duplicate['rows']:,}")
    print(f"  multi-ticker groups:           {duplicate['multi_ticker_groups']:,}")
    print(f"  conflicting market groups:     {duplicate['conflicting_market_groups']:,}")
    print(f"  conflicting locale groups:     {duplicate['conflicting_locale_groups']:,}")
    print(f"  conflicting exchange groups:   {duplicate['conflicting_exchange_groups']:,}")
    print(f"  conflicting security groups:   {duplicate['conflicting_security_type_groups']:,}")
    print(f"  conflicting active groups:     {duplicate['conflicting_active_groups']:,}")

    print("Reference value distributions")
    _print_distribution("market", distributions["market"])
    _print_distribution("locale", distributions["locale"])
    _print_distribution("security_type", distributions["security_type"])
    _print_distribution("identity_quality", distributions["identity_quality"])

    examples = duplicate["examples"]
    if examples:
        print("Duplicate identity examples")
        for row in examples:
            print(
                "  "
                f"{row['instrument_id']} rows={row['row_count']} "
                f"tickers={row['tickers']} types={row['security_types']} "
                f"exchanges={row['exchanges']} active={row['active_values']}"
            )

    security_examples = report["security_type_examples"]
    if security_examples:
        print("Security-type examples")
        for row in security_examples:
            security_type = row["security_type"] if row["security_type"] is not None else "<NULL>"
            print(
                "  "
                f"{security_type:<8} {row['ticker']:<12} "
                f"market={row['market']} locale={row['locale']} "
                f"exchange={row['primary_exchange']} active={row['active']} "
                f"name={row['name']}"
            )

    print(f"  source SHA-256:      {report['source_sha256']}")
    print(f"  report:              {Path(str(report['report_path'])).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
