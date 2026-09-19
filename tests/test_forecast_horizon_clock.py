from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from packages.core.market_calendar import get_market_calendar
from packages.schemas.move_time_forecast import ForecastHorizonUnit
from packages.simulation.forecast_horizon_clock import (
    FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
    ForecastHorizonClockError,
    ForecastHorizonClockPolicyV1,
    SessionHorizonCountingPolicy,
    _add_regular_session_minutes,
    _nth_session_from_entry,
    build_forecast_horizon_clock_evidence_v1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
)


@dataclass(frozen=True)
class _PlanFixture:
    contract_fingerprint: str
    plan_fingerprint: str
    opened_utc: datetime
    forecast_horizon_unit: ForecastHorizonUnit
    forecast_horizon_value: int


def _plan(
    *,
    opened_utc: datetime,
    unit: ForecastHorizonUnit,
    value: int,
) -> _PlanFixture:
    return _PlanFixture(
        contract_fingerprint=(
            RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ),
        plan_fingerprint="a" * 64,
        opened_utc=opened_utc,
        forecast_horizon_unit=unit,
        forecast_horizon_value=value,
    )


def test_forecast_horizon_clock_contract_fingerprint_is_frozen() -> None:
    assert (
        FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        == "a5f3b07439b4ca9f2984aaae30dc7333fc93253ae781513edf99756283318d55"
    )


def test_regular_minutes_pause_overnight_and_weekend() -> None:
    calendar = get_market_calendar()
    friday = datetime(2026, 9, 18, 19, 0, tzinfo=UTC)
    assert calendar.classify(friday).value == "REGULAR"

    expiry = _add_regular_session_minutes(
        calendar=calendar,
        opened_utc=friday,
        minutes=120,
    )
    monday = calendar.sessions_in_range(
        datetime(2026, 9, 21).date(),
        datetime(2026, 9, 21).date(),
    )[0]
    monday_open, _monday_close = calendar.regular_open_close(
        monday
    )
    assert expiry == monday_open + timedelta(minutes=60)


def test_regular_minutes_respect_official_early_close() -> None:
    calendar = get_market_calendar()
    early_close_date = datetime(2026, 11, 27).date()
    regular_open, regular_close = calendar.regular_open_close(
        early_close_date
    )
    assert (regular_close - regular_open) < timedelta(hours=6)

    opened = regular_close - timedelta(minutes=30)
    expiry = _add_regular_session_minutes(
        calendar=calendar,
        opened_utc=opened,
        minutes=90,
    )
    next_session = calendar.sessions_in_range(
        datetime(2026, 11, 30).date(),
        datetime(2026, 11, 30).date(),
    )[0]
    next_open, _next_close = calendar.regular_open_close(
        next_session
    )
    assert expiry == next_open + timedelta(minutes=60)


def test_session_counting_policies_are_explicitly_different() -> None:
    calendar = get_market_calendar()
    entry_session = datetime(2026, 9, 18).date()

    included = _nth_session_from_entry(
        calendar=calendar,
        entry_session=entry_session,
        horizon_value=1,
        policy=SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED,
    )
    following = _nth_session_from_entry(
        calendar=calendar,
        entry_session=entry_session,
        horizon_value=1,
        policy=(
            SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY
        ),
    )
    assert included == entry_session
    assert following == datetime(2026, 9, 21).date()


def test_minute_horizon_end_to_end_uses_regular_elapsed_time_only() -> None:
    opened = datetime(2026, 9, 18, 19, 0, tzinfo=UTC)
    plan = _plan(
        opened_utc=opened,
        unit=ForecastHorizonUnit.MINUTES,
        value=120,
    )
    policy = ForecastHorizonClockPolicyV1()
    before = build_forecast_horizon_clock_evidence_v1(
        plan=plan,
        evaluation_utc=datetime(2026, 9, 19, 18, 0, tzinfo=UTC),
        policy=policy,
    )
    assert before.expired is False
    assert before.regular_session_elapsed_minutes == pytest.approx(
        60.0
    )

    at_expiry = build_forecast_horizon_clock_evidence_v1(
        plan=plan,
        evaluation_utc=before.expiry_utc,
        policy=policy,
    )
    assert at_expiry.expired is True
    assert at_expiry.regular_session_elapsed_minutes == pytest.approx(
        120.0
    )
    assert at_expiry.price_trigger_authority is False
    assert at_expiry.close_fill_authority is False
    assert at_expiry.provider_reads == 0
    assert at_expiry.broker_writes == 0


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
def test_session_horizon_expiry_uses_explicit_policy(
    counting_policy,
    expected_date,
) -> None:
    calendar = get_market_calendar()
    opened = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    plan = _plan(
        opened_utc=opened,
        unit=ForecastHorizonUnit.SESSIONS,
        value=1,
    )
    policy = ForecastHorizonClockPolicyV1(
        session_counting_policy=counting_policy,
    )
    evidence = build_forecast_horizon_clock_evidence_v1(
        plan=plan,
        evaluation_utc=opened,
        policy=policy,
    )
    assert evidence.expiry_utc == calendar.regular_open_close(
        expected_date
    )[1]


def test_session_horizon_requires_policy_and_minutes_reject_it() -> None:
    opened = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    session_plan = _plan(
        opened_utc=opened,
        unit=ForecastHorizonUnit.SESSIONS,
        value=1,
    )
    with pytest.raises(
        ForecastHorizonClockError,
        match="session horizon requires explicit counting policy",
    ):
        build_forecast_horizon_clock_evidence_v1(
            plan=session_plan,
            evaluation_utc=opened,
            policy=ForecastHorizonClockPolicyV1(),
        )

    minute_plan = _plan(
        opened_utc=opened,
        unit=ForecastHorizonUnit.MINUTES,
        value=30,
    )
    with pytest.raises(
        ForecastHorizonClockError,
        match="minute horizon cannot carry session-counting policy",
    ):
        build_forecast_horizon_clock_evidence_v1(
            plan=minute_plan,
            evaluation_utc=opened,
            policy=ForecastHorizonClockPolicyV1(
                session_counting_policy=(
                    SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED
                ),
            ),
        )


def test_clock_rejects_evaluation_before_position_open() -> None:
    opened = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    with pytest.raises(
        ForecastHorizonClockError,
        match="cannot predate position open",
    ):
        build_forecast_horizon_clock_evidence_v1(
            plan=_plan(
                opened_utc=opened,
                unit=ForecastHorizonUnit.MINUTES,
                value=30,
            ),
            evaluation_utc=opened - timedelta(seconds=1),
            policy=ForecastHorizonClockPolicyV1(),
        )
