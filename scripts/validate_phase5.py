from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import websockets

from packages.core.enums import LiveFeedMode, SessionSegment
from packages.core.settings import load_settings
from packages.core.timestamps import utc_to_epoch_ms
from packages.data.paths import MarketDataPaths
from packages.providers.massive.websocket import MassiveStockEventParser
from packages.schemas.live_market import LiveMinuteAggregate


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    cfg = settings.massive.stocks
    paths = MarketDataPaths(settings)

    if not settings.massive.provider.websocket_delayed_url.startswith("wss://"):
        raise RuntimeError("Massive delayed WebSocket endpoint must use wss://")
    if not settings.massive.provider.websocket_realtime_url.startswith("wss://"):
        raise RuntimeError("Massive realtime WebSocket endpoint must use wss://")
    if cfg.websocket_ingress_queue_size < 100:
        raise RuntimeError("Massive WebSocket ingress queue is unreasonably small")
    if cfg.freshness_aging_seconds < cfg.freshness_fresh_seconds:
        raise RuntimeError("Live freshness aging threshold must be >= fresh threshold")
    if cfg.delayed_feed_expected_delay_seconds != 900:
        raise RuntimeError("Initial Massive delayed feed contract must explicitly model 15 minutes")

    start = datetime(2026, 8, 14, 14, 30, tzinfo=UTC)
    parser = MassiveStockEventParser(settings, LiveFeedMode.DELAYED)
    event = parser.parse(
        {
            "ev": cfg.websocket_minute_channel,
            "sym": "TpC",
            "o": 10.0,
            "h": 10.2,
            "l": 9.9,
            "c": 10.1,
            "v": 100,
            "s": utc_to_epoch_ms(start),
            "e": utc_to_epoch_ms(start + timedelta(minutes=1)),
        },
        received_at_utc=start + timedelta(minutes=16),
    )
    if not isinstance(event, LiveMinuteAggregate):
        raise RuntimeError("Massive AM parser smoke test did not return a live minute aggregate")
    if event.symbol != "TpC":
        raise RuntimeError("Phase 5 parser violated provider-native ticker case")
    if event.session_segment != SessionSegment.REGULAR:
        raise RuntimeError("Phase 5 parser failed XNYS session classification smoke test")

    live_root = settings.resolved_path(settings.data.paths.live)
    if live_root not in paths.live_state_file().parents:
        raise RuntimeError("Live state path escaped configured data/live root")

    print(f"websockets: {websockets.__version__}")
    print(f"Delayed WebSocket: {settings.massive.provider.websocket_delayed_url}")
    print(f"Realtime WebSocket: {settings.massive.provider.websocket_realtime_url}")
    print(f"Broad minute channel: {cfg.websocket_minute_channel}.*")
    print(f"Focused quote channel: {cfg.websocket_quote_channel}.<ticker>")
    print(f"Delayed feed expected delay: {cfg.delayed_feed_expected_delay_seconds}s")
    print(f"Ingress queue capacity: {cfg.websocket_ingress_queue_size:,}")
    print(f"Live state root: {live_root}")
    print("Provider-native ticker case: PASS")
    print("Delay-aware live contract: PASS")
    print("Phase 05 validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
