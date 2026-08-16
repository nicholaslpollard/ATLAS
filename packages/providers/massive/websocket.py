from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime, time
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from packages.core.enums import LiveConnectionState, LiveFeedMode
from packages.core.exceptions import ProviderError
from packages.core.market_calendar import MarketCalendar
from packages.core.secrets import get_secret
from packages.core.settings import AtlasSettings
from packages.core.timestamps import epoch_ms_to_utc, market_local_date
from packages.schemas.live_market import LiveMinuteAggregate, LiveQuote


class MassiveWebSocketError(ProviderError):
    """Base error for Massive streaming operations."""


class MassiveWebSocketAuthenticationError(MassiveWebSocketError):
    """Authentication or plan entitlement rejected the stock stream."""


class MassiveWebSocketBackpressureError(MassiveWebSocketError):
    """ATLAS could not drain WebSocket frames fast enough without dropping data."""


@dataclass(frozen=True, slots=True)
class MassiveWebSocketProbeResult:
    endpoint: str
    feed_mode: LiveFeedMode
    connected: bool
    authenticated: bool
    connected_message: str | None = None
    auth_message: str | None = None


def decode_massive_frame(message: str | bytes) -> list[dict[str, object]]:
    if isinstance(message, bytes):
        message = message.decode("utf-8")
    try:
        payload = json.loads(message)
    except json.JSONDecodeError as exc:
        raise MassiveWebSocketError("Massive WebSocket returned invalid JSON") from exc
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise MassiveWebSocketError("Massive WebSocket payload must be a JSON object or array")
    events: list[dict[str, object]] = []
    for item in payload:
        if isinstance(item, dict):
            events.append(item)
    return events


class MassiveStockEventParser:
    """Normalize supported Massive stock stream events into ATLAS live contracts."""

    def __init__(self, settings: AtlasSettings, feed_mode: LiveFeedMode) -> None:
        self.settings = settings
        self.feed_mode = feed_mode
        cfg = settings.massive.stocks
        self.expected_delay_seconds = (
            cfg.delayed_feed_expected_delay_seconds
            if feed_mode == LiveFeedMode.DELAYED
            else cfg.realtime_feed_expected_delay_seconds
        )
        calendar_cfg = settings.data.calendar
        self.market_tz = ZoneInfo(calendar_cfg.market_timezone)
        self.calendar = MarketCalendar(
            exchange=calendar_cfg.exchange,
            market_tz=self.market_tz,
            premarket_start=time.fromisoformat(calendar_cfg.premarket_start_local),
            after_hours_end=time.fromisoformat(calendar_cfg.after_hours_end_local),
        )

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value in (None, ""):
            return None
        return float(value)

    @staticmethod
    def _volume(raw: dict[str, object], decimal_key: str, integer_key: str) -> float:
        value = raw.get(decimal_key)
        if value not in (None, ""):
            return float(value)
        return float(raw.get(integer_key) or 0)

    def parse(
        self,
        raw: dict[str, object],
        *,
        received_at_utc: datetime | None = None,
    ) -> LiveMinuteAggregate | LiveQuote | None:
        received = received_at_utc or datetime.now(UTC)
        event_type = str(raw.get("ev") or "").strip()
        if event_type == self.settings.massive.stocks.websocket_minute_channel:
            start = epoch_ms_to_utc(int(raw["s"]))
            end = epoch_ms_to_utc(int(raw["e"]))
            return LiveMinuteAggregate(
                symbol=str(raw["sym"]),
                bar_start_utc=start,
                bar_end_utc=end,
                session_date=market_local_date(start, self.market_tz),
                session_segment=self.calendar.classify(start),
                open=float(raw["o"]),
                high=float(raw["h"]),
                low=float(raw["l"]),
                close=float(raw["c"]),
                volume=self._volume(raw, "dv", "v"),
                vwap=self._optional_float(raw.get("vw")),
                accumulated_volume=self._volume(raw, "dav", "av"),
                official_open=self._optional_float(raw.get("op")),
                daily_vwap=self._optional_float(raw.get("a")),
                average_trade_size=self._optional_float(raw.get("z")),
                otc=bool(raw.get("otc", False)),
                feed_mode=self.feed_mode,
                expected_delay_seconds=self.expected_delay_seconds,
                received_at_utc=received,
            )
        if event_type == self.settings.massive.stocks.websocket_quote_channel:
            timestamp = epoch_ms_to_utc(int(raw["t"]))
            indicators = raw.get("i") or ()
            if not isinstance(indicators, (list, tuple)):
                indicators = ()
            return LiveQuote(
                symbol=str(raw["sym"]),
                provider_timestamp_utc=timestamp,
                session_date=market_local_date(timestamp, self.market_tz),
                session_segment=self.calendar.classify(timestamp),
                bid_price=float(raw.get("bp") or 0),
                bid_size=int(raw.get("bs") or 0),
                bid_exchange=int(raw["bx"]) if raw.get("bx") is not None else None,
                ask_price=float(raw.get("ap") or 0),
                ask_size=int(raw.get("as") or 0),
                ask_exchange=int(raw["ax"]) if raw.get("ax") is not None else None,
                condition=int(raw["c"]) if raw.get("c") is not None else None,
                indicators=tuple(int(value) for value in indicators),
                sequence=int(raw.get("q") or 0),
                tape=int(raw["z"]) if raw.get("z") is not None else None,
                feed_mode=self.feed_mode,
                expected_delay_seconds=self.expected_delay_seconds,
                received_at_utc=received,
            )
        return None


