from __future__ import annotations

import math
from dataclasses import asdict
from datetime import UTC, date, datetime, time

import pytest

from packages.backtesting import successor_development_engine as engine
from packages.backtesting.successor_minute_fastpath import (
    first_session_failed_break_reclaim,
    first_vwap_reclaim_reject,
)
from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.strategies.successor_intraday_rules import (
    evaluate_session_failed_break_reclaim,
    evaluate_vwap_reclaim_reject,
)


def _bar(
    session: date,
    hour: int,
    minute: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float,
    segment: SessionSegment = SessionSegment.REGULAR,
) -> CanonicalBar:
    local = datetime(
        session.year,
        session.month,
        session.day,
        hour,
        minute,
        tzinfo=engine.MARKET_TZ,
    )
    return CanonicalBar(
        symbol="XYZ",
        timestamp_utc=local.astimezone(UTC),
        session_date=session,
        timeframe=Timeframe.MINUTE_1,
        session_segment=segment,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        vwap=close,
        transaction_count=1,
        provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id="synthetic",
        is_adjusted=False,
    )


def _oracle_vwap(bars: list[CanonicalBar], session: date):
    return engine._first_fired_successor(
        evaluate_vwap_reclaim_reject,
        bars,
        session_date=session,
        earliest=time(9, 31),
        latest=time(15, 30),
    )


def _oracle_failed_break(
    bars: list[CanonicalBar],
    session: date,
    *,
    prior_high: float,
    prior_low: float,
    premarket_high: float | None,
    premarket_low: float | None,
):
    return engine._first_fired_successor(
        evaluate_session_failed_break_reclaim,
        bars,
        session_date=session,
        earliest=time(9, 30),
        latest=time(15, 30),
        kwargs={
            "prior_regular_high": prior_high,
            "prior_regular_low": prior_low,
            "premarket_high": premarket_high,
            "premarket_low": premarket_low,
        },
    )


def _payload(value):
    return None if value is None else asdict(value)


def test_vwap_fastpath_exactly_matches_frozen_repeated_evaluator() -> None:
    session = date(2026, 4, 6)
    scenarios: list[list[CanonicalBar]] = []

    scenarios.append(
        [
            _bar(session, 9, 30, open_price=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
            _bar(session, 9, 31, open_price=100.0, high=102.0, low=99.5, close=101.8, volume=1200.0),
        ]
    )

    zero_then_live: list[CanonicalBar] = []
    for index in range(25):
        price = 100.0 + math.sin(index / 3.0) * 1.5
        zero_then_live.append(
            _bar(
                session,
                9,
                30 + index,
                open_price=price,
                high=price + 0.4,
                low=price - 0.4,
                close=price + (0.2 if index % 3 == 0 else -0.1),
                volume=0.0 if index < 3 else 100.0 + index,
            )
        )
    scenarios.append(zero_then_live)

    missing_minutes: list[CanonicalBar] = []
    minute_of_day = 9 * 60 + 30
    for index in range(90):
        if index % 11 == 5:
            continue
        absolute = minute_of_day + index
        hour, minute = divmod(absolute, 60)
        base = 50.0 + math.sin(index / 5.0) * 2.0
        missing_minutes.append(
            _bar(
                session,
                hour,
                minute,
                open_price=base,
                high=base + 0.6,
                low=base - 0.6,
                close=base + math.cos(index / 4.0) * 0.35,
                volume=500.0 + (index % 7) * 25.0,
            )
        )
    scenarios.append(missing_minutes)

    for bars in scenarios:
        assert _payload(first_vwap_reclaim_reject(bars, session_date=session)) == _payload(
            _oracle_vwap(bars, session)
        )


def test_failed_break_fastpath_exactly_matches_frozen_repeated_evaluator() -> None:
    session = date(2026, 4, 7)
    bars = [
        _bar(session, 9, 30, open_price=100.0, high=103.0, low=97.0, close=100.0, volume=1000.0),
        _bar(session, 9, 31, open_price=100.0, high=101.0, low=98.5, close=100.5, volume=1100.0),
        _bar(session, 9, 32, open_price=100.5, high=102.5, low=100.0, close=101.5, volume=1200.0),
    ]
    kwargs = {
        "prior_high": 102.0,
        "prior_low": 98.0,
        "premarket_high": 102.5,
        "premarket_low": 97.5,
    }
    assert _payload(
        first_session_failed_break_reclaim(
            bars,
            session_date=session,
            prior_regular_high=kwargs["prior_high"],
            prior_regular_low=kwargs["prior_low"],
            premarket_high=kwargs["premarket_high"],
            premarket_low=kwargs["premarket_low"],
        )
    ) == _payload(_oracle_failed_break(bars, session, **kwargs))


def test_failed_break_fastpath_preserves_ambiguous_then_first_one_sided_fire() -> None:
    session = date(2026, 4, 8)
    bars = [
        _bar(session, 9, 30, open_price=100.0, high=103.0, low=97.0, close=100.0, volume=1000.0),
        _bar(session, 9, 31, open_price=100.0, high=101.0, low=97.5, close=99.0, volume=1000.0),
    ]
    kwargs = {
        "prior_high": 102.0,
        "prior_low": 98.0,
        "premarket_high": None,
        "premarket_low": None,
    }
    fast = first_session_failed_break_reclaim(
        bars,
        session_date=session,
        prior_regular_high=kwargs["prior_high"],
        prior_regular_low=kwargs["prior_low"],
        premarket_high=kwargs["premarket_high"],
        premarket_low=kwargs["premarket_low"],
    )
    oracle = _oracle_failed_break(bars, session, **kwargs)
    assert _payload(fast) == _payload(oracle)
    assert fast is not None
    assert fast.direction == "LONG"
    assert fast.signal_available_at_utc == (bars[1].timestamp_utc.replace(tzinfo=UTC) + engine.timedelta(minutes=1)).isoformat()


def test_fastpath_rejects_duplicate_regular_timestamp_like_frozen_evaluator() -> None:
    session = date(2026, 4, 9)
    duplicate = _bar(session, 9, 31, open_price=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0)
    bars = [
        _bar(session, 9, 30, open_price=100.0, high=101.0, low=99.0, close=100.0, volume=1000.0),
        duplicate,
        duplicate,
    ]
    with pytest.raises(ValueError, match="duplicate closed one-minute timestamps"):
        first_vwap_reclaim_reject(bars, session_date=session)
