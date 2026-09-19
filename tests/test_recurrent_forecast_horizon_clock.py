from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import (
    ActionabilityPolicy,
    InstrumentKind,
    TradeExpressionMode,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
)
from packages.simulation.decision_record import (
    build_simulation_decision_record,
    economic_candidate_fingerprint,
)
from packages.simulation.open_position_state import (
    SimulatedOpenPositionV1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    StockExitPolicyInputsV1,
    build_recurrent_decision_stock_exit_plan_v1,
)
from packages.simulation.recurrent_forecast_horizon_clock import (
    RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
    RecurrentForecastHorizonClockError,
    build_recurrent_forecast_horizon_clock_v1,
)


EASTERN = ZoneInfo("America/New_York")


def _threshold(
    fraction: float,
    *,
    median_time: float,
) -> MoveThresholdProbability:
    return MoveThresholdProbability(
        threshold_fraction=fraction,
        favorable_touch_probability=0.50,
        adverse_touch_probability=0.20,
        favorable_before_adverse_probability=0.40,
        adverse_before_favorable_probability=0.10,
        same_interval_collision_probability=0.02,
        median_favorable_time=median_time,
    )


def _plan(
    *,
    opened_utc: datetime,
    horizon_unit: ForecastHorizonUnit,
    horizon_value: int,
):
    forecast_created = opened_utc - timedelta(minutes=2)
    forecast = UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id="iid-AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=forecast_created,
        evidence_cutoff_utc=forecast_created - timedelta(minutes=1),
        horizon_unit=horizon_unit,
        horizon_value=horizon_value,
        method_id="clock-fixture-v1",
        source_label="clock fixture",
        source_fingerprint="1" * 64,
        sample_size=500,
        reference_price=100.0,
        mean_signed_return=0.01,
        median_signed_return=0.008,
        p10_signed_return=-0.02,
        p25_signed_return=-0.005,
        p75_signed_return=0.02,
        p90_signed_return=0.04,
        probability_positive_return=0.60,
        mean_mfe=0.03,
        mean_mae=0.01,
        thresholds=(
            _threshold(
                0.01,
                median_time=min(20.0, float(horizon_value)),
            ),
            _threshold(
                0.02,
                median_time=min(40.0, float(horizon_value)),
            ),
        ),
        uncertainty_score=0.25,
        reason_codes=("CLOCK_FIXTURE",),
    )
    record = build_simulation_decision_record(
        decision_created_utc=opened_utc - timedelta(minutes=1),
        forecast=forecast,
        stock_inputs=StockEconomicsInputs(
            position_notional_dollars=10_000.0,
            capital_required_dollars=10_000.0,
            entry_slippage_bps=0.0,
            exit_slippage_bps=0.0,
            round_trip_commission_dollars=0.0,
            round_trip_fees_dollars=0.0,
            horizon_borrow_cost_dollars=0.0,
            horizon_financing_cost_dollars=0.0,
            net_probability_profit=0.55,
            liquidity_score=0.90,
            executable=True,
            risk_budget_ok=True,
        ),
        actionability_policy=ActionabilityPolicy(
            min_expected_net_value=1.0,
            min_expected_return_on_capital=0.001,
            min_probability_profit=0.50,
            max_expected_loss_to_gain_ratio=1.0,
            max_execution_cost_to_expected_gain_ratio=0.50,
            min_liquidity_score=0.50,
            material_superiority_ratio=1.20,
        ),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
    )
    candidate = record.trade_expression_decision.chosen_candidate
    assert candidate is not None
    candidate_fp = economic_candidate_fingerprint(candidate)
    position = SimulatedOpenPositionV1(
        source_account_state_fingerprint="a" * 64,
        decision_record_fingerprint=record.record_fingerprint,
        candidate_fingerprint=candidate_fp,
        fill_fingerprint="b" * 64,
        funding_terms_fingerprint="c" * 64,
        reservation_fingerprint="d" * 64,
        option_reservation_terms_fingerprint=None,
        option_economics_result_fingerprint=None,
        instrument_kind=InstrumentKind.STOCK,
        instrument_id=forecast.instrument_id,
        ticker=forecast.ticker,
        direction=forecast.direction,
        candidate_identifier=candidate.identifier,
        option_contract_ticker=None,
        option_contract_type=None,
        opened_utc=opened_utc,
        quantity=100.0,
        quantity_unit="SHARES",
        entry_price_per_unit=100.0,
        contract_multiplier=1.0,
        entry_book_value_dollars=10_000.0,
        entry_fees_dollars=0.0,
        all_in_cash_cost_basis_dollars=10_000.0,
        original_reserved_capital_dollars=10_000.0,
        supplemental_cash_consumed_dollars=0.0,
        unspent_reserve_returned_dollars=0.0,
        stock_gross_entry_exposure_dollars=10_000.0,
        option_premium_at_risk_dollars=0.0,
        option_signed_delta_equivalent_entry_reference_dollars=0.0,
        option_abs_delta_equivalent_entry_reference_dollars=0.0,
        reason_codes=("CLOCK_FIXTURE_POSITION",),
    )
    return build_recurrent_decision_stock_exit_plan_v1(
        source_recurrent_state_fingerprint="f" * 64,
        position=position,
        decision_record=record,
        exit_policy=StockExitPolicyInputsV1(
            policy_id="clock-fixture-exit-policy-v1",
            policy_fingerprint="e" * 64,
            stop_threshold_fraction=0.01,
            target_threshold_fraction=0.02,
        ),
        plan_created_utc=opened_utc,
    )


