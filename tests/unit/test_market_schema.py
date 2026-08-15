from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar


def make_bar(**overrides):
    values = dict(
        symbol="aapl",
        timestamp_utc=datetime(2026, 8, 14, 14, 0, tzinfo=ZoneInfo("UTC")),
        session_date=date(2026, 8, 14),
        timeframe=Timeframe.MINUTE_1,
        session_segment=SessionSegment.REGULAR,
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1000,
        vwap=100.5,
        transaction_count=50,
        provider=DataProvider.MASSIVE,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id="src_123",
    )
    values.update(overrides)
    return CanonicalBar(**values)


def test_symbol_is_normalized():
    assert make_bar().symbol == "AAPL"


def test_timestamp_normalized_to_utc():
    et = ZoneInfo("America/New_York")
    bar = make_bar(timestamp_utc=datetime(2026, 8, 14, 10, 0, tzinfo=et))
    assert bar.timestamp_utc.hour == 14
    assert str(bar.timestamp_utc.tzinfo) == "UTC"


def test_invalid_ohlc_rejected():
    with pytest.raises(ValidationError):
        make_bar(high=100.0, close=101.0)


def test_negative_volume_rejected():
    with pytest.raises(ValidationError):
        make_bar(volume=-1)
