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
from packages.schemas.move_time_forecast import ForecastHorizonUnit
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


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
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
    exchange: str = DEFAULT_EXCHANGE_CALENDAR
    session_counting_policy: SessionHorizonCountingPolicy | None = None

    def __post_init__(self) -> None:
        if not self.exchange.strip():
            raise ForecastHorizonClockError(
                "forecast horizon clock exchange cannot be blank"
            )

    @property
    def policy_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _next_session_after(
    calendar: MarketCalendar,
    after_date: date,
) -> date:
    cursor = after_date + timedelta(days=1)
    for _ in range(3700):
        if calendar.is_session(cursor):
            return cursor
        cursor += timedelta(days=1)
    raise ForecastHorizonClockError(
        "unable to resolve next exchange session"
    )


def _nth_session_from_entry(
    *,
    calendar: MarketCalendar,
    entry_session: date,
    horizon_value: int,
    policy: SessionHorizonCountingPolicy,
) -> date:
    if horizon_value < 1:
        raise ForecastHorizonClockError(
            "session horizon must be positive"
        )
    if policy == SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED:
        target = entry_session
        remaining = horizon_value - 1
    elif (
        policy
        == SessionHorizonCountingPolicy.FULL_SESSIONS_AFTER_ENTRY
    ):
        target = _next_session_after(calendar, entry_session)
        remaining = horizon_value - 1
    else:
        raise ForecastHorizonClockError(
            "unsupported session horizon counting policy"
        )
    while remaining:
        target = _next_session_after(calendar, target)
        remaining -= 1
    return target


def _add_regular_session_minutes(
    *,
    calendar: MarketCalendar,
    opened_utc: datetime,
    minutes: int,
) -> datetime:
    if minutes < 1:
        raise ForecastHorizonClockError(
            "minute horizon must be positive"
        )
    opened = _require_aware(
        opened_utc,
        label="position open time",
    )
    if calendar.classify(opened) != SessionSegment.REGULAR:
        raise ForecastHorizonClockError(
            "minute-horizon position open must be in regular session"
        )
    cursor = opened
    remaining_seconds = float(minutes * 60)
    for _ in range(10000):
        session_date = to_market_time(
            cursor,
            calendar.market_tz,
        ).date()
        regular_open, regular_close = calendar.regular_open_close(
            session_date
        )
        if cursor < regular_open:
            cursor = regular_open
        available_seconds = (
            regular_close - cursor
        ).total_seconds()
        if available_seconds < -_TOLERANCE_SECONDS:
            raise ForecastHorizonClockError(
                "regular-session cursor moved beyond official close"
            )
        if remaining_seconds <= (
            available_seconds + _TOLERANCE_SECONDS
        ):
            return cursor + timedelta(
                seconds=remaining_seconds
            )
        remaining_seconds -= max(0.0, available_seconds)
        next_session = _next_session_after(
            calendar,
            session_date,
        )
        cursor = calendar.regular_open_close(
            next_session
        )[0]
    raise ForecastHorizonClockError(
        "minute horizon exceeds supported calendar traversal"
    )


def _regular_elapsed_minutes(
    *,
    calendar: MarketCalendar,
    opened_utc: datetime,
    evaluation_utc: datetime,
) -> float:
    opened = _require_aware(
        opened_utc,
        label="position open time",
    )
    evaluation = _require_aware(
        evaluation_utc,
        label="clock evaluation time",
    )
    if evaluation < opened:
        raise ForecastHorizonClockError(
            "clock evaluation cannot predate position open"
        )
    start_date = to_market_time(
        opened,
        calendar.market_tz,
    ).date()
    end_date = to_market_time(
        evaluation,
        calendar.market_tz,
    ).date()
    total_seconds = 0.0
    for session_date in calendar.sessions_in_range(
        start_date,
        end_date,
    ):
        regular_open, regular_close = calendar.regular_open_close(
            session_date
        )
        left = max(opened, regular_open)
        right = min(evaluation, regular_close)
        if right > left:
            total_seconds += (right - left).total_seconds()
    return total_seconds / 60.0


