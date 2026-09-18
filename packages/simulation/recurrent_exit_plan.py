from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import BaseModel

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.execution.trade_expression import InstrumentKind
from packages.portfolio.phase13_policy import phase13_policy_fingerprint
from packages.schemas.case_file import (
    GeometryStatus,
    PHASE13_CASE_FILE_CONTRACT_VERSION,
    Phase13CaseFile,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.open_position_state import (
    SimulatedOpenPositionV1,
    simulated_open_position_fingerprint,
)
from packages.simulation.recurrent_exit_plan_contract import (
    RECURRENT_STOCK_EXIT_PLAN_CONTRACT,
    RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountStateV1,
    recurrent_lifecycle_account_state_fingerprint,
)


RECURRENT_STOCK_EXIT_PLAN_CONTRACT_VERSION = str(
    RECURRENT_STOCK_EXIT_PLAN_CONTRACT["contract_id"]
)
RECURRENT_STOCK_EXIT_PLAN_SOURCE_ID = (
    "atlas-recurrent-stock-exit-plan/current.json"
)
_MAX_BUNDLE_BYTES = 64 * 1024 * 1024
_TOLERANCE = 1e-9


class RecurrentStockExitPlanError(RuntimeError):
    pass


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentStockExitPlanError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentStockExitPlanError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _same(left: float, right: float) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=1e-12,
        abs_tol=_TOLERANCE,
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


def phase13_case_fingerprint(case: Phase13CaseFile) -> str:
    return _fingerprint_payload(case)


@dataclass(frozen=True)
class RecurrentStockExitPlanV1:
    contract_version: str
    contract_fingerprint: str
    phase13_policy_fingerprint: str
    source_recurrent_state_fingerprint: str
    position_fingerprint: str
    phase13_case_fingerprint: str
    phase13_case: Phase13CaseFile
    plan_created_utc: datetime

    decision_record_fingerprint: str
    entry_fill_fingerprint: str
    funding_terms_fingerprint: str
    instrument_id: str
    ticker: str
    direction: DiscoveryDirection
    opened_utc: datetime
    actual_entry_price_per_unit: float

    reference_entry_price_per_unit: float
    reference_stop_price_per_unit: float
    reference_target_price_per_unit: float
    risk_fraction: float
    reward_fraction: float
    horizon_sessions: int

    stop_price_per_unit: float
    target_price_per_unit: float

    reference_absolute_prices_executable: bool = False
    price_exit_trigger_authority: bool = False
    time_exit_trigger_enabled: bool = False
    close_fill_authority: bool = False
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
        "EXACT_RECURRENT_STOCK_POSITION_BOUND",
        "VALIDATED_PHASE13_REFERENCE_GEOMETRY_BOUND",
        "REFERENCE_ABSOLUTE_PRICES_NOT_USED_AS_EXECUTABLE_LEVELS",
        "RISK_REWARD_FRACTIONS_TRANSFERRED_TO_ACTUAL_ENTRY_FILL",
        "TIME_EXIT_TRIGGER_NOT_ENABLED_IN_V1",
        "NO_CLOSE_OR_TRADING_AUTHORITY_GRANTED",
    )

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != RECURRENT_STOCK_EXIT_PLAN_CONTRACT_VERSION
        ):
            raise RecurrentStockExitPlanError(
                "recurrent stock exit-plan contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise RecurrentStockExitPlanError(
                "recurrent stock exit-plan contract fingerprint mismatch"
            )
        if self.phase13_policy_fingerprint != phase13_policy_fingerprint():
            raise RecurrentStockExitPlanError(
                "Phase 13 policy fingerprint mismatch"
            )
        for label, value in (
            (
                "source recurrent state",
                self.source_recurrent_state_fingerprint,
            ),
            ("position", self.position_fingerprint),
            ("Phase 13 case", self.phase13_case_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("entry fill", self.entry_fill_fingerprint),
            ("funding terms", self.funding_terms_fingerprint),
        ):
            _require_sha(value, label=label)
        created = _require_aware(
            self.plan_created_utc,
            label="exit-plan creation time",
        )
        opened = _require_aware(
            self.opened_utc,
            label="position opened time",
        )
        if created < opened:
            raise RecurrentStockExitPlanError(
                "exit plan cannot be created before position open"
            )
        if self.direction != DiscoveryDirection.BULLISH:
            raise RecurrentStockExitPlanError(
                "recurrent stock exit-plan v1 supports bullish stock longs only"
            )
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise RecurrentStockExitPlanError(
                "exit-plan stock identity cannot be blank"
            )
        if self.phase13_case.contract_version != PHASE13_CASE_FILE_CONTRACT_VERSION:
            raise RecurrentStockExitPlanError(
                "Phase 13 case contract version mismatch"
            )
        if (
            self.phase13_case_fingerprint
            != phase13_case_fingerprint(self.phase13_case)
        ):
            raise RecurrentStockExitPlanError(
                "Phase 13 case fingerprint mismatch"
            )
        case = self.phase13_case
        if not case.phase14_review_ready:
            raise RecurrentStockExitPlanError(
                "exit plan requires Phase 13 case ready for independent review"
            )
        if (
            case.instrument_id != self.instrument_id
            or case.ticker != self.ticker
            or case.direction != self.direction
        ):
            raise RecurrentStockExitPlanError(
                "Phase 13 case identity does not match recurrent position"
            )
        if case.as_of_date > opened.date():
            raise RecurrentStockExitPlanError(
                "Phase 13 exit geometry cannot postdate position open"
            )
        geometry = case.geometry
        if geometry.status != GeometryStatus.AVAILABLE:
            raise RecurrentStockExitPlanError(
                "exit plan requires available Phase 13 geometry"
            )
        if not geometry.reference_only_not_fill:
            raise RecurrentStockExitPlanError(
                "Phase 13 geometry must remain reference-only"
            )
        required_geometry = (
            geometry.reference_entry,
            geometry.stop,
            geometry.target,
            geometry.risk_fraction,
            geometry.reward_fraction,
        )
        if any(value is None for value in required_geometry):
            raise RecurrentStockExitPlanError(
                "exit plan requires complete Phase 13 geometry"
            )
        assert geometry.reference_entry is not None
        assert geometry.stop is not None
        assert geometry.target is not None
        assert geometry.risk_fraction is not None
        assert geometry.reward_fraction is not None
        checks = (
            (
                self.reference_entry_price_per_unit,
                geometry.reference_entry,
                "reference entry",
            ),
            (
                self.reference_stop_price_per_unit,
                geometry.stop,
                "reference stop",
            ),
            (
                self.reference_target_price_per_unit,
                geometry.target,
                "reference target",
            ),
            (
                self.risk_fraction,
                geometry.risk_fraction,
                "risk fraction",
            ),
            (
                self.reward_fraction,
                geometry.reward_fraction,
                "reward fraction",
            ),
        )
        for actual, expected, label in checks:
            if not _same(actual, expected):
                raise RecurrentStockExitPlanError(
                    f"exit-plan {label} does not match Phase 13 geometry"
                )
        if self.horizon_sessions != geometry.horizon_sessions:
            raise RecurrentStockExitPlanError(
                "exit-plan horizon does not match Phase 13 geometry"
            )
        positive = (
            self.actual_entry_price_per_unit,
            self.reference_entry_price_per_unit,
            self.reference_stop_price_per_unit,
            self.reference_target_price_per_unit,
            self.risk_fraction,
            self.reward_fraction,
            self.stop_price_per_unit,
            self.target_price_per_unit,
        )
        if not all(math.isfinite(x) and x > 0.0 for x in positive):
            raise RecurrentStockExitPlanError(
                "exit-plan prices and fractions must be finite and positive"
            )
        expected_stop = self.actual_entry_price_per_unit * (
            1.0 - self.risk_fraction
        )
        expected_target = self.actual_entry_price_per_unit * (
            1.0 + self.reward_fraction
        )
        if expected_stop <= 0.0:
            raise RecurrentStockExitPlanError(
                "actual-fill risk fraction produced nonpositive stop"
            )
        if not _same(self.stop_price_per_unit, expected_stop):
            raise RecurrentStockExitPlanError(
                "exit-plan stop is not derived from actual entry fill"
            )
        if not _same(self.target_price_per_unit, expected_target):
            raise RecurrentStockExitPlanError(
                "exit-plan target is not derived from actual entry fill"
            )
        if not (
            self.stop_price_per_unit
            < self.actual_entry_price_per_unit
            < self.target_price_per_unit
        ):
            raise RecurrentStockExitPlanError(
                "bullish actual-fill exit geometry is invalid"
            )
        if (
            self.reference_absolute_prices_executable
            or self.price_exit_trigger_authority
            or self.time_exit_trigger_enabled
            or self.close_fill_authority
            or self.provider_read_authority
            or self.provider_write_authority
            or self.broker_read_authority
            or self.broker_write_authority
            or self.order_creation_authority
            or self.paper_authority
            or self.live_authority
            or self.promotion_authority
            or self.confluence_authority
        ):
            raise RecurrentStockExitPlanError(
                "exit plan cannot grant reference-price, trigger, close, provider, broker, order, trading, promotion, or confluence authority"
            )
        if not self.reason_codes:
            raise RecurrentStockExitPlanError(
                "exit plan requires reason codes"
            )

    @property
    def plan_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def build_recurrent_stock_exit_plan_v1(
    *,
    source_recurrent_state_fingerprint: str,
    position: SimulatedOpenPositionV1,
    phase13_case: Phase13CaseFile,
    plan_created_utc: datetime | None = None,
) -> RecurrentStockExitPlanV1:
    _require_sha(
        source_recurrent_state_fingerprint,
        label="source recurrent state",
    )
    if position.instrument_kind != InstrumentKind.STOCK:
        raise RecurrentStockExitPlanError(
            "recurrent stock exit-plan v1 accepts stock positions only"
        )
    if position.direction != DiscoveryDirection.BULLISH:
        raise RecurrentStockExitPlanError(
            "recurrent stock exit-plan v1 accepts bullish stock longs only"
        )
    position_fp = simulated_open_position_fingerprint(position)
    geometry = phase13_case.geometry
    if geometry.status != GeometryStatus.AVAILABLE:
        raise RecurrentStockExitPlanError(
            "Phase 13 geometry is unavailable"
        )
    if (
        geometry.reference_entry is None
        or geometry.stop is None
        or geometry.target is None
        or geometry.risk_fraction is None
        or geometry.reward_fraction is None
    ):
        raise RecurrentStockExitPlanError(
            "Phase 13 geometry is incomplete"
        )
    created = _require_aware(
        plan_created_utc or datetime.now(UTC),
        label="exit-plan creation time",
    )
    stop = position.entry_price_per_unit * (
        1.0 - geometry.risk_fraction
    )
    target = position.entry_price_per_unit * (
        1.0 + geometry.reward_fraction
    )
    return RecurrentStockExitPlanV1(
        contract_version=RECURRENT_STOCK_EXIT_PLAN_CONTRACT_VERSION,
        contract_fingerprint=(
            RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ),
        phase13_policy_fingerprint=phase13_policy_fingerprint(),
        source_recurrent_state_fingerprint=(
            source_recurrent_state_fingerprint
        ),
        position_fingerprint=position_fp,
        phase13_case_fingerprint=phase13_case_fingerprint(
            phase13_case
        ),
        phase13_case=phase13_case,
        plan_created_utc=created,
        decision_record_fingerprint=(
            position.decision_record_fingerprint
        ),
        entry_fill_fingerprint=position.fill_fingerprint,
        funding_terms_fingerprint=position.funding_terms_fingerprint,
        instrument_id=position.instrument_id,
        ticker=position.ticker,
        direction=position.direction,
        opened_utc=position.opened_utc,
        actual_entry_price_per_unit=position.entry_price_per_unit,
        reference_entry_price_per_unit=geometry.reference_entry,
        reference_stop_price_per_unit=geometry.stop,
        reference_target_price_per_unit=geometry.target,
        risk_fraction=geometry.risk_fraction,
        reward_fraction=geometry.reward_fraction,
        horizon_sessions=geometry.horizon_sessions,
        stop_price_per_unit=stop,
        target_price_per_unit=target,
    )


@dataclass(frozen=True)
class RecurrentStockExitPlanBundleV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    bundle_fingerprint: str
    source_recurrent_state_fingerprint: str
    built_at_utc: datetime
    plans: tuple[RecurrentStockExitPlanV1, ...]

    provider_reads: int = 0
    provider_writes: int = 0
    broker_reads: int = 0
    broker_writes: int = 0
    close_trigger_authority: bool = False
    close_fill_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != RECURRENT_STOCK_EXIT_PLAN_CONTRACT_VERSION
        ):
            raise RecurrentStockExitPlanError(
                "exit-plan bundle contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise RecurrentStockExitPlanError(
                "exit-plan bundle contract fingerprint mismatch"
            )
        if self.source_id != RECURRENT_STOCK_EXIT_PLAN_SOURCE_ID:
            raise RecurrentStockExitPlanError(
                "exit-plan bundle source id mismatch"
            )
        for label, value in (
            ("bundle", self.bundle_fingerprint),
            (
                "source recurrent state",
                self.source_recurrent_state_fingerprint,
            ),
        ):
            _require_sha(value, label=label)
        built = _require_aware(
            self.built_at_utc,
            label="exit-plan bundle build time",
        )
        ordered = tuple(
            sorted(
                self.plans,
                key=lambda item: item.position_fingerprint,
            )
        )
        if ordered != self.plans:
            raise RecurrentStockExitPlanError(
                "exit plans must be ordered by position fingerprint"
            )
        ids = tuple(plan.position_fingerprint for plan in self.plans)
        if len(ids) != len(set(ids)):
            raise RecurrentStockExitPlanError(
                "exit-plan bundle cannot duplicate positions"
            )
        for plan in self.plans:
            if (
                plan.source_recurrent_state_fingerprint
                != self.source_recurrent_state_fingerprint
            ):
                raise RecurrentStockExitPlanError(
                    "exit plan does not bind bundle recurrent state"
                )
            if plan.plan_created_utc > built:
                raise RecurrentStockExitPlanError(
                    "exit plan cannot postdate bundle construction"
                )
        if any(
            (
                self.provider_reads,
                self.provider_writes,
                self.broker_reads,
                self.broker_writes,
                self.close_trigger_authority,
                self.close_fill_authority,
                self.paper_authority,
                self.live_authority,
            )
        ):
            raise RecurrentStockExitPlanError(
                "exit-plan bundle cannot grant external or close authority"
            )
        expected = _fingerprint_payload(
            {
                "contract_version": self.contract_version,
                "contract_fingerprint": self.contract_fingerprint,
                "source_id": self.source_id,
                "source_recurrent_state_fingerprint": (
                    self.source_recurrent_state_fingerprint
                ),
                "built_at_utc": built,
                "plans": self.plans,
                "provider_reads": 0,
                "provider_writes": 0,
                "broker_reads": 0,
                "broker_writes": 0,
                "close_trigger_authority": False,
                "close_fill_authority": False,
                "paper_authority": False,
                "live_authority": False,
            }
        )
        if self.bundle_fingerprint != expected:
            raise RecurrentStockExitPlanError(
                "exit-plan bundle self-fingerprint mismatch"
            )


