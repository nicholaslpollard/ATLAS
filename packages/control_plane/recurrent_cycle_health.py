from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from packages.control_plane.recurrent_cycle_health_contract import (
    RECURRENT_CYCLE_HEALTH_CONTRACT,
    RECURRENT_CYCLE_HEALTH_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_cycle import (
    RecurrentCycleReceiptV1,
    RecurrentCycleStage,
    RecurrentCycleStatus,
    read_recurrent_cycle_receipt,
)
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleStageAdmissionV1,
    read_recurrent_cycle_stage_admission,
)
from packages.simulation.recurrent_persistence import (
    RecurrentLifecycleCheckpointV1,
    read_recurrent_lifecycle_checkpoint,
)


RECURRENT_CYCLE_HEALTH_CONTRACT_VERSION = str(
    RECURRENT_CYCLE_HEALTH_CONTRACT["contract_id"]
)
_MAX_CYCLE_RECEIPTS = 4096
_MAX_STAGE_ADMISSIONS = _MAX_CYCLE_RECEIPTS * 4
_STAGE_ORDER = (
    RecurrentCycleStage.CLOSE,
    RecurrentCycleStage.RESERVE,
    RecurrentCycleStage.ENTRY,
    RecurrentCycleStage.MARK,
)


class RecurrentCycleHealthError(RuntimeError):
    pass


def _authority() -> dict[str, object]:
    return {
        "read_only": True,
        "provider_reads": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "order_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
    }


def _expected_stage_source(
    receipt: RecurrentCycleReceiptV1,
    stage: RecurrentCycleStage,
) -> tuple[str, str]:
    index = _STAGE_ORDER.index(stage)
    if index < len(receipt.stages):
        record = receipt.stages[index]
        if record.stage != stage:
            raise RecurrentCycleHealthError(
                "cycle receipt stage order is invalid"
            )
        return (
            record.source_checkpoint_sha256,
            record.source_snapshot_fingerprint,
        )
    if index == len(receipt.stages):
        return (
            receipt.current_checkpoint_sha256,
            receipt.current_snapshot_fingerprint,
        )
    raise RecurrentCycleHealthError(
        "stage admission exists ahead of the next cycle stage"
    )


def _validate_recorded_admission(
    *,
    receipt: RecurrentCycleReceiptV1,
    admission: RecurrentCycleStageAdmissionV1,
) -> None:
    index = _STAGE_ORDER.index(admission.stage)
    if index >= len(receipt.stages):
        return
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
        raise RecurrentCycleHealthError(
            "recorded cycle stage does not match its admission lineage"
        )


@dataclass(frozen=True)
class _ValidatedArtifacts:
    checkpoint: RecurrentLifecycleCheckpointV1 | None
    receipts: tuple[RecurrentCycleReceiptV1, ...]
    admissions: dict[
        tuple[str, RecurrentCycleStage],
        RecurrentCycleStageAdmissionV1,
    ]


