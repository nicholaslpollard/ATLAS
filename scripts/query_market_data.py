from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.enums import SessionSegment, Timeframe
from packages.core.settings import load_settings
from packages.data.duckdb_repository import DuckDBMarketRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Query ATLAS Parquet market history through DuckDB.")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", choices=[tf.value for tf in (Timeframe.MINUTE_1, Timeframe.MINUTE_15, Timeframe.HOUR_1, Timeframe.HOUR_4, Timeframe.DAY_1)], required=True)
    parser.add_argument("--segment", choices=[s.value for s in (SessionSegment.PREMARKET, SessionSegment.REGULAR, SessionSegment.AFTER_HOURS)], default=None)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    settings = load_settings(PROJECT_ROOT)
    repo = DuckDBMarketRepository(settings, persistent=False)
    try:
        rows = repo.query_bars(
            args.symbol,
            Timeframe(args.timeframe),
            session_segment=SessionSegment(args.segment) if args.segment else None,
            limit=args.limit,
        )
    finally:
        repo.close()
    if not rows:
        print("No matching bars found.")
        return 0
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
