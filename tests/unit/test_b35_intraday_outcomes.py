from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.backtesting.b35_intraday_outcomes import simulate_intraday_outcome
from packages.strategies.intraday_opening_pack import IntradaySetupResult


ET = ZoneInfo("America/New_York")
DAY = date(2026, 4, 30)


def _bar(hour: int, minute: int, *, open_: float, high: float, low: float, close: float) -> CanonicalBar:
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


def _gap_setup() -> IntradaySetupResult:
    return IntradaySetupResult(
        contract="atlas-b34-intraday-semantics-audit-v1",
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
    assert outcome.primary_50bps_net_directional_return == pytest.approx(
        112.0 / 104.0 - 1.0 - 0.005
    )


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
