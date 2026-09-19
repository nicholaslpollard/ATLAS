from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from packages.core.constants import DEFAULT_EXCHANGE_CALENDAR
from packages.core.enums import SessionSegment
from packages.core.market_calendar import get_market_calendar
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
    FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
    ForecastHorizonClockError,
    ForecastHorizonClockPolicyV1,
    SessionHorizonCountingPolicy,
    _counted_sessions,
    _canonicalize,
    _deadline_for_regular_minutes,
    build_forecast_horizon_clock_v1,
    forecast_horizon_clock_from_payload,
)
from packages.simulation.forecast_horizon_clock_book import (
    FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT,
    ForecastHorizonClockBookError,
    build_forecast_horizon_clock_book_v1,
    read_forecast_horizon_clock_book_v1,
    write_forecast_horizon_clock_book_v1,
)
from packages.simulation.forecast_horizon_time_disposition import (
    FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT,
    ForecastHorizonTimeDispositionError,
    ForecastHorizonTimeDispositionKind,
    build_forecast_horizon_time_disposition_bundle_v1,
    read_forecast_horizon_time_disposition_bundle_v1,
    write_forecast_horizon_time_disposition_bundle_v1,
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
                favorable=0.60,
                adverse=0.30,
                favorable_first=0.45,
                adverse_first=0.18,
                median_time=max(0.1, min(20.0, value * 0.25)),
            ),
            _threshold(
                0.02,
                favorable=0.45,
                adverse=0.20,
                favorable_first=0.34,
                adverse_first=0.12,
                median_time=max(0.1, min(45.0, value * 0.50)),
            ),
        ),
        uncertainty_score=0.25,
        reason_codes=("CLOCK_FIXTURE",),
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


def _open_plan_book(
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
        schedule_id="clock-fixture-cycle",
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
        fee_source_id="clock-fixture-entry-fees",
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
                policy_id="clock-fixture-exit-policy-v1",
                policy_fingerprint=EXIT_POLICY_FP,
                stop_threshold_fraction=0.01,
                target_threshold_fraction=0.02,
            ),
        },
        built_at_utc=opened_utc + timedelta(seconds=3),
    )
    assert len(book.plans) == 1
    return book


def _open_plan(
    tmp_path,
    *,
    opened_utc: datetime,
    unit: ForecastHorizonUnit,
    value: int,
):
    return _open_plan_book(
        tmp_path,
        opened_utc=opened_utc,
        unit=unit,
        value=value,
    ).plans[0]


def _empty_plan_book(tmp_path, *, as_of_utc: datetime):
    settings = _settings(tmp_path)
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=as_of_utc,
    )
    return build_recurrent_decision_stock_exit_plan_book_v1(
        source_state=runtime.current_account().state,
        current_reserve_bundle=None,
        existing_book=None,
        exit_policy_by_decision={},
        built_at_utc=as_of_utc,
    )


def test_forecast_horizon_clock_contract_fingerprint_is_frozen() -> None:
    assert (
        FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        == "5efb0fb3b6bd37ba718ced50d1ebcbd589843cc895aba33426aa6235c643a56a"
    )


def test_regular_minutes_pause_overnight_and_weekend() -> None:
    calendar = get_market_calendar()
    friday = datetime(2026, 9, 18, 19, 0, tzinfo=UTC)
    assert calendar.classify(friday) == SessionSegment.REGULAR

    deadline, counted = _deadline_for_regular_minutes(
        calendar=calendar,
        opened_utc=friday,
        horizon_minutes=120,
    )
    monday = datetime(2026, 9, 21).date()
    monday_open, _monday_close = calendar.regular_open_close(
        monday
    )
    assert deadline == monday_open + timedelta(minutes=60)
    assert counted == (
        datetime(2026, 9, 18).date(),
        monday,
    )


def test_regular_minutes_respect_official_early_close() -> None:
    calendar = get_market_calendar()
    early_close_date = datetime(2026, 11, 27).date()
    regular_open, regular_close = calendar.regular_open_close(
        early_close_date
    )
    assert (regular_close - regular_open) < timedelta(hours=6)

    opened = regular_close - timedelta(minutes=30)
    deadline, counted = _deadline_for_regular_minutes(
        calendar=calendar,
        opened_utc=opened,
        horizon_minutes=90,
    )
    next_session = datetime(2026, 11, 30).date()
    next_open, _next_close = calendar.regular_open_close(
        next_session
    )
    assert deadline == next_open + timedelta(minutes=60)
    assert counted == (early_close_date, next_session)