@dataclass(frozen=True)
class ForecastHorizonClockEvidenceV1:
    contract_version: str
    contract_fingerprint: str
    plan_fingerprint: str
    policy: ForecastHorizonClockPolicyV1
    policy_fingerprint: str

    exchange: str
    horizon_unit: ForecastHorizonUnit
    horizon_value: int
    opened_utc: datetime
    evaluation_utc: datetime
    expiry_utc: datetime
    regular_session_elapsed_minutes: float
    expired: bool

    price_trigger_authority: bool = False
    close_fill_authority: bool = False
    provider_reads: int = 0
    provider_writes: int = 0
    broker_reads: int = 0
    broker_writes: int = 0
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False
    reason_codes: tuple[str, ...] = (
        "EXACT_DECISION_BOUND_EXIT_PLAN_CLOCKED",
        "OFFICIAL_EXCHANGE_REGULAR_SESSION_CALENDAR_USED",
        "NO_CLOSE_OR_TRADING_AUTHORITY_GRANTED",
    )

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != FORECAST_HORIZON_CLOCK_CONTRACT_VERSION
        ):
            raise ForecastHorizonClockError(
                "forecast horizon clock contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        ):
            raise ForecastHorizonClockError(
                "forecast horizon clock contract fingerprint mismatch"
            )
        if len(self.plan_fingerprint) != 64:
            raise ForecastHorizonClockError(
                "forecast horizon clock plan fingerprint is invalid"
            )
        try:
            int(self.plan_fingerprint, 16)
        except ValueError as exc:
            raise ForecastHorizonClockError(
                "forecast horizon clock plan fingerprint is invalid"
            ) from exc
        if self.policy.policy_fingerprint != self.policy_fingerprint:
            raise ForecastHorizonClockError(
                "forecast horizon clock policy fingerprint mismatch"
            )
        if self.exchange != self.policy.exchange:
            raise ForecastHorizonClockError(
                "forecast horizon clock exchange mismatch"
            )
        opened = _require_aware(
            self.opened_utc,
            label="clock evidence position open time",
        )
        evaluation = _require_aware(
            self.evaluation_utc,
            label="clock evidence evaluation time",
        )
        expiry = _require_aware(
            self.expiry_utc,
            label="clock evidence expiry time",
        )
        if evaluation < opened:
            raise ForecastHorizonClockError(
                "clock evidence evaluation predates position open"
            )
        if expiry <= opened:
            raise ForecastHorizonClockError(
                "clock evidence expiry must follow position open"
            )
        if self.regular_session_elapsed_minutes < 0.0:
            raise ForecastHorizonClockError(
                "regular-session elapsed minutes cannot be negative"
            )
        if self.expired != (evaluation >= expiry):
            raise ForecastHorizonClockError(
                "clock expired flag does not match evaluation/expiry"
            )
        if self.horizon_unit == ForecastHorizonUnit.MINUTES:
            if self.policy.session_counting_policy is not None:
                raise ForecastHorizonClockError(
                    "minute horizon cannot carry session-counting policy"
                )
        elif self.horizon_unit == ForecastHorizonUnit.SESSIONS:
            if self.policy.session_counting_policy is None:
                raise ForecastHorizonClockError(
                    "session horizon requires explicit counting policy"
                )
        else:
            raise ForecastHorizonClockError(
                "unsupported forecast horizon unit"
            )
        if any(
            (
                self.price_trigger_authority,
                self.close_fill_authority,
                self.provider_reads,
                self.provider_writes,
                self.broker_reads,
                self.broker_writes,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise ForecastHorizonClockError(
                "forecast horizon clock cannot grant external or trading authority"
            )
        if not self.reason_codes:
            raise ForecastHorizonClockError(
                "forecast horizon clock requires reason codes"
            )

    @property
    def evidence_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def build_forecast_horizon_clock_evidence_v1(
    *,
    plan: RecurrentDecisionStockExitPlanV1,
    evaluation_utc: datetime,
    policy: ForecastHorizonClockPolicyV1,
) -> ForecastHorizonClockEvidenceV1:
    if (
        plan.contract_fingerprint
        != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ):
        raise ForecastHorizonClockError(
            "forecast horizon clock requires accepted exit-plan contract"
        )
    opened = _require_aware(
        plan.opened_utc,
        label="position open time",
    )
    evaluation = _require_aware(
        evaluation_utc,
        label="clock evaluation time",
    )
    if evaluation < opened:
        raise ForecastHorizonClockError(
            "clock evaluation cannot predate position open"
        )
    calendar = get_market_calendar(policy.exchange)
    if calendar.classify(opened) != SessionSegment.REGULAR:
        raise ForecastHorizonClockError(
            "forecast horizon clock requires regular-session position open"
        )

    if plan.forecast_horizon_unit == ForecastHorizonUnit.MINUTES:
        if policy.session_counting_policy is not None:
            raise ForecastHorizonClockError(
                "minute horizon cannot carry session-counting policy"
            )
        expiry = _add_regular_session_minutes(
            calendar=calendar,
            opened_utc=opened,
            minutes=plan.forecast_horizon_value,
        )
    elif (
        plan.forecast_horizon_unit
        == ForecastHorizonUnit.SESSIONS
    ):
        if policy.session_counting_policy is None:
            raise ForecastHorizonClockError(
                "session horizon requires explicit counting policy"
            )
        entry_session = to_market_time(
            opened,
            calendar.market_tz,
        ).date()
        target_session = _nth_session_from_entry(
            calendar=calendar,
            entry_session=entry_session,
            horizon_value=plan.forecast_horizon_value,
            policy=policy.session_counting_policy,
        )
        expiry = calendar.regular_open_close(target_session)[1]
    else:
        raise ForecastHorizonClockError(
            "unsupported forecast horizon unit"
        )

    elapsed = _regular_elapsed_minutes(
        calendar=calendar,
        opened_utc=opened,
        evaluation_utc=evaluation,
    )
    return ForecastHorizonClockEvidenceV1(
        contract_version=FORECAST_HORIZON_CLOCK_CONTRACT_VERSION,
        contract_fingerprint=(
            FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        ),
        plan_fingerprint=plan.plan_fingerprint,
        policy=policy,
        policy_fingerprint=policy.policy_fingerprint,
        exchange=policy.exchange,
        horizon_unit=plan.forecast_horizon_unit,
        horizon_value=plan.forecast_horizon_value,
        opened_utc=opened,
        evaluation_utc=evaluation,
        expiry_utc=expiry,
        regular_session_elapsed_minutes=elapsed,
        expired=evaluation >= expiry,
    )


__all__ = [
    "FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT",
    "FORECAST_HORIZON_CLOCK_CONTRACT_VERSION",
    "ForecastHorizonClockError",
    "ForecastHorizonClockEvidenceV1",
    "ForecastHorizonClockPolicyV1",
    "SessionHorizonCountingPolicy",
    "build_forecast_horizon_clock_evidence_v1",
]
