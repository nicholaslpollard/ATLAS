from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from packages.backtesting import successor_development_engine as engine
from packages.backtesting.b35_development_replay import _SymbolHistory
from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.strategies.successor_intraday_rules import (
    SUCCESSOR_INTRADAY_RULE_CONTRACT,
    SuccessorIntradaySignal,
)


def _minute_bar(
    session: date,
    local_hour: int,
    local_minute: int,
    *,
    open_price: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
    volume: float = 1000.0,
    segment: SessionSegment = SessionSegment.REGULAR,
) -> CanonicalBar:
    local = datetime(
        session.year,
        session.month,
        session.day,
        local_hour,
        local_minute,
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
        transaction_count=10,
        provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id="synthetic",
        is_adjusted=False,
    )


def test_daily_engine_routes_retained_and_new_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = pd.DataFrame(
        [
            {
                "instrument_id": "inst",
                "ticker": "XYZ",
                "session_date": date(2026, 4, 1),
                "signal_available_at_utc": pd.Timestamp("2026-04-01T20:00:00Z"),
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "universe_pit_active_ok": 1.0,
                "universe_common_stock_ok": 1.0,
                "universe_identity_ok": 1.0,
                "universe_close_ok": 1.0,
                "universe_prior_liquidity_ok": 1.0,
            },
            {
                "instrument_id": "inst",
                "ticker": "XYZ",
                "session_date": date(2026, 4, 2),
                "signal_available_at_utc": pd.Timestamp("2026-04-02T20:00:00Z"),
                "open": 101.0,
                "high": 104.0,
                "low": 100.0,
                "close": 103.0,
                "universe_pit_active_ok": 1.0,
                "universe_common_stock_ok": 1.0,
                "universe_identity_ok": 1.0,
                "universe_close_ok": 1.0,
                "universe_prior_liquidity_ok": 1.0,
            },
        ]
    )
    for route in engine._DAILY_ROUTES:
        if route.evaluator_contract_id == "accepted_reference_daily_v1":
            spec = engine.REFERENCE_STRATEGY_CATALOG.get(route.policy_id)
            base[spec.signal.trigger_feature] = 0.0
        else:
            implementation = engine._IMPLEMENTATIONS[route.policy_id]
            for trigger in implementation.trigger_features:
                base[trigger] = 0.0
    base.loc[0, "sma_cross_50_200_up"] = 1.0
    base.loc[0, "bollinger_mean_reversion_long"] = 1.0

    monkeypatch.setattr(
        engine,
        "compute_successor_daily_features",
        lambda frame, *, benchmark_frame: base.copy(),
    )
    monkeypatch.setattr(
        engine,
        "successor_common_context_from_row",
        lambda row: {"signal_time": "DAILY_CLOSE"},
    )

    records = engine.evaluate_successor_daily_standalone(
        pd.DataFrame({"placeholder": [1]}),
        benchmark_frame=pd.DataFrame({"session_date": [], "close": []}),
    )
    policies = [str(record["route"]["policy_id"]) for record in records]
    assert "ma_trend_cross_50_200_long_v1" in policies
    assert "pract_bollinger_mean_reversion_v1" in policies
    retained = next(
        record for record in records if record["route"]["policy_id"] == "ma_trend_cross_50_200_long_v1"
    )
    assert retained["signal"]["universe_eligible"] is True
    new = next(
        record for record in records if record["route"]["policy_id"] == "pract_bollinger_mean_reversion_v1"
    )
    assert new["signal"]["direction"] == "LONG"
    assert new["outcome"]["entry_price"] == pytest.approx(101.0)


