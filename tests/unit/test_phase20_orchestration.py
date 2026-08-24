from __future__ import annotations

import json
from dataclasses import replace

import pytest

from packages.jobs.orchestrator import (
    ManifestConflictError,
    Phase20Orchestrator,
    RunLeaseCollisionError,
)
from packages.jobs.phase20_policy import (
    PHASE20_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE20_BROKER_WRITES_ALLOWED,
    PHASE20_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE20_PROVIDER_READS_ALLOWED,
    PHASE20_PROVIDER_WRITES_ALLOWED,
    phase20_policy_fingerprint,
    validate_phase20_policy,
)
from packages.jobs.queue import (
    DeterministicJobQueue,
    DuplicateIdempotencyKeyError,
    JobEnvelope,
    stage_idempotency_key,
)
from packages.jobs.registry import (
    DependencyCycleError,
    DuplicateStageError,
    MissingDependencyError,
    PipelineRegistry,
    StageAuthority,
    StageAuthorityError,
    StageDefinition,
)
from packages.jobs.status import JobState, RunState, StageStatus
from packages.jobs.worker import LocalWorker, StageExecutionContext


def _registry(*stages: StageDefinition) -> PipelineRegistry:
    return PipelineRegistry("phase20-test", stages)


def test_phase20_authority_is_provider_free_and_non_live() -> None:
    validate_phase20_policy()
    assert len(phase20_policy_fingerprint()) == 64
    assert PHASE20_PROVIDER_READS_ALLOWED is False
    assert PHASE20_PROVIDER_WRITES_ALLOWED is False
    assert PHASE20_BROKER_WRITES_ALLOWED is False
    assert PHASE20_LIVE_EXECUTION_PROMOTION_ALLOWED is False
    assert PHASE20_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False


def test_registry_is_deterministic_and_rejects_invalid_graphs() -> None:
    alpha = StageDefinition("alpha")
    beta = StageDefinition("beta")
    finish = StageDefinition("finish", dependencies=("alpha", "beta"))
    one = _registry(finish, beta, alpha)
    two = _registry(alpha, finish, beta)
    assert one.topological_order() == ("alpha", "beta", "finish")
    assert two.topological_order() == one.topological_order()
    assert two.fingerprint() == one.fingerprint()

    with pytest.raises(DuplicateStageError):
        _registry(alpha, alpha)
    with pytest.raises(MissingDependencyError):
        _registry(StageDefinition("only", dependencies=("missing",)))
    with pytest.raises(DependencyCycleError):
        _registry(
            StageDefinition("a", dependencies=("b",)),
            StageDefinition("b", dependencies=("a",)),
        )


def test_registry_rejects_external_read_and_mutation_authority() -> None:
    with pytest.raises(StageAuthorityError):
        _registry(StageDefinition("read", authority=StageAuthority.EXTERNAL_READ))
    with pytest.raises(StageAuthorityError):
        _registry(StageDefinition("write", authority=StageAuthority.EXTERNAL_MUTATION))


def test_queue_orders_by_topology_then_stage_and_rejects_duplicate_key() -> None:
    queue = DeterministicJobQueue()
    run_id = "run-test"
    later = JobEnvelope(run_id, "later", 2, stage_idempotency_key(run_id, "later"))
    beta = JobEnvelope(run_id, "beta", 0, stage_idempotency_key(run_id, "beta"))
    alpha = JobEnvelope(run_id, "alpha", 0, stage_idempotency_key(run_id, "alpha"))
    queue.enqueue(later)
    queue.enqueue(beta)
    queue.enqueue(alpha)
    assert [queue.pop().stage_id, queue.pop().stage_id, queue.pop().stage_id] == [
        "alpha",
        "beta",
        "later",
    ]

    duplicate_queue = DeterministicJobQueue()
    duplicate_queue.enqueue(alpha)
    with pytest.raises(DuplicateIdempotencyKeyError):
        duplicate_queue.enqueue(alpha)


def test_worker_does_not_persist_exception_message() -> None:
    stage = StageDefinition("safe")

    def handler(_context: StageExecutionContext) -> None:
        raise RuntimeError("secret credential material must not escape")

    result = LocalWorker({"safe": handler}).execute(
        stage,
        context=StageExecutionContext(
            run_id="run-a",
            logical_slot="slot-a",
            stage_id="safe",
            attempt=1,
            idempotency_key="job-a",
        ),
    )
    assert result.succeeded is False
    assert result.error_code == "STAGE_HANDLER_ERROR_RuntimeError"
    assert "secret" not in str(result)


def test_plan_is_deterministic_and_performs_no_local_write(tmp_path) -> None:
    registry = _registry(
        StageDefinition("extract"),
        StageDefinition("score", dependencies=("extract",)),
    )
    orchestrator = Phase20Orchestrator(registry, handlers={}, state_root=tmp_path)
    first = orchestrator.plan("2026-08-24T13:30:00-04:00")
    second = orchestrator.plan("2026-08-24T13:30:00-04:00")
    assert first == second
    assert first.provider_calls_performed == 0
    assert first.provider_writes_performed == 0
    assert first.broker_writes_performed == 0
    assert not tmp_path.exists()


