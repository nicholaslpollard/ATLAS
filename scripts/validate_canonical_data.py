from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.enums import DatasetType, Timeframe
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.data_quality.bar_validator import ParquetBarValidator


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an ATLAS canonical market-data session.")
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--timeframe", choices=["1m", "1d"], required=True)
    args = parser.parse_args()
    settings = load_settings(PROJECT_ROOT)
    tf = Timeframe.MINUTE_1 if args.timeframe == "1m" else Timeframe.DAY_1
    dataset = DatasetType.STOCK_MINUTE_AGGREGATES if tf == Timeframe.MINUTE_1 else DatasetType.STOCK_DAILY_AGGREGATES
    path = MarketDataPaths(settings).canonical_file(tf, args.date)
    report = ParquetBarValidator(dataset=dataset, trading_date=args.date).validate(path)
    print(report.model_dump_json(indent=2))
    return 0 if report.status.value != "invalid" else 2


if __name__ == "__main__":
    raise SystemExit(main())
