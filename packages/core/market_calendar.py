from __future__ import annotations

from datetime import date, datetime, time
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

from .constants import DEFAULT_EXCHANGE_CALENDAR, MARKET_TZ
from .enums import SessionSegment
from .timestamps import require_aware, to_market_time, to_utc


class MarketCalendar:
    """Thin ATLAS wrapper around an exchange calendar.

    Regular-session boundaries come from the exchange calendar. Premarket and
    after-hours boundaries are ATLAS configuration conventions and never alter
    the exchange's official regular session.
    """

    def __init__(
        self,
        exchange: str = DEFAULT_EXCHANGE_CALENDAR,
        market_tz: ZoneInfo = MARKET_TZ,
        premarket_start: time = time(4, 0),
        after_hours_end: time = time(20, 0),
    ) -> None:
        self.exchange = exchange
        self.market_tz = market_tz
        self.premarket_start = premarket_start
        self.after_hours_end = after_hours_end
        self._calendar = xcals.get_calendar(exchange)

    def is_session(self, session_date: date) -> bool:
        return bool(self._calendar.is_session(pd.Timestamp(session_date)))

    def sessions_in_range(self, start: date, end: date) -> list[date]:
        sessions = self._calendar.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
        return [ts.date() for ts in sessions]

    def regular_open_close(self, session_date: date) -> tuple[datetime, datetime]:
        label = pd.Timestamp(session_date)
        if not self._calendar.is_session(label):
            raise ValueError(f"{session_date} is not a {self.exchange} trading session")
        open_ts = self._calendar.session_open(label).to_pydatetime()
        close_ts = self._calendar.session_close(label).to_pydatetime()
        return to_utc(open_ts), to_utc(close_ts)

    def classify(self, timestamp: datetime) -> SessionSegment:
        require_aware(timestamp)
        local = to_market_time(timestamp, self.market_tz)
        session_date = local.date()
        if not self.is_session(session_date):
            return SessionSegment.CLOSED

        regular_open_utc, regular_close_utc = self.regular_open_close(session_date)
        ts_utc = to_utc(timestamp)
        if regular_open_utc <= ts_utc < regular_close_utc:
            return SessionSegment.REGULAR

        premarket_start_local = datetime.combine(session_date, self.premarket_start, self.market_tz)
        after_hours_end_local = datetime.combine(session_date, self.after_hours_end, self.market_tz)
        if premarket_start_local <= local < regular_open_utc.astimezone(self.market_tz):
            return SessionSegment.PREMARKET
        if regular_close_utc.astimezone(self.market_tz) <= local < after_hours_end_local:
            return SessionSegment.AFTER_HOURS
        return SessionSegment.CLOSED


@lru_cache(maxsize=8)
def get_market_calendar(exchange: str = DEFAULT_EXCHANGE_CALENDAR) -> MarketCalendar:
    return MarketCalendar(exchange=exchange)
