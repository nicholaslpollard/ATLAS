from __future__ import annotations

"""Prepare/reuse accepted native RAW stock entry prices for all eligible years."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.multiyear_native_stock_open_v1 import (
    MultiYearRawStockError, build_multiyear_native_raw_open_source,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-time offline source-verified native raw stock opens, 2021..2025"
    )
    parser.add_argument("--duckdb-threads", type=int, default=4)
    parser.add_argument("--news-threads", type=int, default=4)
    args = parser.parse_args()
    print("ATLAS Multi-Year Original Native Raw Stock OPEN / OFFLINE", flush=True)
    print("  Reuse original stock/news; verify C: raw V2 native OHLC; write derived evidence D:.",
          flush=True)
    print("  No provider requests. No protected 2026 native reads. OPEN != 09:35 fill.",
          flush=True)
    try:
        settings = load_settings(ROOT, "development")
        report, path, status = build_multiyear_native_raw_open_source(
            settings, duckdb_threads=args.duckdb_threads,
            news_threads=args.news_threads,
            progress=lambda item: print(
                "  " + " ".join(f"{k}={v}" for k, v in item.items()), flush=True,
            ),
        )
        print(f"  result: {status} / {path}", flush=True)
        print(f"  original signal denominator: {report['case_denominator']}", flush=True)
        print(f"  exact native raw opens: {report['verified_native_raw_open_cases']}",
              flush=True)
        print(f"  deferred 2026 entry sources: {report['deferred_2026_entry_cases']}",
              flush=True)
        print(f"  verified original native raw units: {report['native_units_verified']}",
              flush=True)
        for year, statuses in report["by_year"].items():
            print(f"  {year}: {statuses}", flush=True)
        print(f"  source fingerprint: {report['source_fingerprint']}", flush=True)
        print("  Original price and news inputs ready for bounded PIT option-chain planning; "
              "no EOD option quote, fill or backtest result implied.", flush=True)
        return 0
    except (MultiYearRawStockError, OSError, ValueError, TypeError, KeyError,
            RuntimeError) as exc:
        print(f"ORIGINAL RAW STOCK OPEN STOPPED: {type(exc).__name__}: {exc}",
              flush=True)
        print("  No provider retry; preserve all C:/D: accepted original evidence.",
              flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