def test_session_counting_policies_are_explicitly_different() -> None:
    calendar = get_market_calendar()
    entry_session = datetime(2026, 9, 18).date()

    included = _counted_sessions(
        calendar=calendar,
        entry_session=entry_session,
        horizon_sessions=1,
        policy=SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED,
    )
    following = _counted_sessions(
        calendar=calendar,
        entry_session=entry_session,
        horizon_sessions=1,
        policy=(
            SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY
        ),
    )
    assert included == (entry_session,)
    assert following == (datetime(2026, 9, 21).date(),)


def test_real_minute_plan_builds_immutable_descriptive_deadline(
    tmp_path,
) -> None:
    opened = datetime(2026, 9, 18, 19, 0, tzinfo=UTC)
    plan = _open_plan(
        tmp_path,
        opened_utc=opened,
        unit=ForecastHorizonUnit.MINUTES,
        value=120,
    )
    clock = build_forecast_horizon_clock_v1(
        plan=plan,
        policy=ForecastHorizonClockPolicyV1(),
    )
    calendar = get_market_calendar()
    monday_open, _monday_close = calendar.regular_open_close(
        datetime(2026, 9, 21).date()
    )
    assert clock.opened_utc == opened
    assert clock.deadline_utc == monday_open + timedelta(minutes=60)
    assert clock.regular_session_minutes_to_deadline == 120
    assert clock.counted_session_dates == (
        datetime(2026, 9, 18).date(),
        datetime(2026, 9, 21).date(),
    )
    assert clock.policy.exchange_calendar == DEFAULT_EXCHANGE_CALENDAR
    assert clock.policy.session_counting_policy is None
    assert not hasattr(clock, "evaluation_utc")
    assert not hasattr(clock, "expired")
    assert clock.time_exit_disposition_authority is False
    assert clock.close_fill_authority is False
    assert clock.provider_read_authority is False
    assert clock.broker_write_authority is False


@pytest.mark.parametrize(
    ("counting_policy", "expected_date"),
    (
        (
            SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED,
            datetime(2026, 9, 18).date(),
        ),
        (
            SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY,
            datetime(2026, 9, 21).date(),
        ),
    ),
)
def test_real_session_plan_requires_explicit_counting_policy(
    tmp_path,
    counting_policy,
    expected_date,
) -> None:
    opened = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    plan = _open_plan(
        tmp_path,
        opened_utc=opened,
        unit=ForecastHorizonUnit.SESSIONS,
        value=1,
    )
    clock = build_forecast_horizon_clock_v1(
        plan=plan,
        policy=ForecastHorizonClockPolicyV1(
            session_counting_policy=counting_policy,
        ),
    )
    calendar = get_market_calendar()
    assert clock.deadline_utc == calendar.regular_open_close(
        expected_date
    )[1]
    assert clock.counted_session_dates == (expected_date,)
    assert clock.counted_session_count == 1
    assert clock.regular_session_minutes_to_deadline is None


def test_session_horizon_requires_policy_and_minutes_reject_it(
    tmp_path,
) -> None:
    opened = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    session_plan = _open_plan(
        tmp_path / "sessions",
        opened_utc=opened,
        unit=ForecastHorizonUnit.SESSIONS,
        value=1,
    )
    with pytest.raises(
        ForecastHorizonClockError,
        match="session horizon requires explicit counting policy",
    ):
        build_forecast_horizon_clock_v1(
            plan=session_plan,
            policy=ForecastHorizonClockPolicyV1(),
        )

    minute_plan = _open_plan(
        tmp_path / "minutes",
        opened_utc=opened,
        unit=ForecastHorizonUnit.MINUTES,
        value=30,
    )
    with pytest.raises(
        ForecastHorizonClockError,
        match="minute horizon cannot carry session-counting policy",
    ):
        build_forecast_horizon_clock_v1(
            plan=minute_plan,
            policy=ForecastHorizonClockPolicyV1(
                session_counting_policy=(
                    SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED
                ),
            ),
        )


def test_v1_rejects_arbitrary_exchange_calendar() -> None:
    with pytest.raises(
        ForecastHorizonClockError,
        match="requires the default XNYS calendar",
    ):
        ForecastHorizonClockPolicyV1(
            exchange_calendar="XNAS",
        )


@dataclass(frozen=True)
class _LookalikePlan:
    contract_fingerprint: str
    plan_fingerprint: str


def test_clock_rejects_lookalike_non_typed_plan() -> None:
    with pytest.raises(
        ForecastHorizonClockError,
        match="typed accepted exit plan",
    ):
        build_forecast_horizon_clock_v1(
            plan=_LookalikePlan(
                contract_fingerprint="445d820b0d4268f10d66b842e3ed341ccadd94363418edf2f4ff30f755e44754",
                plan_fingerprint="a" * 64,
            ),
            policy=ForecastHorizonClockPolicyV1(),
        )


