from __future__ import annotations

from datetime import UTC, date, datetime

from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.schemas.strategy_lab import StrategyAuthority
from packages.strategies.intraday_opening_pack import (
    B34_INTRADAY_PACK_FINGERPRINT,
    B34_INTRADAY_SPECIFICATIONS,
    HVD_DAILY_LOOKBACK_SESSIONS,
    PREMARKET_LOOKBACK_SESSIONS,
    evaluate_gap_continuation,
    evaluate_highest_volume_day_style,
    evaluate_opening_range_breakout,
    evaluate_premarket_relvol_consolidation,
    frozen_pack_manifest,
)


SESSION = date(2026, 4, 30)


def _bar(
    hour: int,
    minute: int,
    *,
    segment: SessionSegment,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 100.0,
) -> CanonicalBar:
    # 2026-04-30 is EDT (UTC-4).
    stamp = datetime(2026, 4, 30, hour + 4, minute, tzinfo=UTC)
    return CanonicalBar(
        symbol="TEST",
        timestamp_utc=stamp,
        session_date=SESSION,
        timeframe=Timeframe.MINUTE_1,
        session_segment=segment,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        vwap=close,
        transaction_count=10,
        provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id="alpaca:sip:1Min:raw:asof=-:v2:unit=fixture",
        is_adjusted=False,
        provider_timestamp_utc=stamp,
    )


def _premarket_and_breakout() -> list[CanonicalBar]:
    bars: list[CanonicalBar] = []
    prices = [10.00, 10.04, 10.02, 10.06, 10.03, 10.05]
    for minute, price in zip((0, 5, 10, 15, 20, 29), prices, strict=True):
        bars.append(
            _bar(
                9,
                minute,
                segment=SessionSegment.PREMARKET,
                open_=price,
                high=price + 0.03,
                low=price - 0.03,
                close=price,
                volume=500.0,
            )
        )
    bars.append(
        _bar(
            9,
            30,
            segment=SessionSegment.REGULAR,
            open_=10.06,
            high=10.30,
            low=10.05,
            close=10.25,
            volume=1000.0,
        )
    )
    return bars


def test_b34_pack_is_frozen_research_only_and_hash_bound() -> None:
    assert len(B34_INTRADAY_SPECIFICATIONS) == 4
    assert len(B34_INTRADAY_PACK_FINGERPRINT) == 64
    assert all(spec.authority == StrategyAuthority.RESEARCH for spec in B34_INTRADAY_SPECIFICATIONS)
    assert all(spec.outcome_access_permitted is False for spec in B34_INTRADAY_SPECIFICATIONS)
    assert all(spec.governed_performance_accessed is False for spec in B34_INTRADAY_SPECIFICATIONS)
    manifest = frozen_pack_manifest()
    assert manifest["fingerprint"] == B34_INTRADAY_PACK_FINGERPRINT
    assert manifest["information_clock"]["bar_available_at"] == "timestamp_plus_one_minute"


def test_gap_reference_waits_for_first_minute_close_and_blocks_splits() -> None:
    too_early = evaluate_gap_continuation(
        session_date=SESSION,
        prior_regular_close=100.0,
        current_regular_open=103.0,
        decision_time_utc=datetime(2026, 4, 30, 13, 30, 59, tzinfo=UTC),
        split_crossed=False,
    )
    assert too_early.ready is False
    assert too_early.reason_codes == ("INFORMATION_CLOCK_NOT_READY",)

    fired = evaluate_gap_continuation(
        session_date=SESSION,
        prior_regular_close=100.0,
        current_regular_open=103.0,
        decision_time_utc=datetime(2026, 4, 30, 13, 31, tzinfo=UTC),
        split_crossed=False,
    )
    assert fired.ready is True
    assert fired.fired is True
    assert fired.direction == "LONG"

    blocked = evaluate_gap_continuation(
        session_date=SESSION,
        prior_regular_close=100.0,
        current_regular_open=103.0,
        decision_time_utc=datetime(2026, 4, 30, 13, 31, tzinfo=UTC),
        split_crossed=True,
    )
    assert blocked.ready is False
    assert blocked.fired is False
    assert blocked.reason_codes == ("SPLIT_CROSSES_PRICE_COMPARISON",)


