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
from packages.execution.recurrent_price_time_exit_resolution import (
    RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_FINGERPRINT,
    ExitReason,
    ExitTriggerPrecedenceMode,
    ExitTriggerPrecedencePolicyV1,
    PriceTriggerCondition,
    RecurrentPriceTimeExitResolutionError,
    SelectedExitDisposition,
    build_recurrent_price_time_exit_resolution_bundle_v1,
    read_recurrent_price_time_exit_resolution_bundle_v1,
    write_recurrent_price_time_exit_resolution_bundle_v1,
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
from packages.simulation.recurrent_cycle_runner import (
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    StockExitPolicyInputsV1,
    build_recurrent_decision_stock_exit_plan_book_v1,
)
from packages.simulation.recurrent_forecast_horizon_clock_book import (
    build_recurrent_forecast_horizon_clock_book_v1,
)
from packages.simulation.recurrent_genesis import (
    bootstrap_recurrent_genesis_v1,
)
from packages.simulation.recurrent_reserve_evidence import (
    build_recurrent_reserve_evidence_bundle_v1,
)
from packages.simulation.recurrent_time_expiry_disposition import (
    TimeExpiryDisposition,
    build_recurrent_time_expiry_disposition_bundle_v1,
)


ENTRY_FEE_FP = "f" * 64
EXIT_POLICY_FP = "e" * 64
OPENED = datetime(2026, 9, 18, 14, 0, tzinfo=UTC)


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
        forecast_created_utc=OPENED - timedelta(minutes=8),
        evidence_cutoff_utc=OPENED - timedelta(minutes=9),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=10,
        method_id="price-time-resolution-fixture-v1",
        source_label="price-time resolution fixture",
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
                median_time=5.0,
            ),
            _threshold(
                0.02,
                favorable=0.45,
                adverse=0.20,
                favorable_first=0.34,
                adverse_first=0.12,
                median_time=8.0,
            ),
        ),
        uncertainty_score=0.25,
        reason_codes=("PRICE_TIME_RESOLUTION_FIXTURE",),
    )
    return build_simulation_decision_record(
        decision_created_utc=OPENED - timedelta(minutes=7),
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


def _clock_book(tmp_path):
    settings = _settings(tmp_path)
    genesis = OPENED - timedelta(minutes=10)
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=genesis,
    )
    record = _record()
    identity = build_recurrent_cycle_run_identity_v1(
        schedule_id="price-time-resolution-fixture-cycle",
        scheduled_for_utc=genesis,
    )
    reserve_bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=identity,
        decisions=((record, None),),
        built_at_utc=OPENED - timedelta(minutes=6),
    )
    runtime.apply_reservation_batch(
        reserve_bundle.runner_decisions
    )

    entry_quote = CurrentWebullStockQuoteV1(
        symbol="AAPL",
        provider_timestamp_utc=OPENED - timedelta(seconds=1),
        received_at_utc=OPENED,
        session_date=OPENED.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=100.0,
        bid_size=10,
        ask_price=100.25,
        ask_size=12,
    )
    entry_quotes = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(entry_quote,),
        captured_at_utc=OPENED + timedelta(seconds=1),
    )
    entry_bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve_bundle,
        quote_bundle=entry_quotes,
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 2.50,
        },
        fee_source_id="price-time-resolution-entry-fees",
        fee_source_fingerprint=ENTRY_FEE_FP,
        built_at_utc=OPENED + timedelta(seconds=2),
    )
    runtime.apply_entry_batch(entry_bundle.runner_entries)

    state = runtime.current_account().state
    exit_book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=state,
        current_reserve_bundle=reserve_bundle,
        existing_book=None,
        exit_policy_by_decision={
            record.record_fingerprint: StockExitPolicyInputsV1(
                policy_id="price-time-resolution-exit-policy-v1",
                policy_fingerprint=EXIT_POLICY_FP,
                stop_threshold_fraction=0.01,
                target_threshold_fraction=0.02,
            ),
        },
        built_at_utc=OPENED + timedelta(seconds=3),
    )
    plan = exit_book.plans[0]
    clock_book = build_recurrent_forecast_horizon_clock_book_v1(
        exit_plan_book=exit_book,
        existing_book=None,
        clock_policy_by_plan={
            plan.plan_fingerprint: ForecastHorizonClockPolicyV1(),
        },
        built_at_utc=OPENED + timedelta(seconds=4),
    )
    return settings, clock_book


