from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.core.enums import SessionSegment
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.execution.current_webull_decision_stock_close import (
    build_current_webull_decision_stock_close_evidence_bundle_v1,
)
from packages.execution.current_webull_quote_bundle import (
    CurrentWebullStockQuoteV1,
    build_current_webull_stock_quote_bundle_v1,
)
from packages.execution.current_webull_stock_entry import (
    build_current_webull_stock_entry_evidence_bundle_v1,
)
from packages.execution.current_webull_time_aware_stock_close import (
    FinalStockCloseDisposition,
    build_current_webull_time_aware_stock_close_bundle_v1,
)
from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import (
    ActionabilityPolicy,
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
)
from packages.simulation.forecast_horizon_clock import (
    ForecastHorizonClockPolicyV1,
)
from packages.simulation.forecast_horizon_clock_book import (
    build_forecast_horizon_clock_book_v1,
)
from packages.simulation.forecast_horizon_time_disposition import (
    ForecastHorizonTimeDispositionKind,
    build_forecast_horizon_time_disposition_bundle_v1,
)
from packages.simulation.recurrent_cycle import RecurrentCycleStage
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunnerV1,
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    StockExitPolicyInputsV1,
    build_recurrent_decision_stock_exit_plan_book_v1,
)
from packages.simulation.recurrent_genesis import (
    bootstrap_recurrent_genesis_v1,
)
from packages.simulation.recurrent_production_cycle import (
    RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT,
    RecurrentProductionCycleError,
    RecurrentProductionCycleV1,
)
from packages.simulation.recurrent_reserve_evidence import (
    build_recurrent_reserve_evidence_bundle_v1,
)
from packages.simulation.recurrent_time_aware_production_cycle import (
    RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT,
    RecurrentTimeAwareProductionCycleError,
    RecurrentTimeAwareProductionCycleV1,
)


TIME_SLOT = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
ENTRY_FEE_SOURCE_FP = "f" * 64
EXIT_FEE_SOURCE_FP = "c" * 64
EXIT_POLICY_FP = "e" * 64
TIME_EXIT_FEE_SOURCE_FP = "9" * 64


