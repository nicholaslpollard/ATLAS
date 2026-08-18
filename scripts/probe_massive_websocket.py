from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.enums import LiveFeedMode
from packages.core.settings import load_settings
from packages.providers.massive.websocket import MassiveStocksWebSocketClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Connect and authenticate to the configured Massive stock WebSocket without subscribing."
    )
    parser.add_argument(
        "--feed",
        choices=[mode.value for mode in LiveFeedMode],
        default=LiveFeedMode.DELAYED.value,
        help="Massive stock cluster to probe.",
    )
    return parser


async def _run(feed: LiveFeedMode) -> int:
    client = MassiveStocksWebSocketClient(load_settings(PROJECT_ROOT), feed_mode=feed)
    result = await client.probe()
    print("ATLAS Massive stock WebSocket probe")
    print(f"  feed mode:       {result.feed_mode.value}")
    print(f"  endpoint:        {result.endpoint}")
    print(f"  connected:       {str(result.connected).lower()}")
    print(f"  authenticated:   {str(result.authenticated).lower()}")
    print(f"  server connect:  {result.connected_message or '(no message)'}")
    print(f"  server auth:     {result.auth_message or '(no message)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(_run(LiveFeedMode(args.feed)))


if __name__ == "__main__":
    raise SystemExit(main())
