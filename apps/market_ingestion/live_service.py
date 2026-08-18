from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from packages.core.enums import LiveConnectionState, LiveFeedMode
from packages.core.settings import AtlasSettings
from packages.live.journal import LiveEventJournal
from packages.live.state_store import LiveStateStore
from packages.providers.massive.websocket import (
    MassiveStockEventParser,
    MassiveStocksWebSocketClient,
)
from packages.schemas.live_market import LiveStateSnapshot


class LiveMarketService:
    """Run Massive streaming ingestion into provisional ATLAS live state."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        feed_mode: LiveFeedMode | None = None,
        minute_symbols: tuple[str, ...] = ("*",),
        quote_symbols: tuple[str, ...] = (),
        journal_enabled: bool = True,
    ) -> None:
        self.settings = settings
        self.client = MassiveStocksWebSocketClient(settings, feed_mode=feed_mode)
        self.parser = MassiveStockEventParser(settings, self.client.feed_mode)
        self.subscriptions = self.client.subscription_topics(
            minute_symbols=minute_symbols,
            quote_symbols=quote_symbols,
        )
        self.state = LiveStateStore(
            settings,
            feed_mode=self.client.feed_mode,
            expected_delay_seconds=self.client.expected_delay_seconds,
            subscriptions=self.subscriptions,
        )
        self.journal = LiveEventJournal(settings) if journal_enabled else None
        self._stop_event = asyncio.Event()
        self._fatal_error: Exception | None = None
        self._has_connected_once = False
        self._has_subscribed_once = False

    async def _state_changed(self, state: LiveConnectionState) -> None:
        now = datetime.now(UTC)
        if state == LiveConnectionState.CONNECTING:
            if self._has_connected_once:
                self.state.record_reconnect()
            self._has_connected_once = True
        elif state == LiveConnectionState.DEGRADED:
            # Only a socket that had already reached SUBSCRIBED can create a
            # market-data transport gap. Initial auth/entitlement failure is a
            # startup failure, not a reconnect gap.
            if self._has_subscribed_once:
                self.state.record_transport_gap_start(now)
        elif state == LiveConnectionState.SUBSCRIBED:
            if self._has_subscribed_once:
                self.state.record_transport_gap_end(now)
            self._has_subscribed_once = True
        self.state.set_connection_state(state)

    async def _handle_event(self, raw_event: dict[str, object], received_at_utc: datetime) -> None:
        self.state.record_received(received_at_utc)
        try:
            event = self.parser.parse(raw_event, received_at_utc=received_at_utc)
        except Exception as exc:
            self.state.record_parse_error()
            self._fatal_error = exc
            self.state.set_connection_state(LiveConnectionState.DEGRADED)
            self._stop_event.set()
            raise
        if event is None:
            return
        if self.journal is not None:
            self.journal.append(
                raw_event,
                session_date=event.session_date,
                received_at_utc=received_at_utc,
                feed_mode=self.client.feed_mode,
            )
        self.state.apply(event)

    async def _snapshot_loop(self) -> None:
        interval = self.settings.massive.stocks.live_state_snapshot_interval_seconds
        while not self._stop_event.is_set():
            self.state.persist_snapshot(datetime.now(UTC))
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except TimeoutError:
                pass

    async def _stop_after(self, seconds: float) -> None:
        if seconds <= 0:
            self._stop_event.set()
            return
        await asyncio.sleep(seconds)
        self._stop_event.set()

    def request_stop(self) -> None:
        self._stop_event.set()

    async def run(
        self,
        *,
        max_events: int | None = None,
        max_seconds: float | None = None,
    ) -> LiveStateSnapshot:
        if not self.subscriptions:
            raise ValueError("Live market service has no subscriptions")

        snapshot_task = asyncio.create_task(self._snapshot_loop(), name="atlas-live-snapshot")
        timer_task = (
            asyncio.create_task(self._stop_after(max_seconds), name="atlas-live-timer")
            if max_seconds is not None
            else None
        )
        try:
            await self.client.consume(
                self.subscriptions,
                self._handle_event,
                stop_event=self._stop_event,
                state_handler=self._state_changed,
                max_events=max_events,
            )
        finally:
            self._stop_event.set()
            snapshot_task.cancel()
            try:
                await snapshot_task
            except asyncio.CancelledError:
                pass
            if timer_task is not None:
                timer_task.cancel()
                try:
                    await timer_task
                except asyncio.CancelledError:
                    pass
            if self.journal is not None:
                self.journal.close()
            self.state.set_connection_state(
                LiveConnectionState.DEGRADED if self._fatal_error is not None else LiveConnectionState.STOPPED
            )
            final_snapshot = self.state.persist_snapshot(datetime.now(UTC))

        if self._fatal_error is not None:
            raise RuntimeError(
                f"Live market payload violated the ATLAS contract: {type(self._fatal_error).__name__}: "
                f"{self._fatal_error}"
            ) from self._fatal_error
        return final_snapshot
