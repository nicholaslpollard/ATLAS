from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterator, Mapping, cast

from .queue import DeterministicJobQueue, JobEnvelope, stage_idempotency_key
from .registry import PipelineRegistry, StageDefinition
from .retry import retry_decision
from .status import JobState, RunState, StageStatus, parse_run_state
from .worker import LocalWorker, StageExecutionContext, StageHandler


PHASE20_RUN_ID_CONTRACT_VERSION = "phase20-run-id-v1-pipeline-fingerprint-logical-slot"
PHASE20_RUN_MANIFEST_CONTRACT_VERSION = (
    "phase20-run-manifest-v1-deterministic-local-resumable-zero-provider-calls"
)
PHASE20_RUN_JOURNAL_CONTRACT_VERSION = (
    "phase20-run-journal-v1-sanitized-append-only-zero-provider-calls"
)


class OrchestrationError(RuntimeError):
    pass


class RunLeaseCollisionError(OrchestrationError):
    pass


class ManifestConflictError(OrchestrationError):
    pass


@dataclass(frozen=True)
class Phase20RunPlan:
    run_id: str
    pipeline_id: str
    pipeline_fingerprint: str
    logical_slot: str
    topological_order: tuple[str, ...]
    provider_calls_performed: int = 0
    provider_writes_performed: int = 0
    broker_writes_performed: int = 0

    def to_payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "pipeline_id": self.pipeline_id,
            "pipeline_fingerprint": self.pipeline_fingerprint,
            "logical_slot": self.logical_slot,
            "topological_order": list(self.topological_order),
            "provider_calls_performed": self.provider_calls_performed,
            "provider_writes_performed": self.provider_writes_performed,
            "broker_writes_performed": self.broker_writes_performed,
        }


