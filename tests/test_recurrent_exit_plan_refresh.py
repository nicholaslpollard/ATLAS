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
from packages.simulation.market_mark_evidence import (
    MarketMarkInputs,
    MarketMarkTransport,
    build_simulated_market_mark_evidence,
)
from packages.simulation.recurrent_cycle import (
    read_recurrent_cycle_receipt,
    recurrent_cycle_receipt_path,
)
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunnerV1,
    build_recurrent_cycle_run_identity_v1,
    read_recurrent_cycle_stage_admission,
    recurrent_cycle_stage_admission_path,
)
from packages.simulation.recurrent_decision_exit_plan import (
    StockExitPolicyInputsV1,
    build_recurrent_decision_stock_exit_plan_book_v1,
    write_recurrent_decision_stock_exit_plan_book_v1,
)
from packages.simulation.recurrent_exit_plan_refresh import (
    RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT,
    RecurrentExitPlanRefreshError,
    recurrent_exit_plan_entry_stage_record_fingerprint,
    refresh_recurrent_exit_plans_after_entry_v1,
)
from packages.simulation.recurrent_genesis import (
    bootstrap_recurrent_genesis_v1,
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
        method_id="fixture-forecast-v1",
        source_label="fixture forecast",
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
        reason_codes=("FIXTURE",),
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
        policy_id="fixture-exit-policy-v1",
        policy_fingerprint=POLICY_FP,
        stop_threshold_fraction=stop,
        target_threshold_fraction=target,
    )


def _runtime_and_runner(settings):
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
    return checkpoint, runtime, runner


def _begin_through_reserve(settings):
    checkpoint, runtime, runner = _runtime_and_runner(settings)
    identity = _identity()
    runner.begin(
        identity=identity,
        now_utc=SLOT + timedelta(seconds=3),
    )
    runner.apply_close(
        identity=identity,
        evidence_source_id="fixture-empty-close",
        evidence_source_fingerprint="a" * 64,
        fills=(),
        now_utc=SLOT + timedelta(seconds=4),
    )
    record = _record()
    reserve_bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=identity,
        decisions=((record, None),),
        built_at_utc=SLOT + timedelta(seconds=5),
    )
    runner.apply_reserve(
        identity=identity,
        evidence_source_id=reserve_bundle.source_id,
        evidence_source_fingerprint=reserve_bundle.bundle_fingerprint,
        decisions=reserve_bundle.runner_decisions,
        now_utc=SLOT + timedelta(seconds=6),
    )
    return (
        checkpoint,
        runtime,
        runner,
        identity,
        record,
        reserve_bundle,
    )


def _through_entry(settings):
    (
        checkpoint,
        runtime,
        runner,
        identity,
        record,
        reserve_bundle,
    ) = _begin_through_reserve(settings)

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
        fee_source_id="fixture-entry-fees",
        fee_source_fingerprint=ENTRY_FEE_FP,
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    runner.apply_entry(
        identity=identity,
        evidence_source_id=entry_bundle.source_id,
        evidence_source_fingerprint=entry_bundle.bundle_fingerprint,
        entries=entry_bundle.runner_entries,
        now_utc=SLOT + timedelta(seconds=11),
    )
    return (
        checkpoint,
        runtime,
        runner,
        identity,
        record,
        reserve_bundle,
    )


def test_exit_plan_refresh_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT
        == "7cf394ab6ba2fd3dc7e506a7718acb9f90ff647a55ed7b68c0a6a5f4eade2abc"
    )


def test_refresh_refuses_before_entry(tmp_path) -> None:
    settings = _settings(tmp_path)
    (
        checkpoint,
        runtime,
        _runner,
        identity,
        record,
        reserve_bundle,
    ) = _begin_through_reserve(settings)

    with pytest.raises(
        RecurrentExitPlanRefreshError,
        match="requires exactly CLOSE, RESERVE, ENTRY",
    ):
        refresh_recurrent_exit_plans_after_entry_v1(
            settings=settings,
            checkpoint_path=checkpoint,
            runtime=runtime,
            identity=identity,
            current_reserve_bundle=reserve_bundle,
            exit_policy_by_decision={
                record.record_fingerprint: _policy(),
            },
        )


