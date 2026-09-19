from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.core.enums import SessionSegment
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.execution.current_webull_quote_bundle import (
    CurrentWebullStockQuoteV1,
    build_current_webull_stock_quote_bundle_v1,
)
from packages.execution.current_webull_stock_entry import (
    build_current_webull_stock_entry_evidence_bundle_v1,
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
from packages.simulation.recurrent_cycle_runner import (
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
    RecurrentDecisionStockExitPlanError,
    StockExitPolicyInputsV1,
    build_recurrent_decision_stock_exit_plan_book_v1,
    build_recurrent_decision_stock_exit_plan_v1,
    read_recurrent_decision_stock_exit_plan_book_v1,
    write_recurrent_decision_stock_exit_plan_book_v1,
)
from packages.simulation.recurrent_exit_fill import (
    RecurrentExitFillInputsV1,
    build_recurrent_exit_fill_evidence,
)
from packages.simulation.recurrent_genesis import (
    bootstrap_recurrent_genesis_v1,
)
from packages.simulation.recurrent_reserve_evidence import (
    build_recurrent_reserve_evidence_bundle_v1,
)


SLOT = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
FEE_SOURCE_FP = "f" * 64
POLICY_FP = "e" * 64


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


def _forecast() -> UnderlyingMoveTimeForecast:
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id="iid-AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=SLOT + timedelta(seconds=1),
        evidence_cutoff_utc=SLOT,
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=240,
        method_id="accepted-product-fixture-v1",
        source_label="accepted product fixture",
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
                median_time=20.0,
            ),
            _threshold(
                0.02,
                favorable=0.45,
                adverse=0.20,
                favorable_first=0.34,
                adverse_first=0.12,
                median_time=45.0,
            ),
        ),
        uncertainty_score=0.25,
        reason_codes=("ACCEPTED_PRODUCT_FIXTURE",),
    )


def _record():
    return build_simulation_decision_record(
        decision_created_utc=SLOT + timedelta(seconds=2),
        forecast=_forecast(),
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
        schedule_id="four-hour-simulation",
        scheduled_for_utc=SLOT,
    )


def _policy(
    *,
    stop: float = 0.01,
    target: float = 0.02,
) -> StockExitPolicyInputsV1:
    return StockExitPolicyInputsV1(
        policy_id="fixture-stock-exit-policy-v1",
        policy_fingerprint=POLICY_FP,
        stop_threshold_fraction=stop,
        target_threshold_fraction=target,
    )


def _open_position_runtime(settings):
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=SLOT,
    )
    record = _record()
    reserve_bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=_identity(),
        decisions=((record, None),),
        built_at_utc=SLOT + timedelta(seconds=5),
    )
    runtime.apply_reservation_batch(
        reserve_bundle.runner_decisions
    )

    received = SLOT + timedelta(seconds=8)
    quote = CurrentWebullStockQuoteV1(
        symbol="AAPL",
        provider_timestamp_utc=received - timedelta(seconds=1),
        received_at_utc=received,
        session_date=received.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=100.0,
        bid_size=10,
        ask_price=100.25,
        ask_size=12,
    )
    quote_bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(quote,),
        captured_at_utc=SLOT + timedelta(seconds=9),
    )
    entry_bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve_bundle,
        quote_bundle=quote_bundle,
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 2.50,
        },
        fee_source_id="explicit-test-fees-v1",
        fee_source_fingerprint=FEE_SOURCE_FP,
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    runtime.apply_entry_batch(entry_bundle.runner_entries)
    return runtime, record, reserve_bundle


def test_decision_stock_exit_plan_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        == "445d820b0d4268f10d66b842e3ed341ccadd94363418edf2f4ff30f755e44754"
    )


