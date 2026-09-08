from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from statistics import median
from typing import Sequence

from packages.core.enums import SessionSegment
from packages.schemas.market import CanonicalBar
from packages.strategies.intraday_opening_pack import (
    MARKET_TZ,
    OPENING_RANGE_END,
    OPENING_RANGE_ENTRY_CUTOFF,
    OPENING_RANGE_START,
    PREMARKET_BREAKOUT_CUTOFF,
    PREMARKET_CONSOLIDATION_MAX_RANGE_PCT,
    PREMARKET_END,
    PREMARKET_RELVOL_MIN,
    IntradaySetupResult,
    evaluate_highest_volume_day_style,
    evaluate_opening_range_breakout,
    evaluate_premarket_relvol_consolidation,
    premarket_snapshot,
)


def _regular(bars: Sequence[CanonicalBar], session_date: date) -> list[CanonicalBar]:
    return sorted(
        [
            bar
            for bar in bars
            if bar.session_date == session_date
            and bar.session_segment == SessionSegment.REGULAR
        ],
        key=lambda bar: bar.timestamp_utc,
    )


def first_fired_opening_range(
    bars: Sequence[CanonicalBar], *, session_date: date
) -> IntradaySetupResult | None:
    regular = _regular(bars, session_date)
    opening = [
        bar
        for bar in regular
        if OPENING_RANGE_START
        <= bar.timestamp_utc.astimezone(MARKET_TZ).time()
        < OPENING_RANGE_END
    ]
    if not opening:
        return None
    high = max(float(bar.high) for bar in opening)
    low = min(float(bar.low) for bar in opening)
    for bar in regular:
        stamp = bar.timestamp_utc.astimezone(MARKET_TZ).time()
        if stamp < OPENING_RANGE_END or stamp > OPENING_RANGE_ENTRY_CUTOFF:
            continue
        if float(bar.close) <= high and float(bar.close) >= low:
            continue
        result = evaluate_opening_range_breakout(
            bars,
            session_date=session_date,
            decision_time_utc=bar.timestamp_utc + timedelta(minutes=1),
            # An overnight split occurred before this same-session opening range;
            # it does not cross the 09:30..breakout raw-price comparison.
            split_crossed=False,
        )
        if result.ready and result.fired:
            return result
    return None


def first_fired_premarket_relvol(
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    prior_premarket_volumes: Sequence[float],
    split_free_lookback: bool,
) -> IntradaySetupResult | None:
    if not split_free_lookback or len(prior_premarket_volumes) != 20:
        return None
    baseline = float(median(prior_premarket_volumes))
    if baseline <= 0:
        return None
    decision = (
        datetime.combine(
            session_date, PREMARKET_END, tzinfo=MARKET_TZ
        ).astimezone(UTC)
    )
    snapshot = premarket_snapshot(
        bars, session_date=session_date, decision_time_utc=decision
    )
    if snapshot is None:
        return None
    if (
        snapshot.cumulative_volume / baseline < PREMARKET_RELVOL_MIN
        or snapshot.consolidation_range_pct > PREMARKET_CONSOLIDATION_MAX_RANGE_PCT
    ):
        return None
    for bar in _regular(bars, session_date):
        stamp = bar.timestamp_utc.astimezone(MARKET_TZ).time()
        if stamp < PREMARKET_END or stamp > PREMARKET_BREAKOUT_CUTOFF:
            continue
        if float(bar.close) <= float(snapshot.consolidation_high):
            continue
        result = evaluate_premarket_relvol_consolidation(
            bars,
            session_date=session_date,
            decision_time_utc=bar.timestamp_utc + timedelta(minutes=1),
            prior_premarket_volumes=prior_premarket_volumes,
            split_free_lookback=True,
        )
        if result.ready and result.fired:
            return result
    return None


def first_fired_hvd(
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    prior_regular_daily_volumes: Sequence[float],
    split_free_lookback: bool,
) -> IntradaySetupResult | None:
    if not split_free_lookback or len(prior_regular_daily_volumes) != 252:
        return None
    highest = float(max(prior_regular_daily_volumes))
    if highest <= 0:
        return None
    decision = (
        datetime.combine(
            session_date, PREMARKET_END, tzinfo=MARKET_TZ
        ).astimezone(UTC)
    )
    snapshot = premarket_snapshot(
        bars, session_date=session_date, decision_time_utc=decision
    )
    if snapshot is None:
        return None
    if (
        snapshot.cumulative_volume < highest
        or snapshot.consolidation_range_pct > PREMARKET_CONSOLIDATION_MAX_RANGE_PCT
    ):
        return None
    for bar in _regular(bars, session_date):
        stamp = bar.timestamp_utc.astimezone(MARKET_TZ).time()
        if stamp < PREMARKET_END or stamp > PREMARKET_BREAKOUT_CUTOFF:
            continue
        if float(bar.close) <= float(snapshot.high):
            continue
        result = evaluate_highest_volume_day_style(
            bars,
            session_date=session_date,
            decision_time_utc=bar.timestamp_utc + timedelta(minutes=1),
            prior_regular_daily_volumes=prior_regular_daily_volumes,
            split_free_lookback=True,
        )
        if result.ready and result.fired:
            return result
    return None
