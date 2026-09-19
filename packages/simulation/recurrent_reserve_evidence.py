from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import (
    ActionabilityPolicy,
    EconomicCandidate,
    InstrumentKind,
    SelectionKind,
    TradeExpressionMode,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import UnderlyingMoveTimeForecast
from packages.simulation.decision_record import (
    SimulationDecisionRecord,
    SimulationDecisionRecordError,
    economic_candidate_fingerprint,
    simulation_decision_record_from_payload,
)
from packages.simulation.decision_record_contract import (
    SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT,
)
from packages.simulation.option_reservation import (
    LongOptionReservationTerms,
    long_option_reservation_terms_fingerprint,
)
from packages.simulation.recurrent_cycle import RecurrentCycleReceiptV1
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunIdentityV1,
    RecurrentCycleRunnerV1,
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_reserve_evidence_contract import (
    RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT,
    RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT,
)


RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_VERSION = str(
    RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT["contract_id"]
)
RECURRENT_RESERVE_EVIDENCE_SOURCE_ID = (
    "atlas-recurrent-reserve-evidence/current.json"
)
_MAX_BUNDLE_BYTES = 64 * 1024 * 1024


class RecurrentReserveEvidenceError(RuntimeError):
    pass


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentReserveEvidenceError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentReserveEvidenceError(
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


def _option_terms_from_payload(
    payload: dict[str, object],
) -> LongOptionReservationTerms:
    values = dict(payload)
    values["direction"] = DiscoveryDirection(
        str(values["direction"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return LongOptionReservationTerms(**values)


@dataclass(frozen=True)
class RecurrentReserveEvidenceEntryV1:
    record: SimulationDecisionRecord
    option_terms: LongOptionReservationTerms | None

    def __post_init__(self) -> None:
        if (
            self.record.contract_fingerprint
            != SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT
        ):
            raise RecurrentReserveEvidenceError(
                "reserve entry decision-record contract fingerprint mismatch"
            )
        decision = self.record.trade_expression_decision
        if decision.selection_kind == SelectionKind.OPTION:
            if self.option_terms is None:
                raise RecurrentReserveEvidenceError(
                    "selected option decision requires exact reservation terms"
                )
            chosen = decision.chosen_candidate
            if chosen is None or chosen.kind != InstrumentKind.OPTION:
                raise RecurrentReserveEvidenceError(
                    "selected option decision is missing option candidate"
                )
            terms = self.option_terms
            if (
                terms.decision_record_fingerprint
                != self.record.record_fingerprint
            ):
                raise RecurrentReserveEvidenceError(
                    "option terms decision-record fingerprint mismatch"
                )
            if terms.chosen_candidate_identifier != chosen.identifier:
                raise RecurrentReserveEvidenceError(
                    "option terms chosen candidate identifier mismatch"
                )
            if (
                terms.chosen_candidate_fingerprint
                != economic_candidate_fingerprint(chosen)
            ):
                raise RecurrentReserveEvidenceError(
                    "option terms chosen candidate fingerprint mismatch"
                )
            if (
                terms.source_forecast_fingerprint
                != self.record.forecast_fingerprint
            ):
                raise RecurrentReserveEvidenceError(
                    "option terms forecast fingerprint mismatch"
                )
            if (
                terms.instrument_id != self.record.forecast.instrument_id
                or terms.ticker != self.record.forecast.ticker
                or terms.direction != self.record.forecast.direction
            ):
                raise RecurrentReserveEvidenceError(
                    "option terms underlying identity mismatch"
                )
        elif self.option_terms is not None:
            raise RecurrentReserveEvidenceError(
                "stock or abstain decision cannot carry option reservation terms"
            )

    @property
    def entry_fingerprint(self) -> str:
        return _fingerprint_payload(
            {
                "record_fingerprint": self.record.record_fingerprint,
                "option_terms_fingerprint": (
                    None
                    if self.option_terms is None
                    else long_option_reservation_terms_fingerprint(
                        self.option_terms
                    )
                ),
            }
        )


def _bundle_payload(
    *,
    cycle_id: str,
    cycle_fingerprint: str,
    schedule_id: str,
    scheduled_for_utc: datetime,
    built_at_utc: datetime,
    entries: tuple[RecurrentReserveEvidenceEntryV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT
        ),
        "source_id": RECURRENT_RESERVE_EVIDENCE_SOURCE_ID,
        "cycle_id": cycle_id,
        "cycle_fingerprint": cycle_fingerprint,
        "schedule_id": schedule_id,
        "scheduled_for_utc": scheduled_for_utc,
        "built_at_utc": built_at_utc,
        "entries": entries,
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
class RecurrentReserveEvidenceBundleV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    bundle_fingerprint: str
    cycle_id: str
    cycle_fingerprint: str
    schedule_id: str
    scheduled_for_utc: datetime
    built_at_utc: datetime
    entries: tuple[RecurrentReserveEvidenceEntryV1, ...]

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
            != RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_VERSION
        ):
            raise RecurrentReserveEvidenceError(
                "reserve evidence contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentReserveEvidenceError(
                "reserve evidence contract fingerprint mismatch"
            )
        if self.source_id != RECURRENT_RESERVE_EVIDENCE_SOURCE_ID:
            raise RecurrentReserveEvidenceError(
                "reserve evidence source id mismatch"
            )
        _require_sha(
            self.bundle_fingerprint,
            label="reserve evidence bundle",
        )
        _require_sha(
            self.cycle_fingerprint,
            label="reserve evidence cycle",
        )
        scheduled = _require_aware(
            self.scheduled_for_utc,
            label="reserve evidence scheduled slot",
        )
        built = _require_aware(
            self.built_at_utc,
            label="reserve evidence build time",
        )
        expected_identity = build_recurrent_cycle_run_identity_v1(
            schedule_id=self.schedule_id,
            scheduled_for_utc=scheduled,
        )
        if (
            self.cycle_id != expected_identity.cycle_id
            or self.cycle_fingerprint
            != expected_identity.cycle_fingerprint
        ):
            raise RecurrentReserveEvidenceError(
                "reserve evidence cycle identity mismatch"
            )
        if built < scheduled:
            raise RecurrentReserveEvidenceError(
                "reserve evidence cannot be built before its scheduled cycle slot"
            )
        ordered = tuple(
            sorted(
                self.entries,
                key=lambda item: (
                    item.record.decision_created_utc,
                    item.record.record_fingerprint,
                ),
            )
        )
        if ordered != self.entries:
            raise RecurrentReserveEvidenceError(
                "reserve evidence entries must be deterministically ordered"
            )
        record_fps = tuple(
            entry.record.record_fingerprint
            for entry in self.entries
        )
        if len(record_fps) != len(set(record_fps)):
            raise RecurrentReserveEvidenceError(
                "reserve evidence cannot duplicate decision records"
            )
        if any(
            entry.record.decision_created_utc > built
            for entry in self.entries
        ):
            raise RecurrentReserveEvidenceError(
                "reserve evidence cannot contain a future decision"
            )
        if any(
            (
                self.provider_reads,
                self.provider_writes,
                self.broker_reads,
                self.broker_writes,
            )
        ):
            raise RecurrentReserveEvidenceError(
                "reserve evidence bundle cannot claim provider or broker calls"
            )
        if any(
            (
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise RecurrentReserveEvidenceError(
                "reserve evidence bundle cannot grant trading authority"
            )
        expected = _fingerprint_payload(
            _bundle_payload(
                cycle_id=self.cycle_id,
                cycle_fingerprint=self.cycle_fingerprint,
                schedule_id=self.schedule_id,
                scheduled_for_utc=scheduled,
                built_at_utc=built,
                entries=self.entries,
            )
        )
        if self.bundle_fingerprint != expected:
            raise RecurrentReserveEvidenceError(
                "reserve evidence bundle self-fingerprint mismatch"
            )

    @property
    def decision_count(self) -> int:
        return len(self.entries)

    @property
    def runner_decisions(
        self,
    ) -> tuple[
        tuple[
            SimulationDecisionRecord,
            LongOptionReservationTerms | None,
        ],
        ...,
    ]:
        return tuple(
            (entry.record, entry.option_terms)
            for entry in self.entries
        )


def build_recurrent_reserve_evidence_bundle_v1(
    *,
    identity: RecurrentCycleRunIdentityV1,
    decisions: Sequence[
        tuple[
            SimulationDecisionRecord,
            LongOptionReservationTerms | None,
        ]
    ],
    built_at_utc: datetime | None = None,
) -> RecurrentReserveEvidenceBundleV1:
    built = _require_aware(
        built_at_utc or datetime.now(UTC),
        label="reserve evidence build time",
    )
    entries = tuple(
        sorted(
            (
                RecurrentReserveEvidenceEntryV1(
                    record=record,
                    option_terms=option_terms,
                )
                for record, option_terms in decisions
            ),
            key=lambda item: (
                item.record.decision_created_utc,
                item.record.record_fingerprint,
            ),
        )
    )
    payload = _bundle_payload(
        cycle_id=identity.cycle_id,
        cycle_fingerprint=identity.cycle_fingerprint,
        schedule_id=identity.schedule_id,
        scheduled_for_utc=identity.scheduled_for_utc,
        built_at_utc=built,
        entries=entries,
    )
    return RecurrentReserveEvidenceBundleV1(
        contract_version=(
            RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT
        ),
        source_id=RECURRENT_RESERVE_EVIDENCE_SOURCE_ID,
        bundle_fingerprint=_fingerprint_payload(payload),
        cycle_id=identity.cycle_id,
        cycle_fingerprint=identity.cycle_fingerprint,
        schedule_id=identity.schedule_id,
        scheduled_for_utc=identity.scheduled_for_utc,
        built_at_utc=built,
        entries=entries,
    )


def recurrent_reserve_evidence_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).recurrent_reserve_evidence_file()


def _artifact_payload(
    bundle: RecurrentReserveEvidenceBundleV1,
) -> dict[str, object]:
    return {
        "contract_version": bundle.contract_version,
        "contract_fingerprint": bundle.contract_fingerprint,
        "source_id": bundle.source_id,
        "bundle_fingerprint": bundle.bundle_fingerprint,
        "cycle_id": bundle.cycle_id,
        "cycle_fingerprint": bundle.cycle_fingerprint,
        "schedule_id": bundle.schedule_id,
        "scheduled_for_utc": bundle.scheduled_for_utc.isoformat(),
        "built_at_utc": bundle.built_at_utc.isoformat(),
        "entries": [
            {
                "record": _canonicalize(entry.record),
                "option_terms": (
                    None
                    if entry.option_terms is None
                    else _canonicalize(entry.option_terms)
                ),
            }
            for entry in bundle.entries
        ],
        "provider_reads": bundle.provider_reads,
        "provider_writes": bundle.provider_writes,
        "broker_reads": bundle.broker_reads,
        "broker_writes": bundle.broker_writes,
        "order_creation_authority": bundle.order_creation_authority,
        "paper_authority": bundle.paper_authority,
        "live_authority": bundle.live_authority,
        "promotion_authority": bundle.promotion_authority,
        "confluence_authority": bundle.confluence_authority,
    }


def write_recurrent_reserve_evidence_bundle_v1(
    settings: AtlasSettings,
    bundle: RecurrentReserveEvidenceBundleV1,
) -> Path:
    path = recurrent_reserve_evidence_path(settings)
    raw = json.dumps(
        _artifact_payload(bundle),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_recurrent_reserve_evidence_bundle_v1(
        settings,
        path=path,
    )
    if restored != bundle:
        raise RecurrentReserveEvidenceError(
            "reserve evidence readback verification mismatch"
        )
    return path


def read_recurrent_reserve_evidence_bundle_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> RecurrentReserveEvidenceBundleV1:
    target = (
        Path(path)
        if path is not None
        else recurrent_reserve_evidence_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise RecurrentReserveEvidenceError(
            "reserve evidence artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise RecurrentReserveEvidenceError(
            "reserve evidence artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise RecurrentReserveEvidenceError(
            "reserve evidence artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise RecurrentReserveEvidenceError(
            "reserve evidence artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecurrentReserveEvidenceError(
            "reserve evidence artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise RecurrentReserveEvidenceError(
            "reserve evidence artifact root must be an object"
        )

    try:
        entries = tuple(
            RecurrentReserveEvidenceEntryV1(
                record=simulation_decision_record_from_payload(
                    dict(item["record"])
                ),
                option_terms=(
                    None
                    if item.get("option_terms") is None
                    else _option_terms_from_payload(
                        dict(item["option_terms"])
                    )
                ),
            )
            for item in payload["entries"]
        )
        return RecurrentReserveEvidenceBundleV1(
            contract_version=str(payload["contract_version"]),
            contract_fingerprint=str(
                payload["contract_fingerprint"]
            ),
            source_id=str(payload["source_id"]),
            bundle_fingerprint=str(
                payload["bundle_fingerprint"]
            ),
            cycle_id=str(payload["cycle_id"]),
            cycle_fingerprint=str(
                payload["cycle_fingerprint"]
            ),
            schedule_id=str(payload["schedule_id"]),
            scheduled_for_utc=datetime.fromisoformat(
                str(payload["scheduled_for_utc"])
            ),
            built_at_utc=datetime.fromisoformat(
                str(payload["built_at_utc"])
            ),
            entries=entries,
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
    except (
        KeyError,
        TypeError,
        ValueError,
        RecurrentReserveEvidenceError,
        SimulationDecisionRecordError,
    ) as exc:
        if isinstance(exc, RecurrentReserveEvidenceError):
            raise
        raise RecurrentReserveEvidenceError(
            "reserve evidence artifact failed typed validation"
        ) from exc


def apply_recurrent_reserve_evidence_bundle_v1(
    *,
    runner: RecurrentCycleRunnerV1,
    identity: RecurrentCycleRunIdentityV1,
    bundle: RecurrentReserveEvidenceBundleV1,
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    if (
        bundle.cycle_id != identity.cycle_id
        or bundle.cycle_fingerprint
        != identity.cycle_fingerprint
    ):
        raise RecurrentReserveEvidenceError(
            "reserve evidence bundle is bound to a different cycle"
        )
    return runner.apply_reserve(
        identity=identity,
        evidence_source_id=bundle.source_id,
        evidence_source_fingerprint=bundle.bundle_fingerprint,
        decisions=bundle.runner_decisions,
        now_utc=now_utc,
    )


__all__ = [
    "RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT",
    "RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_VERSION",
    "RECURRENT_RESERVE_EVIDENCE_SOURCE_ID",
    "RecurrentReserveEvidenceBundleV1",
    "RecurrentReserveEvidenceEntryV1",
    "RecurrentReserveEvidenceError",
    "apply_recurrent_reserve_evidence_bundle_v1",
    "build_recurrent_reserve_evidence_bundle_v1",
    "read_recurrent_reserve_evidence_bundle_v1",
    "recurrent_reserve_evidence_path",
    "write_recurrent_reserve_evidence_bundle_v1",
]
