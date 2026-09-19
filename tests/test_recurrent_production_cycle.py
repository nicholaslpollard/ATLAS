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
from packages.execution.current_webull_stock_mark_adapter import (
    build_current_webull_stock_marks_v1,
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
from packages.simulation.recurrent_cycle import (
    RecurrentCycleStatus,
)
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunnerV1,
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    StockExitPolicyInputsV1,
    build_recurrent_decision_stock_exit_plan_book_v1,
)
from packages.simulation.recurrent_exit_plan_refresh import (
    recurrent_exit_plan_refresh_receipt_path,
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


SLOT = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
ENTRY_FEE_FP = "f" * 64
POLICY_FP = "e" * 64


def _settings(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(
        update={"live": tmp_path / "live"}
    )
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _identity():
    return build_recurrent_cycle_run_identity_v1(
        schedule_id="four-hour-simulation",
        scheduled_for_utc=SLOT,
    )


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
        forecast_created_utc=SLOT + timedelta(seconds=1),
        evidence_cutoff_utc=SLOT,
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=240,
        method_id="production-cycle-fixture-v1",
        source_label="production cycle fixture",
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
        reason_codes=("PRODUCTION_CYCLE_FIXTURE",),
    )
    return build_simulation_decision_record(
        decision_created_utc=SLOT + timedelta(seconds=2),
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


def _policy(
    *,
    stop: float = 0.01,
    target: float = 0.02,
) -> StockExitPolicyInputsV1:
    return StockExitPolicyInputsV1(
        policy_id="production-cycle-exit-policy-v1",
        policy_fingerprint=POLICY_FP,
        stop_threshold_fraction=stop,
        target_threshold_fraction=target,
    )


def _quote(
    *,
    bid: float,
    ask: float,
    received_seconds: int,
):
    received = SLOT + timedelta(seconds=received_seconds)
    return CurrentWebullStockQuoteV1(
        symbol="AAPL",
        provider_timestamp_utc=received - timedelta(seconds=1),
        received_at_utc=received,
        session_date=received.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=bid,
        bid_size=10,
        ask_price=ask,
        ask_size=12,
    )


def _build_through_entry(settings):
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=SLOT,
    )
    runner = RecurrentCycleRunnerV1(
        checkpoint_path=checkpoint,
        runtime=runtime,
    )
    identity = _identity()
    production = RecurrentProductionCycleV1(
        settings=settings,
        runner=runner,
        identity=identity,
    )
    production.begin(
        now_utc=SLOT + timedelta(seconds=3),
    )

    initial_state = runtime.current_account().state
    prior_book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=initial_state,
        current_reserve_bundle=None,
        existing_book=None,
        exit_policy_by_decision={},
        built_at_utc=SLOT + timedelta(seconds=3),
    )
    close_bundle = build_current_webull_decision_stock_close_evidence_bundle_v1(
        account=runtime.current_account(),
        identity=identity,
        exit_plan_book=prior_book,
        quote_bundle=None,
        explicit_exit_fees_by_position={},
        built_at_utc=SLOT + timedelta(seconds=4),
    )
    production.apply_close(
        bundle=close_bundle,
        now_utc=SLOT + timedelta(seconds=4),
    )

    record = _record()
    reserve_bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=identity,
        decisions=((record, None),),
        built_at_utc=SLOT + timedelta(seconds=5),
    )
    production.apply_reserve(
        bundle=reserve_bundle,
        now_utc=SLOT + timedelta(seconds=6),
    )

    entry_quote = _quote(
        bid=100.0,
        ask=100.25,
        received_seconds=8,
    )
    entry_quotes = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(entry_quote,),
        captured_at_utc=SLOT + timedelta(seconds=9),
    )
    entry_bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve_bundle,
        quote_bundle=entry_quotes,
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 2.50,
        },
        fee_source_id="production-cycle-entry-fees-v1",
        fee_source_fingerprint=ENTRY_FEE_FP,
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    production.apply_entry(
        bundle=entry_bundle,
        now_utc=SLOT + timedelta(seconds=11),
    )
    return (
        checkpoint,
        runtime,
        production,
        identity,
        record,
        reserve_bundle,
        entry_bundle,
    )


def _mark_batch(runtime):
    quote = _quote(
        bid=100.40,
        ask=100.50,
        received_seconds=12,
    )
    quotes = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(quote,),
        captured_at_utc=SLOT + timedelta(seconds=13),
    )
    valuation = SLOT + timedelta(seconds=14)
    batch = build_current_webull_stock_marks_v1(
        bundle=quotes,
        positions=runtime.current_account().state.open_positions,
        valuation_utc=valuation,
    )
    return batch, valuation


def test_recurrent_production_cycle_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT
        == "c03e6e299076618a537e8ab2d7ebd575b33f22924f25fc1f0ba655f10e7412ca"
    )


