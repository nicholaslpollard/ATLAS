from __future__ import annotations

"""Build/reuse six-year visible stock+PIT news source, all local evidence."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.multiyear_stock_news_source_v1 import (
    StockNewsSourceError, build_stock_news_source,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build/reuse accepted 2021–2025 stock/PIT-news features, keep 2026 gap"
    )
    parser.add_argument("--duckdb-threads", type=int, default=4)
    parser.add_argument("--news-threads", type=int, default=4)
    args = parser.parse_args()
    print("ATLAS Six-Year Stock + PIT News Source Preparation / OFFLINE", flush=True)
    print("  Reuses accepted local evidence; ZERO provider requests or protected outcomes.",
          flush=True)
    try:
        settings = load_settings(ROOT, "development")
        census, report, path, status = build_stock_news_source(
            settings, duckdb_threads=args.duckdb_threads,
            news_threads=args.news_threads,
            progress=lambda row: print(
                "  " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True
            ),
        )
        print(f"  {status} / {path}", flush=True)
        print(f"  original stock signal cases: {report['original_stock_signal_denominator']}",
              flush=True)
        print(f"  indexed news articles scanned: {report['news_articles_scanned']}",
              flush=True)
        print(f"  source news cutoff: {report['news_source_cutoff']}", flush=True)
        print(f"  prior 24h positive cases: {report['news_positive_24h_signals']}", flush=True)
        print(f"  prior 7d positive cases: {report['news_positive_7d_signals']}", flush=True)
        print(f"  missing news-source cases: {report['missing_news_source_signals']}",
              flush=True)
        for year, value in report["six_year_coverage"].items():
            print(
                f"  {year}: accepted stock cases={value['original_stock_signal_denominator']} "
                f"news={value['news_statuses']} "
                f"source={value['stock_source_authority']}",
                flush=True,
            )
        print(f"  accepted stock fingerprint: {census['census_fingerprint']}",
              flush=True)
        print(f"  joined source fingerprint: {report['source_join_fingerprint']}",
              flush=True)
        print("  Next independent gate: source-bound native raw stock marks and PIT "
              "option chain/quote selection. This is not a filled backtest.", flush=True)
        return 0
    except (StockNewsSourceError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"SIX-YEAR STOCK/NEWS SOURCE STOPPED: {type(exc).__name__}: {exc}",
              flush=True)
        print("  No provider retry; preserve accepted original files.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
