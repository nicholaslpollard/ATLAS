from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from packages.core.enums import (
    LiveConnectionState,
    LiveFeedMode,
    LiveFreshness,
    SessionSegment,
)
from packages.core.settings import load_settings
from packages.core.timestamps import utc_to_epoch_ms
from packages.live.benchmark import build_benchmark_summary
from packages.live.freshness import FreshnessPolicy
from packages.live.session_clock import LiveSessionClock
from packages.providers.massive.websocket import (
    MassiveStockEventParser,
    MassiveStocksWebSocketClient,
    MassiveWebSocketRuntimeStats,
    decode_massive_frame,
)
from packages.schemas.live_market import (
    LiveMinuteAggregate,
    LiveQuote,
    LiveSessionStatus,
    LiveStateSnapshot,
    LiveSymbolState,
)

ROOT = Path(__file__).resolve().parents[2]


def test_massive_live_parser_preserves_provider_case_and_delay():
    settings = load_settings(ROOT, "development")
    parser = MassiveStockEventParser(settings, LiveFeedMode.DELAYED)
    start = datetime(2026, 8, 14, 14, 30, tzinfo=UTC)
    end = start + timedelta(minutes=1)
    received = end + timedelta(minutes=15, seconds=20)

    event = parser.parse(
        {
            "ev": "AM",
            "sym": "TpC",
            "v": 100,
            "dv": "100.5",
            "av": 1000,
            "dav": "1001.25",
            "op": 10.0,
            "vw": 10.15,
            "o": 10.0,
            "c": 10.2,
            "h": 10.3,
            "l": 9.9,
            "a": 10.1,
            "z": 25,
            "s": utc_to_epoch_ms(start),
            "e": utc_to_epoch_ms(end),
        },
        received_at_utc=received,
    )

    assert isinstance(event, LiveMinuteAggregate)
    assert event.symbol == "TpC"
    assert event.volume == 100.5
    assert event.accumulated_volume == 1001.25
    assert event.session_segment == SessionSegment.REGULAR
    assert event.expected_delay_seconds == 900


def test_massive_quote_parser_keeps_sequence_and_exact_symbol_case():
    settings = load_settings(ROOT, "development")
    parser = MassiveStockEventParser(settings, LiveFeedMode.REALTIME)
    timestamp = datetime(2026, 8, 14, 15, 0, tzinfo=UTC)
    event = parser.parse(
        {
            "ev": "Q",
            "sym": "BCpC",
            "bx": 4,
            "bp": 25.10,
            "bs": 2,
            "ax": 7,
            "ap": 25.15,
            "as": 3,
            "c": 0,
            "i": [604],
            "t": utc_to_epoch_ms(timestamp),
            "q": 1234,
            "z": 3,
        },
        received_at_utc=timestamp + timedelta(milliseconds=50),
    )

    assert isinstance(event, LiveQuote)
    assert event.symbol == "BCpC"
    assert event.sequence == 1234
    assert event.indicators == (604,)
    assert event.expected_delay_seconds == 0


def test_delayed_freshness_is_measured_after_expected_delay():
    policy = FreshnessPolicy(fresh_seconds=90, aging_seconds=300)
    event_time = datetime(2026, 8, 14, 15, 0, tzinfo=UTC)
    assert policy.classify(
        event_time,
        event_time + timedelta(minutes=15, seconds=30),
        expected_delay_seconds=900,
    ) == LiveFreshness.FRESH
    assert policy.classify(
        event_time,
        event_time + timedelta(minutes=17),
        expected_delay_seconds=900,
    ) == LiveFreshness.AGING
    assert policy.classify(
        event_time,
        event_time + timedelta(minutes=21),
        expected_delay_seconds=900,
    ) == LiveFreshness.STALE


def test_live_session_clock_knows_weekend_and_next_session():
    settings = load_settings(ROOT, "development")
    status = LiveSessionClock(settings).status(datetime(2026, 8, 16, 15, 0, tzinfo=UTC))
    assert status.is_exchange_session is False
    assert status.session_segment == SessionSegment.CLOSED
    assert status.next_session_date.isoformat() == "2026-08-17"
    assert status.next_regular_open_utc == datetime(2026, 8, 17, 13, 30, tzinfo=UTC)


