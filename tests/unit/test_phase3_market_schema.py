from datetime import UTC, date, datetime, timedelta

from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar, DerivedBar


def test_canonical_bar_preserves_provider_timestamp():
    bar = CanonicalBar(
        symbol="aapl",
        timestamp_utc=datetime(2026, 8, 14, 13, 30, tzinfo=UTC),
        provider_timestamp_utc=datetime(2026, 8, 14, 0, 0, tzinfo=UTC),
        session_date=date(2026, 8, 14),
        timeframe=Timeframe.DAY_1,
        session_segment=SessionSegment.REGULAR,
        open=1, high=3, low=1, close=2, volume=100,
        provider=DataProvider.MASSIVE,
        dataset=DatasetType.STOCK_DAILY_AGGREGATES,
        source_id="src_test",
    )
    assert bar.symbol == "AAPL"
    assert bar.provider_timestamp_utc is not None


def test_derived_bar_requires_forward_end_time():
    start = datetime(2026, 8, 14, 13, 30, tzinfo=UTC)
    bar = DerivedBar(
        symbol="AAPL", timestamp_utc=start, bar_end_utc=start + timedelta(minutes=15),
        session_date=date(2026, 8, 14), timeframe=Timeframe.MINUTE_15,
        session_segment=SessionSegment.REGULAR, open=1, high=2, low=1, close=2,
        volume=10, input_bar_count=2, source_id="src:15m"
    )
    assert bar.input_bar_count == 2
