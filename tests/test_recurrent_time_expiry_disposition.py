from __future__ import annotations

import json
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
    RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT,
    RecurrentTimeExpiryDispositionError,
    TimeExpiryDisposition,
    _fingerprint_payload,
    build_recurrent_time_expiry_disposition_bundle_v1,
    read_recurrent_time_expiry_disposition_bundle_v1,
    write_recurrent_time_expiry_disposition_bundle_v1,
)


ENTRY_FEE_SOURCE_FP = "f" * 64
EXIT_POLICY_FP = "e" * 64


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


def _record(*, opened_utc: datetime):
    forecast = UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id="iid-AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=opened_utc - timedelta(minutes=8),
        evidence_cutoff_utc=opened_utc - timedelta(minutes=9),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=120,
        method_id="time-expiry-fixture-v1",
        source_label="time-expiry fixture",
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
        reason_codes=("TIME_EXPIRY_FIXTURE",),
    )
    return build_simulation_decision_record(
        decision_created_utc=opened_utc - timedelta(minutes=7),
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
    opened = datetime(2026, 9, 18, 19, 0, tzinfo=UTC)
    genesis_time = opened - timedelta(minutes=10)
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=genesis_time,
    )

    record = _record(opened_utc=opened)
    identity = build_recurrent_cycle_run_identity_v1(
        schedule_id="time-expiry-fixture-cycle",
        scheduled_for_utc=genesis_time,
    )
    reserve_bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=identity,
        decisions=((record, None),),
        built_at_utc=opened - timedelta(minutes=6),
    )
    runtime.apply_reservation_batch(
        reserve_bundle.runner_decisions
    )

    quote = CurrentWebullStockQuoteV1(
        symbol="AAPL",
        provider_timestamp_utc=opened - timedelta(seconds=1),
        received_at_utc=opened,
        session_date=opened.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=100.0,
        bid_size=10,
        ask_price=100.25,
        ask_size=12,
    )
    quote_bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(quote,),
        captured_at_utc=opened + timedelta(seconds=1),
    )
    entry_bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve_bundle,
        quote_bundle=quote_bundle,
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 2.50,
        },
        fee_source_id="time-expiry-fixture-entry-fees",
        fee_source_fingerprint=ENTRY_FEE_SOURCE_FP,
        built_at_utc=opened + timedelta(seconds=2),
    )
    runtime.apply_entry_batch(entry_bundle.runner_entries)

    state = runtime.current_account().state
    exit_book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=state,
        current_reserve_bundle=reserve_bundle,
        existing_book=None,
        exit_policy_by_decision={
            record.record_fingerprint: StockExitPolicyInputsV1(
                policy_id="time-expiry-fixture-exit-policy-v1",
                policy_fingerprint=EXIT_POLICY_FP,
                stop_threshold_fraction=0.01,
                target_threshold_fraction=0.02,
            ),
        },
        built_at_utc=opened + timedelta(seconds=3),
    )
    plan = exit_book.plans[0]
    clock_book = build_recurrent_forecast_horizon_clock_book_v1(
        exit_plan_book=exit_book,
        existing_book=None,
        clock_policy_by_plan={
            plan.plan_fingerprint: ForecastHorizonClockPolicyV1(),
        },
        built_at_utc=opened + timedelta(seconds=4),
    )
    return settings, clock_book


def test_time_expiry_bundle_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT
        == "36e249c10d7a4bbaba35ace24ef9192e273c5713beb4629b20672fb6b2761b24"
    )


def test_before_deadline_is_not_expired_and_roundtrips(tmp_path) -> None:
    settings, clock_book = _clock_book(tmp_path)
    clock = clock_book.clocks[0]
    evaluation = clock.deadline_utc - timedelta(seconds=1)

    bundle = build_recurrent_time_expiry_disposition_bundle_v1(
        clock_book=clock_book,
        evaluation_utc=evaluation,
    )
    assert bundle.evaluation_utc == evaluation
    assert len(bundle.dispositions) == 1
    item = bundle.dispositions[0]
    assert item.disposition == TimeExpiryDisposition.NOT_EXPIRED
    assert item.signed_seconds_from_deadline == pytest.approx(-1.0)
    assert item.price_evidence_consumed is False
    assert bundle.stop_target_precedence_authority is False
    assert bundle.close_fill_authority is False
    assert bundle.provider_reads == 0
    assert bundle.paper_authority is False

    path = write_recurrent_time_expiry_disposition_bundle_v1(
        settings,
        bundle,
    )
    restored = read_recurrent_time_expiry_disposition_bundle_v1(
        settings,
        path=path,
    )
    assert restored == bundle


def test_exact_deadline_is_time_expired(tmp_path) -> None:
    _settings_obj, clock_book = _clock_book(tmp_path)
    clock = clock_book.clocks[0]
    bundle = build_recurrent_time_expiry_disposition_bundle_v1(
        clock_book=clock_book,
        evaluation_utc=clock.deadline_utc,
    )
    item = bundle.dispositions[0]
    assert item.disposition == TimeExpiryDisposition.TIME_EXPIRED
    assert item.signed_seconds_from_deadline == pytest.approx(0.0)


def test_after_deadline_is_time_expired(tmp_path) -> None:
    _settings_obj, clock_book = _clock_book(tmp_path)
    clock = clock_book.clocks[0]
    bundle = build_recurrent_time_expiry_disposition_bundle_v1(
        clock_book=clock_book,
        evaluation_utc=clock.deadline_utc + timedelta(seconds=30),
    )
    item = bundle.dispositions[0]
    assert item.disposition == TimeExpiryDisposition.TIME_EXPIRED
    assert item.signed_seconds_from_deadline == pytest.approx(30.0)


def test_evaluation_cannot_predate_clock_book(tmp_path) -> None:
    _settings_obj, clock_book = _clock_book(tmp_path)
    with pytest.raises(
        RecurrentTimeExpiryDispositionError,
        match="cannot predate clock-book construction",
    ):
        build_recurrent_time_expiry_disposition_bundle_v1(
            clock_book=clock_book,
            evaluation_utc=clock_book.built_at_utc - timedelta(seconds=1),
        )


def test_rehashed_outer_bundle_cannot_hide_wrong_disposition(
    tmp_path,
) -> None:
    settings, clock_book = _clock_book(tmp_path)
    clock = clock_book.clocks[0]
    evaluation = clock.deadline_utc - timedelta(seconds=1)
    bundle = build_recurrent_time_expiry_disposition_bundle_v1(
        clock_book=clock_book,
        evaluation_utc=evaluation,
    )
    path = write_recurrent_time_expiry_disposition_bundle_v1(
        settings,
        bundle,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["dispositions"][0]["disposition"] = "TIME_EXPIRED"
    fingerprint_payload = dict(payload)
    fingerprint_payload.pop("bundle_fingerprint")
    payload["bundle_fingerprint"] = _fingerprint_payload(
        fingerprint_payload
    )
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RecurrentTimeExpiryDispositionError,
        match="does not match deadline comparison",
    ):
        read_recurrent_time_expiry_disposition_bundle_v1(
            settings,
            path=path,
        )
