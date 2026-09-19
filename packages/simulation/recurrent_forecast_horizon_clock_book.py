from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.simulation.forecast_horizon_clock import (
    FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
    ForecastHorizonClockError,
    ForecastHorizonClockPolicyV1,
    ForecastHorizonClockV1,
    build_forecast_horizon_clock_v1,
    forecast_horizon_clock_from_payload,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
    RecurrentDecisionStockExitPlanBookV1,
    recurrent_decision_stock_exit_plan_book_from_payload,
)
from packages.simulation.recurrent_forecast_horizon_clock_book_contract import (
    RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT,
    RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT,
)


RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION = str(
    RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT["contract_id"]
)
RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID = (
    "atlas-recurrent-forecast-horizon-clock-book/current.json"
)
_MAX_BOOK_BYTES = 128 * 1024 * 1024


class RecurrentForecastHorizonClockBookError(RuntimeError):
    pass


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentForecastHorizonClockBookError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentForecastHorizonClockBookError(
            f"{label} must be a SHA-256 fingerprint"
        )


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


def _book_payload(
    *,
    exit_plan_book: RecurrentDecisionStockExitPlanBookV1,
    built_at_utc: datetime,
    clocks: tuple[ForecastHorizonClockV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        ),
        "source_id": RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID,
        "exit_plan_book": exit_plan_book,
        "built_at_utc": built_at_utc,
        "clocks": clocks,
        "time_exit_disposition_authority": False,
        "price_trigger_authority": False,
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
class RecurrentForecastHorizonClockBookV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    book_fingerprint: str
    exit_plan_book: RecurrentDecisionStockExitPlanBookV1
    built_at_utc: datetime
    clocks: tuple[ForecastHorizonClockV1, ...]

    time_exit_disposition_authority: bool = False
    price_trigger_authority: bool = False
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
            != RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION
        ):
            raise RecurrentForecastHorizonClockBookError(
                "forecast-horizon clock-book contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        ):
            raise RecurrentForecastHorizonClockBookError(
                "forecast-horizon clock-book contract fingerprint mismatch"
            )
        if self.source_id != RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID:
            raise RecurrentForecastHorizonClockBookError(
                "forecast-horizon clock-book source id mismatch"
            )
        _require_sha(
            self.book_fingerprint,
            label="forecast-horizon clock book",
        )
        if (
            self.exit_plan_book.contract_fingerprint
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise RecurrentForecastHorizonClockBookError(
                "clock book exit-plan-book contract mismatch"
            )
        built = _require_aware(
            self.built_at_utc,
            label="forecast-horizon clock-book build time",
        )
        if built < self.exit_plan_book.built_at_utc:
            raise RecurrentForecastHorizonClockBookError(
                "clock book cannot predate its exit-plan book"
            )

        ordered = tuple(
            sorted(
                self.clocks,
                key=lambda item: item.position_fingerprint,
            )
        )
        if ordered != self.clocks:
            raise RecurrentForecastHorizonClockBookError(
                "clock book must be ordered by position fingerprint"
            )
        position_ids = tuple(
            clock.position_fingerprint for clock in self.clocks
        )
        if len(position_ids) != len(set(position_ids)):
            raise RecurrentForecastHorizonClockBookError(
                "clock book cannot duplicate positions"
            )

        plans_by_position = {
            plan.position_fingerprint: plan
            for plan in self.exit_plan_book.plans
        }
        clocks_by_position = {
            clock.position_fingerprint: clock
            for clock in self.clocks
        }
        if set(plans_by_position) != set(clocks_by_position):
            missing = sorted(
                set(plans_by_position) - set(clocks_by_position)
            )
            extra = sorted(
                set(clocks_by_position) - set(plans_by_position)
            )
            raise RecurrentForecastHorizonClockBookError(
                "clock coverage must exactly match open exit plans; "
                f"missing={missing}, extra={extra}"
            )

        for position_fp, plan in plans_by_position.items():
            clock = clocks_by_position[position_fp]
            if (
                clock.contract_fingerprint
                != FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
            ):
                raise RecurrentForecastHorizonClockBookError(
                    "stored clock contract fingerprint mismatch"
                )
            if (
                clock.source_exit_plan_fingerprint
                != plan.plan_fingerprint
            ):
                raise RecurrentForecastHorizonClockBookError(
                    "stored clock is bound to a different exit plan"
                )
            try:
                rebuilt = build_forecast_horizon_clock_v1(
                    plan=plan,
                    policy=clock.policy,
                )
            except ForecastHorizonClockError as exc:
                raise RecurrentForecastHorizonClockBookError(
                    "stored clock cannot be deterministically rebuilt"
                ) from exc
            if rebuilt != clock:
                raise RecurrentForecastHorizonClockBookError(
                    "stored clock does not match deterministic plan/policy rebuild"
                )

        if any(
            (
                self.time_exit_disposition_authority,
                self.price_trigger_authority,
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
            raise RecurrentForecastHorizonClockBookError(
                "clock book cannot grant disposition, mutation, external, or trading authority"
            )

        expected = _fingerprint_payload(
            _book_payload(
                exit_plan_book=self.exit_plan_book,
                built_at_utc=built,
                clocks=self.clocks,
            )
        )
        if self.book_fingerprint != expected:
            raise RecurrentForecastHorizonClockBookError(
                "forecast-horizon clock-book self-fingerprint mismatch"
            )


def build_recurrent_forecast_horizon_clock_book_v1(
    *,
    exit_plan_book: RecurrentDecisionStockExitPlanBookV1,
    existing_book: RecurrentForecastHorizonClockBookV1 | None,
    clock_policy_by_plan: Mapping[
        str,
        ForecastHorizonClockPolicyV1,
    ],
    built_at_utc: datetime | None = None,
) -> RecurrentForecastHorizonClockBookV1:
    if (
        exit_plan_book.contract_fingerprint
        != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ):
        raise RecurrentForecastHorizonClockBookError(
            "source exit-plan-book contract fingerprint mismatch"
        )
    built = _require_aware(
        built_at_utc or datetime.now(UTC),
        label="forecast-horizon clock-book build time",
    )
    if built < exit_plan_book.built_at_utc:
        raise RecurrentForecastHorizonClockBookError(
            "clock book cannot predate its exit-plan book"
        )

    existing_by_position: dict[str, ForecastHorizonClockV1] = {}
    if existing_book is not None:
        if (
            existing_book.contract_fingerprint
            != RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        ):
            raise RecurrentForecastHorizonClockBookError(
                "existing clock-book contract fingerprint mismatch"
            )
        existing_by_position = {
            clock.position_fingerprint: clock
            for clock in existing_book.clocks
        }

    new_plan_fingerprints: set[str] = set()
    clocks: list[ForecastHorizonClockV1] = []
    for plan in sorted(
        exit_plan_book.plans,
        key=lambda item: item.position_fingerprint,
    ):
        existing = existing_by_position.get(
            plan.position_fingerprint
        )
        if existing is not None:
            if (
                existing.source_exit_plan_fingerprint
                != plan.plan_fingerprint
            ):
                raise RecurrentForecastHorizonClockBookError(
                    "existing open position clock is bound to a different plan"
                )
            clocks.append(existing)
            continue

        policy = clock_policy_by_plan.get(plan.plan_fingerprint)
        if policy is None:
            raise RecurrentForecastHorizonClockBookError(
                "new open exit plan lacks explicit horizon-clock policy"
            )
        new_plan_fingerprints.add(plan.plan_fingerprint)
        try:
            clocks.append(
                build_forecast_horizon_clock_v1(
                    plan=plan,
                    policy=policy,
                )
            )
        except ForecastHorizonClockError as exc:
            raise RecurrentForecastHorizonClockBookError(
                "new horizon clock construction failed"
            ) from exc

    supplied = set(clock_policy_by_plan)
    if supplied != new_plan_fingerprints:
        missing = sorted(new_plan_fingerprints - supplied)
        extra = sorted(supplied - new_plan_fingerprints)
        raise RecurrentForecastHorizonClockBookError(
            "clock-policy coverage must exactly match newly unclocked plans; "
            f"missing={missing}, extra={extra}"
        )

    ordered = tuple(
        sorted(
            clocks,
            key=lambda item: item.position_fingerprint,
        )
    )
    payload = _book_payload(
        exit_plan_book=exit_plan_book,
        built_at_utc=built,
        clocks=ordered,
    )
    return RecurrentForecastHorizonClockBookV1(
        contract_version=(
            RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
        ),
        source_id=RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID,
        book_fingerprint=_fingerprint_payload(payload),
        exit_plan_book=exit_plan_book,
        built_at_utc=built,
        clocks=ordered,
    )


def recurrent_forecast_horizon_clock_book_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).recurrent_forecast_horizon_clock_book_file()


def recurrent_forecast_horizon_clock_book_from_payload(
    payload: dict[str, object],
) -> RecurrentForecastHorizonClockBookV1:
    exit_plan_book = (
        recurrent_decision_stock_exit_plan_book_from_payload(
            dict(payload["exit_plan_book"])
        )
    )
    clocks = tuple(
        forecast_horizon_clock_from_payload(dict(item))
        for item in payload["clocks"]
    )
    return RecurrentForecastHorizonClockBookV1(
        contract_version=str(payload["contract_version"]),
        contract_fingerprint=str(payload["contract_fingerprint"]),
        source_id=str(payload["source_id"]),
        book_fingerprint=str(payload["book_fingerprint"]),
        exit_plan_book=exit_plan_book,
        built_at_utc=datetime.fromisoformat(
            str(payload["built_at_utc"])
        ),
        clocks=clocks,
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


def write_recurrent_forecast_horizon_clock_book_v1(
    settings: AtlasSettings,
    book: RecurrentForecastHorizonClockBookV1,
) -> Path:
    path = recurrent_forecast_horizon_clock_book_path(settings)
    raw = json.dumps(
        _canonicalize(book),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_recurrent_forecast_horizon_clock_book_v1(
        settings,
        path=path,
    )
    if restored != book:
        raise RecurrentForecastHorizonClockBookError(
            "forecast-horizon clock-book readback mismatch"
        )
    return path


def read_recurrent_forecast_horizon_clock_book_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> RecurrentForecastHorizonClockBookV1:
    target = (
        Path(path)
        if path is not None
        else recurrent_forecast_horizon_clock_book_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise RecurrentForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BOOK_BYTES:
        raise RecurrentForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise RecurrentForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise RecurrentForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecurrentForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise RecurrentForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact root must be an object"
        )
    try:
        return recurrent_forecast_horizon_clock_book_from_payload(
            payload
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        ForecastHorizonClockError,
        RecurrentForecastHorizonClockBookError,
    ) as exc:
        if isinstance(
            exc,
            RecurrentForecastHorizonClockBookError,
        ):
            raise
        raise RecurrentForecastHorizonClockBookError(
            "forecast-horizon clock-book artifact failed typed validation"
        ) from exc


__all__ = [
    "RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT",
    "RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_VERSION",
    "RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_SOURCE_ID",
    "RecurrentForecastHorizonClockBookError",
    "RecurrentForecastHorizonClockBookV1",
    "build_recurrent_forecast_horizon_clock_book_v1",
    "read_recurrent_forecast_horizon_clock_book_v1",
    "recurrent_forecast_horizon_clock_book_from_payload",
    "recurrent_forecast_horizon_clock_book_path",
    "write_recurrent_forecast_horizon_clock_book_v1",
]
