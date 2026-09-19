from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel

from packages.simulation.recurrent_forecast_horizon_clock import (
    RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
    RecurrentForecastHorizonClockV1,
)
from packages.simulation.recurrent_time_expiry_disposition_contract import (
    RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT,
    RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_FINGERPRINT,
)


RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_VERSION = str(
    RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class RecurrentTimeExpiryDispositionError(RuntimeError):
    pass


class TimeExpiryDisposition(StrEnum):
    NOT_EXPIRED = "NOT_EXPIRED"
    TIME_EXPIRED = "TIME_EXPIRED"


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentTimeExpiryDispositionError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _require_aware(
    value: datetime,
    *,
    label: str,
) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentTimeExpiryDispositionError(
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
class RecurrentTimeExpiryDispositionV1:
    contract_version: str
    contract_fingerprint: str
    source_clock_contract_fingerprint: str
    source_clock_fingerprint: str
    clock: RecurrentForecastHorizonClockV1

    source_exit_plan_fingerprint: str
    position_fingerprint: str
    ticker: str
    evaluation_utc: datetime
    deadline_utc: datetime
    disposition: TimeExpiryDisposition
    signed_seconds_from_deadline: float

    price_evidence_consumed: bool = False
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
        "EXPLICIT_EVALUATION_UTC_COMPARED_TO_IMMUTABLE_HORIZON_DEADLINE",
        "TIME_EXPIRED_ONLY_WHEN_EVALUATION_AT_OR_AFTER_DEADLINE",
        "NO_PRICE_OR_CLOSE_FILL_AUTHORITY_GRANTED",
    )

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_VERSION
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry disposition contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_FINGERPRINT
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry disposition contract fingerprint mismatch"
            )
        if (
            self.source_clock_contract_fingerprint
            != RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
            or self.clock.contract_fingerprint
            != RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry source clock contract mismatch"
            )
        for label, value in (
            ("clock", self.source_clock_fingerprint),
            ("exit plan", self.source_exit_plan_fingerprint),
            ("position", self.position_fingerprint),
        ):
            _require_sha(value, label=label)
        if self.clock.clock_fingerprint != self.source_clock_fingerprint:
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry source clock fingerprint mismatch"
            )
        if (
            self.source_exit_plan_fingerprint
            != self.clock.source_exit_plan_fingerprint
            or self.position_fingerprint
            != self.clock.position_fingerprint
            or self.ticker != self.clock.ticker
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry identity differs from source clock"
            )
        evaluation = _require_aware(
            self.evaluation_utc,
            label="time-expiry evaluation timestamp",
        )
        deadline = _require_aware(
            self.deadline_utc,
            label="time-expiry deadline",
        )
        if deadline != self.clock.deadline_utc:
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry deadline differs from source clock"
            )
        expected_seconds = (
            evaluation - deadline
        ).total_seconds()
        if (
            not math.isfinite(self.signed_seconds_from_deadline)
            or not math.isclose(
                self.signed_seconds_from_deadline,
                expected_seconds,
                rel_tol=1e-12,
                abs_tol=_TOLERANCE,
            )
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry signed deadline distance mismatch"
            )
        expected_disposition = (
            TimeExpiryDisposition.TIME_EXPIRED
            if expected_seconds >= -_TOLERANCE
            else TimeExpiryDisposition.NOT_EXPIRED
        )
        if self.disposition != expected_disposition:
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry disposition does not match deadline comparison"
            )
        if any(
            (
                self.price_evidence_consumed,
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
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry evidence cannot grant price, fill, mutation, external, or trading authority"
            )
        if not self.reason_codes:
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry evidence requires reason codes"
            )

    @property
    def disposition_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def build_recurrent_time_expiry_disposition_v1(
    *,
    clock: RecurrentForecastHorizonClockV1,
    evaluation_utc: datetime,
) -> RecurrentTimeExpiryDispositionV1:
    if (
        clock.contract_fingerprint
        != RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
    ):
        raise RecurrentTimeExpiryDispositionError(
            "source forecast-horizon clock contract fingerprint mismatch"
        )
    if clock.time_exit_trigger_authority:
        raise RecurrentTimeExpiryDispositionError(
            "source forecast-horizon clock unexpectedly grants trigger authority"
        )
    evaluation = _require_aware(
        evaluation_utc,
        label="time-expiry evaluation timestamp",
    )
    deadline = _require_aware(
        clock.deadline_utc,
        label="source forecast-horizon deadline",
    )
    signed_seconds = (
        evaluation - deadline
    ).total_seconds()
    disposition = (
        TimeExpiryDisposition.TIME_EXPIRED
        if signed_seconds >= -_TOLERANCE
        else TimeExpiryDisposition.NOT_EXPIRED
    )
    return RecurrentTimeExpiryDispositionV1(
        contract_version=(
            RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_VERSION
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
        evaluation_utc=evaluation,
        deadline_utc=deadline,
        disposition=disposition,
        signed_seconds_from_deadline=signed_seconds,
    )


__all__ = [
    "RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_FINGERPRINT",
    "RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_VERSION",
    "RecurrentTimeExpiryDispositionError",
    "RecurrentTimeExpiryDispositionV1",
    "TimeExpiryDisposition",
    "build_recurrent_time_expiry_disposition_v1",
]
