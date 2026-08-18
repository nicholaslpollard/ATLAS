from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from packages.core.enums import (
    LiveConnectionState,
    LiveFeedMode,
    LiveFreshness,
    SessionSegment,
)
from packages.core.settings import load_settings
from packages.live.state_store import LiveStateStore
from packages.schemas.live_market import LiveMinuteAggregate, LiveQuote

ROOT = Path(__file__).resolve().parents[2]


def _minute(symbol: str, start: datetime, received: datetime, close: float) -> LiveMinuteAggregate:
    return LiveMinuteAggregate(
        symbol=symbol,
        bar_start_utc=start,
        bar_end_utc=start + timedelta(minutes=1),
        session_date=date(2026, 8, 14),
        session_segment=SessionSegment.REGULAR,
        open=100.0,
        high=max(101.0, close),
        low=min(99.0, close),
        close=close,
        volume=1000,
        feed_mode=LiveFeedMode.DELAYED,
        expected_delay_seconds=900,
        received_at_utc=received,
    )


def _quote(symbol: str, timestamp: datetime, sequence: int, bid: float) -> LiveQuote:
    return LiveQuote(
        symbol=symbol,
        provider_timestamp_utc=timestamp,
        session_date=date(2026, 8, 14),
        session_segment=SessionSegment.REGULAR,
        bid_price=bid,
        bid_size=1,
        ask_price=bid + 0.05,
        ask_size=1,
        sequence=sequence,
        feed_mode=LiveFeedMode.DELAYED,
        expected_delay_seconds=900,
        received_at_utc=timestamp + timedelta(minutes=15),
    )


def test_live_state_rejects_out_of_order_events_and_preserves_symbol_case(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    store = LiveStateStore(
        settings,
        feed_mode=LiveFeedMode.DELAYED,
        expected_delay_seconds=900,
        subscriptions=("AM.*", "Q.TpC"),
    )
    store.set_connection_state(LiveConnectionState.SUBSCRIBED)

    start = datetime(2026, 8, 14, 14, 30, tzinfo=UTC)
    assert store.apply(_minute("TpC", start, start + timedelta(minutes=16), 100.5)) is True
    assert store.apply(_minute("TpC", start - timedelta(minutes=1), start + timedelta(minutes=17), 50.0)) is False
    assert store.apply(_minute("TpC", start, start + timedelta(minutes=15), 90.0)) is False

    quote_time = start + timedelta(seconds=10)
    assert store.apply(_quote("TpC", quote_time, 10, 100.4)) is True
    assert store.apply(_quote("TpC", quote_time, 9, 99.0)) is False

    snapshot = store.persist_snapshot(start + timedelta(minutes=16, seconds=30))
    assert snapshot.symbol_count == 1
    assert snapshot.observed_symbol_count == 1
    assert snapshot.restored_symbol_count == 0
    assert snapshot.symbols[0].symbol == "TpC"
    assert snapshot.symbols[0].minute.close == 100.5
    assert snapshot.symbols[0].quote.bid_price == 100.4
    assert snapshot.ignored_out_of_order_events == 3

    path = store.paths.live_state_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["symbols"][0]["symbol"] == "TpC"
    assert payload["connection_state"] == "subscribed"


def test_live_state_restores_values_without_restoring_run_counters(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    start = datetime(2026, 8, 14, 14, 30, tzinfo=UTC)

    first = LiveStateStore(
        settings,
        feed_mode=LiveFeedMode.DELAYED,
        expected_delay_seconds=900,
        subscriptions=("AM.TpC",),
    )
    first.record_received(start + timedelta(minutes=16))
    first.apply(_minute("TpC", start, start + timedelta(minutes=16), 100.5))
    first.persist_snapshot(start + timedelta(minutes=16, seconds=30))

    restored = LiveStateStore(
        settings,
        feed_mode=LiveFeedMode.DELAYED,
        expected_delay_seconds=900,
        subscriptions=("AM.*",),
    )
    snapshot = restored.snapshot(start + timedelta(minutes=16, seconds=45))

    assert restored.restore_warning is None
    assert restored.restored_symbol_count == 1
    assert restored.observed_symbol_count == 0
    assert snapshot.restored_symbol_count == 1
    assert snapshot.observed_symbol_count == 0
    assert snapshot.received_events == 0
    assert snapshot.accepted_events == 0
    assert snapshot.last_received_at_utc is None
    assert snapshot.symbols[0].symbol == "TpC"
    assert snapshot.symbols[0].minute.close == 100.5
    assert snapshot.symbols[0].minute_freshness == LiveFreshness.FRESH

    newer = _minute(
        "TpC",
        start + timedelta(minutes=1),
        start + timedelta(minutes=17),
        101.0,
    )
    assert restored.apply(newer) is True
    after = restored.snapshot(start + timedelta(minutes=17, seconds=30))
    assert after.observed_symbol_count == 1
    assert after.restored_symbol_count == 1
    assert after.accepted_events == 1
