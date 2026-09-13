from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pandas.testing as pdt

from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.features.successor_practitioner import (
    SUCCESSOR_DAILY_DERIVED_COLUMNS,
    adx_dmi,
    compute_successor_daily_features,
    confirmed_pivot_levels,
    successor_common_context_from_row,
    successor_practitioner_feature_fingerprint,
)
from packages.schemas.market import CanonicalBar
from packages.strategies.successor_intraday_rules import (
    evaluate_gap_quality_condition_long,
    evaluate_orb_15m_close_retest,
    evaluate_orb_stocks_in_play_5m,
    evaluate_premarket_relvol_quality,
    evaluate_session_failed_break_reclaim,
    evaluate_vwap_reclaim_reject,
    successor_intraday_rule_fingerprint,
)
from packages.strategies.successor_practitioner_lab import B35_CHALLENGERS, NEW_FAMILIES, SHARED_PIT_CONTEXT
from packages.strategies.successor_practitioner_rules import (
    B35_CHALLENGER_IMPLEMENTATIONS,
    NEW_POLICY_IMPLEMENTATIONS,
    SUCCESSOR_POLICY_IMPLEMENTATION_FINGERPRINT,
    frozen_successor_implementation_manifest,
)


NY = ZoneInfo("America/New_York")


def _bar(
    session: date,
    hh: int,
    mm: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 100_000.0,
    segment: SessionSegment = SessionSegment.REGULAR,
) -> CanonicalBar:
    local = datetime.combine(session, time(hh, mm), tzinfo=NY)
    return CanonicalBar(
        symbol="TEST",
        timestamp_utc=local.astimezone(UTC),
        session_date=session,
        timeframe=Timeframe.MINUTE_1,
        session_segment=segment,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id=f"test-{hh:02d}{mm:02d}",
        is_adjusted=False,
    )


def _decision(session: date, hh: int, mm: int, second: int = 0) -> datetime:
    return datetime.combine(session, time(hh, mm, second), tzinfo=NY).astimezone(UTC)


def _daily_fixture(rows: int = 320) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2020-01-02", periods=rows)
    x = np.arange(rows, dtype="float64")
    close = 50.0 + 0.04 * x + 1.5 * np.sin(x / 8.0)
    open_ = close * (1.0 + 0.001 * np.sin(x / 5.0))
    high = np.maximum(open_, close) + 0.75
    low = np.minimum(open_, close) - 0.75
    frame = pd.DataFrame(
        {
            "instrument_id": "iid-test",
            "ticker": "TEST",
            "session_date": dates.date,
            "timestamp_utc": dates.tz_localize("UTC") + pd.Timedelta(hours=21),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1_000_000.0 + 5_000.0 * (x % 20),
            "unadjusted_close": close,
            "pit_active": True,
            "security_type": "CS",
            "identity_clear": True,
            "price_adjustment_mode": "SPLIT_ADJUSTED",
            "raw_price_lineage_id": "lineage-test",
        }
    )
    benchmark = pd.DataFrame(
        {
            "session_date": dates.date,
            "close": 100.0 + 0.02 * x + 0.75 * np.sin(x / 11.0),
        }
    )
    return frame, benchmark


