from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from packages.core.market_calendar import MarketCalendar
from packages.core.timestamps import to_utc


@dataclass(frozen=True, slots=True)
class SessionBoundaries:
    trading_date: date
    premarket_start_utc: datetime
    regular_open_utc: datetime
    regular_close_utc: datetime
    after_hours_end_utc: datetime

    def as_epoch_ns(self) -> dict[str, int]:
        return {
            "premarket_start_ns": int(self.premarket_start_utc.timestamp() * 1_000_000_000),
            "regular_open_ns": int(self.regular_open_utc.timestamp() * 1_000_000_000),
            "regular_close_ns": int(self.regular_close_utc.timestamp() * 1_000_000_000),
            "after_hours_end_ns": int(self.after_hours_end_utc.timestamp() * 1_000_000_000),
        }


def _parse_clock(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":", maxsplit=1))
    return time(hour=hour, minute=minute)


def session_boundaries(
    trading_date: date,
    calendar: MarketCalendar,
    *,
    market_timezone: str = "America/New_York",
    premarket_start_local: str = "04:00",
    after_hours_end_local: str = "20:00",
) -> SessionBoundaries:
    regular_open_utc, regular_close_utc = calendar.regular_open_close(trading_date)
    tz = ZoneInfo(market_timezone)
    premarket = datetime.combine(trading_date, _parse_clock(premarket_start_local), tz)
    after_hours = datetime.combine(trading_date, _parse_clock(after_hours_end_local), tz)
    return SessionBoundaries(
        trading_date=trading_date,
        premarket_start_utc=to_utc(premarket),
        regular_open_utc=regular_open_utc,
        regular_close_utc=regular_close_utc,
        after_hours_end_utc=to_utc(after_hours),
    )