def test_opening_range_uses_only_closed_0930_through_0944_bars() -> None:
    bars = [
        _bar(
            9,
            minute,
            segment=SessionSegment.REGULAR,
            open_=100.0,
            high=101.0 if minute == 4 else 100.8,
            low=99.0 if minute == 8 else 99.2,
            close=100.0,
        )
        for minute in range(15)
    ]
    bars.append(
        _bar(
            9,
            45,
            segment=SessionSegment.REGULAR,
            open_=100.5,
            high=102.5,
            low=100.4,
            close=102.0,
        )
    )

    at_0945 = evaluate_opening_range_breakout(
        bars,
        session_date=SESSION,
        decision_time_utc=datetime(2026, 4, 30, 13, 45, tzinfo=UTC),
    )
    assert at_0945.ready is True
    assert at_0945.fired is False
    assert at_0945.evidence["opening_range_high"] == 101.0
    assert at_0945.evidence["opening_range_low"] == 99.0
    assert at_0945.evidence["opening_range_observed_bars"] == 15
    assert at_0945.reason_codes == ("NO_CLOSED_POST_RANGE_BAR",)

    at_0946 = evaluate_opening_range_breakout(
        bars,
        session_date=SESSION,
        decision_time_utc=datetime(2026, 4, 30, 13, 46, tzinfo=UTC),
    )
    assert at_0946.fired is True
    assert at_0946.direction == "LONG"
    assert at_0946.evidence["breakout_bar_timestamp_utc"] == "2026-04-30T13:45:00+00:00"


def test_premarket_relvol_freezes_at_0930_and_needs_closed_regular_breakout() -> None:
    bars = _premarket_and_breakout()
    prior = [1000.0] * PREMARKET_LOOKBACK_SESSIONS

    before_regular_bar_closes = evaluate_premarket_relvol_consolidation(
        bars,
        session_date=SESSION,
        decision_time_utc=datetime(2026, 4, 30, 13, 30, 30, tzinfo=UTC),
        prior_premarket_volumes=prior,
        split_free_lookback=True,
    )
    assert before_regular_bar_closes.ready is True
    assert before_regular_bar_closes.fired is False
    assert "NO_CLOSED_CONSOLIDATION_BREAKOUT" in before_regular_bar_closes.reason_codes

    fired = evaluate_premarket_relvol_consolidation(
        bars,
        session_date=SESSION,
        decision_time_utc=datetime(2026, 4, 30, 13, 31, tzinfo=UTC),
        prior_premarket_volumes=prior,
        split_free_lookback=True,
    )
    assert fired.ready is True
    assert fired.fired is True
    assert fired.direction == "LONG"
    assert fired.evidence["observed_bar_count"] == 6
    assert fired.evidence["cumulative_volume"] == 3000.0
    assert fired.evidence["premarket_relvol"] == 3.0
    assert fired.evidence["breakout_bar_timestamp_utc"] == "2026-04-30T13:30:00+00:00"


def test_highest_volume_day_style_is_quantified_and_split_guarded() -> None:
    bars = _premarket_and_breakout()
    prior = [2500.0] * HVD_DAILY_LOOKBACK_SESSIONS

    fired = evaluate_highest_volume_day_style(
        bars,
        session_date=SESSION,
        decision_time_utc=datetime(2026, 4, 30, 13, 31, tzinfo=UTC),
        prior_regular_daily_volumes=prior,
        split_free_lookback=True,
    )
    assert fired.ready is True
    assert fired.fired is True
    assert fired.direction == "LONG"
    assert fired.evidence["highest_prior_252_daily_volume"] == 2500.0
    assert fired.evidence["premarket_volume_ratio_to_prior_max"] == 1.2

    blocked = evaluate_highest_volume_day_style(
        bars,
        session_date=SESSION,
        decision_time_utc=datetime(2026, 4, 30, 13, 31, tzinfo=UTC),
        prior_regular_daily_volumes=prior,
        split_free_lookback=False,
    )
    assert blocked.ready is False
    assert blocked.reason_codes == ("SPLIT_CROSSES_LOOKBACK",)
