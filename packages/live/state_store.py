from __future__ import annotations

import json
from datetime import UTC, datetime
from threading import RLock

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import LiveConnectionState, LiveFeedMode
from packages.core.settings import AtlasSettings
from packages.core.timestamps import to_utc
from packages.data.paths import MarketDataPaths
from packages.schemas.live_market import (
    LiveMinuteAggregate,
    LiveQuote,
    LiveStateSnapshot,
    LiveSymbolState,
)

from .freshness import FreshnessPolicy
from .session_clock import LiveSessionClock


class LiveStateStore:
    """Thread-safe latest-value state for discovery, monitoring, and the future API.

    Only the latest minute bar and latest quote per symbol are retained in memory.
    Full provisional event history belongs in the append-only live journal, not in
    this cache.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        feed_mode: LiveFeedMode,
        expected_delay_seconds: int,
        subscriptions: tuple[str, ...] = (),
    ) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.feed_mode = feed_mode
        self.expected_delay_seconds = expected_delay_seconds
        self.subscriptions = tuple(subscriptions)
        cfg = settings.massive.stocks
        self.freshness = FreshnessPolicy(
            fresh_seconds=cfg.freshness_fresh_seconds,
            aging_seconds=cfg.freshness_aging_seconds,
        )
        self.clock = LiveSessionClock(settings)
        self._lock = RLock()
        self._minutes: dict[str, LiveMinuteAggregate] = {}
        self._quotes: dict[str, LiveQuote] = {}
        self._connection_state = LiveConnectionState.DISCONNECTED
        self._received_events = 0
        self._accepted_events = 0
        self._ignored_out_of_order_events = 0
        self._parse_errors = 0
        self._reconnects = 0
        self._last_received_at_utc: datetime | None = None

    def set_connection_state(self, state: LiveConnectionState) -> None:
        with self._lock:
            self._connection_state = state

    def record_reconnect(self) -> None:
        with self._lock:
            self._reconnects += 1

    def record_received(self, received_at_utc: datetime) -> None:
        received = to_utc(received_at_utc)
        with self._lock:
            self._received_events += 1
            if self._last_received_at_utc is None or received > self._last_received_at_utc:
                self._last_received_at_utc = received

    def record_parse_error(self) -> None:
        with self._lock:
            self._parse_errors += 1

    def apply_minute(self, event: LiveMinuteAggregate) -> bool:
        with self._lock:
            current = self._minutes.get(event.symbol)
            if current is not None:
                if event.bar_start_utc < current.bar_start_utc:
                    self._ignored_out_of_order_events += 1
                    return False
                if (
                    event.bar_start_utc == current.bar_start_utc
                    and event.received_at_utc <= current.received_at_utc
                ):
                    self._ignored_out_of_order_events += 1
                    return False
            self._minutes[event.symbol] = event
            self._accepted_events += 1
            return True

    def apply_quote(self, event: LiveQuote) -> bool:
        with self._lock:
            current = self._quotes.get(event.symbol)
            if current is not None:
                current_key = (current.provider_timestamp_utc, current.sequence)
                event_key = (event.provider_timestamp_utc, event.sequence)
                if event_key <= current_key:
                    self._ignored_out_of_order_events += 1
                    return False
            self._quotes[event.symbol] = event
            self._accepted_events += 1
            return True

    def apply(self, event: LiveMinuteAggregate | LiveQuote) -> bool:
        if isinstance(event, LiveMinuteAggregate):
            return self.apply_minute(event)
        if isinstance(event, LiveQuote):
            return self.apply_quote(event)
        raise TypeError(f"Unsupported live event type: {type(event).__name__}")

    def snapshot(self, as_of_utc: datetime | None = None) -> LiveStateSnapshot:
        now = to_utc(as_of_utc or datetime.now(UTC))
        with self._lock:
            symbols = sorted(set(self._minutes) | set(self._quotes))
            symbol_states: list[LiveSymbolState] = []
            for symbol in symbols:
                minute = self._minutes.get(symbol)
                quote = self._quotes.get(symbol)
                symbol_states.append(
                    LiveSymbolState(
                        symbol=symbol,
                        as_of_utc=now,
                        minute=minute,
                        minute_freshness=self.freshness.classify(
                            minute.bar_end_utc if minute else None,
                            now,
                            expected_delay_seconds=minute.expected_delay_seconds if minute else self.expected_delay_seconds,
                        ),
                        quote=quote,
                        quote_freshness=self.freshness.classify(
                            quote.provider_timestamp_utc if quote else None,
                            now,
                            expected_delay_seconds=quote.expected_delay_seconds if quote else self.expected_delay_seconds,
                        ),
                    )
                )
            return LiveStateSnapshot(
                generated_at_utc=now,
                feed_mode=self.feed_mode,
                expected_delay_seconds=self.expected_delay_seconds,
                connection_state=self._connection_state,
                subscriptions=self.subscriptions,
                session=self.clock.status(now),
                received_events=self._received_events,
                accepted_events=self._accepted_events,
                ignored_out_of_order_events=self._ignored_out_of_order_events,
                parse_errors=self._parse_errors,
                reconnects=self._reconnects,
                last_received_at_utc=self._last_received_at_utc,
                symbols=tuple(symbol_states),
            )

    def persist_snapshot(self, as_of_utc: datetime | None = None) -> LiveStateSnapshot:
        snapshot = self.snapshot(as_of_utc)
        atomic_write_text(
            self.paths.live_state_file(),
            json.dumps(snapshot.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        )
        return snapshot