def test_subscription_topics_are_exact_case_and_client_does_not_retain_secret():
    settings = load_settings(ROOT, "development")
    client = MassiveStocksWebSocketClient(settings, LiveFeedMode.DELAYED)
    assert not hasattr(client, "api_key")
    assert client.api_key_env == settings.massive.credentials.api_key_env
    assert client.subscription_topics(
        minute_symbols=("*",),
        quote_symbols=("TPC", "TpC", "TPC"),
    ) == ("AM.*", "Q.TPC", "Q.TpC")


def test_websocket_runtime_stats_start_empty_with_configured_capacity():
    settings = load_settings(ROOT, "development")
    client = MassiveStocksWebSocketClient(settings, LiveFeedMode.DELAYED)
    stats = client.runtime_stats
    assert stats.frames_received == 0
    assert stats.processed_events == 0
    assert stats.peak_ingress_queue_depth == 0
    assert stats.ingress_queue_capacity == settings.massive.stocks.websocket_ingress_queue_size
    assert stats.peak_queue_utilization == 0.0


def test_live_benchmark_summary_reports_rates_queue_and_delay_adjusted_lag():
    start = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)
    end = start + timedelta(minutes=1)
    received = end + timedelta(minutes=15, seconds=12)
    minute = LiveMinuteAggregate(
        symbol="AAPL",
        bar_start_utc=start,
        bar_end_utc=end,
        session_date=date(2026, 8, 17),
        session_segment=SessionSegment.REGULAR,
        open=100.0,
        high=101.0,
        low=99.5,
        close=100.5,
        volume=1000.0,
        feed_mode=LiveFeedMode.DELAYED,
        expected_delay_seconds=900,
        received_at_utc=received,
    )
    generated = received + timedelta(seconds=5)
    snapshot = LiveStateSnapshot(
        generated_at_utc=generated,
        feed_mode=LiveFeedMode.DELAYED,
        expected_delay_seconds=900,
        connection_state=LiveConnectionState.STOPPED,
        subscriptions=("AM.*",),
        session=LiveSessionStatus(
            as_of_utc=generated,
            local_date=date(2026, 8, 17),
            is_exchange_session=True,
            session_segment=SessionSegment.REGULAR,
            regular_open_utc=datetime(2026, 8, 17, 13, 30, tzinfo=UTC),
            regular_close_utc=datetime(2026, 8, 17, 20, 0, tzinfo=UTC),
        ),
        received_events=100,
        accepted_events=98,
        symbols=(
            LiveSymbolState(
                symbol="AAPL",
                as_of_utc=generated,
                minute=minute,
                minute_freshness=LiveFreshness.FRESH,
            ),
        ),
    )
    stats = MassiveWebSocketRuntimeStats(
        frames_received=10,
        processed_events=100,
        peak_ingress_queue_depth=25,
        ingress_queue_capacity=10_000,
    )

    summary = build_benchmark_summary(
        snapshot,
        stats,
        wall_seconds=10.0,
        process_cpu_seconds=2.5,
        peak_rss_bytes=128 * 1024 * 1024,
        journal_growth_bytes=4096,
    )

    assert summary["received_events_per_second"] == 10.0
    assert summary["accepted_events_per_second"] == 9.8
    assert summary["cpu_one_core_percent"] == 25.0
    assert summary["peak_queue_utilization"] == 0.0025
    assert summary["minute_freshness_counts"]["fresh"] == 1
    assert summary["latest_minute_excess_lag_seconds"]["p50"] == 12.0
    assert summary["baseline_healthy"] is True


def test_decode_massive_frame_accepts_batched_events():
    events = decode_massive_frame('[{"ev":"AM","sym":"AAPL"},{"ev":"Q","sym":"MSFT"}]')
    assert [event["sym"] for event in events] == ["AAPL", "MSFT"]