def deterministic_run_id(registry: PipelineRegistry, logical_slot: str) -> str:
    if not logical_slot or len(logical_slot) > 128 or logical_slot != logical_slot.strip():
        raise ValueError("logical_slot must be a non-empty trimmed string up to 128 characters")
    payload = {
        "contract_version": PHASE20_RUN_ID_CONTRACT_VERSION,
        "pipeline_id": registry.pipeline_id,
        "pipeline_fingerprint": registry.fingerprint(),
        "logical_slot": logical_slot,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"run-{hashlib.sha256(raw).hexdigest()[:24]}"


class LocalRunStore:
    """Small cross-platform local store used only to prove orchestration semantics."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def manifest_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "manifest.json"

    def journal_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "journal.jsonl"

    def lease_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / ".lease"

    def load_manifest(self, run_id: str) -> dict[str, object] | None:
        path = self.manifest_path(run_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ManifestConflictError("persisted manifest must be a JSON object")
        return cast(dict[str, object], payload)

    def write_manifest(self, run_id: str, manifest: Mapping[str, object]) -> None:
        run_dir = self.run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        path = self.manifest_path(run_id)
        temp_path = run_dir / "manifest.json.tmp"
        serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)

    def append_event(self, run_id: str, event: Mapping[str, object]) -> None:
        run_dir = self.run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        path = self.journal_path(run_id)
        sequence = 1
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                sequence += sum(1 for line in handle if line.strip())
        payload = {
            "contract_version": PHASE20_RUN_JOURNAL_CONTRACT_VERSION,
            "sequence": sequence,
            **event,
        }
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @contextmanager
    def lease(self, run_id: str) -> Iterator[None]:
        run_dir = self.run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        lease_path = self.lease_path(run_id)
        try:
            lease_path.mkdir()
        except FileExistsError as exc:
            raise RunLeaseCollisionError(
                f"run {run_id} already has an active or unreconciled lease"
            ) from exc
        try:
            yield
        finally:
            try:
                lease_path.rmdir()
            except FileNotFoundError:
                pass


class Phase20Orchestrator:
    def __init__(
        self,
        registry: PipelineRegistry,
        *,
        handlers: Mapping[str, StageHandler],
        state_root: Path,
    ) -> None:
        self.registry = registry
        self.worker = LocalWorker(handlers)
        self.store = LocalRunStore(state_root)

    def plan(self, logical_slot: str) -> Phase20RunPlan:
        return Phase20RunPlan(
            run_id=deterministic_run_id(self.registry, logical_slot),
            pipeline_id=self.registry.pipeline_id,
            pipeline_fingerprint=self.registry.fingerprint(),
            logical_slot=logical_slot,
            topological_order=self.registry.topological_order(),
        )

    def execute_shadow(self, logical_slot: str) -> dict[str, object]:
        plan = self.plan(logical_slot)
        with self.store.lease(plan.run_id):
            manifest = self.store.load_manifest(plan.run_id)
            if manifest is None:
                manifest = self._new_manifest(plan)
                self.store.write_manifest(plan.run_id, manifest)
                self._append_run_event(manifest, "RUN_CREATED")
            else:
                self._validate_manifest(manifest, plan)

            if parse_run_state(manifest["run_state"]) is RunState.SUCCEEDED:
                return manifest

            interrupted = self._fail_closed_interrupted_stages(manifest)
            if interrupted:
                self._transition_run(manifest, RunState.FAILED, "RUN_INTERRUPTED_STATE_UNCERTAIN")
                return manifest

            self._transition_run(manifest, RunState.RUNNING, "RUN_STARTED_OR_RESUMED")
            queue = DeterministicJobQueue()
            ranks = {
                stage_id: rank
                for rank, stage_id in enumerate(self.registry.topological_order())
            }

            while True:
                self._block_failed_dependents(manifest)
                self._enqueue_ready(manifest, queue, ranks)
                if len(queue) == 0:
                    break
                envelope = queue.pop()
                stage = self.registry.get(envelope.stage_id)
                self._execute_stage(manifest, stage, envelope)

            self._block_failed_dependents(manifest)
            final_state = self._derive_final_run_state(manifest)
            self._transition_run(manifest, final_state, "RUN_FINISHED")
            return manifest

    def _new_manifest(self, plan: Phase20RunPlan) -> dict[str, object]:
        return {
            "contract_version": PHASE20_RUN_MANIFEST_CONTRACT_VERSION,
            "run_id": plan.run_id,
            "pipeline_id": plan.pipeline_id,
            "pipeline_fingerprint": plan.pipeline_fingerprint,
            "logical_slot": plan.logical_slot,
            "run_state": RunState.PLANNED.value,
            "topological_order": list(plan.topological_order),
            "stages": {
                stage_id: StageStatus(stage_id=stage_id).to_payload()
                for stage_id in plan.topological_order
            },
            "provider_calls_performed": 0,
            "provider_writes_performed": 0,
            "broker_writes_performed": 0,
        }

    def _validate_manifest(self, manifest: dict[str, object], plan: Phase20RunPlan) -> None:
        expected = {
            "contract_version": PHASE20_RUN_MANIFEST_CONTRACT_VERSION,
            "run_id": plan.run_id,
            "pipeline_id": plan.pipeline_id,
            "pipeline_fingerprint": plan.pipeline_fingerprint,
            "logical_slot": plan.logical_slot,
            "topological_order": list(plan.topological_order),
            "provider_calls_performed": 0,
            "provider_writes_performed": 0,
            "broker_writes_performed": 0,
        }
        for key, value in expected.items():
            if manifest.get(key) != value:
                raise ManifestConflictError(f"persisted manifest conflict at field {key}")
        parse_run_state(manifest.get("run_state"))
        stages = manifest.get("stages")
        if not isinstance(stages, dict) or set(stages) != set(plan.topological_order):
            raise ManifestConflictError("persisted stage set does not match pipeline definition")
        for stage_id, stage_payload in stages.items():
            if not isinstance(stage_payload, dict):
                raise ManifestConflictError(f"invalid stage payload for {stage_id}")
            status = StageStatus.from_payload(cast(dict[str, object], stage_payload))
            if status.stage_id != stage_id:
                raise ManifestConflictError(f"stage payload identity mismatch for {stage_id}")

    def _stage_status(self, manifest: dict[str, object], stage_id: str) -> StageStatus:
        stages = cast(dict[str, object], manifest["stages"])
        payload = stages[stage_id]
        if not isinstance(payload, dict):
            raise ManifestConflictError(f"invalid stage payload for {stage_id}")
        status = StageStatus.from_payload(cast(dict[str, object], payload))
        if status.stage_id != stage_id:
            raise ManifestConflictError(f"stage payload identity mismatch for {stage_id}")
        return status

    def _transition_stage(
        self,
        manifest: dict[str, object],
        status: StageStatus,
        event_type: str,
    ) -> None:
        stages = cast(dict[str, object], manifest["stages"])
        stages[status.stage_id] = status.to_payload()
        self.store.write_manifest(str(manifest["run_id"]), manifest)
        self.store.append_event(
            str(manifest["run_id"]),
            {
                "run_id": manifest["run_id"],
                "event_type": event_type,
                "run_state": manifest["run_state"],
                "stage_id": status.stage_id,
                "stage_state": status.state.value,
                "attempt": status.attempts,
                "error_code": status.error_code,
            },
        )

    def _transition_run(
        self,
        manifest: dict[str, object],
        state: RunState,
        event_type: str,
    ) -> None:
        manifest["run_state"] = state.value
        self.store.write_manifest(str(manifest["run_id"]), manifest)
        self._append_run_event(manifest, event_type)

    def _append_run_event(self, manifest: dict[str, object], event_type: str) -> None:
        self.store.append_event(
            str(manifest["run_id"]),
            {
                "run_id": manifest["run_id"],
                "event_type": event_type,
                "run_state": manifest["run_state"],
                "stage_id": None,
                "stage_state": None,
                "attempt": None,
                "error_code": None,
            },
        )

    def _fail_closed_interrupted_stages(self, manifest: dict[str, object]) -> bool:
        interrupted = False
        for stage_id in self.registry.topological_order():
            status = self._stage_status(manifest, stage_id)
            if status.state is JobState.RUNNING:
                interrupted = True
                self._transition_stage(
                    manifest,
                    replace(
                        status,
                        state=JobState.FAILED,
                        error_code="INTERRUPTED_STAGE_STATE_UNCERTAIN",
                    ),
                    "STAGE_INTERRUPTED_FAIL_CLOSED",
                )
        return interrupted

    def _block_failed_dependents(self, manifest: dict[str, object]) -> None:
        for stage_id in self.registry.topological_order():
            status = self._stage_status(manifest, stage_id)
            if status.state is not JobState.PENDING:
                continue
            stage = self.registry.get(stage_id)
            dependency_states = [
                self._stage_status(manifest, dependency).state
                for dependency in stage.dependencies
            ]
            if any(state in {JobState.FAILED, JobState.BLOCKED} for state in dependency_states):
                self._transition_stage(
                    manifest,
                    replace(
                        status,
                        state=JobState.BLOCKED,
                        error_code="DEPENDENCY_NOT_SUCCESSFUL",
                    ),
                    "STAGE_BLOCKED_BY_DEPENDENCY",
                )

    def _enqueue_ready(
        self,
        manifest: dict[str, object],
        queue: DeterministicJobQueue,
        ranks: Mapping[str, int],
    ) -> None:
        run_id = str(manifest["run_id"])
        for stage_id in self.registry.topological_order():
            status = self._stage_status(manifest, stage_id)
            if status.state is not JobState.PENDING or queue.contains_stage(stage_id):
                continue
            stage = self.registry.get(stage_id)
            if all(
                self._stage_status(manifest, dependency).state is JobState.SUCCEEDED
                for dependency in stage.dependencies
            ):
                queue.enqueue(
                    JobEnvelope(
                        run_id=run_id,
                        stage_id=stage_id,
                        topological_rank=ranks[stage_id],
                        idempotency_key=stage_idempotency_key(run_id, stage_id),
                    )
                )

    def _execute_stage(
        self,
        manifest: dict[str, object],
        stage: StageDefinition,
        envelope: JobEnvelope,
    ) -> None:
        while True:
            previous = self._stage_status(manifest, stage.stage_id)
            if previous.state not in {JobState.PENDING, JobState.FAILED}:
                raise ManifestConflictError(
                    f"cannot execute stage {stage.stage_id} from state {previous.state.value}"
                )
            attempt = previous.attempts + 1
            running = replace(
                previous,
                state=JobState.RUNNING,
                attempts=attempt,
                error_code=None,
            )
            self._transition_stage(manifest, running, "STAGE_ATTEMPT_STARTED")
            result = self.worker.execute(
                stage,
                context=StageExecutionContext(
                    run_id=envelope.run_id,
                    logical_slot=str(manifest["logical_slot"]),
                    stage_id=stage.stage_id,
                    attempt=attempt,
                    idempotency_key=envelope.idempotency_key,
                ),
            )
            if result.succeeded:
                self._transition_stage(
                    manifest,
                    replace(running, state=JobState.SUCCEEDED, error_code=None),
                    "STAGE_ATTEMPT_SUCCEEDED",
                )
                return

            failed = replace(
                running,
                state=JobState.FAILED,
                error_code=result.error_code or "STAGE_HANDLER_FAILED",
            )
            self._transition_stage(manifest, failed, "STAGE_ATTEMPT_FAILED")
            decision = retry_decision(stage, completed_attempts=attempt)
            if not decision.allowed:
                return
            self.store.append_event(
                str(manifest["run_id"]),
                {
                    "run_id": manifest["run_id"],
                    "event_type": "STAGE_RETRY_AUTHORIZED",
                    "run_state": manifest["run_state"],
                    "stage_id": stage.stage_id,
                    "stage_state": failed.state.value,
                    "attempt": failed.attempts,
                    "error_code": decision.reason_code,
                },
            )

    def _derive_final_run_state(self, manifest: dict[str, object]) -> RunState:
        states = [
            self._stage_status(manifest, stage_id).state
            for stage_id in self.registry.topological_order()
        ]
        if all(state is JobState.SUCCEEDED for state in states):
            return RunState.SUCCEEDED
        if any(state is JobState.FAILED for state in states):
            return RunState.FAILED
        if any(state is JobState.BLOCKED for state in states):
            return RunState.BLOCKED
        raise ManifestConflictError("run ended with non-terminal unresolved stage state")