def test_plan_aware_production_cycle_runs_entry_refresh_mark_complete(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    (
        checkpoint,
        runtime,
        production,
        identity,
        record,
        reserve_bundle,
        _entry_bundle,
    ) = _build_through_entry(settings)

    policies = {record.record_fingerprint: _policy()}
    mark_batch, valuation = _mark_batch(runtime)
    marked = production.apply_mark(
        reserve_bundle=reserve_bundle,
        exit_policy_by_decision=policies,
        mark_batch=mark_batch,
        valuation_utc=valuation,
        now_utc=valuation,
    )
    assert [stage.stage.value for stage in marked.stages] == [
        "CLOSE",
        "RESERVE",
        "ENTRY",
        "MARK",
    ]
    refresh_path = recurrent_exit_plan_refresh_receipt_path(
        checkpoint,
        identity.cycle_id,
    )
    assert refresh_path.is_file()
    assert (
        MarketDataPaths(
            settings
        ).recurrent_decision_stock_exit_plan_file().is_file()
    )

    completed = production.complete(
        now_utc=SLOT + timedelta(seconds=15),
    )
    assert completed.status == RecurrentCycleStatus.COMPLETE
    assert len(runtime.current_account().state.open_positions) == 1
    assert runtime.current_marked_state() is not None
    assert len(runtime.current_marked_state().marked_positions) == 1


def test_production_restore_after_entry_builds_refresh_before_mark(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    (
        checkpoint,
        _runtime,
        _production,
        identity,
        record,
        reserve_bundle,
        _entry_bundle,
    ) = _build_through_entry(settings)

    restored = RecurrentProductionCycleV1.restore(
        settings=settings,
        checkpoint_path=checkpoint,
        identity=identity,
    )
    assert not recurrent_exit_plan_refresh_receipt_path(
        checkpoint,
        identity.cycle_id,
    ).exists()

    mark_batch, valuation = _mark_batch(restored.runner.runtime)
    receipt = restored.apply_mark(
        reserve_bundle=reserve_bundle,
        exit_policy_by_decision={
            record.record_fingerprint: _policy(),
        },
        mark_batch=mark_batch,
        valuation_utc=valuation,
        now_utc=valuation,
    )
    assert receipt.stages[-1].stage.value == "MARK"
    assert recurrent_exit_plan_refresh_receipt_path(
        checkpoint,
        identity.cycle_id,
    ).is_file()


def test_production_mark_rejects_policy_drift_after_refresh(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    (
        _checkpoint,
        runtime,
        production,
        _identity_value,
        record,
        reserve_bundle,
        _entry_bundle,
    ) = _build_through_entry(settings)

    production.refresh_exit_plans(
        reserve_bundle=reserve_bundle,
        exit_policy_by_decision={
            record.record_fingerprint: _policy(),
        },
    )
    mark_batch, valuation = _mark_batch(runtime)
    with pytest.raises(
        RecurrentProductionCycleError,
        match="post-ENTRY exit-plan refresh failed",
    ):
        production.apply_mark(
            reserve_bundle=reserve_bundle,
            exit_policy_by_decision={
                record.record_fingerprint: _policy(
                    stop=0.02,
                    target=0.01,
                ),
            },
            mark_batch=mark_batch,
            valuation_utc=valuation,
            now_utc=valuation,
        )


def test_recorded_mark_and_complete_retry_are_idempotent(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    (
        _checkpoint,
        runtime,
        production,
        _identity_value,
        record,
        reserve_bundle,
        _entry_bundle,
    ) = _build_through_entry(settings)
    policies = {record.record_fingerprint: _policy()}
    mark_batch, valuation = _mark_batch(runtime)

    first_mark = production.apply_mark(
        reserve_bundle=reserve_bundle,
        exit_policy_by_decision=policies,
        mark_batch=mark_batch,
        valuation_utc=valuation,
        now_utc=valuation,
    )
    first_complete = production.complete(
        now_utc=SLOT + timedelta(seconds=15),
    )
    second_mark = production.apply_mark(
        reserve_bundle=reserve_bundle,
        exit_policy_by_decision=policies,
        mark_batch=mark_batch,
        valuation_utc=valuation,
        now_utc=SLOT + timedelta(seconds=16),
    )
    second_complete = production.complete(
        now_utc=SLOT + timedelta(seconds=17),
    )

    assert first_mark.stages[-1].stage.value == "MARK"
    assert second_mark == first_complete
    assert second_complete == first_complete


def test_recorded_entry_retry_uses_admission_not_post_entry_state(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    (
        _checkpoint,
        runtime,
        production,
        _identity_value,
        _record_value,
        _reserve_bundle,
        entry_bundle,
    ) = _build_through_entry(settings)
    assert runtime.current_account().state.open_positions
    before = production._receipt()

    retried = production.apply_entry(
        bundle=entry_bundle,
        now_utc=SLOT + timedelta(seconds=18),
    )
    assert retried == before
    assert len(runtime.current_account().state.open_positions) == 1
