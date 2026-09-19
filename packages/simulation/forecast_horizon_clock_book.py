from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.simulation.forecast_horizon_clock import (
    FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
    ForecastHorizonClockPolicyV1,
    ForecastHorizonClockV1,
    build_forecast_horizon_clock_v1,
    forecast_horizon_clock_from_payload,
)
from packages.simulation.forecast_horizon_clock_book_contract import (
    FORECAST_HORIZON_CLOCK_BOOK_CONTRACT,
    FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
    RecurrentDecisionStockExitPlanBookV1,
    RecurrentDecisionStockExitPlanV1,
    recurrent_decision_stock_exit_plan_book_from_payload,
)


FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION = str(
    FORECAST_HORIZON_CLOCK_BOOK_CONTRACT["contract_id"]
)
FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID = (
    "atlas-forecast-horizon-clock-book/current.json"
)
_MAX_BOOK_BYTES = 128 * 1024 * 1024


class ForecastHorizonClockBookError(RuntimeError):
    pass


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ForecastHorizonClockBookError(
            f"{label} must be timezone-aware"
        )
    return value


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ForecastHorizonClockBookError(
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


def _validate_clock_against_plan(
    clock: ForecastHorizonClockV1,
    plan: RecurrentDecisionStockExitPlanV1,
) -> None:
    if (
        clock.contract_fingerprint
        != FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
    ):
        raise ForecastHorizonClockBookError(
            "clock contract fingerprint mismatch"
        )
    checks = (
        (
            clock.source_exit_plan_fingerprint,
            plan.plan_fingerprint,
            "exit-plan fingerprint",
        ),
        (
            clock.source_forecast_fingerprint,
            plan.forecast_fingerprint,
            "forecast fingerprint",
        ),
        (
            clock.decision_record_fingerprint,
            plan.decision_record_fingerprint,
            "decision-record fingerprint",
        ),
        (
            clock.position_fingerprint,
            plan.position_fingerprint,
            "position fingerprint",
        ),
        (clock.instrument_id, plan.instrument_id, "instrument id"),
        (clock.ticker, plan.ticker, "ticker"),
        (clock.opened_utc, plan.opened_utc, "opened time"),
        (
            clock.horizon_unit,
            plan.forecast_horizon_unit,
            "horizon unit",
        ),
        (
            clock.horizon_value,
            plan.forecast_horizon_value,
            "horizon value",
        ),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise ForecastHorizonClockBookError(
                f"clock {label} does not match current exit plan"
            )


def _book_payload(
    *,
    source_exit_plan_book: RecurrentDecisionStockExitPlanBookV1,
    built_at_utc: datetime,
    clocks: tuple[ForecastHorizonClockV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION,
        "contract_fingerprint": (
            FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        ),
        "source_id": FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID,
        "source_exit_plan_book": source_exit_plan_book,
        "built_at_utc": built_at_utc,
        "clocks": clocks,
        "provider_reads": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "time_exit_disposition_authority": False,
        "price_trigger_authority": False,
        "close_fill_authority": False,
        "account_mutation_authority": False,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }


@dataclass(frozen=True)
class ForecastHorizonClockBookV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    book_fingerprint: str
    source_exit_plan_book: RecurrentDecisionStockExitPlanBookV1
    built_at_utc: datetime
    clocks: tuple[ForecastHorizonClockV1, ...]

    provider_reads: int = 0
    provider_writes: int = 0
    broker_reads: int = 0
    broker_writes: int = 0
    time_exit_disposition_authority: bool = False
    price_trigger_authority: bool = False
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
            != FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION
        ):
            raise ForecastHorizonClockBookError(
                "forecast-horizon clock-book contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        ):
            raise ForecastHorizonClockBookError(
                "forecast-horizon clock-book contract fingerprint mismatch"
            )
        if self.source_id != FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID:
            raise ForecastHorizonClockBookError(
                "forecast-horizon clock-book source id mismatch"
            )
        _require_sha(
            self.book_fingerprint,
            label="forecast-horizon clock book",
        )
        if (
            self.source_exit_plan_book.contract_fingerprint
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise ForecastHorizonClockBookError(
                "clock book exit-plan-book contract fingerprint mismatch"
            )

        built = _require_aware(
            self.built_at_utc,
            label="forecast-horizon clock-book build time",
        )
        if built != self.source_exit_plan_book.built_at_utc:
            raise ForecastHorizonClockBookError(
                "clock-book build time must equal source exit-plan-book time"
            )

        ordered = tuple(
            sorted(
                self.clocks,
                key=lambda item: item.position_fingerprint,
            )
        )
        if ordered != self.clocks:
            raise ForecastHorizonClockBookError(
                "clock book must be ordered by position fingerprint"
            )
        ids = tuple(
            clock.position_fingerprint for clock in self.clocks
        )
        if len(ids) != len(set(ids)):
            raise ForecastHorizonClockBookError(
                "clock book cannot duplicate positions"
            )

        plans = self.source_exit_plan_book.plans
        if len(plans) != len(self.clocks):
            raise ForecastHorizonClockBookError(
                "clock book must exactly cover source exit plans"
            )
        for plan, clock in zip(plans, self.clocks, strict=True):
            if plan.position_fingerprint != clock.position_fingerprint:
                raise ForecastHorizonClockBookError(
                    "clock-book position order does not match exit-plan book"
                )
            _validate_clock_against_plan(clock, plan)

        if any(
            (
                self.provider_reads,
                self.provider_writes,
                self.broker_reads,
                self.broker_writes,
                self.time_exit_disposition_authority,
                self.price_trigger_authority,
                self.close_fill_authority,
                self.account_mutation_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise ForecastHorizonClockBookError(
                "clock book cannot grant evaluation, trigger, mutation, external, or trading authority"
            )

        expected = _fingerprint_payload(
            _book_payload(
                source_exit_plan_book=self.source_exit_plan_book,
                built_at_utc=built,
                clocks=self.clocks,
            )
        )
        if self.book_fingerprint != expected:
            raise ForecastHorizonClockBookError(
                "forecast-horizon clock-book self-fingerprint mismatch"
            )

    @property
    def source_exit_plan_book_fingerprint(self) -> str:
        return self.source_exit_plan_book.book_fingerprint


def build_forecast_horizon_clock_book_v1(
    *,
    source_exit_plan_book: RecurrentDecisionStockExitPlanBookV1,
    existing_book: ForecastHorizonClockBookV1 | None,
    clock_policy_by_position: Mapping[
        str, ForecastHorizonClockPolicyV1
    ],
) -> ForecastHorizonClockBookV1:
    if (
        source_exit_plan_book.contract_fingerprint
        != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ):
        raise ForecastHorizonClockBookError(
            "source exit-plan-book contract fingerprint mismatch"
        )

    existing_by_position: dict[str, ForecastHorizonClockV1] = {}
    if existing_book is not None:
        if (
            existing_book.contract_fingerprint
            != FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        ):
            raise ForecastHorizonClockBookError(
                "existing clock-book contract fingerprint mismatch"
            )
        existing_by_position = {
            clock.position_fingerprint: clock
            for clock in existing_book.clocks
        }

    new_positions: set[str] = set()
    clocks: list[ForecastHorizonClockV1] = []
    for plan in source_exit_plan_book.plans:
        position_fp = plan.position_fingerprint
        existing = existing_by_position.get(position_fp)
        if existing is not None:
            _validate_clock_against_plan(existing, plan)
            clocks.append(existing)
            continue

        policy = clock_policy_by_position.get(position_fp)
        if policy is None:
            raise ForecastHorizonClockBookError(
                "new exit plan lacks explicit forecast-horizon clock policy"
            )
        new_positions.add(position_fp)
        clocks.append(
            build_forecast_horizon_clock_v1(
                plan=plan,
                policy=policy,
            )
        )

    supplied_policy_keys = set(clock_policy_by_position)
    if supplied_policy_keys != new_positions:
        missing = sorted(new_positions - supplied_policy_keys)
        extra = sorted(supplied_policy_keys - new_positions)
        raise ForecastHorizonClockBookError(
            "clock-policy coverage must exactly match newly unclocked positions; "
            f"missing={missing}, extra={extra}"
        )

    ordered = tuple(
        sorted(
            clocks,
            key=lambda item: item.position_fingerprint,
        )
    )
    built = source_exit_plan_book.built_at_utc
    payload = _book_payload(
        source_exit_plan_book=source_exit_plan_book,
        built_at_utc=built,
        clocks=ordered,
    )
    return ForecastHorizonClockBookV1(
        contract_version=FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION,
        contract_fingerprint=(
            FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        ),
        source_id=FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID,
        book_fingerprint=_fingerprint_payload(payload),
        source_exit_plan_book=source_exit_plan_book,
        built_at_utc=built,
        clocks=ordered,
    )


def forecast_horizon_clock_book_from_payload(
    payload: dict[str, object],
) -> ForecastHorizonClockBookV1:
    source_book = recurrent_decision_stock_exit_plan_book_from_payload(
        dict(payload["source_exit_plan_book"])
    )
    clocks = tuple(
        forecast_horizon_clock_from_payload(dict(item))
        for item in payload["clocks"]
    )
    return ForecastHorizonClockBookV1(
        contract_version=str(payload["contract_version"]),
        contract_fingerprint=str(
            payload["contract_fingerprint"]
        ),
        source_id=str(payload["source_id"]),
        book_fingerprint=str(payload["book_fingerprint"]),
        source_exit_plan_book=source_book,
        built_at_utc=datetime.fromisoformat(
            str(payload["built_at_utc"])
        ),
        clocks=clocks,
        provider_reads=int(payload["provider_reads"]),
        provider_writes=int(payload["provider_writes"]),
        broker_reads=int(payload["broker_reads"]),
        broker_writes=int(payload["broker_writes"]),
        time_exit_disposition_authority=bool(
            payload["time_exit_disposition_authority"]
        ),
        price_trigger_authority=bool(
            payload["price_trigger_authority"]
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


def forecast_horizon_clock_book_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).forecast_horizon_clock_book_file()


def write_forecast_horizon_clock_book_v1(
    settings: AtlasSettings,
    book: ForecastHorizonClockBookV1,
) -> Path:
    path = forecast_horizon_clock_book_path(settings)
    raw = json.dumps(
        _canonicalize(book),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_forecast_horizon_clock_book_v1(
        settings,
        path=path,
    )
    if restored != book:
        raise ForecastHorizonClockBookError(
            "forecast-horizon clock-book readback mismatch"
        )
    return path


def read_forecast_horizon_clock_book_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> ForecastHorizonClockBookV1:
    target = (
        Path(path)
        if path is not None
        else forecast_horizon_clock_book_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise ForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BOOK_BYTES:
        raise ForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise ForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise ForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact root must be an object"
        )
    try:
        return forecast_horizon_clock_book_from_payload(payload)
    except (
        KeyError,
        TypeError,
        ValueError,
        ForecastHorizonClockBookError,
    ) as exc:
        if isinstance(exc, ForecastHorizonClockBookError):
            raise
        raise ForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact failed typed validation"
        ) from exc


__all__ = [
    "FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT",
    "FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION",
    "FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID",
    "ForecastHorizonClockBookError",
    "ForecastHorizonClockBookV1",
    "build_forecast_horizon_clock_book_v1",
    "forecast_horizon_clock_book_from_payload",
    "forecast_horizon_clock_book_path",
    "read_forecast_horizon_clock_book_v1",
    "write_forecast_horizon_clock_book_v1",
]
