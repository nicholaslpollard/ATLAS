from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.simulation.forecast_horizon_clock import (
    FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
    ForecastHorizonClockError,
    ForecastHorizonClockV1,
    forecast_horizon_clock_from_payload,
)
from packages.simulation.recurrent_forecast_horizon_clock_book import (
    RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT,
    RecurrentForecastHorizonClockBookError,
    RecurrentForecastHorizonClockBookV1,
    recurrent_forecast_horizon_clock_book_from_payload,
)
from packages.simulation.recurrent_time_expiry_disposition_contract import (
    RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT,
    RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT,
)


RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_VERSION = str(
    RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT["contract_id"]
)
RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_SOURCE_ID = (
    "atlas-recurrent-time-expiry-disposition/current.json"
)
_MAX_BUNDLE_BYTES = 128 * 1024 * 1024
_TOLERANCE = 1e-9


class RecurrentTimeExpiryDispositionError(RuntimeError):
    pass


class TimeExpiryDisposition(StrEnum):
    NOT_EXPIRED = "NOT_EXPIRED"
    TIME_EXPIRED = "TIME_EXPIRED"


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentTimeExpiryDispositionError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentTimeExpiryDispositionError(
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
class RecurrentTimeExpiryDispositionV1:
    source_clock_fingerprint: str
    clock: ForecastHorizonClockV1
    evaluation_utc: datetime
    disposition: TimeExpiryDisposition
    signed_seconds_from_deadline: float

    price_evidence_consumed: bool = False
    stop_target_precedence_authority: bool = False
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
        "EXPLICIT_EVALUATION_UTC_COMPARED_TO_IMMUTABLE_CLOCK_DEADLINE",
        "TIME_EXPIRED_ONLY_AT_OR_AFTER_DEADLINE",
        "NO_PRICE_OR_CLOSE_PRECEDENCE_AUTHORITY_GRANTED",
    )

    def __post_init__(self) -> None:
        if (
            self.clock.contract_fingerprint
            != FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry source clock contract mismatch"
            )
        _require_sha(
            self.source_clock_fingerprint,
            label="time-expiry source clock",
        )
        if (
            self.clock.clock_fingerprint
            != self.source_clock_fingerprint
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry source clock fingerprint mismatch"
            )

        evaluation = _require_aware(
            self.evaluation_utc,
            label="time-expiry evaluation time",
        )
        deadline = _require_aware(
            self.clock.deadline_utc,
            label="time-expiry deadline",
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
        expected = (
            TimeExpiryDisposition.TIME_EXPIRED
            if evaluation >= deadline
            else TimeExpiryDisposition.NOT_EXPIRED
        )
        if self.disposition != expected:
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry disposition does not match deadline comparison"
            )

        if any(
            (
                self.price_evidence_consumed,
                self.stop_target_precedence_authority,
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
                "time-expiry disposition cannot grant price, precedence, fill, mutation, external, or trading authority"
            )
        if not self.reason_codes:
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry disposition requires reason codes"
            )

    @property
    def disposition_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def build_recurrent_time_expiry_disposition_v1(
    *,
    clock: ForecastHorizonClockV1,
    evaluation_utc: datetime,
) -> RecurrentTimeExpiryDispositionV1:
    evaluation = _require_aware(
        evaluation_utc,
        label="time-expiry evaluation time",
    )
    deadline = _require_aware(
        clock.deadline_utc,
        label="time-expiry deadline",
    )
    signed_seconds = (
        evaluation - deadline
    ).total_seconds()
    disposition = (
        TimeExpiryDisposition.TIME_EXPIRED
        if evaluation >= deadline
        else TimeExpiryDisposition.NOT_EXPIRED
    )
    return RecurrentTimeExpiryDispositionV1(
        source_clock_fingerprint=clock.clock_fingerprint,
        clock=clock,
        evaluation_utc=evaluation,
        disposition=disposition,
        signed_seconds_from_deadline=signed_seconds,
    )


def _bundle_payload(
    *,
    clock_book: RecurrentForecastHorizonClockBookV1,
    source_recurrent_state_fingerprint: str,
    evaluation_utc: datetime,
    dispositions: tuple[RecurrentTimeExpiryDispositionV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT
        ),
        "source_id": (
            RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_SOURCE_ID
        ),
        "clock_book": clock_book,
        "source_recurrent_state_fingerprint": (
            source_recurrent_state_fingerprint
        ),
        "evaluation_utc": evaluation_utc,
        "dispositions": dispositions,
        "price_evidence_consumed": False,
        "stop_target_precedence_authority": False,
        "close_fill_authority": False,
        "account_mutation_authority": False,
        "provider_reads": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }


