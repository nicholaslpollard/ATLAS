from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.strategies.successor_orb_stocks_in_play_literature_v2 import (
    MARKET_TZ,
    evaluate_orb_stocks_in_play_literature_v2,
)
from packages.strategies.successor_orb_stocks_in_play_literature_v2_contract import (
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT,
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT,
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID,
    contract_fingerprint,
)
from packages.strategies.successor_practitioner_lab import B35_CHALLENGERS


def _bar(
    session: date,
    hour: int,
    minute: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> CanonicalBar:
    local = datetime(
        session.year,
        session.month,
        session.day,
        hour,
        minute,
        tzinfo=MARKET_TZ,
    )
    return CanonicalBar(
        symbol="XYZ",
        timestamp_utc=local.astimezone(UTC),
        session_date=session,
        timeframe=Timeframe.MINUTE_1,
        session_segment=SessionSegment.REGULAR,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
        vwap=close,
        transaction_count=10,
        provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id="synthetic",
        is_adjusted=False,
    )


def _opening(session: date, *, bullish: bool = True) -> list[CanonicalBar]:
    closes = [100.2, 100.5, 100.8, 101.0, 101.2] if bullish else [99.8, 99.5, 99.2, 99.0, 98.8]
    result: list[CanonicalBar] = []
    previous = 100.0
    for offset, close in enumerate(closes):
        result.append(
            _bar(
                session,
                9,
                30 + offset,
                open_price=previous,
                high=max(previous, close) + 0.2,
                low=min(previous, close) - 0.2,
                close=close,
            )
        )
        previous = close
    return result


def _evaluate(bars: list[CanonicalBar], session: date, **overrides):
    kwargs = {
        "prior_average_daily_share_volume_14": 2_000_000.0,
        "prior_atr_14_dollars": 2.0,
        "opening_relvol_14": 2.5,
        "daily_relvol_rank": 3,
    }
    kwargs.update(overrides)
    return evaluate_orb_stocks_in_play_literature_v2(
        bars,
        session_date=session,
        **kwargs,
    )


def test_preoutcome_contract_is_frozen_and_has_no_authority() -> None:
    assert contract_fingerprint() == ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT
    assert ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT == (
        "1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb"
    )
    assert ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT["scope"] == "DEVELOPMENT_ONLY"
    for key in (
        "paper_authority",
        "live_authority",
        "strategy_promotion_authority",
        "selector_promotion_authority",
        "confluence_authority",
        "option_trading_authority",
    ):
        assert ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT[key] is False
    assert ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT["consumed_master_reads"] == 0
    assert ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT["future_blind_reads"] == 0
    assert ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID not in {
        route.policy_id for route in B35_CHALLENGERS
    }
    assert "orb_stocks_in_play_5m_v1" in {route.policy_id for route in B35_CHALLENGERS}


def test_bullish_opening_uses_directional_stop_breakout_and_atr_stop() -> None:
    session = date(2026, 4, 1)
    bars = _opening(session, bullish=True)
    range_high = max(bar.high for bar in bars)
    bars.extend(
        [
            _bar(session, 9, 35, open_price=101.1, high=range_high - 0.01, low=100.9, close=101.0),
            _bar(session, 9, 36, open_price=101.0, high=range_high + 0.25, low=100.8, close=range_high + 0.1),
        ]
    )

    signal = _evaluate(bars, session)
    assert signal is not None
    assert signal.direction == "LONG"
    assert signal.entry_price == pytest.approx(range_high)
    assert signal.entry_fill_reason == "STOP_CROSS_AT_STOP_PRICE"
    assert signal.stop_loss_price == pytest.approx(range_high - 0.2)
    assert signal.daily_relvol_rank == 3


def test_bearish_opening_gap_through_stop_fills_at_worse_bar_open() -> None:
    session = date(2026, 4, 2)
    bars = _opening(session, bullish=False)
    range_low = min(bar.low for bar in bars)
    gap_open = range_low - 0.35
    bars.append(
        _bar(
            session,
            9,
            35,
            open_price=gap_open,
            high=gap_open + 0.15,
            low=gap_open - 0.2,
            close=gap_open - 0.05,
        )
    )

    signal = _evaluate(bars, session)
    assert signal is not None
    assert signal.direction == "SHORT"
    assert signal.entry_stop_price == pytest.approx(range_low)
    assert signal.entry_price == pytest.approx(gap_open)
    assert signal.entry_fill_reason == "GAP_THROUGH_STOP_AT_BAR_OPEN"
    assert signal.stop_loss_price == pytest.approx(gap_open + 0.2)


def test_literature_filters_and_direction_fail_closed() -> None:
    session = date(2026, 4, 3)
    bars = _opening(session, bullish=True)
    range_high = max(bar.high for bar in bars)
    bars.append(
        _bar(session, 9, 35, open_price=101.2, high=range_high + 0.1, low=101.0, close=101.3)
    )

    assert _evaluate(bars, session, opening_relvol_14=0.999) is None
    assert _evaluate(bars, session, daily_relvol_rank=21) is None
    assert _evaluate(bars, session, prior_average_daily_share_volume_14=999_999.0) is None
    assert _evaluate(bars, session, prior_atr_14_dollars=0.50) is None

    doji = _opening(session, bullish=True)
    final = doji[-1]
    doji[-1] = _bar(
        session,
        9,
        34,
        open_price=final.open,
        high=max(final.high, 100.2),
        low=min(final.low, 99.8),
        close=100.0,
    )
    doji.append(
        _bar(session, 9, 35, open_price=100.0, high=102.0, low=98.0, close=101.0)
    )
    assert _evaluate(doji, session) is None