def test_clock_payload_roundtrip_preserves_policy_and_deadline(
    tmp_path,
) -> None:
    opened = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    plan = _open_plan(
        tmp_path,
        opened_utc=opened,
        unit=ForecastHorizonUnit.SESSIONS,
        value=2,
    )
    clock = build_forecast_horizon_clock_v1(
        plan=plan,
        policy=ForecastHorizonClockPolicyV1(
            session_counting_policy=(
                SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY
            ),
        ),
    )
    restored = forecast_horizon_clock_from_payload(
        _canonicalize(clock)
    )
    assert restored == clock
    assert restored.clock_fingerprint == clock.clock_fingerprint


def test_forecast_horizon_clock_book_contract_fingerprint_is_frozen() -> None:
    assert (
        FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        == "b6badd42b77c47f5994db08f5c419991831c232041857f968bde80efd3514017"
    )


def test_clock_book_persists_explicit_minute_policy_and_roundtrips(
    tmp_path,
) -> None:
    opened = datetime(2026, 9, 18, 19, 0, tzinfo=UTC)
    source_book = _open_plan_book(
        tmp_path,
        opened_utc=opened,
        unit=ForecastHorizonUnit.MINUTES,
        value=120,
    )
    position_fp = source_book.plans[0].position_fingerprint
    book = build_forecast_horizon_clock_book_v1(
        source_exit_plan_book=source_book,
        existing_book=None,
        clock_policy_by_position={
            position_fp: ForecastHorizonClockPolicyV1(),
        },
    )
    assert book.source_exit_plan_book == source_book
    assert book.built_at_utc == source_book.built_at_utc
    assert len(book.clocks) == 1
    assert book.clocks[0].position_fingerprint == position_fp
    assert book.clocks[0].policy.session_counting_policy is None
    assert not hasattr(book.clocks[0], "expired")
    assert book.time_exit_disposition_authority is False
    assert book.provider_reads == 0
    assert book.broker_writes == 0

    settings = _settings(tmp_path)
    path = write_forecast_horizon_clock_book_v1(
        settings,
        book,
    )
    restored = read_forecast_horizon_clock_book_v1(
        settings,
        path=path,
    )
    assert restored == book


def test_existing_clock_is_immutable_and_reused_without_new_policy(
    tmp_path,
) -> None:
    opened = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    source_book = _open_plan_book(
        tmp_path,
        opened_utc=opened,
        unit=ForecastHorizonUnit.SESSIONS,
        value=1,
    )
    position_fp = source_book.plans[0].position_fingerprint
    first = build_forecast_horizon_clock_book_v1(
        source_exit_plan_book=source_book,
        existing_book=None,
        clock_policy_by_position={
            position_fp: ForecastHorizonClockPolicyV1(
                session_counting_policy=(
                    SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY
                ),
            ),
        },
    )
    second = build_forecast_horizon_clock_book_v1(
        source_exit_plan_book=source_book,
        existing_book=first,
        clock_policy_by_position={},
    )
    assert second == first

    with pytest.raises(
        ForecastHorizonClockBookError,
        match="coverage must exactly match newly unclocked positions",
    ):
        build_forecast_horizon_clock_book_v1(
            source_exit_plan_book=source_book,
            existing_book=first,
            clock_policy_by_position={
                position_fp: ForecastHorizonClockPolicyV1(
                    session_counting_policy=(
                        SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED
                    ),
                ),
            },
        )


def test_new_position_requires_explicit_clock_policy(tmp_path) -> None:
    source_book = _open_plan_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.MINUTES,
        value=30,
    )
    with pytest.raises(
        ForecastHorizonClockBookError,
        match="lacks explicit forecast-horizon clock policy",
    ):
        build_forecast_horizon_clock_book_v1(
            source_exit_plan_book=source_book,
            existing_book=None,
            clock_policy_by_position={},
        )


def test_clock_book_prunes_closed_position_clocks(tmp_path) -> None:
    opened = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    source_book = _open_plan_book(
        tmp_path / "open",
        opened_utc=opened,
        unit=ForecastHorizonUnit.MINUTES,
        value=30,
    )
    position_fp = source_book.plans[0].position_fingerprint
    existing = build_forecast_horizon_clock_book_v1(
        source_exit_plan_book=source_book,
        existing_book=None,
        clock_policy_by_position={
            position_fp: ForecastHorizonClockPolicyV1(),
        },
    )
    empty_source = _empty_plan_book(
        tmp_path / "empty",
        as_of_utc=opened + timedelta(minutes=10),
    )
    pruned = build_forecast_horizon_clock_book_v1(
        source_exit_plan_book=empty_source,
        existing_book=existing,
        clock_policy_by_position={},
    )
    assert pruned.clocks == ()
    assert pruned.source_exit_plan_book == empty_source


