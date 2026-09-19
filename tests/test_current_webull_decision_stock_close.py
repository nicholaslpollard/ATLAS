from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.core.enums import SessionSegment
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.execution.current_webull_decision_stock_close import (
    CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT,
    CurrentWebullDecisionStockCloseEvidenceError,
    StockExitTriggerDisposition,
    build_current_webull_decision_stock_close_evidence_bundle_v1,
    read_current_webull_decision_stock_close_evidence_bundle_v1,
    write_current_webull_decision_stock_close_evidence_bundle_v1,
)
from packages.execution.current_webull_time_aware_stock_close import (
    CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT,
    CurrentWebullTimeAwareStockCloseError,
    FinalStockCloseDisposition,
    build_current_webull_time_aware_stock_close_bundle_v1,
    read_current_webull_time_aware_stock_close_bundle_v1,
    write_current_webull_time_aware_stock_close_bundle_v1,
)
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
from packages.simulation.recurrent_cycle_runner import (
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    StockExitPolicyInputsV1,
    build_recurrent_decision_stock_exit_plan_book_v1,
)
from packages.simulation.recurrent_genesis import (
    bootstrap_recurrent_genesis_v1,
)
from packages.simulation.recurrent_reserve_evidence import (
    build_recurrent_reserve_evidence_bundle_v1,
)


SLOT = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
ENTRY_FEE_SOURCE_FP = "f" * 64
EXIT_FEE_SOURCE_FP = "c" * 64
EXIT_POLICY_FP = "e" * 64
TIME_EXIT_FEE_SOURCE_FP = "9" * 64
TIME_SLOT = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)


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


def _identity():
    return build_recurrent_cycle_run_identity_v1(
        schedule_id="four-hour-simulation",
        scheduled_for_utc=SLOT,
    )


def _quote(
    *,
    bid: float,
    ask: float,
    received_seconds: int = 20,
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


def _quote_bundle(quote):
    return build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(quote,),
        captured_at_utc=quote.received_at_utc + timedelta(seconds=1),
    )


def _open_position_and_plan(settings):
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

    entry_received = SLOT + timedelta(seconds=8)
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
        captured_at_utc=SLOT + timedelta(seconds=9),
    )
    entry_bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve_bundle,
        quote_bundle=entry_quote_bundle,
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 2.50,
        },
        fee_source_id="explicit-entry-fees-v1",
        fee_source_fingerprint=ENTRY_FEE_SOURCE_FP,
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    runtime.apply_entry_batch(entry_bundle.runner_entries)

    state = runtime.current_account().state
    book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=state,
        current_reserve_bundle=reserve_bundle,
        existing_book=None,
        exit_policy_by_decision={
            record.record_fingerprint: StockExitPolicyInputsV1(
                policy_id="fixture-exit-policy-v1",
                policy_fingerprint=EXIT_POLICY_FP,
                stop_threshold_fraction=0.01,
                target_threshold_fraction=0.02,
            ),
        },
        built_at_utc=SLOT + timedelta(seconds=11),
    )
    return runtime, book


def test_current_webull_decision_stock_close_contract_fingerprint_is_frozen() -> None:
    assert (
        CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        == "3834abe2212b794a04ce70b5595d992de38cea77ac82185e6daaf6134bd6db96"
    )


def test_empty_close_is_provider_inert_and_roundtrips(tmp_path) -> None:
    settings = _settings(tmp_path)
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=SLOT,
    )
    state = runtime.current_account().state
    book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=state,
        current_reserve_bundle=None,
        existing_book=None,
        exit_policy_by_decision={},
        built_at_utc=SLOT,
    )

    bundle = build_current_webull_decision_stock_close_evidence_bundle_v1(
        account=runtime.current_account(),
        identity=_identity(),
        exit_plan_book=book,
        quote_bundle=None,
        explicit_exit_fees_by_position={},
        built_at_utc=SLOT,
    )
    assert bundle.triggers == ()
    assert bundle.quote_bundle is None
    assert bundle.fee_source_id is None
    assert bundle.triggered_fills == ()
    assert bundle.provider_calls_performed == 0
    assert bundle.broker_calls_performed == 0

    path = write_current_webull_decision_stock_close_evidence_bundle_v1(
        settings,
        bundle,
    )
    restored = read_current_webull_decision_stock_close_evidence_bundle_v1(
        settings,
        path=path,
    )
    assert restored == bundle