def _settings(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(
        update={"live": tmp_path / "live"}
    )
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _threshold(
    fraction: float,
    *,
    favorable: float,
    adverse: float,
    favorable_first: float,
    adverse_first: float,
    median_time: float,
) -> MoveThresholdProbability:
    return MoveThresholdProbability(
        threshold_fraction=fraction,
        favorable_touch_probability=favorable,
        adverse_touch_probability=adverse,
        favorable_before_adverse_probability=favorable_first,
        adverse_before_favorable_probability=adverse_first,
        same_interval_collision_probability=0.02,
        median_favorable_time=median_time,
    )


def _record():
    forecast = UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id="iid-AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=TIME_SLOT + timedelta(seconds=1),
        evidence_cutoff_utc=TIME_SLOT,
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=1,
        method_id="time-aware-production-fixture-v1",
        source_label="time-aware production fixture",
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
                favorable=0.60,
                adverse=0.30,
                favorable_first=0.45,
                adverse_first=0.18,
                median_time=0.25,
            ),
            _threshold(
                0.02,
                favorable=0.45,
                adverse=0.20,
                favorable_first=0.34,
                adverse_first=0.12,
                median_time=0.50,
            ),
        ),
        uncertainty_score=0.25,
        reason_codes=("TIME_AWARE_PRODUCTION_FIXTURE",),
    )
    return build_simulation_decision_record(
        decision_created_utc=TIME_SLOT + timedelta(seconds=2),
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


def _identity():
    return build_recurrent_cycle_run_identity_v1(
        schedule_id="time-aware-production-fixture",
        scheduled_for_utc=TIME_SLOT,
    )


def _open_position_plan_and_clock(settings):
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=TIME_SLOT,
    )
    record = _record()
    reserve_bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=_identity(),
        decisions=((record, None),),
        built_at_utc=TIME_SLOT + timedelta(seconds=5),
    )
    runtime.apply_reservation_batch(
        reserve_bundle.runner_decisions
    )

    entry_received = TIME_SLOT + timedelta(seconds=8)
    entry_quote = CurrentWebullStockQuoteV1(
        symbol="AAPL",
        provider_timestamp_utc=entry_received - timedelta(seconds=1),
        received_at_utc=entry_received,
        session_date=entry_received.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=100.0,
        bid_size=10,
        ask_price=100.25,
        ask_size=12,
    )
    entry_quote_bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(entry_quote,),
        captured_at_utc=TIME_SLOT + timedelta(seconds=9),
    )
    entry_bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve_bundle,
        quote_bundle=entry_quote_bundle,
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 2.50,
        },
        fee_source_id="time-aware-production-entry-fees",
        fee_source_fingerprint=ENTRY_FEE_SOURCE_FP,
        built_at_utc=TIME_SLOT + timedelta(seconds=10),
    )
    runtime.apply_entry_batch(entry_bundle.runner_entries)

    plan_book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=runtime.current_account().state,
        current_reserve_bundle=reserve_bundle,
        existing_book=None,
        exit_policy_by_decision={
            record.record_fingerprint: StockExitPolicyInputsV1(
                policy_id="time-aware-production-exit-policy-v1",
                policy_fingerprint=EXIT_POLICY_FP,
                stop_threshold_fraction=0.01,
                target_threshold_fraction=0.02,
            ),
        },
        built_at_utc=TIME_SLOT + timedelta(seconds=11),
    )
    position_fp = plan_book.plans[0].position_fingerprint
    clock_book = build_forecast_horizon_clock_book_v1(
        source_exit_plan_book=plan_book,
        existing_book=None,
        clock_policy_by_position={
            position_fp: ForecastHorizonClockPolicyV1(),
        },
    )
    assert clock_book.clocks[0].deadline_utc == (
        entry_received + timedelta(minutes=1)
    )
    return checkpoint, runtime, plan_book, clock_book


def _final_time_close_bundle(runtime, plan_book, clock_book):
    received = TIME_SLOT + timedelta(seconds=70)
    quote = CurrentWebullStockQuoteV1(
        symbol="AAPL",
        provider_timestamp_utc=received - timedelta(seconds=1),
        received_at_utc=received,
        session_date=received.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=100.50,
        bid_size=10,
        ask_price=100.60,
        ask_size=12,
    )
    quote_bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(quote,),
        captured_at_utc=received + timedelta(seconds=1),
    )
    price_bundle = build_current_webull_decision_stock_close_evidence_bundle_v1(
        account=runtime.current_account(),
        identity=_identity(),
        exit_plan_book=plan_book,
        quote_bundle=quote_bundle,
        explicit_exit_fees_by_position={},
        built_at_utc=TIME_SLOT + timedelta(seconds=72),
    )
    time_bundle = build_forecast_horizon_time_disposition_bundle_v1(
        source_clock_book=clock_book,
        evaluation_utc=price_bundle.built_at_utc,
    )
    assert time_bundle.dispositions[0].disposition == (
        ForecastHorizonTimeDispositionKind.TIME_EXPIRED
    )
    position = runtime.current_account().state.open_positions[0]
    final = build_current_webull_time_aware_stock_close_bundle_v1(
        account=runtime.current_account(),
        identity=_identity(),
        price_close_bundle=price_bundle,
        time_disposition_bundle=time_bundle,
        explicit_time_exit_fees_by_position={
            position.position_fingerprint: 1.10,
        },
        time_fee_source_id="time-aware-production-time-fees",
        time_fee_source_fingerprint=TIME_EXIT_FEE_SOURCE_FP,
    )
    assert final.rows[0].final_disposition == (
        FinalStockCloseDisposition.TIME
    )
    return final


def _production(settings, checkpoint, runtime):
    return RecurrentTimeAwareProductionCycleV1(
        settings=settings,
        runner=RecurrentCycleRunnerV1(
            checkpoint_path=checkpoint,
            runtime=runtime,
        ),
        identity=_identity(),
    )