def _clock_book(
    tmp_path,
    *,
    opened_utc: datetime,
    unit: ForecastHorizonUnit,
    value: int,
    session_policy: SessionHorizonCountingPolicy | None = None,
):
    source_book = _open_plan_book(
        tmp_path,
        opened_utc=opened_utc,
        unit=unit,
        value=value,
    )
    position_fp = source_book.plans[0].position_fingerprint
    return build_forecast_horizon_clock_book_v1(
        source_exit_plan_book=source_book,
        existing_book=None,
        clock_policy_by_position={
            position_fp: ForecastHorizonClockPolicyV1(
                session_counting_policy=session_policy,
            ),
        },
    )


def test_forecast_horizon_time_disposition_contract_is_frozen() -> None:
    assert (
        FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT
        == "eda75ce9e816942b46e9c215c429da0b568cd2d2012bba2b09c43fe0672a049b"
    )


def test_time_disposition_before_deadline_is_not_expired(tmp_path) -> None:
    book = _clock_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 19, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.MINUTES,
        value=120,
    )
    clock = book.clocks[0]
    evaluation = clock.deadline_utc - timedelta(microseconds=1)
    bundle = build_forecast_horizon_time_disposition_bundle_v1(
        source_clock_book=book,
        evaluation_utc=evaluation,
    )
    disposition = bundle.dispositions[0]
    assert disposition.disposition == (
        ForecastHorizonTimeDispositionKind.NOT_EXPIRED
    )
    assert disposition.opened_utc == clock.opened_utc
    assert disposition.deadline_utc == clock.deadline_utc
    assert bundle.evaluation_utc == evaluation
    assert bundle.price_trigger_authority is False
    assert bundle.close_precedence_authority is False
    assert bundle.close_fill_authority is False


@pytest.mark.parametrize("offset", (timedelta(0), timedelta(seconds=1)))
def test_time_disposition_at_or_after_deadline_is_expired(
    tmp_path,
    offset,
) -> None:
    book = _clock_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.SESSIONS,
        value=1,
        session_policy=(
            SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY
        ),
    )
    clock = book.clocks[0]
    evaluation = clock.deadline_utc + offset
    bundle = build_forecast_horizon_time_disposition_bundle_v1(
        source_clock_book=book,
        evaluation_utc=evaluation,
    )
    assert bundle.dispositions[0].disposition == (
        ForecastHorizonTimeDispositionKind.TIME_EXPIRED
    )


def test_time_disposition_rejects_evaluation_before_position_open(
    tmp_path,
) -> None:
    book = _clock_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.MINUTES,
        value=30,
    )
    with pytest.raises(
        ForecastHorizonTimeDispositionError,
        match="cannot precede position open",
    ):
        build_forecast_horizon_time_disposition_bundle_v1(
            source_clock_book=book,
            evaluation_utc=book.clocks[0].opened_utc
            - timedelta(microseconds=1),
        )


def test_time_disposition_bundle_roundtrips_full_clock_book(
    tmp_path,
) -> None:
    book = _clock_book(
        tmp_path,
        opened_utc=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
        unit=ForecastHorizonUnit.MINUTES,
        value=30,
    )
    evaluation = book.clocks[0].deadline_utc
    bundle = build_forecast_horizon_time_disposition_bundle_v1(
        source_clock_book=book,
        evaluation_utc=evaluation,
    )
    settings = _settings(tmp_path)
    path = write_forecast_horizon_time_disposition_bundle_v1(
        settings,
        bundle,
    )
    restored = read_forecast_horizon_time_disposition_bundle_v1(
        settings,
        path=path,
    )
    assert restored == bundle
    assert restored.source_clock_book == book
    assert restored.dispositions[0].source_clock_fingerprint == (
        book.clocks[0].clock_fingerprint
    )


def test_empty_clock_book_produces_empty_time_disposition_bundle(
    tmp_path,
) -> None:
    source_plan_book = _empty_plan_book(
        tmp_path,
        as_of_utc=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
    )
    clock_book = build_forecast_horizon_clock_book_v1(
        source_exit_plan_book=source_plan_book,
        existing_book=None,
        clock_policy_by_position={},
    )
    bundle = build_forecast_horizon_time_disposition_bundle_v1(
        source_clock_book=clock_book,
        evaluation_utc=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
    )
    assert bundle.dispositions == ()
    assert bundle.provider_reads == 0
    assert bundle.broker_writes == 0