def test_no_trigger_is_explicit_and_requires_no_fee_source(tmp_path) -> None:
    settings = _settings(tmp_path)
    runtime, book = _open_position_and_plan(settings)
    plan = book.plans[0]
    assert plan.stop_price_per_unit == pytest.approx(99.2475)
    assert plan.target_price_per_unit == pytest.approx(102.255)

    quote_bundle = _quote_bundle(
        _quote(bid=100.50, ask=100.60)
    )
    bundle = build_current_webull_decision_stock_close_evidence_bundle_v1(
        account=runtime.current_account(),
        identity=_identity(),
        exit_plan_book=book,
        quote_bundle=quote_bundle,
        explicit_exit_fees_by_position={},
        built_at_utc=SLOT + timedelta(seconds=22),
    )
    assert len(bundle.triggers) == 1
    trigger = bundle.triggers[0]
    assert trigger.disposition == StockExitTriggerDisposition.NO_TRIGGER
    assert trigger.fill is None
    assert trigger.explicit_exit_fee_dollars is None
    assert bundle.triggered_fills == ()
    assert bundle.fee_source_id is None
    assert bundle.quote_bundle == quote_bundle

    path = write_current_webull_decision_stock_close_evidence_bundle_v1(
        settings,
        bundle,
    )
    restored = read_current_webull_decision_stock_close_evidence_bundle_v1(
        settings,
        path=path,
    )
    assert restored == bundle


@pytest.mark.parametrize(
    ("bid", "ask", "expected"),
    (
        (99.20, 99.30, StockExitTriggerDisposition.STOP),
        (102.30, 102.40, StockExitTriggerDisposition.TARGET),
    ),
)
def test_triggered_close_uses_bid_exact_fee_and_closes_position(
    tmp_path,
    bid,
    ask,
    expected,
) -> None:
    settings = _settings(tmp_path)
    runtime, book = _open_position_and_plan(settings)
    position = runtime.current_account().state.open_positions[0]
    quote_bundle = _quote_bundle(_quote(bid=bid, ask=ask))

    bundle = build_current_webull_decision_stock_close_evidence_bundle_v1(
        account=runtime.current_account(),
        identity=_identity(),
        exit_plan_book=book,
        quote_bundle=quote_bundle,
        explicit_exit_fees_by_position={
            position.position_fingerprint: 1.25,
        },
        fee_source_id="explicit-exit-fees-v1",
        fee_source_fingerprint=EXIT_FEE_SOURCE_FP,
        built_at_utc=SLOT + timedelta(seconds=22),
    )
    trigger = bundle.triggers[0]
    assert trigger.disposition == expected
    assert trigger.fill is not None
    assert trigger.fill.exit_price_per_unit == pytest.approx(bid)
    assert trigger.fill.exit_fees_dollars == pytest.approx(1.25)
    assert trigger.fill.exited_utc == trigger.quote.received_at_utc
    assert bundle.triggered_fills == (trigger.fill,)

    runtime.apply_close_batch(bundle.triggered_fills)
    account = runtime.current_account()
    assert account.state.open_positions == ()
    assert len(account.state.closed_trades) == 1


def test_triggered_close_requires_exact_fee_source(tmp_path) -> None:
    settings = _settings(tmp_path)
    runtime, book = _open_position_and_plan(settings)
    position = runtime.current_account().state.open_positions[0]

    with pytest.raises(
        CurrentWebullDecisionStockCloseEvidenceError,
        match="requires explicit fee-source evidence",
    ):
        build_current_webull_decision_stock_close_evidence_bundle_v1(
            account=runtime.current_account(),
            identity=_identity(),
            exit_plan_book=book,
            quote_bundle=_quote_bundle(
                _quote(bid=102.30, ask=102.40)
            ),
            explicit_exit_fees_by_position={
                position.position_fingerprint: 1.25,
            },
            built_at_utc=SLOT + timedelta(seconds=22),
        )