def test_time_aware_production_cycle_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT
        == "c03e6e299076618a537e8ab2d7ebd575b33f22924f25fc1f0ba655f10e7412ca"
    )
    assert (
        RECURRENT_TIME_AWARE_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT
        == "c16ce1d4b9923d857673a92e6a4378a76699d6413ccf3ee8dbed9b138a894e84"
    )


def test_time_aware_production_close_executes_time_and_exact_retry_is_idempotent(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    checkpoint, runtime, plan_book, clock_book = (
        _open_position_plan_and_clock(settings)
    )
    final = _final_time_close_bundle(
        runtime,
        plan_book,
        clock_book,
    )
    production = _production(
        settings,
        checkpoint,
        runtime,
    )
    production.begin(
        now_utc=TIME_SLOT + timedelta(seconds=60),
    )
    first = production.apply_close(
        bundle=final,
        now_utc=TIME_SLOT + timedelta(seconds=73),
    )
    assert tuple(stage.stage for stage in first.stages) == (
        RecurrentCycleStage.CLOSE,
    )
    assert runtime.current_account().state.open_positions == ()
    assert len(runtime.current_account().state.closed_trades) == 1

    retry = production.apply_close(
        bundle=final,
        now_utc=TIME_SLOT + timedelta(seconds=74),
    )
    assert retry == first
    assert len(runtime.current_account().state.closed_trades) == 1


def test_time_aware_production_restore_reuses_recorded_close(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    checkpoint, runtime, plan_book, clock_book = (
        _open_position_plan_and_clock(settings)
    )
    final = _final_time_close_bundle(
        runtime,
        plan_book,
        clock_book,
    )
    production = _production(
        settings,
        checkpoint,
        runtime,
    )
    production.begin(
        now_utc=TIME_SLOT + timedelta(seconds=60),
    )
    first = production.apply_close(
        bundle=final,
        now_utc=TIME_SLOT + timedelta(seconds=73),
    )

    restored = RecurrentTimeAwareProductionCycleV1.restore(
        settings=settings,
        checkpoint_path=checkpoint,
        identity=_identity(),
    )
    assert isinstance(
        restored,
        RecurrentTimeAwareProductionCycleV1,
    )
    retry = restored.apply_close(
        bundle=final,
        now_utc=TIME_SLOT + timedelta(seconds=74),
    )
    assert retry == first
    assert len(
        restored.runner.runtime.current_account().state.closed_trades
    ) == 1


def test_time_aware_production_rejects_stale_first_close(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    checkpoint, runtime, plan_book, clock_book = (
        _open_position_plan_and_clock(settings)
    )
    final = _final_time_close_bundle(
        runtime,
        plan_book,
        clock_book,
    )
    runtime.apply_close_batch(final.triggered_fills)
    production = _production(
        settings,
        checkpoint,
        runtime,
    )
    production.begin(
        now_utc=TIME_SLOT + timedelta(seconds=60),
    )

    with pytest.raises(
        RecurrentTimeAwareProductionCycleError,
        match="stale for current recurrent state",
    ):
        production.apply_close(
            bundle=final,
            now_utc=TIME_SLOT + timedelta(seconds=73),
        )


def test_base_production_v1_remains_separate_from_time_aware_close(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    checkpoint, runtime, plan_book, clock_book = (
        _open_position_plan_and_clock(settings)
    )
    final = _final_time_close_bundle(
        runtime,
        plan_book,
        clock_book,
    )
    base = RecurrentProductionCycleV1(
        settings=settings,
        runner=RecurrentCycleRunnerV1(
            checkpoint_path=checkpoint,
            runtime=runtime,
        ),
        identity=_identity(),
    )
    base.begin(
        now_utc=TIME_SLOT + timedelta(seconds=60),
    )

    with pytest.raises(
        RecurrentProductionCycleError,
        match="production CLOSE bundle contract fingerprint mismatch",
    ):
        base.apply_close(
            bundle=final,  # type: ignore[arg-type]
            now_utc=TIME_SLOT + timedelta(seconds=73),
        )
