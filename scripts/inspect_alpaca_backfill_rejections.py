from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import duckdb

from packages.core.settings import load_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect Alpaca Gate 3 provider rejections against Gate 2 discovery provenance."
    )
    parser.add_argument("--year", type=int, default=2016)
    parser.add_argument("--batch", type=int, default=0)
    parser.add_argument("--sample", type=int, default=20)
    return parser.parse_args()


def _identifier_shape(symbol: str) -> str:
    if len(symbol) == 9 and symbol.isalnum():
        return "9char_alnum_cusip_like"
    if symbol.isalpha():
        return "alpha_only"
    if symbol.isalnum():
        return "alnum_other"
    return "contains_punctuation"


def main() -> None:
    args = _parse_args()
    if args.sample < 0:
        raise SystemExit("--sample must be non-negative")

    settings = load_settings()
    root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
    manifest_path = root / "acquisition" / "units" / str(args.year) / f"batch_{args.batch:04d}.json"
    inventory_path = root / "inventory" / "candidate_symbols.parquet"

    if not manifest_path.is_file():
        raise SystemExit(f"completed unit manifest not found: {manifest_path}")
    if not inventory_path.is_file():
        raise SystemExit(f"Gate 2 inventory not found: {inventory_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rejected = [
        str(item.get("symbol"))
        for item in manifest.get("provider_rejections") or []
        if isinstance(item, dict) and item.get("symbol")
    ]

    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            "SELECT symbol, discovery_sources, from_active_assets, from_inactive_assets, "
            "from_massive_observed, from_corporate_actions, asset_exchange "
            "FROM read_parquet(?) WHERE symbol IN (SELECT * FROM unnest(?)) ORDER BY symbol",
            [str(inventory_path), rejected],
        ).fetchall()
    finally:
        con.close()

    by_symbol = {
        str(row[0]): {
            "discovery_sources": str(row[1] or ""),
            "active": bool(row[2]),
            "inactive": bool(row[3]),
            "massive": bool(row[4]),
            "corporate_action": bool(row[5]),
            "exchange": str(row[6] or ""),
        }
        for row in rows
    }
    provenance = Counter()
    shapes = Counter()
    missing_inventory = []
    for symbol in rejected:
        record = by_symbol.get(symbol)
        if record is None:
            missing_inventory.append(symbol)
            continue
        provenance[record["discovery_sources"] or "(none)"] += 1
        shapes[_identifier_shape(symbol)] += 1

    print("ATLAS Alpaca Gate 3 Provider-Rejection Provenance Diagnostic")
    print(f"  unit:                        year={args.year} batch={args.batch:04d}")
    print(f"  unit status:                 {manifest.get('status')}")
    print(f"  unit symbols:                {int(manifest.get('symbol_count', 0)):,}")
    print(f"  provider rejected:           {len(rejected):,}")
    print(f"  observed symbols:            {int(manifest.get('observed_symbol_count', 0)):,}")
    print(f"  bar rows:                    {int(manifest.get('bar_rows', 0)):,}")
    print("  rejection provenance:")
    for key, count in sorted(provenance.items()):
        print(f"    {key}: {count:,}")
    print("  identifier-shape diagnostic (shape only; not identity mapping):")
    for key, count in sorted(shapes.items()):
        print(f"    {key}: {count:,}")
    print(f"  rejected symbols missing inventory row: {len(missing_inventory):,}")
    if args.sample:
        print("  sample:")
        for symbol in rejected[: args.sample]:
            record = by_symbol.get(symbol) or {}
            print(
                f"    {symbol}: sources={record.get('discovery_sources', 'MISSING')} "
                f"exchange={record.get('exchange', '') or '-'} shape={_identifier_shape(symbol)}"
            )
    print("  note: CUSIP-like is a lexical diagnostic only; ATLAS does not remap it to a ticker here.")


if __name__ == "__main__":
    main()
