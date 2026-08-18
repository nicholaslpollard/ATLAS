from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.market_ingestion.live_service import LiveMarketService
from packages.core.enums import LiveFeedMode
from packages.core.settings import load_settings


def _symbols(value: str) -> tuple[str, ...]:
    return tuple(symbol.strip() for symbol in value.split(",") if symbol.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ATLAS provisional live stock market state.")
    parser.add_argument(
        "--feed",
        choices=[mode.value for mode in LiveFeedMode],
        default=LiveFeedMode.DELAYED.value,
    )
    parser.add_argument(
        "--minute-symbols",
        default="*",
        help="Comma-separated provider-native tickers or * for all minute aggregates.",
    )
    parser.add_argument(
        "--quote-symbols",
        default="",
        help="Comma-separated focused quote tickers. Empty by default; broad Q.* is not recommended.",
    )
    parser.add_argument("--max-events", type=int, default=None)
    parser.add_argument("--max-seconds", type=float, default=None)
    parser.add_argument("--no-journal", action="store_true")
    return parser


async def _run(args: argparse.Namespace) -> int:
    service = LiveMarketService(
        load_settings(PROJECT_ROOT),
        feed_mode=LiveFeedMode(args.feed),
        minute_symbols=_symbols(args.minute_symbols),
        quote_symbols=_symbols(args.quote_symbols),
        journal_enabled=not args.no_journal,
    )
    print("ATLAS Live Market State")
    print(f"  feed:           {service.client.feed_mode.value}")
    print(f"  expected delay: {service.client.expected_delay_seconds}s")
    print(f"  subscriptions:  {', '.join(service.subscriptions)}")
    print(f"  restored symbols:{service.state.restored_symbol_count}")
    if service.state.restore_warning:
        print(f"  restore warning: {service.state.restore_warning}")
    snapshot = await service.run(max_events=args.max_events, max_seconds=args.max_seconds)
    print("ATLAS Live Market State stopped")
    print(f"  connection state: {snapshot.connection_state.value}")
    print(f"  received events:  {snapshot.received_events}")
    print(f"  accepted events:  {snapshot.accepted_events}")
    print(f"  observed symbols: {snapshot.observed_symbol_count}")
    print(f"  restored symbols: {snapshot.restored_symbol_count}")
    print(f"  ignored old:      {snapshot.ignored_out_of_order_events}")
    print(f"  parse errors:     {snapshot.parse_errors}")
    print(f"  reconnects:       {snapshot.reconnects}")
    print(f"  symbols in state: {snapshot.symbol_count}")
    print(f"  session segment:  {snapshot.session.session_segment.value}")
    print(f"  snapshot:         {service.state.paths.live_state_file().resolve()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
