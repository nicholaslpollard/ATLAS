from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from packages.core.enums import LiveFeedMode, LiveFreshness, SessionSegment
from packages.core.settings import load_settings
from packages.core.timestamps import utc_to_epoch_ms
from packages.live.freshness import FreshnessPolicy
from packages.live.session_clock import LiveSessionClock
from packages.providers.massive.websocket import (
    MassiveStockEventParser,
    MassiveStocksWebSocketClient,
    decode_massive_frame,
)
from packages.schemas.live_market import LiveMinuteAggregate, LiveQuote

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


def test_decode_massive_frame_accepts_batched_events():
    events = decode_massive_frame('[{"ev":"AM","sym":"AAPL"},{"ev":"Q","sym":"MSFT"}]')
    assert [event["sym"] for event in events] == ["AAPL", "MSFT"]