@dataclass(frozen=True)
class RecurrentTimeExpiryDispositionBundleV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    bundle_fingerprint: str
    clock_book: RecurrentForecastHorizonClockBookV1
    source_recurrent_state_fingerprint: str
    evaluation_utc: datetime
    dispositions: tuple[RecurrentTimeExpiryDispositionV1, ...]

    price_evidence_consumed: bool = False
    stop_target_precedence_authority: bool = False
    close_fill_authority: bool = False
    account_mutation_authority: bool = False
    provider_reads: int = 0
    provider_writes: int = 0
    broker_reads: int = 0
    broker_writes: int = 0
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_VERSION
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry bundle contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry bundle contract fingerprint mismatch"
            )
        if (
            self.source_id
            != RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_SOURCE_ID
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry bundle source id mismatch"
            )
        _require_sha(
            self.bundle_fingerprint,
            label="time-expiry bundle",
        )
        if (
            self.clock_book.contract_fingerprint
            != RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry clock-book contract mismatch"
            )
        _require_sha(
            self.source_recurrent_state_fingerprint,
            label="time-expiry source recurrent state",
        )
        if (
            self.clock_book.exit_plan_book.source_recurrent_state_fingerprint
            != self.source_recurrent_state_fingerprint
        ):
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry recurrent state does not match clock book"
            )

        evaluation = _require_aware(
            self.evaluation_utc,
            label="time-expiry bundle evaluation time",
        )
        if evaluation < self.clock_book.built_at_utc:
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry evaluation cannot predate clock-book construction"
            )

        ordered = tuple(
            sorted(
                self.dispositions,
                key=lambda item: item.clock.position_fingerprint,
            )
        )
        if ordered != self.dispositions:
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry dispositions must be ordered by position fingerprint"
            )
        clocks = self.clock_book.clocks
        if tuple(
            item.clock for item in self.dispositions
        ) != clocks:
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry dispositions must exactly cover the clock book"
            )
        for item in self.dispositions:
            if item.evaluation_utc != evaluation:
                raise RecurrentTimeExpiryDispositionError(
                    "time-expiry disposition evaluation time differs from bundle"
                )
            rebuilt = build_recurrent_time_expiry_disposition_v1(
                clock=item.clock,
                evaluation_utc=evaluation,
            )
            if rebuilt != item:
                raise RecurrentTimeExpiryDispositionError(
                    "stored time-expiry disposition does not match deterministic deadline evaluation"
                )

        if any(
            (
                self.price_evidence_consumed,
                self.stop_target_precedence_authority,
                self.close_fill_authority,
                self.account_mutation_authority,
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
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry bundle cannot grant price, precedence, fill, mutation, external, or trading authority"
            )

        expected = _fingerprint_payload(
            _bundle_payload(
                clock_book=self.clock_book,
                source_recurrent_state_fingerprint=(
                    self.source_recurrent_state_fingerprint
                ),
                evaluation_utc=evaluation,
                dispositions=self.dispositions,
            )
        )
        if self.bundle_fingerprint != expected:
            raise RecurrentTimeExpiryDispositionError(
                "time-expiry bundle self-fingerprint mismatch"
            )


def build_recurrent_time_expiry_disposition_bundle_v1(
    *,
    clock_book: RecurrentForecastHorizonClockBookV1,
    evaluation_utc: datetime,
) -> RecurrentTimeExpiryDispositionBundleV1:
    evaluation = _require_aware(
        evaluation_utc,
        label="time-expiry bundle evaluation time",
    )
    if evaluation < clock_book.built_at_utc:
        raise RecurrentTimeExpiryDispositionError(
            "time-expiry evaluation cannot predate clock-book construction"
        )
    dispositions = tuple(
        build_recurrent_time_expiry_disposition_v1(
            clock=clock,
            evaluation_utc=evaluation,
        )
        for clock in clock_book.clocks
    )
    source_state = (
        clock_book.exit_plan_book.source_recurrent_state_fingerprint
    )
    payload = _bundle_payload(
        clock_book=clock_book,
        source_recurrent_state_fingerprint=source_state,
        evaluation_utc=evaluation,
        dispositions=dispositions,
    )
    return RecurrentTimeExpiryDispositionBundleV1(
        contract_version=(
            RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT
        ),
        source_id=RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_SOURCE_ID,
        bundle_fingerprint=_fingerprint_payload(payload),
        clock_book=clock_book,
        source_recurrent_state_fingerprint=source_state,
        evaluation_utc=evaluation,
        dispositions=dispositions,
    )


def recurrent_time_expiry_disposition_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).recurrent_time_expiry_disposition_file()