class RecurrentCycleHealthService:
    def __init__(
        self,
        checkpoint_path: Path,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    @property
    def cycles_dir(self) -> Path:
        return self.checkpoint_path.parent / "cycles"

    @property
    def admissions_dir(self) -> Path:
        return self.checkpoint_path.parent / "cycle_admissions"

    def _cycle_files(self) -> tuple[Path, ...]:
        if not self.cycles_dir.exists():
            return ()
        files = tuple(sorted(self.cycles_dir.glob("*.json")))
        if len(files) > _MAX_CYCLE_RECEIPTS:
            raise RecurrentCycleHealthError(
                "cycle receipt count exceeds health scan cap"
            )
        return files

    def _admission_files(self) -> tuple[Path, ...]:
        if not self.admissions_dir.exists():
            return ()
        files = tuple(sorted(self.admissions_dir.glob("*/*.json")))
        if len(files) > _MAX_STAGE_ADMISSIONS:
            raise RecurrentCycleHealthError(
                "cycle admission count exceeds health scan cap"
            )
        return files

    def _validate_artifacts(self) -> _ValidatedArtifacts:
        cycle_files = self._cycle_files()
        admission_files = self._admission_files()
        checkpoint_exists = self.checkpoint_path.is_file()

        if not checkpoint_exists:
            if cycle_files or admission_files:
                raise RecurrentCycleHealthError(
                    "cycle artifacts exist without authoritative checkpoint"
                )
            return _ValidatedArtifacts(
                checkpoint=None,
                receipts=(),
                admissions={},
            )

        checkpoint = read_recurrent_lifecycle_checkpoint(
            self.checkpoint_path
        )

        receipts: list[RecurrentCycleReceiptV1] = []
        by_fingerprint: dict[str, RecurrentCycleReceiptV1] = {}
        cycle_ids: set[str] = set()
        for path in cycle_files:
            receipt = read_recurrent_cycle_receipt(path)
            if path.name != f"{receipt.cycle_fingerprint}.json":
                raise RecurrentCycleHealthError(
                    "cycle receipt filename/fingerprint mismatch"
                )
            if (
                receipt.cycle_fingerprint in by_fingerprint
                or receipt.cycle_id in cycle_ids
            ):
                raise RecurrentCycleHealthError(
                    "duplicate durable cycle identity detected"
                )
            by_fingerprint[receipt.cycle_fingerprint] = receipt
            cycle_ids.add(receipt.cycle_id)
            receipts.append(receipt)

        receipts.sort(
            key=lambda item: (
                item.created_at_utc,
                item.cycle_id,
            )
        )

        admissions: dict[
            tuple[str, RecurrentCycleStage],
            RecurrentCycleStageAdmissionV1,
        ] = {}
        for path in admission_files:
            admission = read_recurrent_cycle_stage_admission(path)
            receipt = by_fingerprint.get(admission.cycle_fingerprint)
            if receipt is None:
                raise RecurrentCycleHealthError(
                    "orphan cycle stage admission detected"
                )
            if (
                path.parent.name != admission.cycle_fingerprint
                or path.name != f"{admission.stage.value.lower()}.json"
            ):
                raise RecurrentCycleHealthError(
                    "cycle admission path/fingerprint mismatch"
                )
            if admission.cycle_id != receipt.cycle_id:
                raise RecurrentCycleHealthError(
                    "cycle admission identity mismatch"
                )
            key = (admission.cycle_fingerprint, admission.stage)
            if key in admissions:
                raise RecurrentCycleHealthError(
                    "duplicate cycle stage admission detected"
                )
            expected_checkpoint, expected_snapshot = (
                _expected_stage_source(receipt, admission.stage)
            )
            if (
                admission.source_checkpoint_sha256
                != expected_checkpoint
                or admission.source_snapshot_fingerprint
                != expected_snapshot
            ):
                raise RecurrentCycleHealthError(
                    "cycle admission source lineage mismatch"
                )
            index = _STAGE_ORDER.index(admission.stage)
            if index == len(receipt.stages):
                if receipt.status != RecurrentCycleStatus.OPEN:
                    raise RecurrentCycleHealthError(
                        "completed cycle cannot have pending admission"
                    )
            elif index > len(receipt.stages):
                raise RecurrentCycleHealthError(
                    "future cycle stage admission detected"
                )
            _validate_recorded_admission(
                receipt=receipt,
                admission=admission,
            )
            admissions[key] = admission

        return _ValidatedArtifacts(
            checkpoint=checkpoint,
            receipts=tuple(receipts),
            admissions=admissions,
        )

    def _latest_cycle_payload(
        self,
        *,
        receipt: RecurrentCycleReceiptV1,
        admissions: dict[
            tuple[str, RecurrentCycleStage],
            RecurrentCycleStageAdmissionV1,
        ],
    ) -> tuple[dict[str, object], int, bool]:
        rows: list[dict[str, object]] = []
        missing_recorded_admissions = 0
        pending_admission = False

        for index, stage in enumerate(_STAGE_ORDER):
            recorded = index < len(receipt.stages)
            admission = admissions.get(
                (receipt.cycle_fingerprint, stage)
            )
            if recorded and admission is None:
                missing_recorded_admissions += 1
                state = "RECORDED_UNADMITTED_LEGACY"
            elif recorded:
                state = "RECORDED_ADMITTED"
            elif admission is not None:
                if index != len(receipt.stages):
                    raise RecurrentCycleHealthError(
                        "pending admission is not the next cycle stage"
                    )
                pending_admission = True
                state = "ADMITTED_PENDING"
            else:
                state = "PENDING"

            record = receipt.stages[index] if recorded else None
            rows.append(
                {
                    "stage": stage.value,
                    "state": state,
                    "action_count": (
                        None
                        if record is None
                        else len(record.action_fingerprints)
                    ),
                    "source_checkpoint_sha256": (
                        admission.source_checkpoint_sha256
                        if admission is not None
                        else (
                            None
                            if record is None
                            else record.source_checkpoint_sha256
                        )
                    ),
                    "result_checkpoint_sha256": (
                        None
                        if record is None
                        else record.result_checkpoint_sha256
                    ),
                    "admission_sha256": (
                        None
                        if admission is None
                        else admission.admission_sha256
                    ),
                    "evidence_source_id": (
                        None
                        if admission is None
                        else admission.evidence_source_id
                    ),
                    "evidence_source_fingerprint": (
                        None
                        if admission is None
                        else admission.evidence_source_fingerprint
                    ),
                    "evidence_fingerprint": (
                        None
                        if admission is None
                        else admission.evidence_fingerprint
                    ),
                    "evidence_count": (
                        None
                        if admission is None
                        else admission.evidence_count
                    ),
                    "action_context": (
                        None
                        if record is None
                        else record.action_context
                    ),
                }
            )

        next_stage = (
            None
            if len(receipt.stages) == len(_STAGE_ORDER)
            else _STAGE_ORDER[len(receipt.stages)].value
        )
        payload = {
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
            "source_checkpoint_sha256": (
                receipt.source_checkpoint_sha256
            ),
            "current_checkpoint_sha256": (
                receipt.current_checkpoint_sha256
            ),
            "source_snapshot_fingerprint": (
                receipt.source_snapshot_fingerprint
            ),
            "current_snapshot_fingerprint": (
                receipt.current_snapshot_fingerprint
            ),
            "current_revision": receipt.current_revision,
            "recorded_stage_count": len(receipt.stages),
            "next_stage": next_stage,
            "stages": rows,
        }
        return payload, missing_recorded_admissions, pending_admission

    def _snapshot_validated(self) -> dict[str, object]:
        artifacts = self._validate_artifacts()
        checkpoint = artifacts.checkpoint
        if checkpoint is None:
            return {
                "contract_version": (
                    RECURRENT_CYCLE_HEALTH_CONTRACT_VERSION
                ),
                "contract_fingerprint": (
                    RECURRENT_CYCLE_HEALTH_CONTRACT_FINGERPRINT
                ),
                "status": "NOT_CONNECTED",
                "generated_at_utc": self.now_provider().isoformat(),
                "cycle_count": 0,
                "legacy_unadmitted_stage_count": 0,
                "current_checkpoint": None,
                "latest_cycle": None,
                "reason_codes": (
                    "RECURRENT_CHECKPOINT_NOT_CONNECTED",
                ),
                "authority": _authority(),
            }

        current = {
            "checkpoint_sha256": checkpoint.checkpoint_sha256,
            "snapshot_fingerprint": checkpoint.snapshot_fingerprint,
            "revision": checkpoint.snapshot.revision,
            "persisted_at_utc": checkpoint.persisted_at_utc.isoformat(),
            "history_count": len(checkpoint.checkpoint_history),
        }

        if not artifacts.receipts:
            return {
                "contract_version": (
                    RECURRENT_CYCLE_HEALTH_CONTRACT_VERSION
                ),
                "contract_fingerprint": (
                    RECURRENT_CYCLE_HEALTH_CONTRACT_FINGERPRINT
                ),
                "status": "READY_NO_CYCLE",
                "generated_at_utc": self.now_provider().isoformat(),
                "cycle_count": 0,
                "legacy_unadmitted_stage_count": 0,
                "current_checkpoint": current,
                "latest_cycle": None,
                "reason_codes": (
                    "RECURRENT_CHECKPOINT_VALID",
                    "NO_DURABLE_CYCLE_RECEIPT",
                ),
                "authority": _authority(),
            }

        latest = artifacts.receipts[-1]
        latest_payload, latest_missing, pending = (
            self._latest_cycle_payload(
                receipt=latest,
                admissions=artifacts.admissions,
            )
        )
        legacy_missing = 0
        for receipt in artifacts.receipts:
            for index in range(len(receipt.stages)):
                stage = _STAGE_ORDER[index]
                if (
                    receipt.cycle_fingerprint,
                    stage,
                ) not in artifacts.admissions:
                    legacy_missing += 1

        checkpoint_matches = (
            checkpoint.checkpoint_sha256
            == latest.current_checkpoint_sha256
            and checkpoint.snapshot_fingerprint
            == latest.current_snapshot_fingerprint
        )

        if not checkpoint_matches:
            if latest.status == RecurrentCycleStatus.OPEN and pending:
                status = "RECOVERY_REQUIRED"
                reasons = (
                    "LATEST_CYCLE_OPEN",
                    "NEXT_STAGE_ADMITTED",
                    "CHECKPOINT_ADVANCED_BEYOND_RECORDED_STAGE",
                    "RUNNER_RESUME_REQUIRED",
                )
            else:
                raise RecurrentCycleHealthError(
                    "authoritative checkpoint diverged from latest cycle"
                )
        elif latest.status == RecurrentCycleStatus.OPEN:
            status = "OPEN"
            reasons = (
                "LATEST_CYCLE_OPEN",
                (
                    "NEXT_STAGE_ADMITTED"
                    if pending
                    else "NEXT_STAGE_NOT_ADMITTED"
                ),
            )
        elif latest_missing:
            status = "COMPLETE_LEGACY_UNADMITTED"
            reasons = (
                "LATEST_CYCLE_COMPLETE",
                "RECORDED_STAGE_ADMISSION_MISSING",
            )
        else:
            status = "COMPLETE"
            reasons = (
                "LATEST_CYCLE_COMPLETE",
                "ALL_RECORDED_STAGES_ADMITTED",
            )

        return {
            "contract_version": (
                RECURRENT_CYCLE_HEALTH_CONTRACT_VERSION
            ),
            "contract_fingerprint": (
                RECURRENT_CYCLE_HEALTH_CONTRACT_FINGERPRINT
            ),
            "status": status,
            "generated_at_utc": self.now_provider().isoformat(),
            "cycle_count": len(artifacts.receipts),
            "legacy_unadmitted_stage_count": legacy_missing,
            "current_checkpoint": current,
            "latest_cycle": latest_payload,
            "reason_codes": reasons,
            "authority": _authority(),
        }

    def snapshot(self) -> dict[str, object]:
        try:
            return self._snapshot_validated()
        except Exception as exc:
            return {
                "contract_version": (
                    RECURRENT_CYCLE_HEALTH_CONTRACT_VERSION
                ),
                "contract_fingerprint": (
                    RECURRENT_CYCLE_HEALTH_CONTRACT_FINGERPRINT
                ),
                "status": "INVALID",
                "generated_at_utc": self.now_provider().isoformat(),
                "cycle_count": None,
                "legacy_unadmitted_stage_count": None,
                "current_checkpoint": None,
                "latest_cycle": None,
                "reason_codes": (
                    "DURABLE_CYCLE_HEALTH_VALIDATION_FAILED",
                    type(exc).__name__,
                ),
                "authority": _authority(),
            }


__all__ = [
    "RECURRENT_CYCLE_HEALTH_CONTRACT_FINGERPRINT",
    "RECURRENT_CYCLE_HEALTH_CONTRACT_VERSION",
    "RecurrentCycleHealthError",
    "RecurrentCycleHealthService",
]
