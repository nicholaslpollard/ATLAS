from __future__ import annotations

import hashlib
import json
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
    ForecastHorizonClockV1,
)
from packages.simulation.forecast_horizon_clock_book import (
    FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT,
    ForecastHorizonClockBookV1,
    forecast_horizon_clock_book_from_payload,
)
from packages.simulation.forecast_horizon_time_disposition_contract import (
    FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT,
    FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT,
)


FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_VERSION = str(
    FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT["contract_id"]
)
FORECAST_HORIZON_TIME_DISPOSITION_SOURCE_ID = (
    "atlas-forecast-horizon-time-disposition/current.json"
)
_MAX_BUNDLE_BYTES = 128 * 1024 * 1024


class ForecastHorizonTimeDispositionError(RuntimeError):
    pass


class ForecastHorizonTimeDispositionKind(StrEnum):
    NOT_EXPIRED = "NOT_EXPIRED"
    TIME_EXPIRED = "TIME_EXPIRED"


def _require_aware(
    value: datetime,
    *,
    label: str,
) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ForecastHorizonTimeDispositionError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ForecastHorizonTimeDispositionError(
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


def _expected_disposition(
    clock: ForecastHorizonClockV1,
    evaluation_utc: datetime,
) -> ForecastHorizonTimeDispositionKind:
    evaluation = _require_aware(
        evaluation_utc,
        label="time-disposition evaluation time",
    )
    if evaluation < clock.opened_utc:
        raise ForecastHorizonTimeDispositionError(
            "time-disposition evaluation cannot precede position open"
        )
    if evaluation >= clock.deadline_utc:
        return ForecastHorizonTimeDispositionKind.TIME_EXPIRED
    return ForecastHorizonTimeDispositionKind.NOT_EXPIRED


@dataclass(frozen=True)
class ForecastHorizonTimeDispositionV1:
    source_clock_fingerprint: str
    position_fingerprint: str
    instrument_id: str
    ticker: str
    opened_utc: datetime
    evaluation_utc: datetime
    deadline_utc: datetime
    disposition: ForecastHorizonTimeDispositionKind

    price_trigger_authority: bool = False
    close_precedence_authority: bool = False
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
        "EXACT_IMMUTABLE_HORIZON_CLOCK_BOUND",
        "EXPLICIT_EVALUATION_UTC_BOUND",
        "DEADLINE_EQUALITY_COUNTS_AS_TIME_EXPIRED",
        "NO_PRICE_OR_CLOSE_AUTHORITY_GRANTED",
    )

    def __post_init__(self) -> None:
        _require_sha(
            self.source_clock_fingerprint,
            label="source horizon clock",
        )
        _require_sha(
            self.position_fingerprint,
            label="time-disposition position",
        )
        opened = _require_aware(
            self.opened_utc,
            label="time-disposition position-open time",
        )
        evaluation = _require_aware(
            self.evaluation_utc,
            label="time-disposition evaluation time",
        )
        deadline = _require_aware(
            self.deadline_utc,
            label="time-disposition deadline",
        )
        if evaluation < opened:
            raise ForecastHorizonTimeDispositionError(
                "time-disposition evaluation cannot precede position open"
            )
        if deadline <= opened:
            raise ForecastHorizonTimeDispositionError(
                "time-disposition deadline must follow position open"
            )
        if deadline <= evaluation and (
            self.disposition
            != ForecastHorizonTimeDispositionKind.TIME_EXPIRED
        ):
            raise ForecastHorizonTimeDispositionError(
                "evaluation at or after deadline must be TIME_EXPIRED"
            )
        if deadline > evaluation and (
            self.disposition
            != ForecastHorizonTimeDispositionKind.NOT_EXPIRED
        ):
            raise ForecastHorizonTimeDispositionError(
                "evaluation before deadline must be NOT_EXPIRED"
            )
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise ForecastHorizonTimeDispositionError(
                "time-disposition instrument identity cannot be blank"
            )
        if any(
            (
                self.price_trigger_authority,
                self.close_precedence_authority,
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
            raise ForecastHorizonTimeDispositionError(
                "time disposition cannot grant price, close, mutation, external, or trading authority"
            )
        if not self.reason_codes:
            raise ForecastHorizonTimeDispositionError(
                "time disposition requires reason codes"
            )

    @property
    def disposition_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _validate_disposition_against_clock(
    disposition: ForecastHorizonTimeDispositionV1,
    clock: ForecastHorizonClockV1,
    evaluation_utc: datetime,
) -> None:
    checks = (
        (
            disposition.source_clock_fingerprint,
            clock.clock_fingerprint,
            "clock fingerprint",
        ),
        (
            disposition.position_fingerprint,
            clock.position_fingerprint,
            "position fingerprint",
        ),
        (
            disposition.instrument_id,
            clock.instrument_id,
            "instrument id",
        ),
        (disposition.ticker, clock.ticker, "ticker"),
        (
            disposition.opened_utc,
            clock.opened_utc,
            "opened time",
        ),
        (
            disposition.deadline_utc,
            clock.deadline_utc,
            "deadline",
        ),
        (
            disposition.evaluation_utc,
            evaluation_utc,
            "evaluation time",
        ),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise ForecastHorizonTimeDispositionError(
                f"time disposition {label} does not match source clock"
            )
    expected = _expected_disposition(clock, evaluation_utc)
    if disposition.disposition != expected:
        raise ForecastHorizonTimeDispositionError(
            "time disposition does not match deterministic deadline comparison"
        )


def build_forecast_horizon_time_disposition_v1(
    *,
    clock: ForecastHorizonClockV1,
    evaluation_utc: datetime,
) -> ForecastHorizonTimeDispositionV1:
    evaluation = _require_aware(
        evaluation_utc,
        label="time-disposition evaluation time",
    )
    disposition = _expected_disposition(
        clock,
        evaluation,
    )
    return ForecastHorizonTimeDispositionV1(
        source_clock_fingerprint=clock.clock_fingerprint,
        position_fingerprint=clock.position_fingerprint,
        instrument_id=clock.instrument_id,
        ticker=clock.ticker,
        opened_utc=clock.opened_utc,
        evaluation_utc=evaluation,
        deadline_utc=clock.deadline_utc,
        disposition=disposition,
    )


def _bundle_payload(
    *,
    source_clock_book: ForecastHorizonClockBookV1,
    evaluation_utc: datetime,
    dispositions: tuple[ForecastHorizonTimeDispositionV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT
        ),
        "source_id": FORECAST_HORIZON_TIME_DISPOSITION_SOURCE_ID,
        "source_clock_book": source_clock_book,
        "evaluation_utc": evaluation_utc,
        "dispositions": dispositions,
        "provider_reads": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "price_trigger_authority": False,
        "close_precedence_authority": False,
        "close_fill_authority": False,
        "account_mutation_authority": False,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }


@dataclass(frozen=True)
class ForecastHorizonTimeDispositionBundleV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    bundle_fingerprint: str
    source_clock_book: ForecastHorizonClockBookV1
    evaluation_utc: datetime
    dispositions: tuple[ForecastHorizonTimeDispositionV1, ...]

    provider_reads: int = 0
    provider_writes: int = 0
    broker_reads: int = 0
    broker_writes: int = 0
    price_trigger_authority: bool = False
    close_precedence_authority: bool = False
    close_fill_authority: bool = False
    account_mutation_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_VERSION
        ):
            raise ForecastHorizonTimeDispositionError(
                "time-disposition bundle contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT
        ):
            raise ForecastHorizonTimeDispositionError(
                "time-disposition bundle contract fingerprint mismatch"
            )
        if (
            self.source_id
            != FORECAST_HORIZON_TIME_DISPOSITION_SOURCE_ID
        ):
            raise ForecastHorizonTimeDispositionError(
                "time-disposition bundle source id mismatch"
            )
        _require_sha(
            self.bundle_fingerprint,
            label="time-disposition bundle",
        )
        if (
            self.source_clock_book.contract_fingerprint
            != FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        ):
            raise ForecastHorizonTimeDispositionError(
                "time-disposition source clock-book contract mismatch"
            )
        evaluation = _require_aware(
            self.evaluation_utc,
            label="time-disposition bundle evaluation time",
        )

        ordered = tuple(
            sorted(
                self.dispositions,
                key=lambda item: item.position_fingerprint,
            )
        )
        if ordered != self.dispositions:
            raise ForecastHorizonTimeDispositionError(
                "time dispositions must be ordered by position fingerprint"
            )
        if len(self.dispositions) != len(
            self.source_clock_book.clocks
        ):
            raise ForecastHorizonTimeDispositionError(
                "time-disposition bundle must exactly cover source clocks"
            )
        for clock, disposition in zip(
            self.source_clock_book.clocks,
            self.dispositions,
            strict=True,
        ):
            if (
                clock.position_fingerprint
                != disposition.position_fingerprint
            ):
                raise ForecastHorizonTimeDispositionError(
                    "time-disposition position order does not match source clock book"
                )
            _validate_disposition_against_clock(
                disposition,
                clock,
                evaluation,
            )

        if any(
            (
                self.provider_reads,
                self.provider_writes,
                self.broker_reads,
                self.broker_writes,
                self.price_trigger_authority,
                self.close_precedence_authority,
                self.close_fill_authority,
                self.account_mutation_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise ForecastHorizonTimeDispositionError(
                "time-disposition bundle cannot grant price, close, mutation, external, or trading authority"
            )

        expected = _fingerprint_payload(
            _bundle_payload(
                source_clock_book=self.source_clock_book,
                evaluation_utc=evaluation,
                dispositions=self.dispositions,
            )
        )
        if self.bundle_fingerprint != expected:
            raise ForecastHorizonTimeDispositionError(
                "time-disposition bundle self-fingerprint mismatch"
            )

    @property
    def source_clock_book_fingerprint(self) -> str:
        return self.source_clock_book.book_fingerprint


def build_forecast_horizon_time_disposition_bundle_v1(
    *,
    source_clock_book: ForecastHorizonClockBookV1,
    evaluation_utc: datetime,
) -> ForecastHorizonTimeDispositionBundleV1:
    if (
        source_clock_book.contract_fingerprint
        != FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
    ):
        raise ForecastHorizonTimeDispositionError(
            "source clock-book contract fingerprint mismatch"
        )
    evaluation = _require_aware(
        evaluation_utc,
        label="time-disposition evaluation time",
    )
    dispositions = tuple(
        build_forecast_horizon_time_disposition_v1(
            clock=clock,
            evaluation_utc=evaluation,
        )
        for clock in source_clock_book.clocks
    )
    payload = _bundle_payload(
        source_clock_book=source_clock_book,
        evaluation_utc=evaluation,
        dispositions=dispositions,
    )
    return ForecastHorizonTimeDispositionBundleV1(
        contract_version=(
            FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT
        ),
        source_id=FORECAST_HORIZON_TIME_DISPOSITION_SOURCE_ID,
        bundle_fingerprint=_fingerprint_payload(payload),
        source_clock_book=source_clock_book,
        evaluation_utc=evaluation,
        dispositions=dispositions,
    )


def forecast_horizon_time_disposition_from_payload(
    payload: dict[str, object],
) -> ForecastHorizonTimeDispositionV1:
    values = dict(payload)
    values["opened_utc"] = datetime.fromisoformat(
        str(values["opened_utc"])
    )
    values["evaluation_utc"] = datetime.fromisoformat(
        str(values["evaluation_utc"])
    )
    values["deadline_utc"] = datetime.fromisoformat(
        str(values["deadline_utc"])
    )
    values["disposition"] = ForecastHorizonTimeDispositionKind(
        str(values["disposition"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return ForecastHorizonTimeDispositionV1(**values)


def forecast_horizon_time_disposition_bundle_from_payload(
    payload: dict[str, object],
) -> ForecastHorizonTimeDispositionBundleV1:
    clock_book = forecast_horizon_clock_book_from_payload(
        dict(payload["source_clock_book"])
    )
    dispositions = tuple(
        forecast_horizon_time_disposition_from_payload(
            dict(item)
        )
        for item in payload["dispositions"]
    )
    return ForecastHorizonTimeDispositionBundleV1(
        contract_version=str(payload["contract_version"]),
        contract_fingerprint=str(
            payload["contract_fingerprint"]
        ),
        source_id=str(payload["source_id"]),
        bundle_fingerprint=str(payload["bundle_fingerprint"]),
        source_clock_book=clock_book,
        evaluation_utc=datetime.fromisoformat(
            str(payload["evaluation_utc"])
        ),
        dispositions=dispositions,
        provider_reads=int(payload["provider_reads"]),
        provider_writes=int(payload["provider_writes"]),
        broker_reads=int(payload["broker_reads"]),
        broker_writes=int(payload["broker_writes"]),
        price_trigger_authority=bool(
            payload["price_trigger_authority"]
        ),
        close_precedence_authority=bool(
            payload["close_precedence_authority"]
        ),
        close_fill_authority=bool(
            payload["close_fill_authority"]
        ),
        account_mutation_authority=bool(
            payload["account_mutation_authority"]
        ),
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


def forecast_horizon_time_disposition_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).forecast_horizon_time_disposition_file()


def write_forecast_horizon_time_disposition_bundle_v1(
    settings: AtlasSettings,
    bundle: ForecastHorizonTimeDispositionBundleV1,
) -> Path:
    path = forecast_horizon_time_disposition_path(settings)
    raw = json.dumps(
        _canonicalize(bundle),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_forecast_horizon_time_disposition_bundle_v1(
        settings,
        path=path,
    )
    if restored != bundle:
        raise ForecastHorizonTimeDispositionError(
            "time-disposition bundle readback mismatch"
        )
    return path


def read_forecast_horizon_time_disposition_bundle_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> ForecastHorizonTimeDispositionBundleV1:
    target = (
        Path(path)
        if path is not None
        else forecast_horizon_time_disposition_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise ForecastHorizonTimeDispositionError(
            "time-disposition artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise ForecastHorizonTimeDispositionError(
            "time-disposition artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise ForecastHorizonTimeDispositionError(
            "time-disposition artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise ForecastHorizonTimeDispositionError(
            "time-disposition artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ForecastHorizonTimeDispositionError(
            "time-disposition artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ForecastHorizonTimeDispositionError(
            "time-disposition artifact root must be an object"
        )
    try:
        return forecast_horizon_time_disposition_bundle_from_payload(
            payload
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        ForecastHorizonTimeDispositionError,
    ) as exc:
        if isinstance(
            exc,
            ForecastHorizonTimeDispositionError,
        ):
            raise
        raise ForecastHorizonTimeDispositionError(
            "time-disposition artifact failed typed validation"
        ) from exc


__all__ = [
    "FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT",
    "FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_VERSION",
    "FORECAST_HORIZON_TIME_DISPOSITION_SOURCE_ID",
    "ForecastHorizonTimeDispositionBundleV1",
    "ForecastHorizonTimeDispositionError",
    "ForecastHorizonTimeDispositionKind",
    "ForecastHorizonTimeDispositionV1",
    "build_forecast_horizon_time_disposition_bundle_v1",
    "build_forecast_horizon_time_disposition_v1",
    "forecast_horizon_time_disposition_bundle_from_payload",
    "forecast_horizon_time_disposition_from_payload",
    "forecast_horizon_time_disposition_path",
    "read_forecast_horizon_time_disposition_bundle_v1",
    "write_forecast_horizon_time_disposition_bundle_v1",
]
