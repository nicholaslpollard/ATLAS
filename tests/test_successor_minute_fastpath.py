from __future__ import annotations

import math
from dataclasses import asdict
from datetime import UTC, date, datetime, time, timedelta

import pandas as pd
import pytest

from packages.backtesting import successor_development_engine as engine
from packages.backtesting.b35_development_replay import _canonical_bars as validated_canonical_bars
from packages.backtesting.successor_minute_fastpath import (
    fast_prior_natr_14,
    first_gap_quality_condition_long,
    first_orb_15m_close_retest,
    first_orb_stocks_in_play_5m,
    first_premarket_relvol_quality,
    first_session_failed_break_reclaim,
    first_vwap_reclaim_reject,
    prepare_successor_minute_session,
    trusted_canonical_bars,
)
from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.features.volatility import normalized_atr
from packages.schemas.market import CanonicalBar
from packages.strategies.successor_intraday_rules import (
    evaluate_gap_quality_condition_long,
    evaluate_orb_15m_close_retest,
    evaluate_orb_stocks_in_play_5m,
    evaluate_premarket_relvol_quality,
    evaluate_session_failed_break_reclaim,
    evaluate_vwap_reclaim_reject,
)


ORIGINAL_NEW_SUCCESSOR_MINUTE_SIGNALS = engine._new_successor_minute_signals


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
        provider_timestamp_utc=local.astimezone(UTC),
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


def _fired_payload(value):
    if value is None or not value.ready or not value.fired:
        return None
    return asdict(value)


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
    assert fast.signal_available_at_utc == (
        bars[1].timestamp_utc + timedelta(minutes=1)
    ).isoformat()


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


