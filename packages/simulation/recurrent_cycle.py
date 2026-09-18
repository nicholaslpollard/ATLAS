from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Sequence

from packages.core.atomic_io import atomic_write_text
from packages.simulation.decision_record import SimulationDecisionRecord
from packages.simulation.market_mark_evidence import SimulatedMarketMarkEvidence
from packages.simulation.option_reservation import LongOptionReservationTerms
from packages.simulation.recurrent_cycle_contract import (
    RECURRENT_CYCLE_RECEIPT_CONTRACT,
    RECURRENT_CYCLE_RECEIPT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_entry_evidence import (
    RecurrentEntryFillEvidenceV1,
    RecurrentFundingTermsV1,
)
from packages.simulation.recurrent_exit_fill import RecurrentExitFillEvidenceV1
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleEventKind,
)
from packages.simulation.recurrent_runtime import (
    DurableRecurrentLifecycleRuntimeV1,
)


RECURRENT_CYCLE_RECEIPT_CONTRACT_VERSION = str(
    RECURRENT_CYCLE_RECEIPT_CONTRACT["contract_id"]
)
_MAX_RECEIPT_BYTES = 16 * 1024 * 1024


class RecurrentCycleStage(StrEnum):
    CLOSE = "CLOSE"
    RESERVE = "RESERVE"
    ENTRY = "ENTRY"
    MARK = "MARK"


_STAGE_ORDER = (
    RecurrentCycleStage.CLOSE,
    RecurrentCycleStage.RESERVE,
    RecurrentCycleStage.ENTRY,
    RecurrentCycleStage.MARK,
)


class RecurrentCycleStatus(StrEnum):
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"


class RecurrentCycleOrchestrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecurrentCycleStageRecordV1:
    stage: RecurrentCycleStage
    action_fingerprints: tuple[str, ...]
    action_context: str | None
    source_checkpoint_sha256: str
    source_snapshot_fingerprint: str
    result_checkpoint_sha256: str
    result_snapshot_fingerprint: str
    result_revision: int
    recorded_at_utc: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("source checkpoint", self.source_checkpoint_sha256),
            ("source snapshot", self.source_snapshot_fingerprint),
            ("result checkpoint", self.result_checkpoint_sha256),
            ("result snapshot", self.result_snapshot_fingerprint),
        ):
            _require_sha(value, label=label)
        if self.result_revision < 0:
            raise RecurrentCycleOrchestrationError(
                "cycle stage result revision cannot be negative"
            )
        _require_aware(
            self.recorded_at_utc,
            label="cycle stage recorded timestamp",
        )
        if tuple(sorted(self.action_fingerprints)) != self.action_fingerprints:
            raise RecurrentCycleOrchestrationError(
                "cycle stage action fingerprints must be sorted"
            )
        if len(set(self.action_fingerprints)) != len(
            self.action_fingerprints
        ):
            raise RecurrentCycleOrchestrationError(
                "cycle stage action fingerprints cannot duplicate"
            )
        for value in self.action_fingerprints:
            _require_sha(value, label="cycle stage action")


