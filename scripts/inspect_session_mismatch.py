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
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show canonical market rows classified outside the configured market session envelope."
    )
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--timeframe", default="1m", choices=("1m",))
    parser.add_argument("--limit", type=int, default=100)
    return parser


def inspect(trading_date: date, *, limit: int = 100) -> list[tuple[object, ...]]:
    settings = load_settings(PROJECT_ROOT)
    path = MarketDataPaths(settings).canonical_file(Timeframe.MINUTE_1, trading_date)
    if not path.exists():
        raise FileNotFoundError(f"Canonical 1m file not found: {path}")

    con = connect_utc(":memory:")
    try:
        return con.execute(
            f"""
            SELECT
                symbol,
                timestamp_utc,
                open,
                high,
                low,
                close,
                volume,
                transaction_count,
                provider,
                source_id
            FROM read_parquet({sql_string(path)})
            WHERE session_segment = 'closed'
            ORDER BY timestamp_utc, symbol
            LIMIT ?
            """,
            [max(1, limit)],
        ).fetchall()
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = inspect(args.date, limit=args.limit)
    print(f"Session-mismatch rows for {args.date}: {len(rows)}")
    if not rows:
        return 0
    print("symbol | timestamp_utc | open | high | low | close | volume | transactions | provider | source_id")
    for row in rows:
        print(" | ".join(str(value) for value in row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
