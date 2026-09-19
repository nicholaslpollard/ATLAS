from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel

from packages.core.constants import DEFAULT_EXCHANGE_CALENDAR
from packages.core.enums import SessionSegment
from packages.core.market_calendar import MarketCalendar, get_market_calendar
from packages.core.timestamps import to_market_time
from packages.schemas.move_time_forecast import (
    ForecastHorizonUnit,
    forecast_fingerprint,
)
from packages.schemas.move_time_forecast_contract import (
    MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT,
)
from packages.simulation.forecast_horizon_clock_contract import (
    FORECAST_HORIZON_CLOCK_CONTRACT,
    FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
    RecurrentDecisionStockExitPlanV1,
)


FORECAST_HORIZON_CLOCK_CONTRACT_VERSION = str(
    FORECAST_HORIZON_CLOCK_CONTRACT["contract_id"]
)
_SECONDS_PER_MINUTE = 60
_TOLERANCE_SECONDS = 1e-9


class ForecastHorizonClockError(RuntimeError):
    pass


class SessionHorizonCountingPolicy(StrEnum):
    ENTRY_SESSION_INCLUDED = "ENTRY_SESSION_INCLUDED"
    FULL_SESSIONS_AFTER_ENTRY = "FULL_SESSIONS_AFTER_ENTRY"


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ForecastHorizonClockError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ForecastHorizonClockError(
            f"{label} must be a SHA-256 fingerprint"
        )


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


@dataclass(frozen=True)
class ForecastHorizonClockPolicyV1:
    exchange_calendar: str = DEFAULT_EXCHANGE_CALENDAR
    session_counting_policy: SessionHorizonCountingPolicy | None = None

    def __post_init__(self) -> None:
        if self.exchange_calendar != DEFAULT_EXCHANGE_CALENDAR:
            raise ForecastHorizonClockError(
                "forecast-horizon clock v1 requires the default XNYS calendar"
            )

    @property
    def policy_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _next_session_date(
    calendar: MarketCalendar,
    after_session: date,
) -> date:
    cursor = after_session + timedelta(days=1)
    for window_days in (14, 31, 93, 366, 1098):
        end = cursor + timedelta(days=window_days)
        sessions = calendar.sessions_in_range(cursor, end)
        if sessions:
            return sessions[0]
        cursor = end + timedelta(days=1)
    raise ForecastHorizonClockError(
        "unable to resolve the next exchange session"
    )


def _deadline_for_regular_minutes(
    *,
    calendar: MarketCalendar,
    opened_utc: datetime,
    horizon_minutes: int,
) -> tuple[datetime, tuple[date, ...]]:
    if horizon_minutes < 1:
        raise ForecastHorizonClockError(
            "minute horizon must be positive"
        )
    opened = _require_aware(
        opened_utc,
        label="position opened time",
    )
    if calendar.classify(opened) != SessionSegment.REGULAR:
        raise ForecastHorizonClockError(
            "minute-horizon position open must be in regular session"
        )

    session_date = to_market_time(
        opened,
        calendar.market_tz,
    ).date()
    remaining_seconds = float(
        horizon_minutes * _SECONDS_PER_MINUTE
    )
    cursor = opened
    visited: list[date] = []

    for _ in range(10000):
        regular_open, regular_close = calendar.regular_open_close(
            session_date
        )
        if cursor < regular_open:
            cursor = regular_open
        if cursor >= regular_close:
            session_date = _next_session_date(
                calendar,
                session_date,
            )
            cursor = calendar.regular_open_close(
                session_date
            )[0]
            continue
        if not visited or visited[-1] != session_date:
            visited.append(session_date)

        available_seconds = (
            regular_close - cursor
        ).total_seconds()
        if remaining_seconds <= (
            available_seconds + _TOLERANCE_SECONDS
        ):
            deadline = cursor + timedelta(
                seconds=remaining_seconds
            )
            return deadline, tuple(visited)

        remaining_seconds -= available_seconds
        session_date = _next_session_date(
            calendar,
            session_date,
        )
        cursor = calendar.regular_open_close(
            session_date
        )[0]

    raise ForecastHorizonClockError(
        "minute horizon exceeds supported calendar traversal"
    )


