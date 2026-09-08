from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from packages.backtesting.b35_development_context import (
    DailySessionSummary,
    build_condition_snapshot,
    split_crossed_prior_close,
    split_free,
)
from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.strategies.intraday_opening_pack import IntradaySetupResult


ET = ZoneInfo("America/New_York")
DAY = date(2026, 4, 30)


def _premarket_bar(hour: int, minute: int, *, close: float, volume: float) -> CanonicalBar:
    stamp = datetime(2026, 4, 30, hour, minute, tzinfo=ET).astimezone(UTC)
    return CanonicalBar(
        symbol="TEST",
        timestamp_utc=stamp,
        session_date=DAY,
        timeframe=Timeframe.MINUTE_1,
        session_segment=SessionSegment.PREMARKET,
        open=close,
        high=close * 1.001,
        low=close * 0.999,
        close=close,
        volume=volume,
        vwap=close,
        transaction_count=5,
        provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id="alpaca:sip:1Min:raw:asof=-:v2:unit=test",
        is_adjusted=False,
        provider_timestamp_utc=stamp,
    )


def _history(count: int, *, factor: float = 1.0) -> list[DailySessionSummary]:
    start = date(2025, 1, 1)
    return [
        DailySessionSummary(
            session_date=start + timedelta(days=index),
            close=20.0 + index * 0.01,
            regular_volume=1_000_000.0 + index,
            dollar_volume=25_000_000.0 + index * 1000.0,
            split_factor=factor,
        )
        for index in range(count)
    ]


def _opening_setup() -> IntradaySetupResult:
    breakout = datetime(2026, 4, 30, 9, 45, tzinfo=ET).astimezone(UTC)
    return IntradaySetupResult(
        contract="b34",
        strategy_id="b34_opening_range_breakout_15m_v1",
        session_date=DAY.isoformat(),
        ready=True,
        fired=True,
        direction="LONG",
        reason_codes=("OPENING_RANGE_BREAKOUT",),
        evidence={
            "opening_range_high": 25.25,
            "opening_range_low": 24.75,
            "breakout_bar_timestamp_utc": breakout.isoformat(),
        },
    )


def test_condition_snapshot_uses_prior_only_and_setup_evidence() -> None:
    snapshot = build_condition_snapshot(
        _opening_setup(),
        (
            _premarket_bar(9, 0, close=25.0, volume=10_000.0),
            _premarket_bar(9, 15, close=25.1, volume=20_000.0),
        ),
        symbol="TEST",
        session_date=DAY,
        prior_daily=_history(252),
        current_regular_open=25.0,
        current_split_factor=1.0,
        prior_market_regime="UNAVAILABLE",
    )
    assert snapshot.prior_close_price in {"20_TO_100", "5_TO_20"}
    assert snapshot.median_dollar_volume_20 == "10M_TO_50M"
    assert snapshot.opening_range_width_pct == "2_TO_4PCT"
    assert snapshot.signal_time_et == "0945_TO_1000"
    assert snapshot.setup_intensity_dimension == "opening_range_width_pct"
    assert snapshot.split_free_20 is True
    assert snapshot.split_free_252 is True
    assert snapshot.realized_volatility_20 != "UNAVAILABLE"
    assert snapshot.prior_trend_20_50 != "UNAVAILABLE"


def test_split_guards_fail_closed_when_epoch_changes() -> None:
    history = _history(20, factor=1.0)
    assert split_free(history, current_factor=1.0) is True
    assert split_free(history, current_factor=2.0) is False
    assert split_crossed_prior_close(history[-1], current_factor=2.0) is True


def test_split_guards_fail_closed_when_factor_is_missing() -> None:
    history = _history(20, factor=1.0)
    history[-1] = DailySessionSummary(
        session_date=history[-1].session_date,
        close=history[-1].close,
        regular_volume=history[-1].regular_volume,
        dollar_volume=history[-1].dollar_volume,
        split_factor=None,
    )
    assert split_free(history, current_factor=1.0) is False
    assert split_crossed_prior_close(history[-1], current_factor=1.0) is True


def test_trend_is_unavailable_when_prior_window_crosses_split_epoch() -> None:
    history = _history(252, factor=1.0)
    for index in range(len(history) - 30, len(history)):
        item = history[index]
        history[index] = DailySessionSummary(
            session_date=item.session_date,
            close=item.close,
            regular_volume=item.regular_volume,
            dollar_volume=item.dollar_volume,
            split_factor=2.0,
        )
    snapshot = build_condition_snapshot(
        _opening_setup(),
        (_premarket_bar(9, 0, close=25.0, volume=10_000.0),),
        symbol="TEST",
        session_date=DAY,
        prior_daily=history,
        current_regular_open=25.0,
        current_split_factor=2.0,
        prior_market_regime="UNAVAILABLE",
    )
    assert snapshot.realized_volatility_20 != "UNAVAILABLE"
    assert snapshot.prior_trend_20_50 == "UNAVAILABLE"
    assert snapshot.split_free_20 is True
    assert snapshot.split_free_252 is False
