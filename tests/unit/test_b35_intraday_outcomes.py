from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from packages.backtesting.b35_intraday_outcomes import simulate_intraday_outcome
from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.strategies.intraday_opening_pack import IntradaySetupResult


ET = ZoneInfo("America/New_York")
DAY = date(2026, 4, 30)


def _bar(
    hour: int,
    minute: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> CanonicalBar:
    stamp = datetime(2026, 4, 30, hour, minute, tzinfo=ET).astimezone(UTC)
    return CanonicalBar(
        symbol="TEST",
        timestamp_utc=stamp,
        session_date=DAY,
        timeframe=Timeframe.MINUTE_1,
        session_segment=SessionSegment.REGULAR,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
        vwap=close,
        transaction_count=10,
        provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id="alpaca:sip:1Min:raw:asof=-:v2:unit=test",
        is_adjusted=False,
        provider_timestamp_utc=stamp,
    )


def _gap_setup(*, direction: str = "LONG", prior_close: float = 100.0) -> IntradaySetupResult:
    return IntradaySetupResult(
        contract="atlas-b34-intraday-semantics-audit-v1",
        strategy_id="b34_gap_continuation_v1",
        session_date=DAY.isoformat(),
        ready=True,
        fired=True,
        direction=direction,
        reason_codes=("GAP_THRESHOLD_MET",),
        evidence={"prior_regular_close": prior_close},
    )


def test_gap_outcome_enters_next_minute_and_hits_2r_target() -> None:
    bars = (
        _bar(9, 30, open_=103.0, high=104.0, low=102.0, close=103.5),
        _bar(9, 31, open_=104.0, high=105.0, low=103.0, close=104.5),
        _bar(9, 32, open_=104.5, high=112.5, low=104.0, close=112.0),
    )
    outcome = simulate_intraday_outcome(_gap_setup(), bars, symbol="TEST", session_date=DAY)
    assert outcome.comparable is True
    assert outcome.entry_price == 104.0
    assert outcome.stop_price == 100.0
    assert outcome.target_price == 112.0
    assert outcome.exit_price == 112.0
    assert outcome.exit_reason == "TARGET_2R"
    assert outcome.risk_multiple == pytest.approx(2.0)
    expected_50bps = ((112.0 * 0.9975) - (104.0 * 1.0025)) / 104.0
    assert outcome.primary_50bps_net_directional_return == pytest.approx(expected_50bps)


def test_short_returns_costs_and_excursions_use_entry_notional() -> None:
    bars = (
        _bar(9, 30, open_=97.0, high=98.0, low=96.0, close=97.0),
        _bar(9, 31, open_=96.0, high=98.0, low=92.0, close=94.0),
        _bar(9, 32, open_=94.0, high=95.0, low=88.0, close=89.0),
    )
    outcome = simulate_intraday_outcome(
        _gap_setup(direction="SHORT", prior_close=100.0),
        bars,
        symbol="TEST",
        session_date=DAY,
    )
    assert outcome.entry_price == 96.0
    assert outcome.stop_price == 100.0
    assert outcome.target_price == 88.0
    assert outcome.exit_price == 88.0
    assert outcome.gross_directional_return == pytest.approx((96.0 - 88.0) / 96.0)
    adverse_entry_proceeds = 96.0 * 0.9975
    adverse_cover = 88.0 * 1.0025
    assert outcome.primary_50bps_net_directional_return == pytest.approx(
        (adverse_entry_proceeds - adverse_cover) / 96.0
    )
    assert outcome.maximum_favorable_excursion == pytest.approx((96.0 - 88.0) / 96.0)
    assert outcome.maximum_adverse_excursion == pytest.approx((96.0 - 98.0) / 96.0)
    assert outcome.risk_multiple == pytest.approx(2.0)


def test_same_bar_stop_target_collision_is_adverse_first() -> None:
    bars = (
        _bar(9, 30, open_=103.0, high=104.0, low=102.0, close=103.5),
        _bar(9, 31, open_=104.0, high=113.0, low=99.0, close=108.0),
    )
    outcome = simulate_intraday_outcome(_gap_setup(), bars, symbol="TEST", session_date=DAY)
    assert outcome.exit_price == 100.0
    assert outcome.exit_reason == "STOP_AND_TARGET_SAME_BAR_ADVERSE_FIRST"
    assert outcome.same_bar_collision_adverse_first is True
    assert outcome.risk_multiple == pytest.approx(-1.0)


def test_stop_gap_fills_at_worse_open() -> None:
    bars = (
        _bar(9, 30, open_=103.0, high=104.0, low=102.0, close=103.5),
        _bar(9, 31, open_=104.0, high=105.0, low=103.0, close=104.5),
        _bar(9, 32, open_=98.0, high=101.0, low=97.0, close=99.0),
    )
    outcome = simulate_intraday_outcome(_gap_setup(), bars, symbol="TEST", session_date=DAY)
    assert outcome.exit_reason == "STOP_GAP_WORSE_OPEN"
    assert outcome.exit_price == 98.0
    assert outcome.risk_multiple == pytest.approx(-1.5)


def test_target_gap_gets_no_price_improvement() -> None:
    bars = (
        _bar(9, 30, open_=103.0, high=104.0, low=102.0, close=103.5),
        _bar(9, 31, open_=104.0, high=105.0, low=103.0, close=104.5),
        _bar(9, 32, open_=115.0, high=116.0, low=114.0, close=115.5),
    )
    outcome = simulate_intraday_outcome(_gap_setup(), bars, symbol="TEST", session_date=DAY)
    assert outcome.exit_reason == "TARGET_GAP_NO_BETTER_THAN_TARGET"
    assert outcome.exit_price == 112.0
    assert outcome.risk_multiple == pytest.approx(2.0)


def test_time_exit_uses_first_observed_1555_to_1559_bar_open() -> None:
    bars = (
        _bar(9, 30, open_=103.0, high=104.0, low=102.0, close=103.5),
        _bar(9, 31, open_=104.0, high=105.0, low=103.0, close=104.5),
        _bar(15, 55, open_=106.0, high=120.0, low=90.0, close=100.0),
    )
    outcome = simulate_intraday_outcome(_gap_setup(), bars, symbol="TEST", session_date=DAY)
    assert outcome.exit_reason == "TIME_EXIT"
    assert outcome.exit_price == 106.0
    assert outcome.same_bar_collision_adverse_first is False


def test_entered_but_unresolved_preserves_attempted_exposure() -> None:
    bars = (
        _bar(9, 30, open_=103.0, high=103.5, low=102.5, close=103.0),
        _bar(9, 31, open_=104.0, high=105.0, low=103.0, close=104.0),
        _bar(9, 32, open_=104.0, high=106.0, low=103.0, close=105.0),
    )
    outcome = simulate_intraday_outcome(_gap_setup(), bars, symbol="TEST", session_date=DAY)
    assert outcome.comparable is False
    assert outcome.status == "NONCOMPARABLE_UNRESOLVED_EXIT_AFTER_ENTRY"
    assert outcome.entry_bar_timestamp_utc == bars[1].timestamp_utc.isoformat()
    assert outcome.entry_price == 104.0
    assert outcome.stop_price == 100.0
    assert outcome.target_price == 112.0
    assert outcome.exit_price is None
    assert outcome.gross_directional_return is None
    assert outcome.primary_50bps_net_directional_return is None
    assert outcome.bars_observed_after_entry == 2
    assert outcome.maximum_favorable_excursion == pytest.approx((106.0 - 104.0) / 104.0)
    assert outcome.maximum_adverse_excursion == pytest.approx((103.0 - 104.0) / 104.0)


def test_development_outcome_rejects_consumed_master_date() -> None:
    protected = date(2026, 5, 12)
    setup = IntradaySetupResult(
        contract="x",
        strategy_id="b34_gap_continuation_v1",
        session_date=protected.isoformat(),
        ready=True,
        fired=True,
        direction="LONG",
        reason_codes=("x",),
        evidence={"prior_regular_close": 100.0},
    )
    with pytest.raises(ValueError, match="restricted to sessions through 2026-04-30"):
        simulate_intraday_outcome(setup, (), symbol="TEST", session_date=protected)