def test_exit_plan_uses_explicit_forecast_thresholds_and_actual_fill(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    runtime, record, reserve_bundle = _open_position_runtime(
        settings
    )
    state = runtime.current_account().state
    assert len(state.open_positions) == 1
    position = state.open_positions[0]

    book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=state,
        current_reserve_bundle=reserve_bundle,
        existing_book=None,
        exit_policy_by_decision={
            record.record_fingerprint: _policy(),
        },
        built_at_utc=SLOT + timedelta(seconds=11),
    )
    assert len(book.plans) == 1
    plan = book.plans[0]
    assert plan.decision_record == record
    assert plan.actual_entry_price_per_unit == pytest.approx(100.25)
    assert plan.stop_threshold.threshold_fraction == pytest.approx(0.01)
    assert plan.target_threshold.threshold_fraction == pytest.approx(0.02)
    assert plan.stop_price_per_unit == pytest.approx(99.2475)
    assert plan.target_price_per_unit == pytest.approx(102.255)
    assert plan.forecast_horizon_unit == ForecastHorizonUnit.MINUTES
    assert plan.forecast_horizon_value == 240
    assert plan.time_exit_trigger_enabled is False
    assert plan.price_trigger_authority is False
    assert book.provider_reads == 0
    assert book.paper_authority is False

    path = write_recurrent_decision_stock_exit_plan_book_v1(
        settings,
        book,
    )
    restored = read_recurrent_decision_stock_exit_plan_book_v1(
        settings,
        path=path,
    )
    assert restored == book

    carried = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=state,
        current_reserve_bundle=None,
        existing_book=restored,
        exit_policy_by_decision={},
        built_at_utc=SLOT + timedelta(seconds=12),
    )
    assert carried.plans == restored.plans


def test_exit_policy_threshold_must_exist_in_original_forecast(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    runtime, record, _reserve_bundle = _open_position_runtime(
        settings
    )
    position = runtime.current_account().state.open_positions[0]
    with pytest.raises(
        RecurrentDecisionStockExitPlanError,
        match="target threshold must match exactly one accepted forecast threshold",
    ):
        build_recurrent_decision_stock_exit_plan_v1(
            source_recurrent_state_fingerprint=(
                runtime.current_account().state.state_fingerprint
            ),
            position=position,
            decision_record=record,
            exit_policy=_policy(target=0.03),
            plan_created_utc=SLOT + timedelta(seconds=11),
        )


def test_exit_plan_book_prunes_plan_after_authoritative_close(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    runtime, record, reserve_bundle = _open_position_runtime(
        settings
    )
    state = runtime.current_account().state
    position = state.open_positions[0]
    book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=state,
        current_reserve_bundle=reserve_bundle,
        existing_book=None,
        exit_policy_by_decision={
            record.record_fingerprint: _policy(),
        },
        built_at_utc=SLOT + timedelta(seconds=11),
    )

    exit_fill = build_recurrent_exit_fill_evidence(
        source_state=state,
        position_fingerprint=position.position_fingerprint,
        inputs=RecurrentExitFillInputsV1(
            fill_source_id="fixture-close",
            fill_source_fingerprint="d" * 64,
            exited_utc=SLOT + timedelta(seconds=20),
            exit_price_per_unit=101.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )
    runtime.apply_close_batch((exit_fill,))
    closed_state = runtime.current_account().state
    assert closed_state.open_positions == ()

    pruned = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=closed_state,
        current_reserve_bundle=None,
        existing_book=book,
        exit_policy_by_decision={},
        built_at_utc=SLOT + timedelta(seconds=21),
    )
    assert pruned.plans == ()


def test_new_open_position_cannot_lose_original_decision_evidence(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    runtime, record, _reserve_bundle = _open_position_runtime(
        settings
    )
    with pytest.raises(
        RecurrentDecisionStockExitPlanError,
        match="lacks current RESERVE decision evidence",
    ):
        build_recurrent_decision_stock_exit_plan_book_v1(
            source_state=runtime.current_account().state,
            current_reserve_bundle=None,
            existing_book=None,
            exit_policy_by_decision={
                record.record_fingerprint: _policy(),
            },
            built_at_utc=SLOT + timedelta(seconds=11),
        )
