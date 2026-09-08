from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from packages.backtesting.b35_intraday_outcomes import simulate_intraday_outcome
from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.strategies.intraday_opening_pack import IntradaySetupResult


ET = ZoneInfo("America/New_York")
DAY = date(2026, 4, 30)


def _bar(minute: int, *, open_: float, high: float, low: float, close: float) -> CanonicalBar:
    stamp = datetime(2026, 4, 30, 9, minute, tzinfo=ET).astimezone(UTC)
    return CanonicalBar(
        symbol="SPARSE",
        timestamp_utc=stamp,
        session_date=DAY,
        timeframe=Timeframe.MINUTE_1,
        session_segment=SessionSegment.REGULAR,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        vwap=close,
        transaction_count=2,
        provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id="alpaca:sip:1Min:raw:asof=-:v2:unit=sparse",
        is_adjusted=False,
        provider_timestamp_utc=stamp,
    )


def test_gap_signal_uses_first_observed_regular_bar_then_next_bar_entry() -> None:
    setup = IntradaySetupResult(
        contract="b34",
        strategy_id="b34_gap_continuation_v1",
        session_date=DAY.isoformat(),
        ready=True,
        fired=True,
        direction="LONG",
        reason_codes=("GAP_THRESHOLD_MET",),
        evidence={
            "prior_regular_close": 100.0,
            "current_regular_open": 103.0,
            "gap_pct": 0.03,
        },
    )
    bars = (
        _bar(35, open_=103.0, high=104.0, low=102.5, close=103.5),
        _bar(36, open_=104.0, high=112.5, low=103.5, close=112.0),
    )
    outcome = simulate_intraday_outcome(
        setup,
        bars,
        symbol="SPARSE",
        session_date=DAY,
    )
    assert outcome.signal_bar_timestamp_utc == bars[0].timestamp_utc.isoformat()
    assert outcome.entry_bar_timestamp_utc == bars[1].timestamp_utc.isoformat()
    assert outcome.entry_price == 104.0
