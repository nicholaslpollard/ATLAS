from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from .constants import MARKET_TZ, UTC
from .exceptions import TimestampError


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise TimestampError("ATLAS requires timezone-aware datetimes; naive timestamps are not accepted.")
    return value


def to_utc(value: datetime) -> datetime:
    return require_aware(value).astimezone(UTC)


def to_market_time(value: datetime, market_tz: ZoneInfo = MARKET_TZ) -> datetime:
    return require_aware(value).astimezone(market_tz)


def epoch_ms_to_utc(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000.0, tz=UTC)


def utc_to_epoch_ms(value: datetime) -> int:
    return int(to_utc(value).timestamp() * 1000)


def market_local_date(value: datetime, market_tz: ZoneInfo = MARKET_TZ) -> date:
    return to_market_time(value, market_tz).date()