EventHandler = Callable[[dict[str, object], datetime], object | Awaitable[object]]
StateHandler = Callable[[LiveConnectionState], object | Awaitable[object]]


class MassiveStocksWebSocketClient:
    """One resilient Massive stock-cluster connection for ATLAS live state."""

    def __init__(self, settings: AtlasSettings, feed_mode: LiveFeedMode | None = None) -> None:
        self.settings = settings
        self.feed_mode = feed_mode or (
            LiveFeedMode.DELAYED
            if settings.massive.stocks.use_delayed_feed_initially
            else LiveFeedMode.REALTIME
        )
        self.config = settings.massive.stocks
        self.endpoint = (
            settings.massive.provider.websocket_delayed_url
            if self.feed_mode == LiveFeedMode.DELAYED
            else settings.massive.provider.websocket_realtime_url
        )
        self.api_key_env = settings.massive.credentials.api_key_env

    @property
    def expected_delay_seconds(self) -> int:
        return (
            self.config.delayed_feed_expected_delay_seconds
            if self.feed_mode == LiveFeedMode.DELAYED
            else self.config.realtime_feed_expected_delay_seconds
        )

    def subscription_topics(
        self,
        *,
        minute_symbols: Iterable[str] = ("*",),
        quote_symbols: Iterable[str] = (),
    ) -> tuple[str, ...]:
        topics: list[str] = []
        seen: set[str] = set()
        for channel, symbols in (
            (self.config.websocket_minute_channel, minute_symbols),
            (self.config.websocket_quote_channel, quote_symbols),
        ):
            for raw_symbol in symbols:
                symbol = str(raw_symbol).strip()
                if not symbol:
                    continue
                topic = f"{channel}.{symbol}"
                if topic not in seen:
                    topics.append(topic)
                    seen.add(topic)
        return tuple(topics)

    async def _notify(self, handler: StateHandler | None, state: LiveConnectionState) -> None:
        if handler is None:
            return
        result = handler(state)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _status_text(event: dict[str, object]) -> tuple[str, str]:
        return str(event.get("status") or "").lower(), str(event.get("message") or "")

    async def _next_status(
        self,
        websocket: ClientConnection,
        *,
        accepted: set[str],
        timeout_seconds: float,
    ) -> tuple[str, str]:
        async with asyncio.timeout(timeout_seconds):
            while True:
                frame = await websocket.recv()
                for event in decode_massive_frame(frame):
                    if str(event.get("ev") or "").lower() != "status":
                        continue
                    status, message = self._status_text(event)
                    if status in accepted:
                        return status, message
                    if any(token in status for token in ("auth_failed", "not_authorized", "unauthorized")):
                        raise MassiveWebSocketAuthenticationError(
                            f"Massive WebSocket authentication rejected: {status}: {message}"
                        )

    async def _authenticate(self, websocket: ClientConnection) -> tuple[str | None, str | None]:
        _, connected_message = await self._next_status(
            websocket,
            accepted={"connected"},
            timeout_seconds=self.config.websocket_auth_timeout_seconds,
        )
        api_key = get_secret(self.api_key_env)
        await websocket.send(json.dumps({"action": "auth", "params": api_key}))
        _, auth_message = await self._next_status(
            websocket,
            accepted={"auth_success"},
            timeout_seconds=self.config.websocket_auth_timeout_seconds,
        )
        return connected_message, auth_message

    def _connection(self):
        return connect(
            self.endpoint,
            open_timeout=self.config.websocket_open_timeout_seconds,
            ping_interval=self.config.websocket_ping_interval_seconds,
            ping_timeout=self.config.websocket_ping_timeout_seconds,
        )

    async def probe(self) -> MassiveWebSocketProbeResult:
        try:
            async with self._connection() as websocket:
                connected_message, auth_message = await self._authenticate(websocket)
                return MassiveWebSocketProbeResult(
                    endpoint=self.endpoint,
                    feed_mode=self.feed_mode,
                    connected=True,
                    authenticated=True,
                    connected_message=connected_message,
                    auth_message=auth_message,
                )
        except MassiveWebSocketAuthenticationError:
            raise
        except Exception as exc:
            raise MassiveWebSocketError(
                f"Massive {self.feed_mode.value} stock WebSocket probe failed: {type(exc).__name__}"
            ) from exc

    async def consume(
        self,
        subscriptions: tuple[str, ...],
        handler: EventHandler,
        *,
        stop_event: asyncio.Event | None = None,
        state_handler: StateHandler | None = None,
        max_events: int | None = None,
    ) -> int:
        if not subscriptions:
            raise ValueError("At least one Massive WebSocket subscription is required")
        stop = stop_event or asyncio.Event()
        processed = 0
        reconnect_delay = 1.0

        while not stop.is_set() and (max_events is None or processed < max_events):
            try:
                await self._notify(state_handler, LiveConnectionState.CONNECTING)
                async with self._connection() as websocket:
                    await self._notify(state_handler, LiveConnectionState.CONNECTED)
                    await self._authenticate(websocket)
                    await self._notify(state_handler, LiveConnectionState.AUTHENTICATED)
                    await websocket.send(
                        json.dumps({"action": "subscribe", "params": ",".join(subscriptions)})
                    )
                    await self._notify(state_handler, LiveConnectionState.SUBSCRIBED)
                    reconnect_delay = 1.0

                    queue: asyncio.Queue[tuple[str | bytes, datetime]] = asyncio.Queue(
                        maxsize=self.config.websocket_ingress_queue_size
                    )

                    async def reader() -> None:
                        async for frame in websocket:
                            try:
                                queue.put_nowait((frame, datetime.now(UTC)))
                            except asyncio.QueueFull as exc:
                                raise MassiveWebSocketBackpressureError(
                                    "Massive WebSocket ingress queue filled; refusing to drop market data"
                                ) from exc

                    reader_task = asyncio.create_task(reader(), name="massive-stocks-reader")
                    try:
                        while not stop.is_set() and (max_events is None or processed < max_events):
                            if reader_task.done() and queue.empty():
                                await reader_task
                                raise MassiveWebSocketError("Massive WebSocket closed unexpectedly")
                            try:
                                frame, received_at = await asyncio.wait_for(queue.get(), timeout=1.0)
                            except TimeoutError:
                                continue
                            for raw_event in decode_massive_frame(frame):
                                if str(raw_event.get("ev") or "").lower() == "status":
                                    continue
                                result = handler(raw_event, received_at)
                                if inspect.isawaitable(result):
                                    await result
                                processed += 1
                                if max_events is not None and processed >= max_events:
                                    stop.set()
                                    break
                    finally:
                        reader_task.cancel()
                        try:
                            await reader_task
                        except (asyncio.CancelledError, ConnectionClosed):
                            pass
            except asyncio.CancelledError:
                raise
            except MassiveWebSocketAuthenticationError:
                await self._notify(state_handler, LiveConnectionState.DEGRADED)
                raise
            except Exception:
                if stop.is_set() or (max_events is not None and processed >= max_events):
                    break
                await self._notify(state_handler, LiveConnectionState.DEGRADED)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(30.0, reconnect_delay * 2.0)

        await self._notify(state_handler, LiveConnectionState.STOPPED)
        return processed
