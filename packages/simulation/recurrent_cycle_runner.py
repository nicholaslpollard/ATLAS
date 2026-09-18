from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from packages.core.atomic_io import atomic_write_text
from packages.simulation.decision_record import SimulationDecisionRecord
from packages.simulation.market_mark_evidence import SimulatedMarketMarkEvidence
from packages.simulation.option_reservation import LongOptionReservationTerms
from packages.simulation.recurrent_cycle import (
    RecurrentCycleReceiptV1,
    RecurrentCycleStage,
    RecurrentCycleStatus,
    apply_recurrent_cycle_close_stage,
    apply_recurrent_cycle_entry_stage,
    apply_recurrent_cycle_mark_stage,
    apply_recurrent_cycle_reserve_stage,
    begin_recurrent_cycle,
    complete_recurrent_cycle,
    cycle_fingerprint,
    read_recurrent_cycle_receipt,
    recurrent_cycle_receipt_path,
)
from packages.simulation.recurrent_cycle_runner_contract import (
    RECURRENT_CYCLE_RUNNER_CONTRACT,
    RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_entry_evidence import (
    RecurrentEntryFillEvidenceV1,
    RecurrentFundingTermsV1,
)
from packages.simulation.recurrent_exit_fill import RecurrentExitFillEvidenceV1
from packages.simulation.recurrent_runtime import (
    DurableRecurrentLifecycleRuntimeV1,
    restore_durable_recurrent_lifecycle_runtime,
)


RECURRENT_CYCLE_RUNNER_CONTRACT_VERSION = str(
    RECURRENT_CYCLE_RUNNER_CONTRACT["contract_id"]
)
_MAX_ADMISSION_BYTES = 4 * 1024 * 1024
_SCHEDULE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_STAGE_ORDER = (
    RecurrentCycleStage.CLOSE,
    RecurrentCycleStage.RESERVE,
    RecurrentCycleStage.ENTRY,
    RecurrentCycleStage.MARK,
)


class RecurrentCycleRunnerError(RuntimeError):
    pass


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentCycleRunnerError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentCycleRunnerError(f"{label} must be timezone-aware")


def _hash_payload(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class RecurrentCycleRunIdentityV1:
    contract_version: str
    contract_fingerprint: str
    schedule_id: str
    scheduled_for_utc: datetime
    cycle_id: str
    cycle_fingerprint: str

    def __post_init__(self) -> None:
        if self.contract_version != RECURRENT_CYCLE_RUNNER_CONTRACT_VERSION:
            raise RecurrentCycleRunnerError(
                "recurrent cycle runner contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT
        ):
            raise RecurrentCycleRunnerError(
                "recurrent cycle runner contract fingerprint mismatch"
            )
        if not _SCHEDULE_ID_RE.fullmatch(self.schedule_id):
            raise RecurrentCycleRunnerError(
                "schedule id must be 1..64 safe identifier characters"
            )
        _require_aware(
            self.scheduled_for_utc,
            label="scheduled cycle timestamp",
        )
        if self.scheduled_for_utc.utcoffset().total_seconds() != 0:
            raise RecurrentCycleRunnerError(
                "stored scheduled cycle timestamp must be normalized to UTC"
            )
        expected_id = deterministic_recurrent_cycle_id(
            schedule_id=self.schedule_id,
            scheduled_for_utc=self.scheduled_for_utc,
        )
        if self.cycle_id != expected_id:
            raise RecurrentCycleRunnerError("deterministic cycle id mismatch")
        if self.cycle_fingerprint != cycle_fingerprint(self.cycle_id):
            raise RecurrentCycleRunnerError(
                "deterministic cycle fingerprint mismatch"
            )


def deterministic_recurrent_cycle_id(
    *,
    schedule_id: str,
    scheduled_for_utc: datetime,
) -> str:
    if not _SCHEDULE_ID_RE.fullmatch(schedule_id):
        raise RecurrentCycleRunnerError(
            "schedule id must be 1..64 safe identifier characters"
        )
    _require_aware(
        scheduled_for_utc,
        label="scheduled cycle timestamp",
    )
    slot = scheduled_for_utc.astimezone(UTC)
    return f"{schedule_id}@{slot.isoformat().replace('+00:00', 'Z')}"


def build_recurrent_cycle_run_identity_v1(
    *,
    schedule_id: str,
    scheduled_for_utc: datetime,
) -> RecurrentCycleRunIdentityV1:
    slot = scheduled_for_utc.astimezone(UTC) if (
        scheduled_for_utc.tzinfo is not None
        and scheduled_for_utc.utcoffset() is not None
    ) else scheduled_for_utc
    _require_aware(slot, label="scheduled cycle timestamp")
    cycle_id = deterministic_recurrent_cycle_id(
        schedule_id=schedule_id,
        scheduled_for_utc=slot,
    )
    return RecurrentCycleRunIdentityV1(
        contract_version=RECURRENT_CYCLE_RUNNER_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT,
        schedule_id=schedule_id,
        scheduled_for_utc=slot,
        cycle_id=cycle_id,
        cycle_fingerprint=cycle_fingerprint(cycle_id),
    )


@dataclass(frozen=True)
class RecurrentCycleStageAdmissionV1:
    contract_version: str
    contract_fingerprint: str
    admission_sha256: str
    cycle_id: str
    cycle_fingerprint: str
    stage: RecurrentCycleStage
    source_checkpoint_sha256: str
    source_snapshot_fingerprint: str
    evidence_source_id: str
    evidence_source_fingerprint: str
    evidence_fingerprint: str
    evidence_count: int
    action_context: str | None
    created_at_utc: datetime
    scheduler_trigger_authority: bool = False
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
        if self.contract_version != RECURRENT_CYCLE_RUNNER_CONTRACT_VERSION:
            raise RecurrentCycleRunnerError(
                "stage admission contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT
        ):
            raise RecurrentCycleRunnerError(
                "stage admission contract fingerprint mismatch"
            )
        for label, value in (
            ("admission", self.admission_sha256),
            ("cycle", self.cycle_fingerprint),
            ("source checkpoint", self.source_checkpoint_sha256),
            ("source snapshot", self.source_snapshot_fingerprint),
            ("evidence source", self.evidence_source_fingerprint),
            ("evidence", self.evidence_fingerprint),
        ):
            _require_sha(value, label=label)
        if self.cycle_fingerprint != cycle_fingerprint(self.cycle_id):
            raise RecurrentCycleRunnerError(
                "stage admission cycle fingerprint mismatch"
            )
        if not self.evidence_source_id.strip():
            raise RecurrentCycleRunnerError(
                "stage admission evidence source id cannot be blank"
            )
        if len(self.evidence_source_id) > 256:
            raise RecurrentCycleRunnerError(
                "stage admission evidence source id is too long"
            )
        if self.evidence_count < 0:
            raise RecurrentCycleRunnerError(
                "stage admission evidence count cannot be negative"
            )
        _require_aware(
            self.created_at_utc,
            label="stage admission timestamp",
        )
        forbidden = (
            self.scheduler_trigger_authority,
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
            raise RecurrentCycleRunnerError(
                "stage admission cannot grant scheduler, external, or trading authority"
            )


def recurrent_cycle_stage_admission_path(
    checkpoint_path: Path,
    cycle_id: str,
    stage: RecurrentCycleStage,
) -> Path:
    return (
        Path(checkpoint_path).parent
        / "cycle_admissions"
        / cycle_fingerprint(cycle_id)
        / f"{stage.value.lower()}.json"
    )


def _admission_payload(
    admission: RecurrentCycleStageAdmissionV1,
    *,
    include_sha: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_version": admission.contract_version,
        "contract_fingerprint": admission.contract_fingerprint,
        "cycle_id": admission.cycle_id,
        "cycle_fingerprint": admission.cycle_fingerprint,
        "stage": admission.stage.value,
        "source_checkpoint_sha256": admission.source_checkpoint_sha256,
        "source_snapshot_fingerprint": admission.source_snapshot_fingerprint,
        "evidence_source_id": admission.evidence_source_id,
        "evidence_source_fingerprint": admission.evidence_source_fingerprint,
        "evidence_fingerprint": admission.evidence_fingerprint,
        "evidence_count": admission.evidence_count,
        "action_context": admission.action_context,
        "created_at_utc": admission.created_at_utc.isoformat(),
        "scheduler_trigger_authority": False,
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
        payload["admission_sha256"] = admission.admission_sha256
    return payload


def recurrent_cycle_stage_admission_sha256(
    admission: RecurrentCycleStageAdmissionV1,
) -> str:
    return _hash_payload(_admission_payload(admission, include_sha=False))


def _with_admission_sha(
    *,
    cycle_id: str,
    stage: RecurrentCycleStage,
    source_checkpoint_sha256: str,
    source_snapshot_fingerprint: str,
    evidence_source_id: str,
    evidence_source_fingerprint: str,
    evidence_fingerprint: str,
    evidence_count: int,
    action_context: str | None,
    created_at_utc: datetime,
) -> RecurrentCycleStageAdmissionV1:
    placeholder = RecurrentCycleStageAdmissionV1(
        contract_version=RECURRENT_CYCLE_RUNNER_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT,
        admission_sha256="0" * 64,
        cycle_id=cycle_id,
        cycle_fingerprint=cycle_fingerprint(cycle_id),
        stage=stage,
        source_checkpoint_sha256=source_checkpoint_sha256,
        source_snapshot_fingerprint=source_snapshot_fingerprint,
        evidence_source_id=evidence_source_id,
        evidence_source_fingerprint=evidence_source_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        evidence_count=evidence_count,
        action_context=action_context,
        created_at_utc=created_at_utc,
    )
    return RecurrentCycleStageAdmissionV1(
        **{
            **placeholder.__dict__,
            "admission_sha256": recurrent_cycle_stage_admission_sha256(
                placeholder
            ),
        }
    )


def read_recurrent_cycle_stage_admission(
    path: Path,
) -> RecurrentCycleStageAdmissionV1:
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise RecurrentCycleRunnerError(
            f"could not stat stage admission: {path}"
        ) from exc
    if size <= 0 or size > _MAX_ADMISSION_BYTES:
        raise RecurrentCycleRunnerError("stage admission size is invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecurrentCycleRunnerError(
            f"could not read stage admission: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RecurrentCycleRunnerError(
            "stage admission must be a JSON object"
        )
    try:
        created = datetime.fromisoformat(str(value["created_at_utc"]))
        admission = RecurrentCycleStageAdmissionV1(
            contract_version=str(value["contract_version"]),
            contract_fingerprint=str(value["contract_fingerprint"]),
            admission_sha256=str(value["admission_sha256"]),
            cycle_id=str(value["cycle_id"]),
            cycle_fingerprint=str(value["cycle_fingerprint"]),
            stage=RecurrentCycleStage(str(value["stage"])),
            source_checkpoint_sha256=str(
                value["source_checkpoint_sha256"]
            ),
            source_snapshot_fingerprint=str(
                value["source_snapshot_fingerprint"]
            ),
            evidence_source_id=str(value["evidence_source_id"]),
            evidence_source_fingerprint=str(
                value["evidence_source_fingerprint"]
            ),
            evidence_fingerprint=str(value["evidence_fingerprint"]),
            evidence_count=int(value["evidence_count"]),
            action_context=(
                None
                if value.get("action_context") is None
                else str(value["action_context"])
            ),
            created_at_utc=created,
            scheduler_trigger_authority=bool(
                value["scheduler_trigger_authority"]
            ),
            provider_read_authority=bool(value["provider_read_authority"]),
            provider_write_authority=bool(value["provider_write_authority"]),
            broker_read_authority=bool(value["broker_read_authority"]),
            broker_write_authority=bool(value["broker_write_authority"]),
            order_creation_authority=bool(value["order_creation_authority"]),
            paper_authority=bool(value["paper_authority"]),
            live_authority=bool(value["live_authority"]),
            promotion_authority=bool(value["promotion_authority"]),
            confluence_authority=bool(value["confluence_authority"]),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        RecurrentCycleRunnerError,
    ) as exc:
        if isinstance(exc, RecurrentCycleRunnerError):
            raise
        raise RecurrentCycleRunnerError(
            "stage admission schema is invalid"
        ) from exc
    if (
        admission.admission_sha256
        != recurrent_cycle_stage_admission_sha256(admission)
    ):
        raise RecurrentCycleRunnerError(
            "stage admission self-hash mismatch"
        )
    return admission


def _write_admission(
    path: Path,
    admission: RecurrentCycleStageAdmissionV1,
) -> RecurrentCycleStageAdmissionV1:
    atomic_write_text(
        Path(path),
        json.dumps(
            _admission_payload(admission, include_sha=True),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        fsync=True,
    )
    verified = read_recurrent_cycle_stage_admission(path)
    if verified != admission:
        raise RecurrentCycleRunnerError(
            "stage admission readback verification mismatch"
        )
    return verified


def _expected_stage_source(
    receipt: RecurrentCycleReceiptV1,
    stage: RecurrentCycleStage,
) -> tuple[str, str]:
    index = _STAGE_ORDER.index(stage)
    if len(receipt.stages) > index:
        record = receipt.stages[index]
        if record.stage != stage:
            raise RecurrentCycleRunnerError(
                "cycle receipt stage order is invalid"
            )
        return (
            record.source_checkpoint_sha256,
            record.source_snapshot_fingerprint,
        )
    if len(receipt.stages) == index:
        return (
            receipt.current_checkpoint_sha256,
            receipt.current_snapshot_fingerprint,
        )
    raise RecurrentCycleRunnerError(
        f"cannot admit {stage.value} before prior stages"
    )


def admit_recurrent_cycle_stage_v1(
    *,
    checkpoint_path: Path,
    receipt: RecurrentCycleReceiptV1,
    stage: RecurrentCycleStage,
    evidence_source_id: str,
    evidence_source_fingerprint: str,
    evidence_fingerprint: str,
    evidence_count: int,
    action_context: str | None,
    now_utc: datetime | None = None,
) -> tuple[Path, RecurrentCycleStageAdmissionV1]:
    _require_sha(
        evidence_source_fingerprint,
        label="evidence source",
    )
    _require_sha(evidence_fingerprint, label="evidence")
    source_checkpoint, source_snapshot = _expected_stage_source(
        receipt,
        stage,
    )
    path = recurrent_cycle_stage_admission_path(
        checkpoint_path,
        receipt.cycle_id,
        stage,
    )
    if path.exists():
        existing = read_recurrent_cycle_stage_admission(path)
        expected = (
            receipt.cycle_id,
            receipt.cycle_fingerprint,
            stage,
            source_checkpoint,
            source_snapshot,
            evidence_source_id,
            evidence_source_fingerprint,
            evidence_fingerprint,
            evidence_count,
            action_context,
        )
        observed = (
            existing.cycle_id,
            existing.cycle_fingerprint,
            existing.stage,
            existing.source_checkpoint_sha256,
            existing.source_snapshot_fingerprint,
            existing.evidence_source_id,
            existing.evidence_source_fingerprint,
            existing.evidence_fingerprint,
            existing.evidence_count,
            existing.action_context,
        )
        if observed != expected:
            raise RecurrentCycleRunnerError(
                "stage admission already exists with conflicting evidence"
            )
        return path, existing

    now = now_utc or datetime.now(UTC)
    _require_aware(now, label="stage admission timestamp")
    admission = _with_admission_sha(
        cycle_id=receipt.cycle_id,
        stage=stage,
        source_checkpoint_sha256=source_checkpoint,
        source_snapshot_fingerprint=source_snapshot,
        evidence_source_id=evidence_source_id,
        evidence_source_fingerprint=evidence_source_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        evidence_count=evidence_count,
        action_context=action_context,
        created_at_utc=now,
    )
    return path, _write_admission(path, admission)


def _close_evidence(
    fills: Sequence[RecurrentExitFillEvidenceV1],
) -> tuple[str, int]:
    values = sorted(fill.exit_fill_fingerprint for fill in fills)
    return (
        _hash_payload({"stage": "CLOSE", "fills": values}),
        len(values),
    )


def _reserve_evidence(
    decisions: Sequence[
        tuple[SimulationDecisionRecord, LongOptionReservationTerms | None]
    ],
) -> tuple[str, int]:
    values = sorted(
        (
            record.record_fingerprint,
            None if terms is None else terms.terms_fingerprint,
        )
        for record, terms in decisions
    )
    return (
        _hash_payload(
            {
                "stage": "RESERVE",
                "decisions": [
                    {
                        "decision_record_fingerprint": decision,
                        "reservation_terms_fingerprint": terms,
                    }
                    for decision, terms in values
                ],
            }
        ),
        len(values),
    )


def _entry_evidence(
    entries: Sequence[
        tuple[RecurrentEntryFillEvidenceV1, RecurrentFundingTermsV1]
    ],
) -> tuple[str, int]:
    values = sorted(
        (fill.fill_fingerprint, funding.terms_fingerprint)
        for fill, funding in entries
    )
    return (
        _hash_payload(
            {
                "stage": "ENTRY",
                "entries": [
                    {
                        "fill_fingerprint": fill,
                        "funding_terms_fingerprint": funding,
                    }
                    for fill, funding in values
                ],
            }
        ),
        len(values),
    )


def _mark_evidence(
    marks: Sequence[SimulatedMarketMarkEvidence],
    *,
    valuation_utc: datetime,
) -> tuple[str, int, str]:
    _require_aware(valuation_utc, label="mark valuation timestamp")
    context = valuation_utc.astimezone(UTC).isoformat()
    values = sorted(mark.mark_fingerprint for mark in marks)
    return (
        _hash_payload(
            {
                "stage": "MARK",
                "marks": values,
                "valuation_utc": context,
            }
        ),
        len(values),
        context,
    )


def _verify_stage_result(
    *,
    receipt: RecurrentCycleReceiptV1,
    admission: RecurrentCycleStageAdmissionV1,
) -> None:
    index = _STAGE_ORDER.index(admission.stage)
    if len(receipt.stages) <= index:
        raise RecurrentCycleRunnerError(
            "cycle stage did not produce a durable stage record"
        )
    record = receipt.stages[index]
    if (
        record.stage != admission.stage
        or record.source_checkpoint_sha256
        != admission.source_checkpoint_sha256
        or record.source_snapshot_fingerprint
        != admission.source_snapshot_fingerprint
        or record.action_context != admission.action_context
        or len(record.action_fingerprints) != admission.evidence_count
    ):
        raise RecurrentCycleRunnerError(
            "cycle stage result does not match admitted evidence boundary"
        )


@dataclass
class RecurrentCycleRunnerV1:
    checkpoint_path: Path
    runtime: DurableRecurrentLifecycleRuntimeV1

    @classmethod
    def restore(
        cls,
        checkpoint_path: Path,
    ) -> "RecurrentCycleRunnerV1":
        path = Path(checkpoint_path)
        return cls(
            checkpoint_path=path,
            runtime=restore_durable_recurrent_lifecycle_runtime(path),
        )

    def begin(
        self,
        *,
        identity: RecurrentCycleRunIdentityV1,
        now_utc: datetime | None = None,
    ) -> tuple[Path, RecurrentCycleReceiptV1]:
        return begin_recurrent_cycle(
            checkpoint_path=self.checkpoint_path,
            runtime=self.runtime,
            cycle_id=identity.cycle_id,
            now_utc=now_utc,
        )

    def _receipt(
        self,
        identity: RecurrentCycleRunIdentityV1,
    ) -> tuple[Path, RecurrentCycleReceiptV1]:
        path = recurrent_cycle_receipt_path(
            self.checkpoint_path,
            identity.cycle_id,
        )
        if not path.is_file():
            raise RecurrentCycleRunnerError(
                "cycle receipt does not exist; begin the cycle first"
            )
        receipt = read_recurrent_cycle_receipt(path)
        if (
            receipt.cycle_id != identity.cycle_id
            or receipt.cycle_fingerprint != identity.cycle_fingerprint
        ):
            raise RecurrentCycleRunnerError(
                "cycle receipt does not match run identity"
            )
        return path, receipt

    def apply_close(
        self,
        *,
        identity: RecurrentCycleRunIdentityV1,
        evidence_source_id: str,
        evidence_source_fingerprint: str,
        fills: Sequence[RecurrentExitFillEvidenceV1],
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        path, receipt = self._receipt(identity)
        evidence_fp, count = _close_evidence(fills)
        _admission_path, admission = admit_recurrent_cycle_stage_v1(
            checkpoint_path=self.checkpoint_path,
            receipt=receipt,
            stage=RecurrentCycleStage.CLOSE,
            evidence_source_id=evidence_source_id,
            evidence_source_fingerprint=evidence_source_fingerprint,
            evidence_fingerprint=evidence_fp,
            evidence_count=count,
            action_context=None,
            now_utc=now_utc,
        )
        result = apply_recurrent_cycle_close_stage(
            path=path,
            runtime=self.runtime,
            fills=fills,
            now_utc=now_utc,
        )
        _verify_stage_result(receipt=result, admission=admission)
        return result

    def apply_reserve(
        self,
        *,
        identity: RecurrentCycleRunIdentityV1,
        evidence_source_id: str,
        evidence_source_fingerprint: str,
        decisions: Sequence[
            tuple[
                SimulationDecisionRecord,
                LongOptionReservationTerms | None,
            ]
        ],
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        path, receipt = self._receipt(identity)
        evidence_fp, count = _reserve_evidence(decisions)
        _admission_path, admission = admit_recurrent_cycle_stage_v1(
            checkpoint_path=self.checkpoint_path,
            receipt=receipt,
            stage=RecurrentCycleStage.RESERVE,
            evidence_source_id=evidence_source_id,
            evidence_source_fingerprint=evidence_source_fingerprint,
            evidence_fingerprint=evidence_fp,
            evidence_count=count,
            action_context=None,
            now_utc=now_utc,
        )
        result = apply_recurrent_cycle_reserve_stage(
            path=path,
            runtime=self.runtime,
            decisions=decisions,
            now_utc=now_utc,
        )
        _verify_stage_result(receipt=result, admission=admission)
        return result

    def apply_entry(
        self,
        *,
        identity: RecurrentCycleRunIdentityV1,
        evidence_source_id: str,
        evidence_source_fingerprint: str,
        entries: Sequence[
            tuple[
                RecurrentEntryFillEvidenceV1,
                RecurrentFundingTermsV1,
            ]
        ],
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        path, receipt = self._receipt(identity)
        evidence_fp, count = _entry_evidence(entries)
        _admission_path, admission = admit_recurrent_cycle_stage_v1(
            checkpoint_path=self.checkpoint_path,
            receipt=receipt,
            stage=RecurrentCycleStage.ENTRY,
            evidence_source_id=evidence_source_id,
            evidence_source_fingerprint=evidence_source_fingerprint,
            evidence_fingerprint=evidence_fp,
            evidence_count=count,
            action_context=None,
            now_utc=now_utc,
        )
        result = apply_recurrent_cycle_entry_stage(
            path=path,
            runtime=self.runtime,
            entries=entries,
            now_utc=now_utc,
        )
        _verify_stage_result(receipt=result, admission=admission)
        return result

    def apply_mark(
        self,
        *,
        identity: RecurrentCycleRunIdentityV1,
        evidence_source_id: str,
        evidence_source_fingerprint: str,
        marks: Sequence[SimulatedMarketMarkEvidence],
        valuation_utc: datetime,
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        path, receipt = self._receipt(identity)
        _require_aware(valuation_utc, label="mark valuation timestamp")
        normalized_valuation = valuation_utc.astimezone(UTC)
        evidence_fp, count, context = _mark_evidence(
            marks,
            valuation_utc=normalized_valuation,
        )
        _admission_path, admission = admit_recurrent_cycle_stage_v1(
            checkpoint_path=self.checkpoint_path,
            receipt=receipt,
            stage=RecurrentCycleStage.MARK,
            evidence_source_id=evidence_source_id,
            evidence_source_fingerprint=evidence_source_fingerprint,
            evidence_fingerprint=evidence_fp,
            evidence_count=count,
            action_context=context,
            now_utc=now_utc,
        )
        result = apply_recurrent_cycle_mark_stage(
            path=path,
            runtime=self.runtime,
            marks=marks,
            valuation_utc=normalized_valuation,
            now_utc=now_utc,
        )
        _verify_stage_result(receipt=result, admission=admission)
        return result

    def complete(
        self,
        *,
        identity: RecurrentCycleRunIdentityV1,
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        path, receipt = self._receipt(identity)
        if receipt.status == RecurrentCycleStatus.COMPLETE:
            return receipt
        return complete_recurrent_cycle(
            path=path,
            runtime=self.runtime,
            now_utc=now_utc,
        )


__all__ = [
    "RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT",
    "RecurrentCycleRunIdentityV1",
    "RecurrentCycleRunnerError",
    "RecurrentCycleRunnerV1",
    "RecurrentCycleStageAdmissionV1",
    "admit_recurrent_cycle_stage_v1",
    "build_recurrent_cycle_run_identity_v1",
    "deterministic_recurrent_cycle_id",
    "read_recurrent_cycle_stage_admission",
    "recurrent_cycle_stage_admission_path",
    "recurrent_cycle_stage_admission_sha256",
]
