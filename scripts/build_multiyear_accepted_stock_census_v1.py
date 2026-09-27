from __future__ import annotations

"""One-time local selected-development census, visible 2021–2026 coverage."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.multiyear_accepted_stock_census_v1 import (
    MultiYearStockSignalError, build_development_census, write_development_census,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build accepted 2021–2025 signals and visible 2026 source gap, offline"
    )
    parser.add_argument("--duckdb-threads", type=int, default=4)
    args = parser.parse_args()
    print("ATLAS 2021–2026 Accepted Multi-Year Stock Signal Census V1", flush=True)
    print("  ZERO provider calls; no historical outcomes/returns projected", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        result = build_development_census(
            settings, duckdb_threads=args.duckdb_threads,
            progress=lambda row: print(
                "  " + " ".join(f"{key}={value}" for key, value in row.items()),
                flush=True,
            ),
        )
        path, action = write_development_census(settings, result)
        print(f"  original accepted selection rows: {result['original_selected_source_count']}", flush=True)
        print(f"  daily LONG full denominator: {result['daily_long_case_denominator']}", flush=True)
        for year, row in result["by_year"].items():
            print(f"  {year}: accepted daily LONG={row['accepted_development_daily_long_signals']} "
                  f"statuses={row['source_statuses']}", flush=True)
        print(f"  lineage: {result['original_source_integrity_fingerprint']}", flush=True)
        print(f"  census fingerprint: {result['census_fingerprint']}", flush=True)
        print(f"  derived evidence: {action} / {path}", flush=True)
        print("  This is a cross-year stock-signal source census, not option "
              "contract selection, completed trade history or a 2026 protected replay.",
              flush=True)
        return 0
    except (MultiYearStockSignalError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"MULTIYEAR STOCK CENSUS STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  Preserve all existing source artifacts; no provider retry.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