def test_implementation_roster_matches_frozen_successor_lab() -> None:
    assert {item.policy_id for item in NEW_POLICY_IMPLEMENTATIONS} == {
        item.policy_id for item in NEW_FAMILIES
    }
    assert {item.policy_id for item in B35_CHALLENGER_IMPLEMENTATIONS} == {
        item.policy_id for item in B35_CHALLENGERS
    }
    assert all(item.same_family_for_multiplicity for item in B35_CHALLENGER_IMPLEMENTATIONS)
    manifest = frozen_successor_implementation_manifest()
    assert manifest["fingerprint"] == SUCCESSOR_POLICY_IMPLEMENTATION_FINGERPRINT
    assert manifest["authority"]["outcome_access_authorized_by_this_manifest"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_feature_and_intraday_fingerprints_are_stable_sha256() -> None:
    assert len(successor_practitioner_feature_fingerprint()) == 64
    assert len(successor_intraday_rule_fingerprint()) == 64
    int(successor_practitioner_feature_fingerprint(), 16)
    int(successor_intraday_rule_fingerprint(), 16)


def test_confirmed_pivot_waits_for_both_right_bars() -> None:
    high = pd.Series([1.0, 2.0, 5.0, 2.0, 1.0, 1.5])
    low = pd.Series([0.5, 0.8, 1.0, 0.8, 0.5, 0.7])
    pivots = confirmed_pivot_levels(high, low, radius=2)
    assert pivots["confirmed_pivot_high"].iloc[:4].isna().all()
    assert pivots["confirmed_pivot_high"].iloc[4] == 5.0
    assert pivots["confirmed_pivot_high_center_position"].iloc[4] == 2.0


def test_adx_dmi_identifies_clean_uptrend_without_future_data() -> None:
    close = pd.Series(np.linspace(10.0, 20.0, 80))
    high = close + 0.5
    low = close - 0.5
    result = adx_dmi(high, low, close)
    final = result.iloc[-1]
    assert final["plus_di_14"] > final["minus_di_14"]
    assert final["adx_14"] > 25.0


def test_successor_daily_overlay_contains_all_shared_features_and_is_future_blind() -> None:
    frame, benchmark = _daily_fixture()
    baseline = compute_successor_daily_features(frame, benchmark_frame=benchmark)
    for column in SUCCESSOR_DAILY_DERIVED_COLUMNS:
        assert column in baseline.columns

    context = successor_common_context_from_row(baseline.iloc[-1].to_dict())
    assert set(context) == set(SHARED_PIT_CONTEXT)

    changed_frame = frame.copy()
    changed_benchmark = benchmark.copy()
    changed_frame.loc[len(changed_frame) - 1, ["open", "high", "low", "close", "unadjusted_close"]] = [200.0, 205.0, 195.0, 202.0, 202.0]
    changed_benchmark.loc[len(changed_benchmark) - 1, "close"] = 500.0
    changed = compute_successor_daily_features(changed_frame, benchmark_frame=changed_benchmark)

    compare_columns = list(SUCCESSOR_DAILY_DERIVED_COLUMNS)
    pdt.assert_frame_equal(
        baseline.loc[: len(baseline) - 2, compare_columns].reset_index(drop=True),
        changed.loc[: len(changed) - 2, compare_columns].reset_index(drop=True),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def test_vwap_reclaim_uses_only_fully_closed_bars() -> None:
    session = date(2026, 9, 10)
    bars = [
        _bar(session, 9, 30, open_=10.0, high=10.4, low=9.6, close=9.8),
        _bar(session, 9, 31, open_=9.8, high=10.6, low=9.8, close=10.5),
    ]
    early = evaluate_vwap_reclaim_reject(bars, session_date=session, decision_time_utc=_decision(session, 9, 31, 30))
    assert early.ready is False
    result = evaluate_vwap_reclaim_reject(bars, session_date=session, decision_time_utc=_decision(session, 9, 32))
    assert result.ready is True
    assert result.fired is True
    assert result.direction == "LONG"
    assert result.signal_available_at_utc == _decision(session, 9, 32).isoformat()


def test_failed_break_reclaim_is_objective_and_ambiguous_bars_abstain() -> None:
    session = date(2026, 9, 10)
    long_bar = _bar(session, 10, 0, open_=10.1, high=10.4, low=9.8, close=10.2)
    result = evaluate_session_failed_break_reclaim(
        [long_bar], session_date=session, decision_time_utc=_decision(session, 10, 1),
        prior_regular_high=12.0, prior_regular_low=10.0, premarket_high=11.5, premarket_low=9.9,
    )
    assert result.fired is True
    assert result.direction == "LONG"

    ambiguous = _bar(session, 10, 1, open_=11.0, high=12.2, low=9.8, close=11.0)
    result = evaluate_session_failed_break_reclaim(
        [ambiguous], session_date=session, decision_time_utc=_decision(session, 10, 2),
        prior_regular_high=12.0, prior_regular_low=10.0, premarket_high=None, premarket_low=None,
    )
    assert result.fired is False
    assert "AMBIGUOUS_TWO_SIDED_FAILED_BREAK" in result.reason_codes


def test_gap_quality_challenger_is_not_a_neighbor_threshold_search() -> None:
    session = date(2026, 9, 10)
    result = evaluate_gap_quality_condition_long(
        session_date=session, decision_time_utc=_decision(session, 9, 31), prior_regular_close=10.0,
        current_regular_open=10.25, current_price=10.3, prior_median_dollar_volume_20=25_000_000.0,
        natr_14=0.03, premarket_relvol_20=1.8, split_crossed=False,
    )
    assert result.fired is True
    assert result.direction == "LONG"
    failed = evaluate_gap_quality_condition_long(
        session_date=session, decision_time_utc=_decision(session, 9, 31), prior_regular_close=10.0,
        current_regular_open=10.25, current_price=10.3, prior_median_dollar_volume_20=5_000_000.0,
        natr_14=0.03, premarket_relvol_20=1.8, split_crossed=False,
    )
    assert failed.fired is False


def test_five_minute_orb_requires_stocks_in_play_quality_and_closed_breakout() -> None:
    session = date(2026, 9, 10)
    bars = [
        _bar(session, 9, 30 + minute, open_=10.0, high=10.4 + 0.02 * minute, low=9.6, close=10.0)
        for minute in range(5)
    ]
    bars.append(_bar(session, 9, 35, open_=10.1, high=10.8, low=10.0, close=10.7))
    result = evaluate_orb_stocks_in_play_5m(
        bars, session_date=session, decision_time_utc=_decision(session, 9, 36),
        same_time_opening_relvol=2.2, prior_median_dollar_volume_20=30_000_000.0, current_price=10.7,
    )
    assert result.fired is True
    assert result.direction == "LONG"


def test_15m_orb_retest_requires_break_retest_then_separate_confirmation() -> None:
    session = date(2026, 9, 10)
    opening = [
        _bar(session, 9, 30 + minute, open_=9.5, high=10.0, low=9.0, close=9.5)
        for minute in range(15)
    ]
    bars = opening + [
        _bar(session, 9, 45, open_=9.8, high=10.3, low=9.8, close=10.2),
        _bar(session, 9, 46, open_=10.2, high=10.2, low=9.98, close=10.05),
        _bar(session, 9, 47, open_=10.05, high=10.1, low=10.0, close=10.04),
    ]
    result = evaluate_orb_15m_close_retest(
        bars, session_date=session, decision_time_utc=_decision(session, 9, 48), atr_reference=0.20,
    )
    assert result.fired is True
    assert result.direction == "LONG"
    assert result.signal_available_at_utc == _decision(session, 9, 48).isoformat()


def test_premarket_quality_requires_participation_and_breakout() -> None:
    session = date(2026, 9, 10)
    premarket = [
        _bar(session, 9, minute, open_=10.0, high=10.10, low=9.95, close=10.02, volume=100_000.0, segment=SessionSegment.PREMARKET)
        for minute in range(5)
    ]
    regular = [_bar(session, 9, 30, open_=10.02, high=10.25, low=10.0, close=10.20, volume=200_000.0)]
    result = evaluate_premarket_relvol_quality(
        premarket + regular, session_date=session, decision_time_utc=_decision(session, 9, 31),
        prior_premarket_median_volume_20=200_000.0, prior_median_dollar_volume_20=30_000_000.0,
        current_price=10.2, breakout_same_time_relvol=1.8,
    )
    assert result.fired is True
    assert result.direction == "LONG"
