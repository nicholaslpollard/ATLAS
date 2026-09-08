from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from packages.backtesting.b35_development_replay import _first_fired
from packages.backtesting.b35_setup_scan import first_fired_opening_range
from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.strategies.intraday_opening_pack import evaluate_opening_range_breakout

ET = ZoneInfo("America/New_York")
DAY = date(2026, 4, 30)


def _bar(hour: int, minute: int, close: float) -> CanonicalBar:
    stamp = datetime(2026, 4, 30, hour, minute, tzinfo=ET).astimezone(UTC)
    return CanonicalBar(
        symbol="TEST", timestamp_utc=stamp, session_date=DAY, timeframe=Timeframe.MINUTE_1,
        session_segment=SessionSegment.REGULAR, open=close, high=close + 0.1, low=close - 0.1, close=close,
        volume=100, vwap=close, transaction_count=2, provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES, source_id="alpaca:sip:1Min:raw:asof=-:v2:unit=test",
        is_adjusted=False, provider_timestamp_utc=stamp,
    )


def test_fast_opening_scan_matches_unchanged_b34_evaluator_first_fire() -> None:
    bars = tuple([_bar(9, minute, 100.0) for minute in range(30, 45)] + [
        _bar(9, 45, 100.0), _bar(9, 46, 100.0), _bar(9, 47, 101.0)
    ])
    slow = _first_fired(
        evaluate_opening_range_breakout, bars, session_date=DAY, earliest_stamp=time(9, 45),
        latest_stamp=time(11, 30), kwargs={"split_crossed": False}
    )
    fast = first_fired_opening_range(bars, session_date=DAY)
    assert fast == slow
    assert fast is not None and fast.fired
