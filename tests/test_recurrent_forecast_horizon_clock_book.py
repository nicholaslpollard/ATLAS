from __future__ import annotations

from dataclasses import replace
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
    SessionHorizonCountingPolicy,
)
from packages.simulation.recurrent_cycle_runner import (
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RecurrentDecisionStockExitPlanBookV1,
    StockExitPolicyInputsV1,
    _book_payload as _exit_plan_book_payload,
    _fingerprint_payload as _exit_plan_fingerprint_payload,
    build_recurrent_decision_stock_exit_plan_book_v1,
)
from packages.simulation.recurrent_forecast_horizon_clock_book import (
    RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT,
    RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION,
    RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID,
    RecurrentForecastHorizonClockBookError,
    RecurrentForecastHorizonClockBookV1,
    _book_payload,
    _fingerprint_payload,
    build_recurrent_forecast_horizon_clock_book_v1,
    read_recurrent_forecast_horizon_clock_book_v1,
    write_recurrent_forecast_horizon_clock_book_v1,
)
from packages.simulation.recurrent_genesis import (
    bootstrap_recurrent_genesis_v1,
)
from packages.simulation.recurrent_reserve_evidence import (
    build_recurrent_reserve_evidence_bundle_v1,
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


def _record(
    *,
    opened_utc: datetime,
    unit: ForecastHorizonUnit,
    value: int,
):
    forecast = UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id="iid-AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=opened_utc - timedelta(minutes=8),
        evidence_cutoff_utc=opened_utc - timedelta(minutes=9),
        horizon_unit=unit,
        horizon_value=value,
        method_id="clock-book-fixture-v1",
        source_label="clock-book fixture",
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
        reason_codes=("CLOCK_BOOK_FIXTURE",),
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


def _open_exit_plan_book(
    tmp_path,
    *,
    opened_utc: datetime,
    unit: ForecastHorizonUnit,
    value: int,
):
    settings = _settings(tmp_path)
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    genesis_time = opened_utc - timedelta(minutes=10)
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=genesis_time,
    )
    record = _record(
        opened_utc=opened_utc,
        unit=unit,
        value=value,
    )
    identity = build_recurrent_cycle_run_identity_v1(
        schedule_id="clock-book-fixture-cycle",
        scheduled_for_utc=genesis_time,
    )
    reserve_bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=identity,
        decisions=((record, None),),
        built_at_utc=opened_utc - timedelta(minutes=6),
    )
    runtime.apply_reservation_batch(
        reserve_bundle.runner_decisions
    )

    quote = CurrentWebullStockQuoteV1(
        symbol="AAPL",
        provider_timestamp_utc=opened_utc - timedelta(seconds=1),
        received_at_utc=opened_utc,
        session_date=opened_utc.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=100.0,
        bid_size=10,
        ask_price=100.25,
        ask_size=12,
    )
    quote_bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(quote,),
        captured_at_utc=opened_utc + timedelta(seconds=1),
    )
    entry_bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve_bundle,
        quote_bundle=quote_bundle,
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 2.50,
        },
        fee_source_id="clock-book-fixture-entry-fees",
        fee_source_fingerprint=ENTRY_FEE_SOURCE_FP,
        built_at_utc=opened_utc + timedelta(seconds=2),
    )
    runtime.apply_entry_batch(entry_bundle.runner_entries)

    state = runtime.current_account().state
    book = build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=state,
        current_reserve_bundle=reserve_bundle,
        existing_book=None,
        exit_policy_by_decision={
            record.record_fingerprint: StockExitPolicyInputsV1(
                policy_id="clock-book-fixture-exit-policy-v1",
                policy_fingerprint=EXIT_POLICY_FP,
                stop_threshold_fraction=0.01,
                target_threshold_fraction=0.02,
            ),
        },
        built_at_utc=opened_utc + timedelta(seconds=3),
    )
    return settings, book


def test_clock_book_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        == "cf338ae3f654dee31608c2bd62747833d6810936bf0a54dd828c3f9851d709b1"
    )


def test_clock_book_persists_exact_minute_policy_and_roundtrips(
    tmp_path,
) -> None:
    settings, exit_book = _open_exit_plan_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 19, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.MINUTES,
        value=120,
    )
    plan = exit_book.plans[0]
    book = build_recurrent_forecast_horizon_clock_book_v1(
        exit_plan_book=exit_book,
        existing_book=None,
        clock_policy_by_plan={
            plan.plan_fingerprint: ForecastHorizonClockPolicyV1(),
        },
        built_at_utc=exit_book.built_at_utc + timedelta(seconds=1),
    )
    assert len(book.clocks) == 1
    clock = book.clocks[0]
    assert clock.source_exit_plan_fingerprint == plan.plan_fingerprint
    assert clock.policy.session_counting_policy is None
    assert clock.time_exit_disposition_authority is False
    assert book.provider_reads == 0
    assert book.paper_authority is False

    path = write_recurrent_forecast_horizon_clock_book_v1(
        settings,
        book,
    )
    restored = read_recurrent_forecast_horizon_clock_book_v1(
        settings,
        path=path,
    )
    assert restored == book