def _quotes(*, received: datetime, bid: float):
    quote = CurrentWebullStockQuoteV1(
        symbol="AAPL",
        provider_timestamp_utc=received - timedelta(seconds=1),
        received_at_utc=received,
        session_date=received.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=bid,
        bid_size=10,
        ask_price=bid + 0.10,
        ask_size=12,
    )
    return build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(quote,),
        captured_at_utc=received + timedelta(milliseconds=100),
    )


def _policy(mode: ExitTriggerPrecedenceMode):
    return ExitTriggerPrecedencePolicyV1(
        policy_id=f"fixture-{mode.value.lower()}",
        mode=mode,
    )


def _resolve(
    clock_book,
    *,
    evaluation: datetime,
    received: datetime,
    bid: float,
    mode: ExitTriggerPrecedenceMode = (
        ExitTriggerPrecedenceMode.PRICE_THEN_TIME
    ),
):
    expiry = build_recurrent_time_expiry_disposition_bundle_v1(
        clock_book=clock_book,
        evaluation_utc=evaluation,
    )
    return build_recurrent_price_time_exit_resolution_bundle_v1(
        expiry_bundle=expiry,
        quote_bundle=_quotes(received=received, bid=bid),
        precedence_policy=_policy(mode),
    )


def test_price_time_resolution_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_FINGERPRINT
        == "e07d09158c2221823eaa4364a1b6b6feb343dc7443b67bb643187a4166c9c633"
    )


def test_hold_when_no_price_or_executable_time_trigger(tmp_path) -> None:
    _settings_obj, clock_book = _clock_book(tmp_path)
    deadline = clock_book.clocks[0].deadline_utc
    evaluation = deadline - timedelta(minutes=5)
    bundle = _resolve(
        clock_book,
        evaluation=evaluation,
        received=evaluation - timedelta(seconds=1),
        bid=100.50,
    )
    item = bundle.resolutions[0]
    assert item.price_condition == PriceTriggerCondition.NO_PRICE_TRIGGER
    assert item.time_disposition == TimeExpiryDisposition.NOT_EXPIRED
    assert item.time_exit_executable is False
    assert item.true_exit_reasons == ()
    assert item.selected_disposition == SelectedExitDisposition.HOLD


@pytest.mark.parametrize(
    ("bid", "condition", "selected", "reason"),
    (
        (
            99.0,
            PriceTriggerCondition.STOP,
            SelectedExitDisposition.STOP,
            ExitReason.STOP,
        ),
        (
            103.0,
            PriceTriggerCondition.TARGET,
            SelectedExitDisposition.TARGET,
            ExitReason.TARGET,
        ),
    ),
)
def test_price_trigger_without_time_expiry(
    tmp_path,
    bid,
    condition,
    selected,
    reason,
) -> None:
    _settings_obj, clock_book = _clock_book(tmp_path)
    deadline = clock_book.clocks[0].deadline_utc
    evaluation = deadline - timedelta(minutes=2)
    bundle = _resolve(
        clock_book,
        evaluation=evaluation,
        received=evaluation - timedelta(seconds=1),
        bid=bid,
    )
    item = bundle.resolutions[0]
    assert item.price_condition == condition
    assert item.time_exit_executable is False
    assert item.true_exit_reasons == (reason,)
    assert item.selected_disposition == selected


