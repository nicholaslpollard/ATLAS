from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from packages.core.enums import SessionSegment
from packages.core.exceptions import TimestampError
from packages.core.market_calendar import MarketCalendar
from packages.core.timestamps import to_utc


def test_naive_timestamp_rejected():
    with pytest.raises(TimestampError):
        to_utc(datetime(2026, 8, 14, 10, 0))


def test_calendar_session_and_weekend():
    cal = MarketCalendar()
    assert cal.is_session(date(2026, 8, 14))
    assert not cal.is_session(date(2026, 8, 15))


def test_session_classification():
    cal = MarketCalendar()
    et = ZoneInfo("America/New_York")
    assert cal.classify(datetime(2026, 8, 14, 8, 0, tzinfo=et)) == SessionSegment.PREMARKET
    assert cal.classify(datetime(2026, 8, 14, 10, 0, tzinfo=et)) == SessionSegment.REGULAR
    assert cal.classify(datetime(2026, 8, 14, 17, 0, tzinfo=et)) == SessionSegment.AFTER_HOURS
    assert cal.classify(datetime(2026, 8, 15, 10, 0, tzinfo=et)) == SessionSegment.CLOSED