def test_existing_clock_is_carried_without_redefining_policy(
    tmp_path,
) -> None:
    _settings_obj, exit_book = _open_exit_plan_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.SESSIONS,
        value=2,
    )
    plan = exit_book.plans[0]
    policy = ForecastHorizonClockPolicyV1(
        session_counting_policy=(
            SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY
        ),
    )
    first = build_recurrent_forecast_horizon_clock_book_v1(
        exit_plan_book=exit_book,
        existing_book=None,
        clock_policy_by_plan={
            plan.plan_fingerprint: policy,
        },
        built_at_utc=exit_book.built_at_utc + timedelta(seconds=1),
    )
    carried = build_recurrent_forecast_horizon_clock_book_v1(
        exit_plan_book=exit_book,
        existing_book=first,
        clock_policy_by_plan={},
        built_at_utc=first.built_at_utc + timedelta(seconds=1),
    )
    assert carried.clocks == first.clocks
    assert carried.clocks[0].policy == policy


def test_existing_clock_rejects_policy_redefinition(tmp_path) -> None:
    _settings_obj, exit_book = _open_exit_plan_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.SESSIONS,
        value=1,
    )
    plan = exit_book.plans[0]
    first = build_recurrent_forecast_horizon_clock_book_v1(
        exit_plan_book=exit_book,
        existing_book=None,
        clock_policy_by_plan={
            plan.plan_fingerprint: ForecastHorizonClockPolicyV1(
                session_counting_policy=(
                    SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED
                ),
            ),
        },
        built_at_utc=exit_book.built_at_utc + timedelta(seconds=1),
    )
    with pytest.raises(
        RecurrentForecastHorizonClockBookError,
        match="coverage must exactly match newly unclocked plans",
    ):
        build_recurrent_forecast_horizon_clock_book_v1(
            exit_plan_book=exit_book,
            existing_book=first,
            clock_policy_by_plan={
                plan.plan_fingerprint: ForecastHorizonClockPolicyV1(
                    session_counting_policy=(
                        SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY
                    ),
                ),
            },
            built_at_utc=first.built_at_utc + timedelta(seconds=1),
        )


def test_new_plan_requires_explicit_clock_policy(tmp_path) -> None:
    _settings_obj, exit_book = _open_exit_plan_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.SESSIONS,
        value=1,
    )
    with pytest.raises(
        RecurrentForecastHorizonClockBookError,
        match="lacks explicit horizon-clock policy",
    ):
        build_recurrent_forecast_horizon_clock_book_v1(
            exit_plan_book=exit_book,
            existing_book=None,
            clock_policy_by_plan={},
            built_at_utc=exit_book.built_at_utc + timedelta(seconds=1),
        )


def test_closed_plan_clock_is_pruned_by_current_exit_plan_book(
    tmp_path,
) -> None:
    _settings_obj, exit_book = _open_exit_plan_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.MINUTES,
        value=60,
    )
    plan = exit_book.plans[0]
    first = build_recurrent_forecast_horizon_clock_book_v1(
        exit_plan_book=exit_book,
        existing_book=None,
        clock_policy_by_plan={
            plan.plan_fingerprint: ForecastHorizonClockPolicyV1(),
        },
        built_at_utc=exit_book.built_at_utc + timedelta(seconds=1),
    )

    empty_built = first.built_at_utc + timedelta(seconds=1)
    empty_payload = _exit_plan_book_payload(
        source_recurrent_state_fingerprint=(
            exit_book.source_recurrent_state_fingerprint
        ),
        built_at_utc=empty_built,
        plans=(),
    )
    empty_exit_book = RecurrentDecisionStockExitPlanBookV1(
        contract_version=exit_book.contract_version,
        contract_fingerprint=exit_book.contract_fingerprint,
        source_id=exit_book.source_id,
        book_fingerprint=_exit_plan_fingerprint_payload(
            empty_payload
        ),
        source_recurrent_state_fingerprint=(
            exit_book.source_recurrent_state_fingerprint
        ),
        built_at_utc=empty_built,
        plans=(),
    )
    pruned = build_recurrent_forecast_horizon_clock_book_v1(
        exit_plan_book=empty_exit_book,
        existing_book=first,
        clock_policy_by_plan={},
        built_at_utc=empty_built + timedelta(seconds=1),
    )
    assert pruned.clocks == ()


def test_clock_book_rederivation_rejects_tampered_deadline(
    tmp_path,
) -> None:
    _settings_obj, exit_book = _open_exit_plan_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 19, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.MINUTES,
        value=120,
    )
    plan = exit_book.plans[0]
    good = build_recurrent_forecast_horizon_clock_book_v1(
        exit_plan_book=exit_book,
        existing_book=None,
        clock_policy_by_plan={
            plan.plan_fingerprint: ForecastHorizonClockPolicyV1(),
        },
        built_at_utc=exit_book.built_at_utc + timedelta(seconds=1),
    )
    tampered_clock = replace(
        good.clocks[0],
        deadline_utc=good.clocks[0].deadline_utc + timedelta(minutes=1),
    )
    tampered_payload = _book_payload(
        exit_plan_book=good.exit_plan_book,
        built_at_utc=good.built_at_utc,
        clocks=(tampered_clock,),
    )
    with pytest.raises(
        RecurrentForecastHorizonClockBookError,
        match="does not match deterministic plan/policy rebuild",
    ):
        RecurrentForecastHorizonClockBookV1(
            contract_version=(
                RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION
            ),
            contract_fingerprint=(
                RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
            ),
            source_id=RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID,
            book_fingerprint=_fingerprint_payload(tampered_payload),
            exit_plan_book=good.exit_plan_book,
            built_at_utc=good.built_at_utc,
            clocks=(tampered_clock,),
        )