def test_remaining_successor_routes_match_frozen_fired_payloads() -> None:
    session = date(2026, 4, 10)

    gap_bars = [
        _bar(session, 9, 30, open_price=103.0, high=104.0, low=102.8, close=103.5, volume=5000.0)
    ]
    gap_view = prepare_successor_minute_session(gap_bars, session_date=session)
    fast_gap = first_gap_quality_condition_long(
        session_date=session,
        view=gap_view,
        prior_regular_close=100.0,
        prior_median_dollar_volume_20=30_000_000.0,
        natr_14=0.04,
        premarket_relvol_20=2.0,
        split_crossed=False,
    )
    oracle_gap = evaluate_gap_quality_condition_long(
        gap_bars,
        session_date=session,
        decision_time_utc=datetime.combine(session, time(9, 31), tzinfo=engine.MARKET_TZ).astimezone(UTC),
        prior_regular_close=100.0,
        prior_median_dollar_volume_20=30_000_000.0,
        natr_14=0.04,
        premarket_relvol_20=2.0,
        split_crossed=False,
    )
    assert _fired_payload(fast_gap) == _fired_payload(oracle_gap)

    orb5_bars = [
        _bar(
            session,
            9,
            30 + index,
            open_price=100.0,
            high=100.5,
            low=99.5,
            close=100.0,
            volume=1000.0,
        )
        for index in range(5)
    ]
    orb5_bars.append(
        _bar(session, 9, 35, open_price=100.0, high=102.0, low=99.9, close=101.5, volume=2000.0)
    )
    orb5_view = prepare_successor_minute_session(orb5_bars, session_date=session)
    fast_orb5 = first_orb_stocks_in_play_5m(
        session_date=session,
        view=orb5_view,
        same_time_opening_relvol=2.5,
        prior_median_dollar_volume_20=30_000_000.0,
    )
    oracle_orb5 = evaluate_orb_stocks_in_play_5m(
        orb5_bars,
        session_date=session,
        decision_time_utc=datetime.combine(session, time(11, 31), tzinfo=engine.MARKET_TZ).astimezone(UTC),
        same_time_opening_relvol=2.5,
        prior_median_dollar_volume_20=30_000_000.0,
    )
    assert _fired_payload(fast_orb5) == _fired_payload(oracle_orb5)

    orb15_bars = [
        _bar(
            session,
            9,
            30 + index,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000.0,
        )
        for index in range(15)
    ]
    orb15_bars.extend(
        [
            _bar(session, 9, 45, open_price=100.0, high=102.0, low=100.0, close=101.5, volume=2000.0),
            _bar(session, 9, 46, open_price=101.5, high=101.6, low=100.9, close=101.05, volume=1500.0),
            _bar(session, 9, 47, open_price=101.05, high=101.4, low=101.0, close=101.2, volume=1500.0),
        ]
    )
    orb15_view = prepare_successor_minute_session(orb15_bars, session_date=session)
    fast_orb15 = first_orb_15m_close_retest(
        session_date=session,
        view=orb15_view,
        atr_reference=1.0,
    )
    oracle_orb15 = evaluate_orb_15m_close_retest(
        orb15_bars,
        session_date=session,
        decision_time_utc=datetime.combine(session, time(15, 31), tzinfo=engine.MARKET_TZ).astimezone(UTC),
        atr_reference=1.0,
    )
    assert _fired_payload(fast_orb15) == _fired_payload(oracle_orb15)

    pm_bars = [
        _bar(
            session,
            9,
            minute,
            open_price=100.0,
            high=100.2,
            low=99.8,
            close=100.0,
            volume=1000.0,
            segment=SessionSegment.PREMARKET,
        )
        for minute in range(30)
    ]
    breakout = _bar(
        session, 9, 30, open_price=100.0, high=101.5, low=99.9, close=101.0, volume=2000.0
    )
    pm_bars.append(breakout)
    pm_view = prepare_successor_minute_session(pm_bars, session_date=session)
    relvol_map = {breakout.timestamp_utc: 2.0}
    fast_pm = first_premarket_relvol_quality(
        session_date=session,
        view=pm_view,
        prior_premarket_median_volume_20=10_000.0,
        prior_median_dollar_volume_20=30_000_000.0,
        breakout_same_time_relvol_by_timestamp=relvol_map,
    )
    oracle_pm = evaluate_premarket_relvol_quality(
        pm_bars,
        session_date=session,
        decision_time_utc=datetime.combine(session, time(11, 31), tzinfo=engine.MARKET_TZ).astimezone(UTC),
        prior_premarket_median_volume_20=10_000.0,
        prior_median_dollar_volume_20=30_000_000.0,
        breakout_same_time_relvol_by_timestamp=relvol_map,
    )
    assert _fired_payload(fast_pm) == _fired_payload(oracle_pm)


def test_fast_natr_matches_frozen_normalized_atr_math() -> None:
    start = date(2025, 1, 1)
    daily = [
        engine.RawMinuteDailySummary(
            session_date=start + timedelta(days=index),
            high=101.0 + index * 0.15,
            low=99.0 + index * 0.10,
            close=100.0 + index * 0.12,
            dollar_volume=25_000_000.0 + index,
            split_epoch=1.0,
        )
        for index in range(80)
    ]
    history = engine.SuccessorMinuteHistory(daily=daily)
    expected = normalized_atr(
        pd.Series([item.high for item in daily]),
        pd.Series([item.low for item in daily]),
        pd.Series([item.close for item in daily]),
        14,
    ).iloc[-1]
    assert fast_prior_natr_14(history, 1.0) == pytest.approx(float(expected), rel=1e-14, abs=1e-14)


def test_trusted_canonical_construction_matches_validated_constructor() -> None:
    session = date(2026, 4, 13)
    source = _bar(
        session,
        9,
        30,
        open_price=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1234.0,
    )
    frame = pd.DataFrame([source.model_dump(mode="python")])
    trusted = trusted_canonical_bars(frame)
    validated = validated_canonical_bars(frame)
    assert len(trusted) == len(validated) == 1
    assert trusted[0].model_dump(mode="python") == validated[0].model_dump(mode="python")
