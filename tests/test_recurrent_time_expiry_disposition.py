from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from packages.schemas.move_time_forecast import ForecastHorizonUnit
from packages.schemas.move_time_forecast_contract import (
    MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_forecast_horizon_clock import (
    RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
    RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_VERSION,
    RecurrentForecastHorizonClockV1,
)
from packages.simulation.recurrent_time_expiry_disposition import (
    RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_FINGERPRINT,
    RecurrentTimeExpiryDispositionError,
    RecurrentTimeExpiryDispositionV1,
    TimeExpiryDisposition,
    build_recurrent_time_expiry_disposition_v1,
)


OPENED = datetime(2026, 9, 18, 14, 0, tzinfo=UTC)
DEADLINE = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
SESSION = date(2026, 9, 18)


def _clock() -> RecurrentForecastHorizonClockV1:
    return RecurrentForecastHorizonClockV1(
        contract_version=(
            RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        ),
        source_exit_plan_contract_fingerprint=(
            RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ),
        source_exit_plan_fingerprint="a" * 64,
        source_forecast_contract_fingerprint=(
            MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
        ),
        source_forecast_fingerprint="b" * 64,
        decision_record_fingerprint="c" * 64,
        position_fingerprint="d" * 64,
        instrument_id="iid-AAPL",
        ticker="AAPL",
        exchange_calendar="XNYS",
        opened_utc=OPENED,
        entry_session_date=SESSION,
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=60,
        deadline_utc=DEADLINE,
        deadline_session_date=SESSION,
        session_dates=(SESSION,),
        regular_session_elapsed_minutes=60,
        included_session_count=1,
    )


def test_time_expiry_disposition_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_FINGERPRINT
        == "1616a9e5b9c950688081a45e4972e92d59c074a37fc129dc8449cf8fbc20617b"
    )


def test_before_deadline_is_not_expired() -> None:
    evidence = build_recurrent_time_expiry_disposition_v1(
        clock=_clock(),
        evaluation_utc=DEADLINE - timedelta(seconds=1),
    )
    assert evidence.disposition == TimeExpiryDisposition.NOT_EXPIRED
    assert evidence.signed_seconds_from_deadline == pytest.approx(-1.0)
    assert evidence.price_evidence_consumed is False
    assert evidence.close_fill_authority is False
    assert evidence.account_mutation_authority is False


def test_deadline_equality_is_first_expired_instant() -> None:
    evidence = build_recurrent_time_expiry_disposition_v1(
        clock=_clock(),
        evaluation_utc=DEADLINE,
    )
    assert evidence.disposition == TimeExpiryDisposition.TIME_EXPIRED
    assert evidence.signed_seconds_from_deadline == pytest.approx(0.0)


def test_after_deadline_is_expired() -> None:
    evidence = build_recurrent_time_expiry_disposition_v1(
        clock=_clock(),
        evaluation_utc=DEADLINE + timedelta(seconds=30),
    )
    assert evidence.disposition == TimeExpiryDisposition.TIME_EXPIRED
    assert evidence.signed_seconds_from_deadline == pytest.approx(30.0)


def test_timezone_equivalent_evaluations_normalize_identically() -> None:
    clock = _clock()
    utc_evidence = build_recurrent_time_expiry_disposition_v1(
        clock=clock,
        evaluation_utc=DEADLINE,
    )
    eastern = datetime(
        2026,
        9,
        18,
        11,
        0,
        tzinfo=timezone(timedelta(hours=-4)),
    )
    eastern_evidence = build_recurrent_time_expiry_disposition_v1(
        clock=clock,
        evaluation_utc=eastern,
    )
    assert eastern_evidence == utc_evidence
    assert (
        eastern_evidence.disposition_fingerprint
        == utc_evidence.disposition_fingerprint
    )
    assert eastern_evidence.evaluation_utc == DEADLINE


def test_disposition_is_deterministic_and_retains_full_clock() -> None:
    clock = _clock()
    first = build_recurrent_time_expiry_disposition_v1(
        clock=clock,
        evaluation_utc=DEADLINE - timedelta(minutes=5),
    )
    second = build_recurrent_time_expiry_disposition_v1(
        clock=clock,
        evaluation_utc=DEADLINE - timedelta(minutes=5),
    )
    assert first == second
    assert first.clock == clock
    assert first.source_clock_fingerprint == clock.clock_fingerprint
    assert first.source_exit_plan_fingerprint == (
        clock.source_exit_plan_fingerprint
    )
    assert first.position_fingerprint == clock.position_fingerprint
    assert first.disposition_fingerprint == second.disposition_fingerprint


def test_typed_evidence_rejects_wrong_disposition_for_timestamp() -> None:
    clock = _clock()
    with pytest.raises(
        RecurrentTimeExpiryDispositionError,
        match="does not match deadline comparison",
    ):
        RecurrentTimeExpiryDispositionV1(
            contract_version=(
                "atlas-simulation-recurrent-time-expiry-disposition-v1"
            ),
            contract_fingerprint=(
                RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_FINGERPRINT
            ),
            source_clock_contract_fingerprint=(
                RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
            ),
            source_clock_fingerprint=clock.clock_fingerprint,
            clock=clock,
            source_exit_plan_fingerprint=(
                clock.source_exit_plan_fingerprint
            ),
            position_fingerprint=clock.position_fingerprint,
            ticker=clock.ticker,
            evaluation_utc=DEADLINE - timedelta(seconds=1),
            deadline_utc=DEADLINE,
            disposition=TimeExpiryDisposition.TIME_EXPIRED,
            signed_seconds_from_deadline=-1.0,
        )
