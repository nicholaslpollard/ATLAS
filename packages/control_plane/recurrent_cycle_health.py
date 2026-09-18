from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.simulation.current_live_evidence import (
    CurrentLiveEvidenceError,
    capture_current_live_evidence_v1,
    current_live_evidence_payload,
)
from packages.simulation.recurrent_cycle import (
    RecurrentCycleOrchestrationError,
    RecurrentCycleReceiptV1,
    RecurrentCycleStage,
    RecurrentCycleStatus,
    read_recurrent_cycle_receipt,
)
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunnerError,
    read_recurrent_cycle_stage_admission,
    recurrent_cycle_stage_admission_path,
)
from packages.simulation.recurrent_persistence import (
    RecurrentLifecyclePersistenceError,
)
from packages.simulation.recurrent_runtime import (
    RecurrentDurableRuntimeError,
    restore_durable_recurrent_lifecycle_runtime,
)


RECURRENT_CYCLE_HEALTH_CONTRACT_VERSION = (
    "recurrent-cycle-health-v1-readonly-durable-lineage-and-local-current-evidence"
)
_STAGE_ORDER = (
    RecurrentCycleStage.CLOSE,
    RecurrentCycleStage.RESERVE,
    RecurrentCycleStage.ENTRY,
    RecurrentCycleStage.MARK,
)
_RECENT_LIMIT = 10
_SCAN_LIMIT = 1000


class RecurrentCycleHealthError(RuntimeError):
    pass