def _counted_sessions(
    *,
    calendar: MarketCalendar,
    entry_session: date,
    horizon_sessions: int,
    policy: SessionHorizonCountingPolicy,
) -> tuple[date, ...]:
    if horizon_sessions < 1:
        raise ForecastHorizonClockError(
            "session horizon must be positive"
        )
    if not calendar.is_session(entry_session):
        raise ForecastHorizonClockError(
            "entry date is not an exchange session"
        )

    if policy == SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED:
        current = entry_session
    elif (
        policy
        == SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY
    ):
        current = _next_session_date(
            calendar,
            entry_session,
        )
    else:
        raise ForecastHorizonClockError(
            "unsupported session horizon counting policy"
        )

    sessions = [current]
    while len(sessions) < horizon_sessions:
        sessions.append(
            _next_session_date(
                calendar,
                sessions[-1],
            )
        )
    return tuple(sessions)


def _deadline_for_sessions(
    *,
    calendar: MarketCalendar,
    opened_utc: datetime,
    horizon_sessions: int,
    policy: SessionHorizonCountingPolicy,
) -> tuple[datetime, date, tuple[date, ...]]:
    opened = _require_aware(
        opened_utc,
        label="position opened time",
    )
    if calendar.classify(opened) != SessionSegment.REGULAR:
        raise ForecastHorizonClockError(
            "session-horizon position open must be in regular session"
        )
    entry_session = to_market_time(
        opened,
        calendar.market_tz,
    ).date()
    counted = _counted_sessions(
        calendar=calendar,
        entry_session=entry_session,
        horizon_sessions=horizon_sessions,
        policy=policy,
    )
    deadline = calendar.regular_open_close(
        counted[-1]
    )[1]
    return deadline, entry_session, counted


