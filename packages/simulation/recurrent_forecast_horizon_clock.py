from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel

from packages.core.constants import DEFAULT_EXCHANGE_CALENDAR
from packages.core.enums import SessionSegment
from packages.core.market_calendar import (
    MarketCalendar,
    get_market_calendar,
)
from packages.schemas.move_time_forecast import ForecastHorizonUnit
from packages.schemas.move_time_forecast_contract import (
    MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
    RecurrentDecisionStockExitPlanV1,
)
from packages.simulation.recurrent_forecast_horizon_clock_contract import (
    RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT,
    RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
)


RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_VERSION = str(
    RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT["contract_id"]
)
_SECONDS_PER_MINUTE = 60


class RecurrentForecastHorizonClockError(RuntimeError):
    pass


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentForecastHorizonClockError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _require_aware(
    value: datetime,
    *,
    label: str,
) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentForecastHorizonClockError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="json"))
    if is_dataclass(value):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    return value


def _fingerprint_payload(value: object) -> str:
    raw = json.dumps(
        _canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _next_session_date(
    calendar: MarketCalendar,
    after_session: date,
) -> date:
    start = after_session + timedelta(days=1)
    cursor = start
    for window_days in (14, 31, 93, 366, 1098):
        end = start + timedelta(days=window_days)
        sessions = calendar.sessions_in_range(cursor, end)
        if sessions:
            return sessions[0]
        cursor = end + timedelta(days=1)
    raise RecurrentForecastHorizonClockError(
        "unable to resolve the next exchange session"
    )


def _session_dates_including_entry(
    *,
    calendar: MarketCalendar,
    entry_session_date: date,
    count: int,
) -> tuple[date, ...]:
    if count < 1:
        raise RecurrentForecastHorizonClockError(
            "session horizon must be positive"
        )
    if not calendar.is_session(entry_session_date):
        raise RecurrentForecastHorizonClockError(
            "entry date is not an exchange session"
        )
    sessions = [entry_session_date]
    while len(sessions) < count:
        sessions.append(
            _next_session_date(
                calendar,
                sessions[-1],
            )
        )
    return tuple(sessions)


def _deadline_for_regular_minutes(
    *,
    calendar: MarketCalendar,
    opened_utc: datetime,
    horizon_minutes: int,
) -> tuple[datetime, tuple[date, ...]]:
    if horizon_minutes < 1:
        raise RecurrentForecastHorizonClockError(
            "minute horizon must be positive"
        )
    opened = _require_aware(
        opened_utc,
        label="position opened time",
    )
    if calendar.classify(opened) != SessionSegment.REGULAR:
        raise RecurrentForecastHorizonClockError(
            "forecast clock requires a regular-session position open"
        )
    session_date = opened.astimezone(
        calendar.market_tz
    ).date()
    remaining_seconds = horizon_minutes * _SECONDS_PER_MINUTE
    cursor = opened
    visited: list[date] = []

    while True:
        regular_open, regular_close = calendar.regular_open_close(
            session_date
        )
        if cursor < regular_open:
            cursor = regular_open
        if cursor > regular_close:
            raise RecurrentForecastHorizonClockError(
                "regular-minute clock cursor exceeded session close"
            )
        if not visited or visited[-1] != session_date:
            visited.append(session_date)

        available_seconds = int(
            (regular_close - cursor).total_seconds()
        )
        if remaining_seconds <= available_seconds:
            return (
                cursor
                + timedelta(seconds=remaining_seconds),
                tuple(visited),
            )

        remaining_seconds -= available_seconds
        session_date = _next_session_date(
            calendar,
            session_date,
        )
        cursor = calendar.regular_open_close(
            session_date
        )[0]


def _deadline_for_sessions(
    *,
    calendar: MarketCalendar,
    opened_utc: datetime,
    horizon_sessions: int,
) -> tuple[datetime, tuple[date, ...]]:
    opened = _require_aware(
        opened_utc,
        label="position opened time",
    )
    if calendar.classify(opened) != SessionSegment.REGULAR:
        raise RecurrentForecastHorizonClockError(
            "forecast clock requires a regular-session position open"
        )
    entry_session_date = opened.astimezone(
        calendar.market_tz
    ).date()
    sessions = _session_dates_including_entry(
        calendar=calendar,
        entry_session_date=entry_session_date,
        count=horizon_sessions,
    )
    deadline = calendar.regular_open_close(
        sessions[-1]
    )[1]
    return deadline, sessions


@dataclass(frozen=True)
class RecurrentForecastHorizonClockV1:
    contract_version: str
    contract_fingerprint: str
    source_exit_plan_contract_fingerprint: str
    source_exit_plan_fingerprint: str
    source_forecast_contract_fingerprint: str
    source_forecast_fingerprint: str
    decision_record_fingerprint: str
    position_fingerprint: str
    instrument_id: str
    ticker: str

    exchange_calendar: str
    opened_utc: datetime
    entry_session_date: date
    horizon_unit: ForecastHorizonUnit
    horizon_value: int
    deadline_utc: datetime
    deadline_session_date: date
    session_dates: tuple[date, ...]

    regular_session_elapsed_minutes: int | None
    included_session_count: int

    time_exit_trigger_authority: bool = False
    close_fill_authority: bool = False
    account_mutation_authority: bool = False
    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    reason_codes: tuple[str, ...] = (
        "CLOCK_STARTS_AT_ACTUAL_SIMULATED_POSITION_OPEN",
        "XNYS_REGULAR_SESSION_BOUNDARIES_FROM_EXCHANGE_CALENDAR",
        "NON_SESSION_TIME_DOES_NOT_ADVANCE_HORIZON",
        "HOLIDAYS_AND_EARLY_CLOSES_FOLLOW_EXCHANGE_CALENDAR",
        "DESCRIPTIVE_DEADLINE_ONLY_NO_TIME_EXIT_TRIGGER_AUTHORITY",
    )

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_VERSION
        ):
            raise RecurrentForecastHorizonClockError(
                "forecast-horizon clock contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        ):
            raise RecurrentForecastHorizonClockError(
                "forecast-horizon clock contract fingerprint mismatch"
            )
        if (
            self.source_exit_plan_contract_fingerprint
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise RecurrentForecastHorizonClockError(
                "forecast-horizon clock exit-plan contract mismatch"
            )
        if (
            self.source_forecast_contract_fingerprint
            != MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
        ):
            raise RecurrentForecastHorizonClockError(
                "forecast-horizon clock source forecast contract mismatch"
            )
        for label, value in (
            ("exit plan", self.source_exit_plan_fingerprint),
            ("forecast", self.source_forecast_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("position", self.position_fingerprint),
        ):
            _require_sha(value, label=label)
        opened = _require_aware(
            self.opened_utc,
            label="forecast-horizon clock opened time",
        )
        deadline = _require_aware(
            self.deadline_utc,
            label="forecast-horizon deadline",
        )
        if deadline <= opened:
            raise RecurrentForecastHorizonClockError(
                "forecast-horizon deadline must follow position open"
            )
        if self.exchange_calendar != DEFAULT_EXCHANGE_CALENDAR:
            raise RecurrentForecastHorizonClockError(
                "forecast-horizon clock v1 requires default exchange calendar"
            )
        if self.horizon_value < 1:
            raise RecurrentForecastHorizonClockError(
                "forecast-horizon value must be positive"
            )
        if not self.session_dates:
            raise RecurrentForecastHorizonClockError(
                "forecast-horizon clock requires session trace"
            )
        if self.session_dates[0] != self.entry_session_date:
            raise RecurrentForecastHorizonClockError(
                "session trace must begin with entry session"
            )
        if self.session_dates[-1] != self.deadline_session_date:
            raise RecurrentForecastHorizonClockError(
                "session trace must end with deadline session"
            )
        if tuple(sorted(set(self.session_dates))) != self.session_dates:
            raise RecurrentForecastHorizonClockError(
                "session trace must be unique and increasing"
            )
        if self.included_session_count != len(
            self.session_dates
        ):
            raise RecurrentForecastHorizonClockError(
                "included session count mismatch"
            )
        if self.horizon_unit == ForecastHorizonUnit.MINUTES:
            if (
                self.regular_session_elapsed_minutes
                != self.horizon_value
            ):
                raise RecurrentForecastHorizonClockError(
                    "minute horizon elapsed-minute trace mismatch"
                )
        elif self.horizon_unit == ForecastHorizonUnit.SESSIONS:
            if self.regular_session_elapsed_minutes is not None:
                raise RecurrentForecastHorizonClockError(
                    "session horizon cannot claim elapsed-minute count"
                )
            if self.included_session_count != self.horizon_value:
                raise RecurrentForecastHorizonClockError(
                    "session horizon must include exactly horizon_value sessions"
                )
        else:
            raise RecurrentForecastHorizonClockError(
                "unsupported forecast horizon unit"
            )
        if any(
            (
                self.time_exit_trigger_authority,
                self.close_fill_authority,
                self.account_mutation_authority,
                self.provider_read_authority,
                self.provider_write_authority,
                self.broker_read_authority,
                self.broker_write_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise RecurrentForecastHorizonClockError(
                "forecast-horizon clock cannot grant trigger, mutation, external, or trading authority"
            )
        if not self.reason_codes:
            raise RecurrentForecastHorizonClockError(
                "forecast-horizon clock requires reason codes"
            )

    @property
    def clock_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def build_recurrent_forecast_horizon_clock_v1(
    *,
    plan: RecurrentDecisionStockExitPlanV1,
    exchange_calendar: str = DEFAULT_EXCHANGE_CALENDAR,
) -> RecurrentForecastHorizonClockV1:
    if (
        plan.contract_fingerprint
        != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ):
        raise RecurrentForecastHorizonClockError(
            "source exit plan contract fingerprint mismatch"
        )
    if plan.time_exit_trigger_enabled:
        raise RecurrentForecastHorizonClockError(
            "source exit plan unexpectedly grants time-exit trigger authority"
        )
    if exchange_calendar != DEFAULT_EXCHANGE_CALENDAR:
        raise RecurrentForecastHorizonClockError(
            "forecast-horizon clock v1 supports XNYS only"
        )

    forecast = plan.decision_record.forecast
    if (
        forecast.contract_fingerprint
        != MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
    ):
        raise RecurrentForecastHorizonClockError(
            "source forecast contract fingerprint mismatch"
        )
    if (
        forecast.horizon_unit != plan.forecast_horizon_unit
        or forecast.horizon_value != plan.forecast_horizon_value
    ):
        raise RecurrentForecastHorizonClockError(
            "source exit plan horizon differs from retained forecast"
        )

    calendar = get_market_calendar(exchange_calendar)
    opened = _require_aware(
        plan.opened_utc,
        label="source exit-plan opened time",
    )
    if forecast.horizon_unit == ForecastHorizonUnit.MINUTES:
        deadline, sessions = _deadline_for_regular_minutes(
            calendar=calendar,
            opened_utc=opened,
            horizon_minutes=forecast.horizon_value,
        )
        elapsed_minutes: int | None = forecast.horizon_value
    elif forecast.horizon_unit == ForecastHorizonUnit.SESSIONS:
        deadline, sessions = _deadline_for_sessions(
            calendar=calendar,
            opened_utc=opened,
            horizon_sessions=forecast.horizon_value,
        )
        elapsed_minutes = None
    else:
        raise RecurrentForecastHorizonClockError(
            "unsupported source forecast horizon unit"
        )

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
        source_exit_plan_fingerprint=plan.plan_fingerprint,
        source_forecast_contract_fingerprint=(
            MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
        ),
        source_forecast_fingerprint=plan.forecast_fingerprint,
        decision_record_fingerprint=(
            plan.decision_record_fingerprint
        ),
        position_fingerprint=plan.position_fingerprint,
        instrument_id=plan.instrument_id,
        ticker=plan.ticker,
        exchange_calendar=exchange_calendar,
        opened_utc=opened,
        entry_session_date=sessions[0],
        horizon_unit=forecast.horizon_unit,
        horizon_value=forecast.horizon_value,
        deadline_utc=deadline,
        deadline_session_date=sessions[-1],
        session_dates=sessions,
        regular_session_elapsed_minutes=elapsed_minutes,
        included_session_count=len(sessions),
    )


__all__ = [
    "RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT",
    "RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_VERSION",
    "RecurrentForecastHorizonClockError",
    "RecurrentForecastHorizonClockV1",
    "build_recurrent_forecast_horizon_clock_v1",
]