def test_no_trigger_rejects_unused_fee_source(tmp_path) -> None:
    settings = _settings(tmp_path)
    runtime, book = _open_position_and_plan(settings)

    with pytest.raises(
        CurrentWebullDecisionStockCloseEvidenceError,
        match="must not claim fee-source evidence",
    ):
        build_current_webull_decision_stock_close_evidence_bundle_v1(
            account=runtime.current_account(),
            identity=_identity(),
            exit_plan_book=book,
            quote_bundle=_quote_bundle(
                _quote(bid=100.50, ask=100.60)
            ),
            explicit_exit_fees_by_position={},
            fee_source_id="unused-exit-fees-v1",
            fee_source_fingerprint=EXIT_FEE_SOURCE_FP,
            built_at_utc=SLOT + timedelta(seconds=22),
        )


def test_stale_exit_plan_book_fails_after_account_state_changes(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    runtime, book = _open_position_and_plan(settings)
    position = runtime.current_account().state.open_positions[0]

    exit_quote = _quote(bid=102.30, ask=102.40)
    quote_bundle = _quote_bundle(exit_quote)
    close_bundle = build_current_webull_decision_stock_close_evidence_bundle_v1(
        account=runtime.current_account(),
        identity=_identity(),
        exit_plan_book=book,
        quote_bundle=quote_bundle,
        explicit_exit_fees_by_position={
            position.position_fingerprint: 1.0,
        },
        fee_source_id="explicit-exit-fees-v1",
        fee_source_fingerprint=EXIT_FEE_SOURCE_FP,
        built_at_utc=SLOT + timedelta(seconds=22),
    )
    runtime.apply_close_batch(close_bundle.triggered_fills)

    with pytest.raises(
        CurrentWebullDecisionStockCloseEvidenceError,
        match="stale for current recurrent state",
    ):
        build_current_webull_decision_stock_close_evidence_bundle_v1(
            account=runtime.current_account(),
            identity=_identity(),
            exit_plan_book=book,
            quote_bundle=None,
            explicit_exit_fees_by_position={},
            built_at_utc=SLOT + timedelta(seconds=23),
        )


def test_close_rejects_quote_bundle_captured_after_build(tmp_path) -> None:
    settings = _settings(tmp_path)
    runtime, book = _open_position_and_plan(settings)
    quote = _quote(bid=100.50, ask=100.60)
    future_capture_bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(quote,),
        captured_at_utc=SLOT + timedelta(seconds=30),
    )

    with pytest.raises(
        CurrentWebullDecisionStockCloseEvidenceError,
        match="capture postdates build time",
    ):
        build_current_webull_decision_stock_close_evidence_bundle_v1(
            account=runtime.current_account(),
            identity=_identity(),
            exit_plan_book=book,
            quote_bundle=future_capture_bundle,
            explicit_exit_fees_by_position={},
            built_at_utc=SLOT + timedelta(seconds=22),
        )


def _time_record():
    forecast = UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id="iid-AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=TIME_SLOT + timedelta(seconds=1),
        evidence_cutoff_utc=TIME_SLOT,
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=1,
        method_id="time-close-fixture-v1",
        source_label="time close fixture",
        source_fingerprint="7" * 64,
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
        reason_codes=("TIME_CLOSE_FIXTURE",),
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


def _time_identity():
    return build_recurrent_cycle_run_identity_v1(
        schedule_id="time-aware-close-fixture",
        scheduled_for_utc=TIME_SLOT,
    )