def _et(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=EASTERN,
    ).astimezone(UTC)


def test_forecast_horizon_clock_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        == "12de0a1214dac8fe566e0eb33ea8de34b5ec5729ab32411625431f778033fe53"
    )


def test_minute_horizon_uses_regular_session_elapsed_time() -> None:
    plan = _plan(
        opened_utc=_et(2026, 9, 18, 10, 0),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=240,
    )
    clock = build_recurrent_forecast_horizon_clock_v1(
        plan=plan
    )
    assert clock.deadline_utc == _et(2026, 9, 18, 14, 0)
    assert clock.session_dates == (
        datetime(2026, 9, 18).date(),
    )
    assert clock.regular_session_elapsed_minutes == 240
    assert clock.time_exit_trigger_authority is False
    assert clock.close_fill_authority is False


def test_minute_horizon_pauses_over_weekend() -> None:
    plan = _plan(
        opened_utc=_et(2026, 9, 18, 15, 0),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=120,
    )
    clock = build_recurrent_forecast_horizon_clock_v1(
        plan=plan
    )
    assert clock.deadline_utc == _et(2026, 9, 21, 10, 30)
    assert clock.session_dates == (
        datetime(2026, 9, 18).date(),
        datetime(2026, 9, 21).date(),
    )


def test_minute_horizon_respects_thanksgiving_and_early_close() -> None:
    plan = _plan(
        opened_utc=_et(2026, 11, 25, 15, 0),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=390,
    )
    clock = build_recurrent_forecast_horizon_clock_v1(
        plan=plan
    )
    assert clock.deadline_utc == _et(2026, 11, 30, 11, 30)
    assert clock.session_dates == (
        datetime(2026, 11, 25).date(),
        datetime(2026, 11, 27).date(),
        datetime(2026, 11, 30).date(),
    )


def test_session_horizon_counts_entry_session_as_session_one() -> None:
    plan = _plan(
        opened_utc=_et(2026, 11, 25, 15, 0),
        horizon_unit=ForecastHorizonUnit.SESSIONS,
        horizon_value=2,
    )
    clock = build_recurrent_forecast_horizon_clock_v1(
        plan=plan
    )
    assert clock.deadline_utc == _et(2026, 11, 27, 13, 0)
    assert clock.session_dates == (
        datetime(2026, 11, 25).date(),
        datetime(2026, 11, 27).date(),
    )
    assert clock.included_session_count == 2
    assert clock.regular_session_elapsed_minutes is None


def test_clock_is_deterministic_and_binds_plan_forecast_position() -> None:
    plan = _plan(
        opened_utc=_et(2026, 9, 18, 10, 0),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=60,
    )
    first = build_recurrent_forecast_horizon_clock_v1(
        plan=plan
    )
    second = build_recurrent_forecast_horizon_clock_v1(
        plan=plan
    )
    assert first == second
    assert first.clock_fingerprint == second.clock_fingerprint
    assert first.source_exit_plan_fingerprint == plan.plan_fingerprint
    assert first.source_forecast_fingerprint == plan.forecast_fingerprint
    assert first.position_fingerprint == plan.position_fingerprint
    assert first.deadline_utc == _et(2026, 9, 18, 11, 0)


def test_clock_rejects_position_opened_outside_regular_session() -> None:
    plan = _plan(
        opened_utc=_et(2026, 9, 18, 8, 0),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=60,
    )
    with pytest.raises(
        RecurrentForecastHorizonClockError,
        match="regular-session position open",
    ):
        build_recurrent_forecast_horizon_clock_v1(
            plan=plan
        )