@dataclass(frozen=True)
class ForecastHorizonClockV1:
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

    policy: ForecastHorizonClockPolicyV1
    policy_fingerprint: str
    exchange_calendar: str
    opened_utc: datetime
    entry_session_date: date
    horizon_unit: ForecastHorizonUnit
    horizon_value: int
    deadline_utc: datetime
    deadline_session_date: date
    counted_session_dates: tuple[date, ...]
    regular_session_minutes_to_deadline: int | None
    counted_session_count: int

    time_exit_disposition_authority: bool = False
    price_trigger_authority: bool = False
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
        "EXACT_DECISION_BOUND_EXIT_PLAN_CLOCKED",
        "XNYS_REGULAR_SESSION_CALENDAR_USED",
        "HORIZON_DEADLINE_DESCRIPTIVE_ONLY",
        "NO_EXPIRY_DISPOSITION_OR_CLOSE_AUTHORITY_GRANTED",
    )

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != FORECAST_HORIZON_CLOCK_CONTRACT_VERSION
        ):
            raise ForecastHorizonClockError(
                "forecast-horizon clock contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        ):
            raise ForecastHorizonClockError(
                "forecast-horizon clock contract fingerprint mismatch"
            )
        if (
            self.source_exit_plan_contract_fingerprint
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise ForecastHorizonClockError(
                "forecast-horizon clock exit-plan contract mismatch"
            )
        if (
            self.source_forecast_contract_fingerprint
            != MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
        ):
            raise ForecastHorizonClockError(
                "forecast-horizon clock forecast contract mismatch"
            )
        for label, value in (
            ("exit plan", self.source_exit_plan_fingerprint),
            ("forecast", self.source_forecast_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("position", self.position_fingerprint),
            ("policy", self.policy_fingerprint),
        ):
            _require_sha(value, label=label)

        opened = _require_aware(
            self.opened_utc,
            label="forecast-horizon clock opened time",
        )
        deadline = _require_aware(
            self.deadline_utc,
            label="forecast-horizon clock deadline",
        )
        if deadline <= opened:
            raise ForecastHorizonClockError(
                "forecast-horizon deadline must follow position open"
            )
        if self.policy.policy_fingerprint != self.policy_fingerprint:
            raise ForecastHorizonClockError(
                "forecast-horizon clock policy fingerprint mismatch"
            )
        if (
            self.exchange_calendar
            != self.policy.exchange_calendar
            or self.exchange_calendar
            != DEFAULT_EXCHANGE_CALENDAR
        ):
            raise ForecastHorizonClockError(
                "forecast-horizon clock exchange-calendar mismatch"
            )
        if self.horizon_value < 1:
            raise ForecastHorizonClockError(
                "forecast-horizon value must be positive"
            )
        if not self.counted_session_dates:
            raise ForecastHorizonClockError(
                "forecast-horizon clock requires counted-session trace"
            )
        if (
            tuple(sorted(set(self.counted_session_dates)))
            != self.counted_session_dates
        ):
            raise ForecastHorizonClockError(
                "counted-session trace must be unique and increasing"
            )
        if (
            self.counted_session_dates[-1]
            != self.deadline_session_date
        ):
            raise ForecastHorizonClockError(
                "counted-session trace must end with deadline session"
            )
        if self.counted_session_count != len(
            self.counted_session_dates
        ):
            raise ForecastHorizonClockError(
                "counted-session count mismatch"
            )

        if self.horizon_unit == ForecastHorizonUnit.MINUTES:
            if self.policy.session_counting_policy is not None:
                raise ForecastHorizonClockError(
                    "minute horizon cannot carry session-counting policy"
                )
            if (
                self.regular_session_minutes_to_deadline
                != self.horizon_value
            ):
                raise ForecastHorizonClockError(
                    "minute horizon elapsed-minute value mismatch"
                )
            if (
                self.counted_session_dates[0]
                != self.entry_session_date
            ):
                raise ForecastHorizonClockError(
                    "minute horizon trace must begin with entry session"
                )
        elif self.horizon_unit == ForecastHorizonUnit.SESSIONS:
            if self.policy.session_counting_policy is None:
                raise ForecastHorizonClockError(
                    "session horizon requires explicit counting policy"
                )
            if self.regular_session_minutes_to_deadline is not None:
                raise ForecastHorizonClockError(
                    "session horizon cannot claim elapsed-minute total"
                )
            if self.counted_session_count != self.horizon_value:
                raise ForecastHorizonClockError(
                    "session horizon must count exactly horizon_value sessions"
                )
            if (
                self.policy.session_counting_policy
                == SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED
                and self.counted_session_dates[0]
                != self.entry_session_date
            ):
                raise ForecastHorizonClockError(
                    "entry-session-included trace must begin with entry session"
                )
            if (
                self.policy.session_counting_policy
                == SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY
                and self.counted_session_dates[0]
                == self.entry_session_date
            ):
                raise ForecastHorizonClockError(
                    "full-sessions-after-entry trace cannot count entry session"
                )
        else:
            raise ForecastHorizonClockError(
                "unsupported forecast horizon unit"
            )

        if any(
            (
                self.time_exit_disposition_authority,
                self.price_trigger_authority,
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
            raise ForecastHorizonClockError(
                "forecast-horizon clock cannot grant disposition, mutation, external, or trading authority"
            )
        if not self.reason_codes:
            raise ForecastHorizonClockError(
                "forecast-horizon clock requires reason codes"
            )

    @property
    def clock_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def forecast_horizon_clock_from_payload(
    payload: dict[str, object],
) -> ForecastHorizonClockV1:
    values = dict(payload)
    policy_payload = dict(values["policy"])
    counting = policy_payload.get("session_counting_policy")
    values["policy"] = ForecastHorizonClockPolicyV1(
        exchange_calendar=str(
            policy_payload["exchange_calendar"]
        ),
        session_counting_policy=(
            None
            if counting is None
            else SessionHorizonCountingPolicy(
                str(counting)
            )
        ),
    )
    values["opened_utc"] = datetime.fromisoformat(
        str(values["opened_utc"])
    )
    values["entry_session_date"] = date.fromisoformat(
        str(values["entry_session_date"])
    )
    values["horizon_unit"] = ForecastHorizonUnit(
        str(values["horizon_unit"])
    )
    values["deadline_utc"] = datetime.fromisoformat(
        str(values["deadline_utc"])
    )
    values["deadline_session_date"] = date.fromisoformat(
        str(values["deadline_session_date"])
    )
    values["counted_session_dates"] = tuple(
        date.fromisoformat(str(item))
        for item in values["counted_session_dates"]
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    try:
        return ForecastHorizonClockV1(**values)
    except (KeyError, TypeError, ValueError) as exc:
        raise ForecastHorizonClockError(
            "stored forecast-horizon clock failed typed validation"
        ) from exc


def build_forecast_horizon_clock_v1(
    *,
    plan: RecurrentDecisionStockExitPlanV1,
    policy: ForecastHorizonClockPolicyV1,
) -> ForecastHorizonClockV1:
    if not isinstance(plan, RecurrentDecisionStockExitPlanV1):
        raise ForecastHorizonClockError(
            "forecast-horizon clock requires a typed accepted exit plan"
        )
    if (
        plan.contract_fingerprint
        != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ):
        raise ForecastHorizonClockError(
            "forecast-horizon clock exit-plan contract mismatch"
        )
    if plan.time_exit_trigger_enabled:
        raise ForecastHorizonClockError(
            "source exit plan unexpectedly grants time-exit trigger authority"
        )
    if plan.plan_fingerprint != _fingerprint_payload(plan):
        raise ForecastHorizonClockError(
            "source exit-plan fingerprint verification failed"
        )

    forecast = plan.decision_record.forecast
    if (
        forecast.contract_fingerprint
        != MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
    ):
        raise ForecastHorizonClockError(
            "source forecast contract fingerprint mismatch"
        )
    if (
        forecast_fingerprint(forecast)
        != plan.forecast_fingerprint
    ):
        raise ForecastHorizonClockError(
            "source forecast fingerprint mismatch"
        )
    if (
        forecast.horizon_unit != plan.forecast_horizon_unit
        or forecast.horizon_value != plan.forecast_horizon_value
    ):
        raise ForecastHorizonClockError(
            "source exit-plan horizon differs from retained forecast"
        )

    calendar = get_market_calendar(
        policy.exchange_calendar
    )
    opened = _require_aware(
        plan.opened_utc,
        label="source exit-plan opened time",
    )
    if calendar.classify(opened) != SessionSegment.REGULAR:
        raise ForecastHorizonClockError(
            "forecast-horizon clock requires regular-session position open"
        )
    entry_session = to_market_time(
        opened,
        calendar.market_tz,
    ).date()

    if plan.forecast_horizon_unit == ForecastHorizonUnit.MINUTES:
        if policy.session_counting_policy is not None:
            raise ForecastHorizonClockError(
                "minute horizon cannot carry session-counting policy"
            )
        deadline, counted = _deadline_for_regular_minutes(
            calendar=calendar,
            opened_utc=opened,
            horizon_minutes=plan.forecast_horizon_value,
        )
        elapsed_minutes: int | None = plan.forecast_horizon_value
    elif plan.forecast_horizon_unit == ForecastHorizonUnit.SESSIONS:
        if policy.session_counting_policy is None:
            raise ForecastHorizonClockError(
                "session horizon requires explicit counting policy"
            )
        deadline, resolved_entry, counted = _deadline_for_sessions(
            calendar=calendar,
            opened_utc=opened,
            horizon_sessions=plan.forecast_horizon_value,
            policy=policy.session_counting_policy,
        )
        if resolved_entry != entry_session:
            raise ForecastHorizonClockError(
                "session horizon entry-session resolution mismatch"
            )
        elapsed_minutes = None
    else:
        raise ForecastHorizonClockError(
            "unsupported forecast horizon unit"
        )

    return ForecastHorizonClockV1(
        contract_version=FORECAST_HORIZON_CLOCK_CONTRACT_VERSION,
        contract_fingerprint=(
            FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
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
        policy=policy,
        policy_fingerprint=policy.policy_fingerprint,
        exchange_calendar=policy.exchange_calendar,
        opened_utc=opened,
        entry_session_date=entry_session,
        horizon_unit=plan.forecast_horizon_unit,
        horizon_value=plan.forecast_horizon_value,
        deadline_utc=deadline,
        deadline_session_date=counted[-1],
        counted_session_dates=counted,
        regular_session_minutes_to_deadline=elapsed_minutes,
        counted_session_count=len(counted),
    )


__all__ = [
    "FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT",
    "FORECAST_HORIZON_CLOCK_CONTRACT_VERSION",
    "ForecastHorizonClockError",
    "ForecastHorizonClockPolicyV1",
    "ForecastHorizonClockV1",
    "SessionHorizonCountingPolicy",
    "build_forecast_horizon_clock_v1",
    "forecast_horizon_clock_from_payload",
]
