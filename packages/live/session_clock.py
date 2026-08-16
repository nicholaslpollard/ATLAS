from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.core.timestamps import to_market_time, to_utc
from packages.schemas.live_market import LiveSessionStatus


class LiveSessionClock:
    """Project an aware timestamp into ATLAS's configured stock-session state."""

    def __init__(self, settings: AtlasSettings) -> None:
        cfg = settings.data.calendar
        self.market_tz = ZoneInfo(cfg.market_timezone)
        self.calendar = MarketCalendar(
            exchange=cfg.exchange,
            market_tz=self.market_tz,
            premarket_start=time.fromisoformat(cfg.premarket_start_local),
            after_hours_end=time.fromisoformat(cfg.after_hours_end_local),
        )

    def _next_session(self, local_date: date, now_utc: datetime) -> tuple[date | None, datetime | None]:
        candidates = self.calendar.sessions_in_range(local_date, local_date + timedelta(days=14))
        for session_date in candidates:
            regular_open, _ = self.calendar.regular_open_close(session_date)
            if regular_open > now_utc:
                return session_date, regular_open
        return None, None

    def status(self, as_of_utc: datetime) -> LiveSessionStatus:
        now_utc = to_utc(as_of_utc)
        local = to_market_time(now_utc, self.market_tz)
        local_date = local.date()
        is_session = self.calendar.is_session(local_date)
        regular_open = regular_close = None
        if is_session:
            regular_open, regular_close = self.calendar.regular_open_close(local_date)

        next_session_date, next_open = self._next_session(local_date, now_utc)
        return LiveSessionStatus(
            as_of_utc=now_utc,
            local_date=local_date,
            is_exchange_session=is_session,
            session_segment=self.calendar.classify(now_utc),
            regular_open_utc=regular_open,
            regular_close_utc=regular_close,
            next_session_date=next_session_date,
            next_regular_open_utc=next_open,
        )
