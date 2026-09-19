from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from packages.backtesting.recurrent_successor_daily_exit_sweep import (
    DailyPathBar,
    DailyPathCase,
    PriorPathEvidence,
    _forecast_for_case,
    resolve_daily_exit,
)
from packages.backtesting.recurrent_successor_daily_exit_sweep_contract import (
    AUTHORITY,
    RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
    STOP_TARGET_POLICY_PAIRS,
    recurrent_successor_daily_exit_sweep_manifest,
)
from packages.backtesting.recurrent_successor_outcome_replay import (
    SelectedReplayOpportunity,
)
from packages.schemas.move_time_forecast import MoveThresholdProbability


def _threshold(value: float) -> MoveThresholdProbability:
    return MoveThresholdProbability(
        threshold_fraction=value,
        favorable_touch_probability=0.5,
        adverse_touch_probability=0.5,
        favorable_before_adverse_probability=0.2,
        adverse_before_favorable_probability=0.2,
        same_interval_collision_probability=0.1,
        median_favorable_time=2.0,
    )


def _case(bars: tuple[DailyPathBar, ...]) -> DailyPathCase:
    opportunity = SelectedReplayOpportunity(
        opportunity_id="1" * 64,
        fold_id=10,
        policy_id="synthetic_daily_v1",
        economic_family_id="synthetic_family",
        native_timeframe="1d",
        instrument_id="SYNTH",
        ticker="SYNTH",
        signal_session=date(2025, 1, 2),
        direction="LONG",
        fallback_level=5,
        selector_score=0.01,
        primary_net_return=0.01,
        gross_return=0.011,
        liquidity_bucket="GE_250M",
        decision_utc=datetime(2025, 1, 2, 21, 0, tzinfo=UTC),
        entry_utc=datetime(2025, 1, 3, 14, 30, tzinfo=UTC),
        exit_utc=datetime(2025, 1, 9, 21, 0, tzinfo=UTC),
        round_trip_cost_bps=10.0,
        training_start=date(2023, 1, 3),
        training_end=date(2024, 12, 31),
        training_sample_size=200,
        training_mean_gross_return=0.02,
        training_p10_gross_return=-0.02,
        training_p25_gross_return=-0.005,
        training_median_gross_return=0.01,
        training_p75_gross_return=0.03,
        training_p90_gross_return=0.05,
        training_probability_positive_gross=0.60,
        training_probability_positive_net=0.55,
        training_mean_mfe=0.04,
        training_mean_mae=0.02,
        training_max_abs_excursion=0.08,
        training_median_holding_minutes=None,
        source_analysis_fingerprint="a" * 64,
    )
    prior = PriorPathEvidence(
        fold_id=10,
        policy_id="synthetic_daily_v1",
        direction="LONG",
        sample_size=100,
        evidence_cutoff_session=date(2024, 12, 30),
        thresholds=tuple(_threshold(value) for value in (0.01, 0.02, 0.03, 0.05)),
        source_fingerprint="b" * 64,
    )
    return DailyPathCase(
        opportunity=opportunity,
        bars=bars,
        prior_path_evidence=prior,
    )


