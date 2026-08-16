from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.instruments.ticker_events import TickerEventStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync Massive ticker-change events for one exact point-in-time ATLAS ticker."
    )
    parser.add_argument("--ticker", required=True, help="Exact provider-native ticker from the reference snapshot.")
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="Reference snapshot date (YYYY-MM-DD).")
    parser.add_argument("--force", action="store_true", help="Refetch even when the current event contract is already stored.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = TickerEventStore(load_settings(PROJECT_ROOT))
    result = store.sync_for_ticker(args.ticker, args.date, force=args.force)
    status = "SKIPPED" if result.skipped else "SYNCED"
    print(f"ATLAS ticker events {args.ticker} @ {args.date}: {status}")
    print(f"  instrument_id:         {result.instrument_id}")
    print(f"  provider query:        {result.query_identifier_type}={result.query_identifier}")
    print(f"  continuity authority: {str(result.continuity_authority).lower()}")
    print(f"  ticker-change events:  {result.event_count}")
    print(f"  canonical:             {Path(result.path).resolve()}")
    print("  timeline:")
    timeline = store.timeline_for_ticker(args.ticker, args.date)
    if not timeline:
        print("    (no provider-reported ticker-change events)")
    else:
        for item in timeline:
            print(
                f"    {item['event_date']}  {item['ticker']}  "
                f"[{item['query_identifier_type']}; authority={str(item['continuity_authority']).lower()}]"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