def test_minute_history_same_time_and_opening_relvol_are_prior_only() -> None:
    history = engine.SuccessorMinuteHistory()
    start = date(2026, 3, 1)
    for offset in range(20):
        session = start + timedelta(days=offset)
        bars = [
            _minute_bar(session, 9, 30 + minute, volume=100.0)
            for minute in range(5)
        ]
        history.append_session(bars, session_date=session, split_epoch=1.0)

    current = start + timedelta(days=20)
    current_bars = [
        _minute_bar(current, 9, 30 + minute, volume=200.0)
        for minute in range(5)
    ]
    assert history.opening_five_minute_relvol(current_bars, current) == pytest.approx(2.0)
    relvol = history.same_time_relvol_map(current_bars, current)
    assert relvol[current_bars[0].timestamp_utc] == pytest.approx(2.0)

    history.append_session(current_bars, session_date=current, split_epoch=1.0)
    following = current + timedelta(days=1)
    following_bars = [
        _minute_bar(following, 9, 30 + minute, volume=200.0)
        for minute in range(5)
    ]
    # The current 200-volume session is now prior evidence and changes the rolling median only by history order.
    assert history.opening_five_minute_relvol(following_bars, following) >= 1.0


def test_minute_history_natr_fails_closed_across_recent_split() -> None:
    history = engine.SuccessorMinuteHistory()
    start = date(2026, 3, 1)
    for offset in range(20):
        session = start + timedelta(days=offset)
        bars = [_minute_bar(session, 9, 30, high=101.0, low=99.0, close=100.0)]
        history.append_session(
            bars,
            session_date=session,
            split_epoch=1.0 if offset < 10 else 2.0,
        )
    assert history.prior_natr_14(2.0) is None
    assert history.split_crossed_prior_close(2.0) is False
    assert history.split_crossed_prior_close(3.0) is True


def test_minute_session_maps_new_signal_to_frozen_route_and_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = date(2026, 4, 1)
    bars = [
        _minute_bar(session, 10, 0, open_price=100.0, high=100.5, low=99.5, close=100.0),
        _minute_bar(session, 10, 1, open_price=100.0, high=102.2, low=99.8, close=102.0),
    ]
    signal = SuccessorIntradaySignal(
        contract=SUCCESSOR_INTRADAY_RULE_CONTRACT,
        policy_id="pract_vwap_reclaim_reject_v1",
        session_date=session.isoformat(),
        ready=True,
        fired=True,
        direction="LONG",
        signal_available_at_utc=(bars[0].timestamp_utc + timedelta(minutes=1)).isoformat(),
        reason_codes=("TEST",),
        evidence={},
    )
    monkeypatch.setattr(engine, "_evaluate_setups", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        engine,
        "_new_successor_minute_signals",
        lambda *args, **kwargs: [(signal, None, None)],
    )
    records = engine.evaluate_successor_minute_session(
        bars,
        symbol="XYZ",
        session_date=session,
        retained_history=_SymbolHistory.empty(),
        successor_history=engine.SuccessorMinuteHistory(),
        symbol_split_dates=(),
    )
    assert len(records) == 1
    record = records[0]
    assert record["route"]["policy_id"] == "pract_vwap_reclaim_reject_v1"
    assert record["outcome"]["status"] == "EXITED"
    assert record["outcome"]["exit_reason"] == "TARGET_2R"


def test_signal_bar_stop_uses_adverse_signal_extreme() -> None:
    session = date(2026, 4, 1)
    signal_bar = _minute_bar(
        session, 10, 0, open_price=100.0, high=101.0, low=98.0, close=100.0
    )
    long_signal = SuccessorIntradaySignal(
        contract=SUCCESSOR_INTRADAY_RULE_CONTRACT,
        policy_id="pract_vwap_reclaim_reject_v1",
        session_date=session.isoformat(),
        ready=True,
        fired=True,
        direction="LONG",
        signal_available_at_utc=(signal_bar.timestamp_utc + timedelta(minutes=1)).isoformat(),
        reason_codes=("TEST",),
        evidence={},
    )
    short_signal = SuccessorIntradaySignal(
        contract=SUCCESSOR_INTRADAY_RULE_CONTRACT,
        policy_id="pract_vwap_reclaim_reject_v1",
        session_date=session.isoformat(),
        ready=True,
        fired=True,
        direction="SHORT",
        signal_available_at_utc=(signal_bar.timestamp_utc + timedelta(minutes=1)).isoformat(),
        reason_codes=("TEST",),
        evidence={},
    )
    assert engine._stop_for_successor_signal(
        long_signal, [signal_bar], prior_regular_close=None
    ) == pytest.approx(98.0)
    assert engine._stop_for_successor_signal(
        short_signal, [signal_bar], prior_regular_close=None
    ) == pytest.approx(101.0)