def build_recurrent_stock_exit_plan_bundle_v1(
    *,
    source_state: RecurrentLifecycleAccountStateV1,
    phase13_cases_by_position: Mapping[str, Phase13CaseFile],
    built_at_utc: datetime | None = None,
) -> RecurrentStockExitPlanBundleV1:
    if (
        source_state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentStockExitPlanError(
            "source recurrent account contract fingerprint mismatch"
        )
    if (
        source_state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(source_state)
    ):
        raise RecurrentStockExitPlanError(
            "source recurrent account state fingerprint mismatch"
        )
    positions = tuple(source_state.open_positions)
    if any(
        position.instrument_kind != InstrumentKind.STOCK
        for position in positions
    ):
        raise RecurrentStockExitPlanError(
            "exit-plan v1 cannot cover open option positions"
        )
    expected = {
        position.position_fingerprint for position in positions
    }
    supplied = set(phase13_cases_by_position)
    if expected != supplied:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise RecurrentStockExitPlanError(
            "Phase 13 exit-case coverage must exactly match open stock positions; "
            f"missing={missing}, extra={extra}"
        )
    built = _require_aware(
        built_at_utc or datetime.now(UTC),
        label="exit-plan bundle build time",
    )
    if built < source_state.as_of_utc:
        raise RecurrentStockExitPlanError(
            "exit-plan bundle cannot predate recurrent state"
        )
    plans = tuple(
        sorted(
            (
                build_recurrent_stock_exit_plan_v1(
                    source_recurrent_state_fingerprint=(
                        source_state.state_fingerprint
                    ),
                    position=position,
                    phase13_case=phase13_cases_by_position[
                        position.position_fingerprint
                    ],
                    plan_created_utc=built,
                )
                for position in positions
            ),
            key=lambda item: item.position_fingerprint,
        )
    )
    payload = {
        "contract_version": RECURRENT_STOCK_EXIT_PLAN_CONTRACT_VERSION,
        "contract_fingerprint": (
            RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ),
        "source_id": RECURRENT_STOCK_EXIT_PLAN_SOURCE_ID,
        "source_recurrent_state_fingerprint": (
            source_state.state_fingerprint
        ),
        "built_at_utc": built,
        "plans": plans,
        "provider_reads": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "close_trigger_authority": False,
        "close_fill_authority": False,
        "paper_authority": False,
        "live_authority": False,
    }
    return RecurrentStockExitPlanBundleV1(
        contract_version=RECURRENT_STOCK_EXIT_PLAN_CONTRACT_VERSION,
        contract_fingerprint=(
            RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ),
        source_id=RECURRENT_STOCK_EXIT_PLAN_SOURCE_ID,
        bundle_fingerprint=_fingerprint_payload(payload),
        source_recurrent_state_fingerprint=(
            source_state.state_fingerprint
        ),
        built_at_utc=built,
        plans=plans,
    )


def recurrent_stock_exit_plan_path(settings: AtlasSettings) -> Path:
    return MarketDataPaths(settings).recurrent_exit_plan_file()


def _artifact_payload(
    bundle: RecurrentStockExitPlanBundleV1,
) -> dict[str, object]:
    return _canonicalize(bundle)


def write_recurrent_stock_exit_plan_bundle_v1(
    settings: AtlasSettings,
    bundle: RecurrentStockExitPlanBundleV1,
) -> Path:
    path = recurrent_stock_exit_plan_path(settings)
    raw = json.dumps(
        _artifact_payload(bundle),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_recurrent_stock_exit_plan_bundle_v1(
        settings,
        path=path,
    )
    if restored != bundle:
        raise RecurrentStockExitPlanError(
            "exit-plan readback verification mismatch"
        )
    return path


def recurrent_stock_exit_plan_from_payload(
    payload: dict[str, object],
) -> RecurrentStockExitPlanV1:
    values = dict(payload)
    values["phase13_case"] = Phase13CaseFile.model_validate(
        values["phase13_case"]
    )
    values["plan_created_utc"] = datetime.fromisoformat(
        str(values["plan_created_utc"])
    )
    values["opened_utc"] = datetime.fromisoformat(
        str(values["opened_utc"])
    )
    values["direction"] = DiscoveryDirection(
        str(values["direction"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return RecurrentStockExitPlanV1(**values)


def read_recurrent_stock_exit_plan_bundle_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> RecurrentStockExitPlanBundleV1:
    target = (
        Path(path)
        if path is not None
        else recurrent_stock_exit_plan_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise RecurrentStockExitPlanError(
            "exit-plan artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise RecurrentStockExitPlanError(
            "exit-plan artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise RecurrentStockExitPlanError(
            "exit-plan artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise RecurrentStockExitPlanError(
            "exit-plan artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecurrentStockExitPlanError(
            "exit-plan artifact is invalid JSON"
        ) from exc
    try:
        plans = tuple(
            recurrent_stock_exit_plan_from_payload(dict(item))
            for item in payload["plans"]
        )
        return RecurrentStockExitPlanBundleV1(
            contract_version=str(payload["contract_version"]),
            contract_fingerprint=str(
                payload["contract_fingerprint"]
            ),
            source_id=str(payload["source_id"]),
            bundle_fingerprint=str(payload["bundle_fingerprint"]),
            source_recurrent_state_fingerprint=str(
                payload["source_recurrent_state_fingerprint"]
            ),
            built_at_utc=datetime.fromisoformat(
                str(payload["built_at_utc"])
            ),
            plans=plans,
            provider_reads=int(payload["provider_reads"]),
            provider_writes=int(payload["provider_writes"]),
            broker_reads=int(payload["broker_reads"]),
            broker_writes=int(payload["broker_writes"]),
            close_trigger_authority=bool(
                payload["close_trigger_authority"]
            ),
            close_fill_authority=bool(
                payload["close_fill_authority"]
            ),
            paper_authority=bool(payload["paper_authority"]),
            live_authority=bool(payload["live_authority"]),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        RecurrentStockExitPlanError,
    ) as exc:
        if isinstance(exc, RecurrentStockExitPlanError):
            raise
        raise RecurrentStockExitPlanError(
            "exit-plan artifact failed typed validation"
        ) from exc


__all__ = [
    "RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT",
    "RECURRENT_STOCK_EXIT_PLAN_CONTRACT_VERSION",
    "RECURRENT_STOCK_EXIT_PLAN_SOURCE_ID",
    "RecurrentStockExitPlanBundleV1",
    "RecurrentStockExitPlanError",
    "RecurrentStockExitPlanV1",
    "build_recurrent_stock_exit_plan_bundle_v1",
    "build_recurrent_stock_exit_plan_v1",
    "phase13_case_fingerprint",
    "recurrent_stock_exit_plan_from_payload",
    "read_recurrent_stock_exit_plan_bundle_v1",
    "recurrent_stock_exit_plan_path",
    "write_recurrent_stock_exit_plan_bundle_v1",
]