@dataclass(frozen=True)
class RecurrentCycleReceiptV1:
    contract_version: str
    contract_fingerprint: str
    receipt_sha256: str
    cycle_id: str
    cycle_fingerprint: str
    status: RecurrentCycleStatus
    created_at_utc: datetime
    updated_at_utc: datetime
    completed_at_utc: datetime | None

    source_checkpoint_sha256: str
    source_snapshot_fingerprint: str
    current_checkpoint_sha256: str
    current_snapshot_fingerprint: str
    current_revision: int
    stages: tuple[RecurrentCycleStageRecordV1, ...]

    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != RECURRENT_CYCLE_RECEIPT_CONTRACT_VERSION:
            raise RecurrentCycleOrchestrationError(
                "recurrent cycle receipt contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_CYCLE_RECEIPT_CONTRACT_FINGERPRINT
        ):
            raise RecurrentCycleOrchestrationError(
                "recurrent cycle receipt contract fingerprint mismatch"
            )
        _require_sha(self.receipt_sha256, label="cycle receipt")
        if not self.cycle_id.strip():
            raise RecurrentCycleOrchestrationError(
                "cycle id cannot be blank"
            )
        if self.cycle_fingerprint != cycle_fingerprint(self.cycle_id):
            raise RecurrentCycleOrchestrationError(
                "cycle fingerprint mismatch"
            )
        for label, value in (
            ("source checkpoint", self.source_checkpoint_sha256),
            ("source snapshot", self.source_snapshot_fingerprint),
            ("current checkpoint", self.current_checkpoint_sha256),
            ("current snapshot", self.current_snapshot_fingerprint),
        ):
            _require_sha(value, label=label)
        _require_aware(self.created_at_utc, label="cycle created timestamp")
        _require_aware(self.updated_at_utc, label="cycle updated timestamp")
        if self.updated_at_utc < self.created_at_utc:
            raise RecurrentCycleOrchestrationError(
                "cycle updated timestamp cannot precede creation"
            )
        if self.current_revision < 0:
            raise RecurrentCycleOrchestrationError(
                "cycle current revision cannot be negative"
            )
        if len(self.stages) > len(_STAGE_ORDER):
            raise RecurrentCycleOrchestrationError(
                "cycle contains too many stage records"
            )
        for index, record in enumerate(self.stages):
            if record.stage != _STAGE_ORDER[index]:
                raise RecurrentCycleOrchestrationError(
                    "cycle stage order is invalid"
                )
            if index:
                previous = self.stages[index - 1]
                if (
                    record.source_checkpoint_sha256
                    != previous.result_checkpoint_sha256
                    or record.source_snapshot_fingerprint
                    != previous.result_snapshot_fingerprint
                ):
                    raise RecurrentCycleOrchestrationError(
                        "cycle stage checkpoint chain is broken"
                    )
        if self.stages:
            last = self.stages[-1]
            if (
                self.current_checkpoint_sha256
                != last.result_checkpoint_sha256
                or self.current_snapshot_fingerprint
                != last.result_snapshot_fingerprint
                or self.current_revision != last.result_revision
            ):
                raise RecurrentCycleOrchestrationError(
                    "cycle current state does not match latest stage"
                )
        else:
            if (
                self.current_checkpoint_sha256
                != self.source_checkpoint_sha256
                or self.current_snapshot_fingerprint
                != self.source_snapshot_fingerprint
            ):
                raise RecurrentCycleOrchestrationError(
                    "empty cycle current state must equal source state"
                )
        if self.status == RecurrentCycleStatus.COMPLETE:
            if len(self.stages) != len(_STAGE_ORDER):
                raise RecurrentCycleOrchestrationError(
                    "complete cycle requires all four stages"
                )
            if self.completed_at_utc is None:
                raise RecurrentCycleOrchestrationError(
                    "complete cycle requires completion timestamp"
                )
        elif self.completed_at_utc is not None:
            raise RecurrentCycleOrchestrationError(
                "open cycle cannot carry completion timestamp"
            )
        if self.completed_at_utc is not None:
            _require_aware(
                self.completed_at_utc,
                label="cycle completed timestamp",
            )
            if self.completed_at_utc < self.updated_at_utc:
                raise RecurrentCycleOrchestrationError(
                    "cycle completion cannot precede latest update"
                )
        forbidden = (
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
        if any(forbidden):
            raise RecurrentCycleOrchestrationError(
                "recurrent cycle cannot grant external/trading authority"
            )


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentCycleOrchestrationError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentCycleOrchestrationError(
            f"{label} must be timezone-aware"
        )


def cycle_fingerprint(cycle_id: str) -> str:
    if not cycle_id.strip():
        raise RecurrentCycleOrchestrationError(
            "cycle id cannot be blank"
        )
    return hashlib.sha256(cycle_id.encode("utf-8")).hexdigest()


def recurrent_cycle_receipt_path(
    checkpoint_path: Path,
    cycle_id: str,
) -> Path:
    return (
        Path(checkpoint_path).parent
        / "cycles"
        / f"{cycle_fingerprint(cycle_id)}.json"
    )


def _canonical_receipt_payload(
    receipt: RecurrentCycleReceiptV1,
    *,
    include_sha: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_version": receipt.contract_version,
        "contract_fingerprint": receipt.contract_fingerprint,
        "cycle_id": receipt.cycle_id,
        "cycle_fingerprint": receipt.cycle_fingerprint,
        "status": receipt.status.value,
        "created_at_utc": receipt.created_at_utc.isoformat(),
        "updated_at_utc": receipt.updated_at_utc.isoformat(),
        "completed_at_utc": (
            None
            if receipt.completed_at_utc is None
            else receipt.completed_at_utc.isoformat()
        ),
        "source_checkpoint_sha256": receipt.source_checkpoint_sha256,
        "source_snapshot_fingerprint": receipt.source_snapshot_fingerprint,
        "current_checkpoint_sha256": receipt.current_checkpoint_sha256,
        "current_snapshot_fingerprint": receipt.current_snapshot_fingerprint,
        "current_revision": receipt.current_revision,
        "stages": [
            {
                "stage": stage.stage.value,
                "action_fingerprints": list(stage.action_fingerprints),
                "action_context": stage.action_context,
                "source_checkpoint_sha256": stage.source_checkpoint_sha256,
                "source_snapshot_fingerprint": stage.source_snapshot_fingerprint,
                "result_checkpoint_sha256": stage.result_checkpoint_sha256,
                "result_snapshot_fingerprint": stage.result_snapshot_fingerprint,
                "result_revision": stage.result_revision,
                "recorded_at_utc": stage.recorded_at_utc.isoformat(),
            }
            for stage in receipt.stages
        ],
        "provider_read_authority": False,
        "provider_write_authority": False,
        "broker_read_authority": False,
        "broker_write_authority": False,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }
    if include_sha:
        payload["receipt_sha256"] = receipt.receipt_sha256
    return payload


def recurrent_cycle_receipt_sha256(
    receipt: RecurrentCycleReceiptV1,
) -> str:
    body = _canonical_receipt_payload(receipt, include_sha=False)
    raw = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _with_sha(
    *,
    cycle_id: str,
    status: RecurrentCycleStatus,
    created_at_utc: datetime,
    updated_at_utc: datetime,
    completed_at_utc: datetime | None,
    source_checkpoint_sha256: str,
    source_snapshot_fingerprint: str,
    current_checkpoint_sha256: str,
    current_snapshot_fingerprint: str,
    current_revision: int,
    stages: tuple[RecurrentCycleStageRecordV1, ...],
) -> RecurrentCycleReceiptV1:
    placeholder = RecurrentCycleReceiptV1(
        contract_version=RECURRENT_CYCLE_RECEIPT_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_CYCLE_RECEIPT_CONTRACT_FINGERPRINT,
        receipt_sha256="0" * 64,
        cycle_id=cycle_id,
        cycle_fingerprint=cycle_fingerprint(cycle_id),
        status=status,
        created_at_utc=created_at_utc,
        updated_at_utc=updated_at_utc,
        completed_at_utc=completed_at_utc,
        source_checkpoint_sha256=source_checkpoint_sha256,
        source_snapshot_fingerprint=source_snapshot_fingerprint,
        current_checkpoint_sha256=current_checkpoint_sha256,
        current_snapshot_fingerprint=current_snapshot_fingerprint,
        current_revision=current_revision,
        stages=stages,
    )
    return RecurrentCycleReceiptV1(
        **{
            **placeholder.__dict__,
            "receipt_sha256": recurrent_cycle_receipt_sha256(placeholder),
        }
    )


def _parse_time(value: object, *, label: str) -> datetime:
    if not isinstance(value, str):
        raise RecurrentCycleOrchestrationError(
            f"{label} must be an ISO timestamp"
        )
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RecurrentCycleOrchestrationError(
            f"{label} must be an ISO timestamp"
        ) from exc
    _require_aware(result, label=label)
    return result


def _read_json(path: Path) -> dict[str, object]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise RecurrentCycleOrchestrationError(
            f"could not stat cycle receipt: {path}"
        ) from exc
    if size <= 0 or size > _MAX_RECEIPT_BYTES:
        raise RecurrentCycleOrchestrationError(
            "cycle receipt size is invalid"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecurrentCycleOrchestrationError(
            f"could not read cycle receipt: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RecurrentCycleOrchestrationError(
            "cycle receipt must be a JSON object"
        )
    return value


def read_recurrent_cycle_receipt(
    path: Path,
) -> RecurrentCycleReceiptV1:
    value = _read_json(Path(path))
    try:
        stages = tuple(
            RecurrentCycleStageRecordV1(
                stage=RecurrentCycleStage(item["stage"]),
                action_fingerprints=tuple(item["action_fingerprints"]),
                action_context=item.get("action_context"),
                source_checkpoint_sha256=item[
                    "source_checkpoint_sha256"
                ],
                source_snapshot_fingerprint=item[
                    "source_snapshot_fingerprint"
                ],
                result_checkpoint_sha256=item[
                    "result_checkpoint_sha256"
                ],
                result_snapshot_fingerprint=item[
                    "result_snapshot_fingerprint"
                ],
                result_revision=int(item["result_revision"]),
                recorded_at_utc=_parse_time(
                    item["recorded_at_utc"],
                    label="cycle stage timestamp",
                ),
            )
            for item in value["stages"]  # type: ignore[index]
        )
        receipt = RecurrentCycleReceiptV1(
            contract_version=str(value["contract_version"]),
            contract_fingerprint=str(value["contract_fingerprint"]),
            receipt_sha256=str(value["receipt_sha256"]),
            cycle_id=str(value["cycle_id"]),
            cycle_fingerprint=str(value["cycle_fingerprint"]),
            status=RecurrentCycleStatus(str(value["status"])),
            created_at_utc=_parse_time(
                value["created_at_utc"],
                label="cycle created timestamp",
            ),
            updated_at_utc=_parse_time(
                value["updated_at_utc"],
                label="cycle updated timestamp",
            ),
            completed_at_utc=(
                None
                if value.get("completed_at_utc") is None
                else _parse_time(
                    value["completed_at_utc"],
                    label="cycle completed timestamp",
                )
            ),
            source_checkpoint_sha256=str(
                value["source_checkpoint_sha256"]
            ),
            source_snapshot_fingerprint=str(
                value["source_snapshot_fingerprint"]
            ),
            current_checkpoint_sha256=str(
                value["current_checkpoint_sha256"]
            ),
            current_snapshot_fingerprint=str(
                value["current_snapshot_fingerprint"]
            ),
            current_revision=int(value["current_revision"]),
            stages=stages,
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        RecurrentCycleOrchestrationError,
    ) as exc:
        if isinstance(exc, RecurrentCycleOrchestrationError):
            raise
        raise RecurrentCycleOrchestrationError(
            "cycle receipt schema is invalid"
        ) from exc
    if receipt.receipt_sha256 != recurrent_cycle_receipt_sha256(receipt):
        raise RecurrentCycleOrchestrationError(
            "cycle receipt self-hash mismatch"
        )
    return receipt


def _write_receipt(
    path: Path,
    receipt: RecurrentCycleReceiptV1,
) -> RecurrentCycleReceiptV1:
    atomic_write_text(
        Path(path),
        json.dumps(
            _canonical_receipt_payload(receipt, include_sha=True),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        fsync=True,
    )
    verified = read_recurrent_cycle_receipt(path)
    if verified != receipt:
        raise RecurrentCycleOrchestrationError(
            "cycle receipt readback verification failed"
        )
    return verified


def begin_recurrent_cycle(
    *,
    checkpoint_path: Path,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    cycle_id: str,
    now_utc: datetime | None = None,
) -> tuple[Path, RecurrentCycleReceiptV1]:
    status = runtime.status()
    if status.uncertain:
        raise RecurrentCycleOrchestrationError(
            "cannot begin cycle while durable runtime is uncertain"
        )
    path = recurrent_cycle_receipt_path(checkpoint_path, cycle_id)
    if path.exists():
        existing = read_recurrent_cycle_receipt(path)
        if existing.cycle_id != cycle_id:
            raise RecurrentCycleOrchestrationError(
                "cycle receipt fingerprint collision"
            )
        return path, existing
    now = now_utc or datetime.now(UTC)
    _require_aware(now, label="cycle begin timestamp")
    receipt = _with_sha(
        cycle_id=cycle_id,
        status=RecurrentCycleStatus.OPEN,
        created_at_utc=now,
        updated_at_utc=now,
        completed_at_utc=None,
        source_checkpoint_sha256=status.checkpoint_sha256,
        source_snapshot_fingerprint=status.snapshot_fingerprint,
        current_checkpoint_sha256=status.checkpoint_sha256,
        current_snapshot_fingerprint=status.snapshot_fingerprint,
        current_revision=status.revision,
        stages=(),
    )
    return path, _write_receipt(path, receipt)


def _action_sha(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _close_actions(
    fills: Sequence[RecurrentExitFillEvidenceV1],
) -> tuple[str, ...]:
    return tuple(sorted(fill.exit_fill_fingerprint for fill in fills))


def _reservation_actions(
    decisions: Sequence[
        tuple[SimulationDecisionRecord, LongOptionReservationTerms | None]
    ],
) -> tuple[str, ...]:
    return tuple(
        sorted(record.record_fingerprint for record, _terms in decisions)
    )


def _entry_actions(
    entries: Sequence[
        tuple[RecurrentEntryFillEvidenceV1, RecurrentFundingTermsV1]
    ],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            _action_sha(
                {
                    "fill_fingerprint": fill.fill_fingerprint,
                    "funding_terms_fingerprint": funding.terms_fingerprint,
                }
            )
            for fill, funding in entries
        )
    )


def _mark_actions(
    marks: Sequence[SimulatedMarketMarkEvidence],
) -> tuple[str, ...]:
    return tuple(sorted(mark.mark_fingerprint for mark in marks))


def _stage_already_applied(
    *,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    stage: RecurrentCycleStage,
    actions: tuple[str, ...],
    action_context: str | None,
) -> bool:
    snapshot = runtime.snapshot()
    if stage == RecurrentCycleStage.CLOSE:
        observed = {
            event.exit_fill_fingerprint
            for event in snapshot.account.ledger.events
            if event.kind == RecurrentLifecycleEventKind.CLOSE_POSITION
            and event.exit_fill_fingerprint is not None
        }
        return all(action in observed for action in actions)

    if stage == RecurrentCycleStage.RESERVE:
        observed = {
            event.decision_record_fingerprint
            for event in snapshot.account.ledger.events
            if event.kind
            in {
                RecurrentLifecycleEventKind.RESERVE_STOCK,
                RecurrentLifecycleEventKind.RESERVE_OPTION,
                RecurrentLifecycleEventKind.ABSTAIN,
                RecurrentLifecycleEventKind.REJECT_MISSING_OPTION_TERMS,
                RecurrentLifecycleEventKind.REJECT_INSUFFICIENT_CAPITAL,
            }
            and event.decision_record_fingerprint is not None
        }
        return all(action in observed for action in actions)

    if stage == RecurrentCycleStage.ENTRY:
        observed = {
            _action_sha(
                {
                    "fill_fingerprint": event.fill_fingerprint,
                    "funding_terms_fingerprint": event.funding_terms_fingerprint,
                }
            )
            for event in snapshot.account.ledger.events
            if event.kind == RecurrentLifecycleEventKind.OPEN_POSITION
            and event.fill_fingerprint is not None
            and event.funding_terms_fingerprint is not None
        }
        return all(action in observed for action in actions)

    if stage == RecurrentCycleStage.MARK:
        marked = snapshot.marked_state
        if marked is None or action_context is None:
            return False
        if marked.valuation_utc.isoformat() != action_context:
            return False
        observed = {
            item.mark_fingerprint
            for item in marked.marked_positions
        }
        return set(actions) == observed

    return False


def _record_stage(
    *,
    path: Path,
    receipt: RecurrentCycleReceiptV1,
    stage: RecurrentCycleStage,
    actions: tuple[str, ...],
    action_context: str | None,
    source_checkpoint_sha256: str,
    source_snapshot_fingerprint: str,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    now_utc: datetime | None,
) -> RecurrentCycleReceiptV1:
    status = runtime.status()
    if status.uncertain:
        raise RecurrentCycleOrchestrationError(
            "cannot record cycle stage while durable runtime is uncertain"
        )
    now = now_utc or datetime.now(UTC)
    _require_aware(now, label="cycle stage timestamp")
    record = RecurrentCycleStageRecordV1(
        stage=stage,
        action_fingerprints=actions,
        action_context=action_context,
        source_checkpoint_sha256=source_checkpoint_sha256,
        source_snapshot_fingerprint=source_snapshot_fingerprint,
        result_checkpoint_sha256=status.checkpoint_sha256,
        result_snapshot_fingerprint=status.snapshot_fingerprint,
        result_revision=status.revision,
        recorded_at_utc=now,
    )
    updated = _with_sha(
        cycle_id=receipt.cycle_id,
        status=RecurrentCycleStatus.OPEN,
        created_at_utc=receipt.created_at_utc,
        updated_at_utc=now,
        completed_at_utc=None,
        source_checkpoint_sha256=receipt.source_checkpoint_sha256,
        source_snapshot_fingerprint=receipt.source_snapshot_fingerprint,
        current_checkpoint_sha256=status.checkpoint_sha256,
        current_snapshot_fingerprint=status.snapshot_fingerprint,
        current_revision=status.revision,
        stages=receipt.stages + (record,),
    )
    return _write_receipt(path, updated)


def _prepare_stage(
    *,
    path: Path,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    stage: RecurrentCycleStage,
    actions: tuple[str, ...],
    action_context: str | None,
) -> tuple[RecurrentCycleReceiptV1, bool]:
    receipt = read_recurrent_cycle_receipt(path)
    if receipt.status != RecurrentCycleStatus.OPEN:
        raise RecurrentCycleOrchestrationError(
            "cannot mutate a completed recurrent cycle receipt"
        )
    index = _STAGE_ORDER.index(stage)
    if len(receipt.stages) > index:
        prior = receipt.stages[index]
        if (
            prior.stage == stage
            and prior.action_fingerprints == actions
            and prior.action_context == action_context
        ):
            return receipt, True
        raise RecurrentCycleOrchestrationError(
            "cycle stage was already recorded with different evidence"
        )
    if len(receipt.stages) != index:
        raise RecurrentCycleOrchestrationError(
            f"cycle stage {stage.value} is out of order"
        )

    status = runtime.status()
    if status.uncertain:
        raise RecurrentCycleOrchestrationError(
            "cannot run cycle while durable runtime is uncertain"
        )
    if status.checkpoint_sha256 != receipt.current_checkpoint_sha256:
        if _stage_already_applied(
            runtime=runtime,
            stage=stage,
            actions=actions,
            action_context=action_context,
        ):
            return receipt, False
        raise RecurrentCycleOrchestrationError(
            "runtime checkpoint advanced outside the current cycle stage"
        )
    return receipt, False


def apply_recurrent_cycle_close_stage(
    *,
    path: Path,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    fills: Sequence[RecurrentExitFillEvidenceV1],
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    actions = _close_actions(fills)
    receipt, recorded = _prepare_stage(
        path=path,
        runtime=runtime,
        stage=RecurrentCycleStage.CLOSE,
        actions=actions,
        action_context=None,
    )
    if recorded:
        return receipt
    source_checkpoint = receipt.current_checkpoint_sha256
    source_snapshot = receipt.current_snapshot_fingerprint
    status = runtime.status()
    if status.checkpoint_sha256 == source_checkpoint and fills:
        runtime.apply_close_batch(fills)
    return _record_stage(
        path=path,
        receipt=receipt,
        stage=RecurrentCycleStage.CLOSE,
        actions=actions,
        action_context=None,
        source_checkpoint_sha256=source_checkpoint,
        source_snapshot_fingerprint=source_snapshot,
        runtime=runtime,
        now_utc=now_utc,
    )


def apply_recurrent_cycle_reserve_stage(
    *,
    path: Path,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    decisions: Sequence[
        tuple[SimulationDecisionRecord, LongOptionReservationTerms | None]
    ],
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    actions = _reservation_actions(decisions)
    receipt, recorded = _prepare_stage(
        path=path,
        runtime=runtime,
        stage=RecurrentCycleStage.RESERVE,
        actions=actions,
        action_context=None,
    )
    if recorded:
        return receipt
    source_checkpoint = receipt.current_checkpoint_sha256
    source_snapshot = receipt.current_snapshot_fingerprint
    status = runtime.status()
    if status.checkpoint_sha256 == source_checkpoint and decisions:
        runtime.apply_reservation_batch(decisions)
    return _record_stage(
        path=path,
        receipt=receipt,
        stage=RecurrentCycleStage.RESERVE,
        actions=actions,
        action_context=None,
        source_checkpoint_sha256=source_checkpoint,
        source_snapshot_fingerprint=source_snapshot,
        runtime=runtime,
        now_utc=now_utc,
    )


def apply_recurrent_cycle_entry_stage(
    *,
    path: Path,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    entries: Sequence[
        tuple[RecurrentEntryFillEvidenceV1, RecurrentFundingTermsV1]
    ],
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    actions = _entry_actions(entries)
    receipt, recorded = _prepare_stage(
        path=path,
        runtime=runtime,
        stage=RecurrentCycleStage.ENTRY,
        actions=actions,
        action_context=None,
    )
    if recorded:
        return receipt
    source_checkpoint = receipt.current_checkpoint_sha256
    source_snapshot = receipt.current_snapshot_fingerprint
    status = runtime.status()
    if status.checkpoint_sha256 == source_checkpoint and entries:
        runtime.apply_entry_batch(entries)
    return _record_stage(
        path=path,
        receipt=receipt,
        stage=RecurrentCycleStage.ENTRY,
        actions=actions,
        action_context=None,
        source_checkpoint_sha256=source_checkpoint,
        source_snapshot_fingerprint=source_snapshot,
        runtime=runtime,
        now_utc=now_utc,
    )


def apply_recurrent_cycle_mark_stage(
    *,
    path: Path,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    marks: Sequence[SimulatedMarketMarkEvidence],
    valuation_utc: datetime,
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    _require_aware(valuation_utc, label="cycle mark valuation timestamp")
    actions = _mark_actions(marks)
    context = valuation_utc.isoformat()
    receipt, recorded = _prepare_stage(
        path=path,
        runtime=runtime,
        stage=RecurrentCycleStage.MARK,
        actions=actions,
        action_context=context,
    )
    if recorded:
        return receipt
    source_checkpoint = receipt.current_checkpoint_sha256
    source_snapshot = receipt.current_snapshot_fingerprint
    status = runtime.status()
    if status.checkpoint_sha256 == source_checkpoint:
        runtime.publish_marks(
            marks=marks,
            valuation_utc=valuation_utc,
        )
    return _record_stage(
        path=path,
        receipt=receipt,
        stage=RecurrentCycleStage.MARK,
        actions=actions,
        action_context=context,
        source_checkpoint_sha256=source_checkpoint,
        source_snapshot_fingerprint=source_snapshot,
        runtime=runtime,
        now_utc=now_utc,
    )


def complete_recurrent_cycle(
    *,
    path: Path,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    receipt = read_recurrent_cycle_receipt(path)
    if receipt.status == RecurrentCycleStatus.COMPLETE:
        return receipt
    if len(receipt.stages) != len(_STAGE_ORDER):
        raise RecurrentCycleOrchestrationError(
            "cannot complete cycle before all four stages are recorded"
        )
    status = runtime.status()
    if status.uncertain:
        raise RecurrentCycleOrchestrationError(
            "cannot complete cycle while runtime is uncertain"
        )
    if (
        status.checkpoint_sha256 != receipt.current_checkpoint_sha256
        or status.snapshot_fingerprint != receipt.current_snapshot_fingerprint
    ):
        raise RecurrentCycleOrchestrationError(
            "runtime state changed after the cycle mark stage"
        )
    now = now_utc or datetime.now(UTC)
    _require_aware(now, label="cycle completion timestamp")
    if now < receipt.updated_at_utc:
        raise RecurrentCycleOrchestrationError(
            "cycle completion cannot precede latest stage"
        )
    completed = _with_sha(
        cycle_id=receipt.cycle_id,
        status=RecurrentCycleStatus.COMPLETE,
        created_at_utc=receipt.created_at_utc,
        updated_at_utc=receipt.updated_at_utc,
        completed_at_utc=now,
        source_checkpoint_sha256=receipt.source_checkpoint_sha256,
        source_snapshot_fingerprint=receipt.source_snapshot_fingerprint,
        current_checkpoint_sha256=receipt.current_checkpoint_sha256,
        current_snapshot_fingerprint=receipt.current_snapshot_fingerprint,
        current_revision=receipt.current_revision,
        stages=receipt.stages,
    )
    return _write_receipt(path, completed)


__all__ = [
    "RECURRENT_CYCLE_RECEIPT_CONTRACT_FINGERPRINT",
    "RecurrentCycleOrchestrationError",
    "RecurrentCycleReceiptV1",
    "RecurrentCycleStage",
    "RecurrentCycleStageRecordV1",
    "RecurrentCycleStatus",
    "apply_recurrent_cycle_close_stage",
    "apply_recurrent_cycle_entry_stage",
    "apply_recurrent_cycle_mark_stage",
    "apply_recurrent_cycle_reserve_stage",
    "begin_recurrent_cycle",
    "complete_recurrent_cycle",
    "cycle_fingerprint",
    "read_recurrent_cycle_receipt",
    "recurrent_cycle_receipt_path",
    "recurrent_cycle_receipt_sha256",
]