def _open_time_position_and_plan(settings):
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=TIME_SLOT,
    )
    record = _time_record()
    reserve_bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=_time_identity(),
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
        fee_source_id="time-close-entry-fees",
        fee_source_fingerprint=ENTRY_FEE_SOURCE_FP,
        built_at_utc=TIME_SLOT + timedelta(seconds=10),
    )
    runtime.apply_entry_batch(entry_bundle.runner_entries)

    state = runtime.current_account().state
    plan_book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=state,
        current_reserve_bundle=reserve_bundle,
        existing_book=None,
        exit_policy_by_decision={
            record.record_fingerprint: StockExitPolicyInputsV1(
                policy_id="time-close-exit-policy-v1",
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
    return runtime, plan_book, clock_book


def _time_price_close_bundle(
    *,
    runtime,
    plan_book,
    bid: float,
    ask: float,
    received_seconds: int,
    built_seconds: int | None = None,
):
    received = TIME_SLOT + timedelta(seconds=received_seconds)
    quote = CurrentWebullStockQuoteV1(
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
    quote_bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(quote,),
        captured_at_utc=received + timedelta(seconds=1),
    )
    position = runtime.current_account().state.open_positions[0]
    price_triggered = (
        bid <= plan_book.plans[0].stop_price_per_unit
        or bid >= plan_book.plans[0].target_price_per_unit
    )
    fees = (
        {position.position_fingerprint: 1.25}
        if price_triggered
        else {}
    )
    built_at = TIME_SLOT + timedelta(
        seconds=(
            received_seconds + 2
            if built_seconds is None
            else built_seconds
        )
    )
    return build_current_webull_decision_stock_close_evidence_bundle_v1(
        account=runtime.current_account(),
        identity=_time_identity(),
        exit_plan_book=plan_book,
        quote_bundle=quote_bundle,
        explicit_exit_fees_by_position=fees,
        fee_source_id=(
            "time-close-price-fees"
            if price_triggered
            else None
        ),
        fee_source_fingerprint=(
            EXIT_FEE_SOURCE_FP
            if price_triggered
            else None
        ),
        built_at_utc=built_at,
    )


def _time_disposition_for(price_bundle, clock_book):
    return build_forecast_horizon_time_disposition_bundle_v1(
        source_clock_book=clock_book,
        evaluation_utc=price_bundle.built_at_utc,
    )


def test_time_aware_close_contract_fingerprint_is_frozen() -> None:
    assert (
        CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT
        == "7b3a9f25959002ea070eca4611a16ce57f73771430d7075f855cd924ca7cac45"
    )


@pytest.mark.parametrize(
    ("bid", "ask", "expected"),
    (
        (99.20, 99.30, FinalStockCloseDisposition.STOP),
        (102.30, 102.40, FinalStockCloseDisposition.TARGET),
    ),
)
def test_price_trigger_retains_precedence_when_time_is_expired(
    tmp_path,
    bid,
    ask,
    expected,
) -> None:
    settings = _settings(tmp_path)
    runtime, plan_book, clock_book = _open_time_position_and_plan(
        settings
    )
    price_bundle = _time_price_close_bundle(
        runtime=runtime,
        plan_book=plan_book,
        bid=bid,
        ask=ask,
        received_seconds=70,
    )
    time_bundle = _time_disposition_for(
        price_bundle,
        clock_book,
    )
    assert time_bundle.dispositions[0].disposition == (
        ForecastHorizonTimeDispositionKind.TIME_EXPIRED
    )

    final = build_current_webull_time_aware_stock_close_bundle_v1(
        account=runtime.current_account(),
        identity=_time_identity(),
        price_close_bundle=price_bundle,
        time_disposition_bundle=time_bundle,
        explicit_time_exit_fees_by_position={},
    )
    row = final.rows[0]
    assert row.final_disposition == expected
    assert row.final_fill == price_bundle.triggers[0].fill
    assert row.explicit_time_exit_fee_dollars is None
    assert final.time_fee_source_id is None


def test_no_trigger_before_deadline_remains_no_trigger(tmp_path) -> None:
    settings = _settings(tmp_path)
    runtime, plan_book, clock_book = _open_time_position_and_plan(
        settings
    )
    price_bundle = _time_price_close_bundle(
        runtime=runtime,
        plan_book=plan_book,
        bid=100.50,
        ask=100.60,
        received_seconds=30,
    )
    time_bundle = _time_disposition_for(
        price_bundle,
        clock_book,
    )
    assert time_bundle.dispositions[0].disposition == (
        ForecastHorizonTimeDispositionKind.NOT_EXPIRED
    )
    final = build_current_webull_time_aware_stock_close_bundle_v1(
        account=runtime.current_account(),
        identity=_time_identity(),
        price_close_bundle=price_bundle,
        time_disposition_bundle=time_bundle,
        explicit_time_exit_fees_by_position={},
    )
    assert final.rows[0].final_disposition == (
        FinalStockCloseDisposition.NO_TRIGGER
    )
    assert final.rows[0].final_fill is None
    assert final.triggered_fills == ()


def test_expired_no_trigger_becomes_time_exit_and_roundtrips(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    runtime, plan_book, clock_book = _open_time_position_and_plan(
        settings
    )
    position = runtime.current_account().state.open_positions[0]
    price_bundle = _time_price_close_bundle(
        runtime=runtime,
        plan_book=plan_book,
        bid=100.50,
        ask=100.60,
        received_seconds=70,
    )
    time_bundle = _time_disposition_for(
        price_bundle,
        clock_book,
    )
    assert time_bundle.dispositions[0].disposition == (
        ForecastHorizonTimeDispositionKind.TIME_EXPIRED
    )

    final = build_current_webull_time_aware_stock_close_bundle_v1(
        account=runtime.current_account(),
        identity=_time_identity(),
        price_close_bundle=price_bundle,
        time_disposition_bundle=time_bundle,
        explicit_time_exit_fees_by_position={
            position.position_fingerprint: 1.10,
        },
        time_fee_source_id="explicit-time-exit-fees-v1",
        time_fee_source_fingerprint=TIME_EXIT_FEE_SOURCE_FP,
    )
    row = final.rows[0]
    assert row.final_disposition == FinalStockCloseDisposition.TIME
    assert row.price_trigger.disposition == (
        StockExitTriggerDisposition.NO_TRIGGER
    )
    assert row.final_fill is not None
    assert row.final_fill.exit_price_per_unit == pytest.approx(100.50)
    assert row.final_fill.exit_fees_dollars == pytest.approx(1.10)
    assert row.final_fill.exited_utc == row.price_trigger.quote.received_at_utc

    path = write_current_webull_time_aware_stock_close_bundle_v1(
        settings,
        final,
    )
    restored = read_current_webull_time_aware_stock_close_bundle_v1(
        settings,
        path=path,
    )
    assert restored == final

    runtime.apply_close_batch(final.triggered_fills)
    assert runtime.current_account().state.open_positions == ()
    assert len(runtime.current_account().state.closed_trades) == 1


def test_time_exit_rejects_quote_received_before_deadline(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    runtime, plan_book, clock_book = _open_time_position_and_plan(
        settings
    )
    position = runtime.current_account().state.open_positions[0]
    price_bundle = _time_price_close_bundle(
        runtime=runtime,
        plan_book=plan_book,
        bid=100.50,
        ask=100.60,
        received_seconds=60,
        built_seconds=72,
    )
    time_bundle = _time_disposition_for(
        price_bundle,
        clock_book,
    )
    assert time_bundle.dispositions[0].disposition == (
        ForecastHorizonTimeDispositionKind.TIME_EXPIRED
    )
    assert price_bundle.triggers[0].quote.received_at_utc < (
        time_bundle.dispositions[0].deadline_utc
    )

    with pytest.raises(
        CurrentWebullTimeAwareStockCloseError,
        match="quote received at or after deadline",
    ):
        build_current_webull_time_aware_stock_close_bundle_v1(
            account=runtime.current_account(),
            identity=_time_identity(),
            price_close_bundle=price_bundle,
            time_disposition_bundle=time_bundle,
            explicit_time_exit_fees_by_position={
                position.position_fingerprint: 1.10,
            },
            time_fee_source_id="explicit-time-exit-fees-v1",
            time_fee_source_fingerprint=TIME_EXIT_FEE_SOURCE_FP,
        )


def test_time_exit_requires_exact_time_fee_source(tmp_path) -> None:
    settings = _settings(tmp_path)
    runtime, plan_book, clock_book = _open_time_position_and_plan(
        settings
    )
    position = runtime.current_account().state.open_positions[0]
    price_bundle = _time_price_close_bundle(
        runtime=runtime,
        plan_book=plan_book,
        bid=100.50,
        ask=100.60,
        received_seconds=70,
    )
    time_bundle = _time_disposition_for(
        price_bundle,
        clock_book,
    )
    with pytest.raises(
        CurrentWebullTimeAwareStockCloseError,
        match="require explicit time-fee source evidence",
    ):
        build_current_webull_time_aware_stock_close_bundle_v1(
            account=runtime.current_account(),
            identity=_time_identity(),
            price_close_bundle=price_bundle,
            time_disposition_bundle=time_bundle,
            explicit_time_exit_fees_by_position={
                position.position_fingerprint: 1.10,
            },
        )
