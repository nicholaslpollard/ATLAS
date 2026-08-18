from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apps.market_ingestion.live_service import LiveMarketService
from packages.core.enums import LiveConnectionState, LiveFeedMode
from packages.core.settings import load_settings
from packages.live.benchmark import process_peak_rss_bytes
from packages.live.state_store import LiveStateStore

ROOT = Path(__file__).resolve().parents[2]


def test_state_store_records_exact_closed_and_open_transport_gaps():
    settings = load_settings(ROOT, "development")
    store = LiveStateStore(
        settings,
        feed_mode=LiveFeedMode.DELAYED,
        expected_delay_seconds=900,
        subscriptions=("AM.*",),
    )
    start = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)
    end = start + timedelta(seconds=3.25)

    store.record_transport_gap_start(start)
    store.record_transport_gap_start(start + timedelta(seconds=1))
    store.record_transport_gap_end(end)

    snapshot = store.snapshot(end)
    assert snapshot.transport_gap_count == 1
    assert snapshot.transport_gap_total_seconds == 3.25
    assert snapshot.transport_gaps[0].started_at_utc == start
    assert snapshot.transport_gaps[0].ended_at_utc == end
    assert snapshot.open_transport_gap_started_at_utc is None

    next_start = end + timedelta(seconds=10)
    store.record_transport_gap_start(next_start)
    open_snapshot = store.snapshot(next_start + timedelta(seconds=1))
    assert open_snapshot.transport_gap_count == 1
    assert open_snapshot.open_transport_gap_started_at_utc == next_start


def test_live_service_counts_only_post_subscription_degradation_as_transport_gap():
    settings = load_settings(ROOT, "development")

    async def exercise() -> None:
        startup_failure = LiveMarketService(
            settings,
            feed_mode=LiveFeedMode.DELAYED,
            minute_symbols=("AAPL",),
            journal_enabled=False,
        )
        await startup_failure._state_changed(LiveConnectionState.CONNECTING)
        await startup_failure._state_changed(LiveConnectionState.DEGRADED)
        first = startup_failure.state.snapshot()
        assert first.reconnects == 0
        assert first.transport_gap_count == 0
        assert first.open_transport_gap_started_at_utc is None

        service = LiveMarketService(
            settings,
            feed_mode=LiveFeedMode.DELAYED,
            minute_symbols=("AAPL",),
            journal_enabled=False,
        )
        await service._state_changed(LiveConnectionState.CONNECTING)
        await service._state_changed(LiveConnectionState.CONNECTED)
        await service._state_changed(LiveConnectionState.AUTHENTICATED)
        await service._state_changed(LiveConnectionState.SUBSCRIBED)
        await service._state_changed(LiveConnectionState.DEGRADED)

        degraded = service.state.snapshot()
        assert degraded.transport_gap_count == 0
        assert degraded.open_transport_gap_started_at_utc is not None

        await service._state_changed(LiveConnectionState.CONNECTING)
        await service._state_changed(LiveConnectionState.CONNECTED)
        await service._state_changed(LiveConnectionState.AUTHENTICATED)
        await service._state_changed(LiveConnectionState.SUBSCRIBED)

        restored = service.state.snapshot()
        assert restored.reconnects == 1
        assert restored.transport_gap_count == 1
        assert restored.transport_gap_total_seconds >= 0.0
        assert restored.open_transport_gap_started_at_utc is None

    asyncio.run(exercise())


def test_peak_process_rss_telemetry_is_available_on_ci_platforms():
    peak = process_peak_rss_bytes()
    assert peak is not None
    assert peak > 0