def test_post_entry_refresh_builds_durable_book_and_exact_retry_reuses(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    (
        checkpoint,
        runtime,
        _runner,
        identity,
        record,
        reserve_bundle,
    ) = _through_entry(settings)
    policies = {record.record_fingerprint: _policy()}

    first = refresh_recurrent_exit_plans_after_entry_v1(
        settings=settings,
        checkpoint_path=checkpoint,
        runtime=runtime,
        identity=identity,
        current_reserve_bundle=reserve_bundle,
        exit_policy_by_decision=policies,
    )
    assert first.idempotent_reuse is False
    assert first.book_path.is_file()
    assert first.receipt_path.is_file()
    assert len(first.book.plans) == 1
    assert first.receipt.output_plan_book_fingerprint == (
        first.book.book_fingerprint
    )
    assert first.receipt.output_plan_count == 1
    assert first.receipt.provider_reads == 0
    assert first.receipt.broker_writes == 0

    second = refresh_recurrent_exit_plans_after_entry_v1(
        settings=settings,
        checkpoint_path=checkpoint,
        runtime=runtime,
        identity=identity,
        current_reserve_bundle=reserve_bundle,
        exit_policy_by_decision=policies,
    )
    assert second.idempotent_reuse is True
    assert second.book == first.book
    assert second.receipt == first.receipt


def test_refresh_rejects_conflicting_retry_policy(tmp_path) -> None:
    settings = _settings(tmp_path)
    (
        checkpoint,
        runtime,
        _runner,
        identity,
        record,
        reserve_bundle,
    ) = _through_entry(settings)
    refresh_recurrent_exit_plans_after_entry_v1(
        settings=settings,
        checkpoint_path=checkpoint,
        runtime=runtime,
        identity=identity,
        current_reserve_bundle=reserve_bundle,
        exit_policy_by_decision={
            record.record_fingerprint: _policy(),
        },
    )

    with pytest.raises(
        RecurrentExitPlanRefreshError,
        match="already recorded with different evidence",
    ):
        refresh_recurrent_exit_plans_after_entry_v1(
            settings=settings,
            checkpoint_path=checkpoint,
            runtime=runtime,
            identity=identity,
            current_reserve_bundle=reserve_bundle,
            exit_policy_by_decision={
                record.record_fingerprint: _policy(
                    stop=0.02,
                    target=0.01,
                ),
            },
        )


def test_refresh_recovers_book_written_before_receipt(tmp_path) -> None:
    settings = _settings(tmp_path)
    (
        checkpoint,
        runtime,
        _runner,
        identity,
        record,
        reserve_bundle,
    ) = _through_entry(settings)
    policies = {record.record_fingerprint: _policy()}

    state = runtime.current_account().state
    existing = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=state,
        current_reserve_bundle=reserve_bundle,
        existing_book=None,
        exit_policy_by_decision=policies,
        built_at_utc=SLOT + timedelta(seconds=11),
    )
    write_recurrent_decision_stock_exit_plan_book_v1(
        settings,
        existing,
    )

    recovered = refresh_recurrent_exit_plans_after_entry_v1(
        settings=settings,
        checkpoint_path=checkpoint,
        runtime=runtime,
        identity=identity,
        current_reserve_bundle=reserve_bundle,
        exit_policy_by_decision=policies,
    )
    assert recovered.idempotent_reuse is False
    assert recovered.book == existing
    assert recovered.receipt_path.is_file()


def test_empty_post_entry_refresh_requires_no_reserve_bundle(tmp_path) -> None:
    settings = _settings(tmp_path)
    checkpoint, runtime, runner = _runtime_and_runner(settings)
    identity = _identity()
    runner.begin(
        identity=identity,
        now_utc=SLOT + timedelta(seconds=1),
    )
    runner.apply_close(
        identity=identity,
        evidence_source_id="empty-close",
        evidence_source_fingerprint="a" * 64,
        fills=(),
        now_utc=SLOT + timedelta(seconds=2),
    )
    runner.apply_reserve(
        identity=identity,
        evidence_source_id="empty-reserve",
        evidence_source_fingerprint="b" * 64,
        decisions=(),
        now_utc=SLOT + timedelta(seconds=3),
    )
    runner.apply_entry(
        identity=identity,
        evidence_source_id="empty-entry",
        evidence_source_fingerprint="c" * 64,
        entries=(),
        now_utc=SLOT + timedelta(seconds=4),
    )

    refreshed = refresh_recurrent_exit_plans_after_entry_v1(
        settings=settings,
        checkpoint_path=checkpoint,
        runtime=runtime,
        identity=identity,
        current_reserve_bundle=None,
        exit_policy_by_decision={},
    )
    assert refreshed.book.plans == ()
    assert refreshed.receipt.output_plan_count == 0
    assert refreshed.receipt.reserve_bundle_fingerprint is None


def test_refresh_lineage_survives_mark_and_cycle_completion(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    (
        checkpoint,
        runtime,
        runner,
        identity,
        record,
        reserve_bundle,
    ) = _through_entry(settings)
    refreshed = refresh_recurrent_exit_plans_after_entry_v1(
        settings=settings,
        checkpoint_path=checkpoint,
        runtime=runtime,
        identity=identity,
        current_reserve_bundle=reserve_bundle,
        exit_policy_by_decision={
            record.record_fingerprint: _policy(),
        },
    )

    valuation = SLOT + timedelta(seconds=12)
    position = runtime.current_account().state.open_positions[0]
    mark = build_simulated_market_mark_evidence(
        position=position,
        inputs=MarketMarkInputs(
            source_id="fixture-current-stock-mark",
            source_fingerprint="d" * 64,
            provider="fixture",
            feed="fixture-l1",
            transport=MarketMarkTransport.SNAPSHOT,
            feed_quality="REALTIME_TEST_FIXTURE",
            market_timestamp_utc=SLOT + timedelta(seconds=11),
            received_utc=valuation,
            valuation_utc=valuation,
            bid_price_per_unit=100.40,
            ask_price_per_unit=100.50,
            last_price_per_unit=100.45,
        ),
    )
    runner.apply_mark(
        identity=identity,
        evidence_source_id="fixture-current-stock-mark",
        evidence_source_fingerprint="d" * 64,
        marks=(mark,),
        valuation_utc=valuation,
        now_utc=valuation,
    )
    completed = runner.complete(
        identity=identity,
        now_utc=SLOT + timedelta(seconds=13),
    )
    final_receipt = read_recurrent_cycle_receipt(
        recurrent_cycle_receipt_path(
            checkpoint,
            identity.cycle_id,
        )
    )
    assert final_receipt == completed
    entry_stage = final_receipt.stages[2]
    assert refreshed.receipt.entry_stage_record_fingerprint == (
        recurrent_exit_plan_entry_stage_record_fingerprint(
            entry_stage
        )
    )
    admission = read_recurrent_cycle_stage_admission(
        recurrent_cycle_stage_admission_path(
            checkpoint,
            identity.cycle_id,
            entry_stage.stage,
        )
    )
    assert refreshed.receipt.entry_stage_admission_sha256 == (
        admission.admission_sha256
    )