def test_time_only_requires_quote_received_at_or_after_deadline(
    tmp_path,
) -> None:
    _settings_obj, clock_book = _clock_book(tmp_path)
    deadline = clock_book.clocks[0].deadline_utc
    evaluation = deadline + timedelta(seconds=2)
    bundle = _resolve(
        clock_book,
        evaluation=evaluation,
        received=deadline + timedelta(seconds=1),
        bid=100.50,
    )
    item = bundle.resolutions[0]
    assert item.time_disposition == TimeExpiryDisposition.TIME_EXPIRED
    assert item.price_condition == PriceTriggerCondition.NO_PRICE_TRIGGER
    assert item.time_exit_executable is True
    assert item.true_exit_reasons == (ExitReason.TIME,)
    assert item.selected_disposition == SelectedExitDisposition.TIME


def test_expired_evaluation_cannot_use_predeadline_quote_for_time(
    tmp_path,
) -> None:
    _settings_obj, clock_book = _clock_book(tmp_path)
    deadline = clock_book.clocks[0].deadline_utc
    evaluation = deadline + timedelta(seconds=1)
    bundle = _resolve(
        clock_book,
        evaluation=evaluation,
        received=deadline - timedelta(seconds=1),
        bid=100.50,
    )
    item = bundle.resolutions[0]
    assert item.time_disposition == TimeExpiryDisposition.TIME_EXPIRED
    assert item.time_exit_executable is False
    assert item.true_exit_reasons == ()
    assert item.selected_disposition == SelectedExitDisposition.HOLD


@pytest.mark.parametrize(
    ("mode", "selected"),
    (
        (
            ExitTriggerPrecedenceMode.PRICE_THEN_TIME,
            SelectedExitDisposition.STOP,
        ),
        (
            ExitTriggerPrecedenceMode.TIME_THEN_PRICE,
            SelectedExitDisposition.TIME,
        ),
    ),
)
def test_simultaneous_stop_and_time_retains_both_and_obeys_policy(
    tmp_path,
    mode,
    selected,
) -> None:
    settings, clock_book = _clock_book(tmp_path)
    deadline = clock_book.clocks[0].deadline_utc
    evaluation = deadline + timedelta(seconds=2)
    expiry = build_recurrent_time_expiry_disposition_bundle_v1(
        clock_book=clock_book,
        evaluation_utc=evaluation,
    )
    quotes = _quotes(
        received=deadline + timedelta(seconds=1),
        bid=99.0,
    )
    bundle = build_recurrent_price_time_exit_resolution_bundle_v1(
        expiry_bundle=expiry,
        quote_bundle=quotes,
        precedence_policy=_policy(mode),
    )
    item = bundle.resolutions[0]
    assert item.true_exit_reasons == (
        ExitReason.STOP,
        ExitReason.TIME,
    )
    assert item.selected_disposition == selected
    assert bundle.fee_evidence_consumed is False
    assert bundle.close_fill_authority is False
    assert bundle.paper_authority is False

    path = write_recurrent_price_time_exit_resolution_bundle_v1(
        settings,
        bundle,
    )
    restored = read_recurrent_price_time_exit_resolution_bundle_v1(
        settings,
        path=path,
    )
    assert restored == bundle


def test_stale_quote_is_rejected_at_resolution_evaluation(tmp_path) -> None:
    _settings_obj, clock_book = _clock_book(tmp_path)
    deadline = clock_book.clocks[0].deadline_utc
    evaluation = deadline + timedelta(seconds=40)
    expiry = build_recurrent_time_expiry_disposition_bundle_v1(
        clock_book=clock_book,
        evaluation_utc=evaluation,
    )
    with pytest.raises(
        RecurrentPriceTimeExitResolutionError,
        match="stale",
    ):
        build_recurrent_price_time_exit_resolution_bundle_v1(
            expiry_bundle=expiry,
            quote_bundle=_quotes(
                received=deadline + timedelta(seconds=1),
                bid=100.50,
            ),
            precedence_policy=_policy(
                ExitTriggerPrecedenceMode.PRICE_THEN_TIME
            ),
        )