def recurrent_time_expiry_disposition_from_payload(
    payload: dict[str, object],
) -> RecurrentTimeExpiryDispositionV1:
    clock = forecast_horizon_clock_from_payload(
        dict(payload["clock"])
    )
    values = dict(payload)
    values["clock"] = clock
    values["evaluation_utc"] = datetime.fromisoformat(
        str(values["evaluation_utc"])
    )
    values["disposition"] = TimeExpiryDisposition(
        str(values["disposition"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return RecurrentTimeExpiryDispositionV1(**values)


def recurrent_time_expiry_disposition_bundle_from_payload(
    payload: dict[str, object],
) -> RecurrentTimeExpiryDispositionBundleV1:
    clock_book = (
        recurrent_forecast_horizon_clock_book_from_payload(
            dict(payload["clock_book"])
        )
    )
    dispositions = tuple(
        recurrent_time_expiry_disposition_from_payload(
            dict(item)
        )
        for item in payload["dispositions"]
    )
    return RecurrentTimeExpiryDispositionBundleV1(
        contract_version=str(payload["contract_version"]),
        contract_fingerprint=str(payload["contract_fingerprint"]),
        source_id=str(payload["source_id"]),
        bundle_fingerprint=str(payload["bundle_fingerprint"]),
        clock_book=clock_book,
        source_recurrent_state_fingerprint=str(
            payload["source_recurrent_state_fingerprint"]
        ),
        evaluation_utc=datetime.fromisoformat(
            str(payload["evaluation_utc"])
        ),
        dispositions=dispositions,
        price_evidence_consumed=bool(
            payload["price_evidence_consumed"]
        ),
        stop_target_precedence_authority=bool(
            payload["stop_target_precedence_authority"]
        ),
        close_fill_authority=bool(
            payload["close_fill_authority"]
        ),
        account_mutation_authority=bool(
            payload["account_mutation_authority"]
        ),
        provider_reads=int(payload["provider_reads"]),
        provider_writes=int(payload["provider_writes"]),
        broker_reads=int(payload["broker_reads"]),
        broker_writes=int(payload["broker_writes"]),
        order_creation_authority=bool(
            payload["order_creation_authority"]
        ),
        paper_authority=bool(payload["paper_authority"]),
        live_authority=bool(payload["live_authority"]),
        promotion_authority=bool(
            payload["promotion_authority"]
        ),
        confluence_authority=bool(
            payload["confluence_authority"]
        ),
    )


def write_recurrent_time_expiry_disposition_bundle_v1(
    settings: AtlasSettings,
    bundle: RecurrentTimeExpiryDispositionBundleV1,
) -> Path:
    path = recurrent_time_expiry_disposition_path(settings)
    raw = json.dumps(
        _canonicalize(bundle),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_recurrent_time_expiry_disposition_bundle_v1(
        settings,
        path=path,
    )
    if restored != bundle:
        raise RecurrentTimeExpiryDispositionError(
            "time-expiry bundle readback mismatch"
        )
    return path


def read_recurrent_time_expiry_disposition_bundle_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> RecurrentTimeExpiryDispositionBundleV1:
    target = (
        Path(path)
        if path is not None
        else recurrent_time_expiry_disposition_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise RecurrentTimeExpiryDispositionError(
            "time-expiry bundle artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise RecurrentTimeExpiryDispositionError(
            "time-expiry bundle artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise RecurrentTimeExpiryDispositionError(
            "time-expiry bundle artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise RecurrentTimeExpiryDispositionError(
            "time-expiry bundle artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecurrentTimeExpiryDispositionError(
            "time-expiry bundle artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise RecurrentTimeExpiryDispositionError(
            "time-expiry bundle root must be an object"
        )
    try:
        return recurrent_time_expiry_disposition_bundle_from_payload(
            payload
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        ForecastHorizonClockError,
        RecurrentForecastHorizonClockBookError,
        RecurrentTimeExpiryDispositionError,
    ) as exc:
        if isinstance(exc, RecurrentTimeExpiryDispositionError):
            raise
        raise RecurrentTimeExpiryDispositionError(
            "time-expiry bundle failed typed validation"
        ) from exc


__all__ = [
    "RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT",
    "RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_VERSION",
    "RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_SOURCE_ID",
    "RecurrentTimeExpiryDispositionBundleV1",
    "RecurrentTimeExpiryDispositionError",
    "RecurrentTimeExpiryDispositionV1",
    "TimeExpiryDisposition",
    "build_recurrent_time_expiry_disposition_bundle_v1",
    "build_recurrent_time_expiry_disposition_v1",
    "read_recurrent_time_expiry_disposition_bundle_v1",
    "recurrent_time_expiry_disposition_bundle_from_payload",
    "recurrent_time_expiry_disposition_from_payload",
    "recurrent_time_expiry_disposition_path",
    "write_recurrent_time_expiry_disposition_bundle_v1",
]