def _bar(
    offset: int,
    session: date,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> DailyPathBar:
    return DailyPathBar(
        session_offset=offset,
        session_date=session,
        open=open_,
        high=high,
        low=low,
        close=close,
    )


def test_contract_freezes_sixteen_policy_pairs_without_authority() -> None:
    manifest = recurrent_successor_daily_exit_sweep_manifest()
    assert manifest["fingerprint"] == RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT
    assert len(STOP_TARGET_POLICY_PAIRS) == 16
    assert len(set(STOP_TARGET_POLICY_PAIRS)) == 16
    assert AUTHORITY["consumed_master_rows_permitted"] == 0
    assert AUTHORITY["future_blind_rows_permitted"] == 0
    assert AUTHORITY["paper_authority"] is False
    assert AUTHORITY["live_authority"] is False
    assert AUTHORITY["strategy_promotion"] is False


def test_same_session_stop_target_collision_resolves_to_stop() -> None:
    case = _case(
        (
            _bar(
                1,
                date(2025, 1, 3),
                open_=100.0,
                high=103.0,
                low=97.0,
                close=101.0,
            ),
            _bar(2, date(2025, 1, 6), open_=101.0, high=102.0, low=100.0, close=101.0),
            _bar(3, date(2025, 1, 7), open_=101.0, high=102.0, low=100.0, close=101.0),
            _bar(4, date(2025, 1, 8), open_=101.0, high=102.0, low=100.0, close=101.0),
            _bar(5, date(2025, 1, 9), open_=101.0, high=102.0, low=100.0, close=101.0),
        )
    )
    result = resolve_daily_exit(case, stop_fraction=0.02, target_fraction=0.02)
    assert result.disposition == "STOP"
    assert result.exit_session_offset == 1
    assert result.exit_price_per_unit == pytest.approx(98.0)
    assert result.same_session_collision is True


def test_gap_through_stop_fills_at_worse_open() -> None:
    case = _case(
        (
            _bar(1, date(2025, 1, 3), open_=100.0, high=101.0, low=99.0, close=100.0),
            _bar(2, date(2025, 1, 6), open_=96.0, high=102.0, low=95.0, close=101.0),
            _bar(3, date(2025, 1, 7), open_=101.0, high=102.0, low=100.0, close=101.0),
            _bar(4, date(2025, 1, 8), open_=101.0, high=102.0, low=100.0, close=101.0),
            _bar(5, date(2025, 1, 9), open_=101.0, high=102.0, low=100.0, close=101.0),
        )
    )
    result = resolve_daily_exit(case, stop_fraction=0.02, target_fraction=0.05)
    assert result.disposition == "STOP"
    assert result.exit_session_offset == 2
    assert result.exit_price_per_unit == pytest.approx(96.0)
    assert result.gap_through_stop is True
    assert result.same_session_collision is False


def test_gap_through_target_does_not_grant_positive_slippage() -> None:
    case = _case(
        (
            _bar(1, date(2025, 1, 3), open_=100.0, high=101.0, low=99.0, close=100.0),
            _bar(2, date(2025, 1, 6), open_=104.0, high=105.0, low=103.0, close=104.0),
            _bar(3, date(2025, 1, 7), open_=104.0, high=105.0, low=103.0, close=104.0),
            _bar(4, date(2025, 1, 8), open_=104.0, high=105.0, low=103.0, close=104.0),
            _bar(5, date(2025, 1, 9), open_=104.0, high=105.0, low=103.0, close=104.0),
        )
    )
    result = resolve_daily_exit(case, stop_fraction=0.02, target_fraction=0.03)
    assert result.disposition == "TARGET"
    assert result.exit_session_offset == 2
    assert result.exit_price_per_unit == pytest.approx(103.0)
    assert result.gap_through_target is True
    assert result.same_session_collision is False


def test_no_trigger_exits_at_fifth_session_close() -> None:
    case = _case(
        (
            _bar(1, date(2025, 1, 3), open_=100.0, high=100.8, low=99.2, close=100.2),
            _bar(2, date(2025, 1, 6), open_=100.2, high=100.9, low=99.3, close=100.1),
            _bar(3, date(2025, 1, 7), open_=100.1, high=100.7, low=99.4, close=100.3),
            _bar(4, date(2025, 1, 8), open_=100.3, high=100.8, low=99.5, close=100.4),
            _bar(5, date(2025, 1, 9), open_=100.4, high=100.9, low=99.6, close=100.6),
        )
    )
    result = resolve_daily_exit(case, stop_fraction=0.02, target_fraction=0.02)
    assert result.disposition == "TIME"
    assert result.exit_session_offset == 5
    assert result.exit_price_per_unit == pytest.approx(100.6)


def test_current_opportunity_outcome_cannot_change_exit_sweep_forecast() -> None:
    bars = (
        _bar(1, date(2025, 1, 3), open_=100.0, high=101.0, low=99.0, close=100.2),
        _bar(2, date(2025, 1, 6), open_=100.2, high=101.0, low=99.2, close=100.3),
        _bar(3, date(2025, 1, 7), open_=100.3, high=101.1, low=99.3, close=100.4),
        _bar(4, date(2025, 1, 8), open_=100.4, high=101.2, low=99.4, close=100.5),
        _bar(5, date(2025, 1, 9), open_=100.5, high=101.3, low=99.5, close=100.6),
    )
    original = _case(bars)
    changed = DailyPathCase(
        opportunity=replace(
            original.opportunity,
            gross_return=-0.75,
            primary_net_return=-0.751,
        ),
        bars=original.bars,
        prior_path_evidence=original.prior_path_evidence,
    )
    assert _forecast_for_case(original) == _forecast_for_case(changed)