def test_successful_run_resumes_without_rerunning_completed_stages(tmp_path) -> None:
    calls: list[tuple[str, int]] = []
    registry = _registry(
        StageDefinition("alpha"),
        StageDefinition("beta", dependencies=("alpha",)),
    )

    def record(context: StageExecutionContext) -> None:
        calls.append((context.stage_id, context.attempt))

    orchestrator = Phase20Orchestrator(
        registry,
        handlers={"alpha": record, "beta": record},
        state_root=tmp_path,
    )
    first = orchestrator.execute_shadow("slot-1")
    assert first["run_state"] == RunState.SUCCEEDED.value
    assert calls == [("alpha", 1), ("beta", 1)]

    second = orchestrator.execute_shadow("slot-1")
    assert second == first
    assert calls == [("alpha", 1), ("beta", 1)]

    journal = (
        tmp_path / str(first["run_id"]) / "journal.jsonl"
    ).read_text(encoding="utf-8")
    assert "provider" not in journal.lower()


def test_retry_is_bounded_and_owned_by_orchestrator(tmp_path) -> None:
    attempts: list[int] = []
    stage = StageDefinition("flaky", retry_safe_local=True, max_attempts=3)
    registry = _registry(stage)

    def flaky(context: StageExecutionContext) -> None:
        attempts.append(context.attempt)
        if context.attempt < 3:
            raise OSError("transient secret-bearing message")

    manifest = Phase20Orchestrator(
        registry,
        handlers={"flaky": flaky},
        state_root=tmp_path,
    ).execute_shadow("slot-retry")
    assert manifest["run_state"] == RunState.SUCCEEDED.value
    assert attempts == [1, 2, 3]
    status = StageStatus.from_payload(manifest["stages"]["flaky"])
    assert status.state is JobState.SUCCEEDED
    assert status.attempts == 3
    serialized = json.dumps(manifest, sort_keys=True)
    assert "transient secret-bearing message" not in serialized


def test_failed_dependency_blocks_downstream_without_calling_it(tmp_path) -> None:
    child_calls: list[str] = []
    registry = _registry(
        StageDefinition("root"),
        StageDefinition("child", dependencies=("root",)),
    )

    def fail(_context: StageExecutionContext) -> None:
        raise RuntimeError("do not persist this")

    def child(context: StageExecutionContext) -> None:
        child_calls.append(context.stage_id)

    manifest = Phase20Orchestrator(
        registry,
        handlers={"root": fail, "child": child},
        state_root=tmp_path,
    ).execute_shadow("slot-fail")
    assert manifest["run_state"] == RunState.FAILED.value
    root = StageStatus.from_payload(manifest["stages"]["root"])
    child_status = StageStatus.from_payload(manifest["stages"]["child"])
    assert root.state is JobState.FAILED
    assert child_status.state is JobState.BLOCKED
    assert child_calls == []


def test_interrupted_running_state_fails_closed_without_reexecution(tmp_path) -> None:
    calls: list[str] = []
    registry = _registry(StageDefinition("only", retry_safe_local=True, max_attempts=3))

    def handler(context: StageExecutionContext) -> None:
        calls.append(context.stage_id)

    orchestrator = Phase20Orchestrator(
        registry,
        handlers={"only": handler},
        state_root=tmp_path,
    )
    plan = orchestrator.plan("slot-interrupted")
    manifest = orchestrator._new_manifest(plan)
    manifest["run_state"] = RunState.RUNNING.value
    manifest["stages"]["only"] = replace(
        StageStatus("only"), state=JobState.RUNNING, attempts=1
    ).to_payload()
    orchestrator.store.write_manifest(plan.run_id, manifest)

    resumed = orchestrator.execute_shadow("slot-interrupted")
    status = StageStatus.from_payload(resumed["stages"]["only"])
    assert resumed["run_state"] == RunState.FAILED.value
    assert status.state is JobState.FAILED
    assert status.error_code == "INTERRUPTED_STAGE_STATE_UNCERTAIN"
    assert calls == []


def test_run_lease_collision_fails_closed(tmp_path) -> None:
    registry = _registry(StageDefinition("only"))
    orchestrator = Phase20Orchestrator(
        registry,
        handlers={"only": lambda _context: None},
        state_root=tmp_path,
    )
    run_id = orchestrator.plan("slot-lease").run_id
    with orchestrator.store.lease(run_id):
        with pytest.raises(RunLeaseCollisionError):
            orchestrator.execute_shadow("slot-lease")


def test_persisted_authority_counter_conflict_fails_closed(tmp_path) -> None:
    registry = _registry(StageDefinition("only"))
    orchestrator = Phase20Orchestrator(
        registry,
        handlers={"only": lambda _context: None},
        state_root=tmp_path,
    )
    plan = orchestrator.plan("slot-conflict")
    manifest = orchestrator._new_manifest(plan)
    manifest["provider_calls_performed"] = 1
    orchestrator.store.write_manifest(plan.run_id, manifest)
    with pytest.raises(ManifestConflictError):
        orchestrator.execute_shadow("slot-conflict")
