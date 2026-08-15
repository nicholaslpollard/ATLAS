from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.enums import Timeframe
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.data_quality.daily_reconciliation import DailyMinuteReconciler


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare regular-session canonical 1m bars with Massive canonical 1d bars.")
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    paths = MarketDataPaths(load_settings(PROJECT_ROOT))
    minute = paths.canonical_file(Timeframe.MINUTE_1, args.date)
    daily = paths.canonical_file(Timeframe.DAY_1, args.date)
    if not minute.exists() or not daily.exists():
        raise SystemExit("Both canonical 1m and 1d session files are required.")
    summary = DailyMinuteReconciler().compare(minute, daily, args.date)
    print(f"Daily/minute reconciliation: {args.date}")
    print(f"  compared symbols:    {summary.compared_symbols:,}")
    print(f"  exact OHLC matches:  {summary.exact_ohlc_matches:,}")
    print(f"  OHLC mismatches:     {summary.ohlc_mismatches:,}")
    print(f"  volume mismatches:   {summary.volume_mismatches:,}")
    print(f"  minute-only symbols: {summary.minute_only_symbols:,}")
    print(f"  daily-only symbols:  {summary.daily_only_symbols:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