class RecurrentCycleHealthService:
    def __init__(
        self,
        settings: AtlasSettings,
        *,
        now_utc: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self._now_utc = now_utc or (lambda: datetime.now(UTC))

    @staticmethod
    def _authority() -> dict[str, object]:
        return {
            "read_only": True,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "scheduler_trigger_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "promotion_authority": False,
            "confluence_authority": False,
        }

    def _current_evidence(self, now: datetime) -> dict[str, object]:
        try:
            evidence = capture_current_live_evidence_v1(
                self.settings,
                captured_at_utc=now,
            )
        except CurrentLiveEvidenceError as exc:
            return {
                "available": False,
                "reason": type(exc).__name__,
                "network_provider_calls_performed": 0,
                "network_broker_calls_performed": 0,
                "minute_to_quote_fabrication": False,
            }
        return {
            "available": True,
            **current_live_evidence_payload(evidence),
        }

    def _admissions(
        self,
        *,
        checkpoint_path: Path,
        receipt: RecurrentCycleReceiptV1,
    ) -> tuple[list[dict[str, object]], int]:
        rows: list[dict[str, object]] = []
        invalid = 0
        for stage in _STAGE_ORDER:
            path = recurrent_cycle_stage_admission_path(
                checkpoint_path,
                receipt.cycle_id,
                stage,
            )
            if not path.is_file():
                rows.append(
                    {
                        "stage": stage.value,
                        "status": "MISSING",
                        "evidence_source_id": None,
                        "evidence_source_fingerprint": None,
                        "evidence_fingerprint": None,
                        "evidence_count": None,
                    }
                )
                continue
            try:
                admission = read_recurrent_cycle_stage_admission(path)
            except RecurrentCycleRunnerError:
                invalid += 1
                rows.append(
                    {
                        "stage": stage.value,
                        "status": "INVALID",
                        "evidence_source_id": None,
                        "evidence_source_fingerprint": None,
                        "evidence_fingerprint": None,
                        "evidence_count": None,
                    }
                )
                continue
            status = "ADMITTED"
            index = _STAGE_ORDER.index(stage)
            if len(receipt.stages) > index:
                stage_record = receipt.stages[index]
                if (
                    stage_record.stage != stage
                    or stage_record.source_checkpoint_sha256
                    != admission.source_checkpoint_sha256
                    or stage_record.source_snapshot_fingerprint
                    != admission.source_snapshot_fingerprint
                ):
                    status = "INVALID"
                    invalid += 1
            rows.append(
                {
                    "stage": stage.value,
                    "status": status,
                    "evidence_source_id": admission.evidence_source_id,
                    "evidence_source_fingerprint": (
                        admission.evidence_source_fingerprint
                    ),
                    "evidence_fingerprint": admission.evidence_fingerprint,
                    "evidence_count": admission.evidence_count,
                    "admission_sha256": admission.admission_sha256,
                    "created_at_utc": admission.created_at_utc.isoformat(),
                }
            )
        return rows, invalid

    def _cycle_row(
        self,
        *,
        checkpoint_path: Path,
        receipt: RecurrentCycleReceiptV1,
    ) -> tuple[dict[str, object], int]:
        admissions, invalid_admissions = self._admissions(
            checkpoint_path=checkpoint_path,
            receipt=receipt,
        )
        completed_stages = [record.stage.value for record in receipt.stages]
        next_stage = None
        if receipt.status == RecurrentCycleStatus.OPEN:
            next_stage = _STAGE_ORDER[len(receipt.stages)].value
        return (
            {
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
                "current_snapshot_fingerprint": (
                    receipt.current_snapshot_fingerprint
                ),
                "current_revision": receipt.current_revision,
                "completed_stages": completed_stages,
                "next_stage": next_stage,
                "admissions": admissions,
                "invalid_admission_count": invalid_admissions,
            },
            invalid_admissions,
        )

    def snapshot(self) -> dict[str, object]:
        now = self._now_utc()
        if now.tzinfo is None or now.utcoffset() is None:
            raise RecurrentCycleHealthError(
                "cycle-health clock must be timezone-aware"
            )
        now = now.astimezone(UTC)
        checkpoint_path = self.paths.recurrent_lifecycle_checkpoint_file()
        base: dict[str, object] = {
            "contract_version": RECURRENT_CYCLE_HEALTH_CONTRACT_VERSION,
            "generated_at_utc": now.isoformat(),
            "authority": self._authority(),
            "current_evidence": self._current_evidence(now),
            "runtime": None,
            "latest_cycle": None,
            "recent_cycles": [],
            "invalid_cycle_receipt_count": 0,
            "invalid_stage_admission_count": 0,
        }
        if not checkpoint_path.is_file():
            return {
                **base,
                "status": "NOT_BOOTSTRAPPED",
                "reason": "RECURRENT_CHECKPOINT_UNAVAILABLE",
            }

        try:
            runtime = restore_durable_recurrent_lifecycle_runtime(
                checkpoint_path
            )
            runtime_status = runtime.status()
        except (
            RecurrentLifecyclePersistenceError,
            RecurrentDurableRuntimeError,
        ) as exc:
            return {
                **base,
                "status": "INVALID",
                "reason": type(exc).__name__,
            }

        base["runtime"] = {
            "checkpoint_sha256": runtime_status.checkpoint_sha256,
            "snapshot_fingerprint": runtime_status.snapshot_fingerprint,
            "revision": runtime_status.revision,
            "uncertain": runtime_status.uncertain,
            "open_position_count": len(
                runtime.current_account().state.open_positions
            ),
            "stock_reservation_count": len(
                runtime.current_account().state.stock_reservations
            ),
            "option_reservation_count": len(
                runtime.current_account().state.option_reservations
            ),
        }
        if runtime_status.uncertain:
            return {
                **base,
                "status": "INVALID",
                "reason": "DURABLE_RUNTIME_UNCERTAIN",
            }

        cycle_dir = checkpoint_path.parent / "cycles"
        candidates = (
            sorted(cycle_dir.glob("*.json"))
            if cycle_dir.is_dir()
            else []
        )
        if len(candidates) > _SCAN_LIMIT:
            return {
                **base,
                "status": "INVALID",
                "reason": "CYCLE_RECEIPT_SCAN_LIMIT_EXCEEDED",
            }

        valid: list[RecurrentCycleReceiptV1] = []
        invalid_receipts = 0
        for path in candidates:
            try:
                valid.append(read_recurrent_cycle_receipt(path))
            except RecurrentCycleOrchestrationError:
                invalid_receipts += 1
        valid.sort(key=lambda item: (item.created_at_utc, item.cycle_id))
        recent_receipts = list(reversed(valid[-_RECENT_LIMIT:]))

        recent_rows: list[dict[str, object]] = []
        invalid_admissions = 0
        for receipt in recent_receipts:
            row, invalid = self._cycle_row(
                checkpoint_path=checkpoint_path,
                receipt=receipt,
            )
            recent_rows.append(row)
            invalid_admissions += invalid

        base["invalid_cycle_receipt_count"] = invalid_receipts
        base["invalid_stage_admission_count"] = invalid_admissions
        base["recent_cycles"] = recent_rows
        base["latest_cycle"] = recent_rows[0] if recent_rows else None

        if invalid_receipts or invalid_admissions:
            return {
                **base,
                "status": "DEGRADED",
                "reason": "INVALID_CYCLE_OR_ADMISSION_ARTIFACT",
            }
        if not recent_rows:
            return {
                **base,
                "status": "IDLE",
                "reason": "NO_CYCLE_RECEIPTS",
            }
        latest = recent_rows[0]
        return {
            **base,
            "status": (
                "OPEN_CYCLE"
                if latest["status"] == RecurrentCycleStatus.OPEN.value
                else "HEALTHY"
            ),
            "reason": None,
        }


__all__ = [
    "RECURRENT_CYCLE_HEALTH_CONTRACT_VERSION",
    "RecurrentCycleHealthError",
    "RecurrentCycleHealthService",
]
