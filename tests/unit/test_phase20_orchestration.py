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
    DuplicateStageQueueError,
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


def _registry(*stages: StageDefinition, version: str = "v1") -> PipelineRegistry:
    return PipelineRegistry("phase20-test", version, stages)


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
    assert _registry(alpha, finish, beta, version="v2").fingerprint() != one.fingerprint()
    with pytest.raises(DuplicateStageError):
        _registry(alpha, alpha)
    with pytest.raises(MissingDependencyError):
        _registry(StageDefinition("only", dependencies=("missing",)))
    with pytest.raises(DependencyCycleError):
        _registry(
            StageDefinition("a", dependencies=("b",)),
            StageDefinition("b", dependencies=("a",)),
        )


def test_registry_rejects_external_authority() -> None:
    with pytest.raises(StageAuthorityError):
        _registry(StageDefinition("read", authority=StageAuthority.EXTERNAL_READ))
    with pytest.raises(StageAuthorityError):
        _registry(StageDefinition("write", authority=StageAuthority.EXTERNAL_MUTATION))


def test_queue_is_deterministic_and_duplicate_safe() -> None:
    queue = DeterministicJobQueue()
    run_id = "run-test"
    jobs = [
        JobEnvelope(run_id, "later", 2, stage_idempotency_key(run_id, "later")),
        JobEnvelope(run_id, "beta", 0, stage_idempotency_key(run_id, "beta")),
        JobEnvelope(run_id, "alpha", 0, stage_idempotency_key(run_id, "alpha")),
    ]
    for job in jobs:
        queue.enqueue(job)
    assert [queue.pop().stage_id for _ in range(3)] == ["alpha", "beta", "later"]

    duplicate_key_queue = DeterministicJobQueue()
    duplicate_key_queue.enqueue(jobs[2])
    with pytest.raises(DuplicateIdempotencyKeyError):
        duplicate_key_queue.enqueue(jobs[2])

    duplicate_stage_queue = DeterministicJobQueue()
    duplicate_stage_queue.enqueue(jobs[2])
    duplicate_stage_queue.pop()
    with pytest.raises(DuplicateStageQueueError):
        duplicate_stage_queue.enqueue(
            JobEnvelope(run_id, "alpha", 0, "job-different-but-same-stage")
        )


def test_worker_sanitizes_exception_message() -> None:
    def handler(_context: StageExecutionContext) -> None:
        raise RuntimeError("secret credential material must not escape")

    result = LocalWorker({"safe": handler}).execute(
        StageDefinition("safe"),
        context=StageExecutionContext("run-a", "slot-a", "safe", 1, "job-a"),
    )
    assert result.succeeded is False
    assert result.error_code == "STAGE_HANDLER_ERROR_RuntimeError"
    assert "secret" not in str(result)


def test_stage_status_rejects_impossible_persisted_state_shapes() -> None:
    with pytest.raises(ValueError):
        StageStatus("pending", state=JobState.PENDING, attempts=1)
    with pytest.raises(ValueError):
        StageStatus("running", state=JobState.RUNNING, attempts=0)
    with pytest.raises(ValueError):
        StageStatus("success", state=JobState.SUCCEEDED, attempts=0)
    with pytest.raises(ValueError):
        StageStatus("failed", state=JobState.FAILED, attempts=1, error_code=None)
    with pytest.raises(ValueError):
        StageStatus("blocked", state=JobState.BLOCKED, attempts=0, error_code=None)


def test_plan_is_deterministic_and_zero_write(tmp_path) -> None:
    registry = _registry(
        StageDefinition("extract"),
        StageDefinition("score", dependencies=("extract",)),
    )
    state_root = tmp_path / "state"
    orchestrator = Phase20Orchestrator(registry, handlers={}, state_root=state_root)
    first = orchestrator.plan("2026-08-24T13:30:00-04:00")
    assert orchestrator.plan("2026-08-24T13:30:00-04:00") == first
    assert first.provider_calls_performed == 0
    assert first.provider_writes_performed == 0
    assert first.broker_writes_performed == 0
    assert not state_root.exists()


def test_successful_run_is_idempotent_on_resume(tmp_path) -> None:
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
    assert orchestrator.execute_shadow("slot-1") == first
    assert calls == [("alpha", 1), ("beta", 1)]
    journal = (tmp_path / str(first["run_id"]) / "journal.jsonl").read_text(
        encoding="utf-8"
    )
    assert "secret credential material" not in journal


def test_retry_is_bounded_and_exception_text_is_not_persisted(tmp_path) -> None:
    attempts: list[int] = []
    registry = _registry(StageDefinition("flaky", retry_safe_local=True, max_attempts=3))

    def flaky(context: StageExecutionContext) -> None:
        attempts.append(context.attempt)
        if context.attempt < 3:
            raise OSError("transient secret-bearing message")

    manifest = Phase20Orchestrator(
        registry,
        handlers={"flaky": flaky},
        state_root=tmp_path,
    ).execute_shadow("slot-retry")
    status = StageStatus.from_payload(manifest["stages"]["flaky"])
    assert manifest["run_state"] == RunState.SUCCEEDED.value
    assert attempts == [1, 2, 3]
    assert status.state is JobState.SUCCEEDED
    assert status.attempts == 3
    assert "transient secret-bearing message" not in json.dumps(manifest, sort_keys=True)


def test_failed_dependency_blocks_downstream(tmp_path) -> None:
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
    assert StageStatus.from_payload(manifest["stages"]["root"]).state is JobState.FAILED
    assert StageStatus.from_payload(manifest["stages"]["child"]).state is JobState.BLOCKED
    assert child_calls == []


def test_interrupted_running_state_fails_closed_without_reexecution(tmp_path) -> None:
    calls: list[str] = []
    registry = _registry(StageDefinition("only", retry_safe_local=True, max_attempts=3))
    orchestrator = Phase20Orchestrator(
        registry,
        handlers={"only": lambda context: calls.append(context.stage_id)},
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


def test_lease_and_manifest_authority_conflicts_fail_closed(tmp_path) -> None:
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

    plan = orchestrator.plan("slot-conflict")
    manifest = orchestrator._new_manifest(plan)
    manifest["provider_calls_performed"] = 1
    orchestrator.store.write_manifest(plan.run_id, manifest)
    with pytest.raises(ManifestConflictError):
        orchestrator.execute_shadow("slot-conflict")


def test_manifest_semantic_conflicts_fail_closed(tmp_path) -> None:
    registry = _registry(
        StageDefinition("parent"),
        StageDefinition("child", dependencies=("parent",)),
    )
    orchestrator = Phase20Orchestrator(
        registry,
        handlers={"parent": lambda _context: None, "child": lambda _context: None},
        state_root=tmp_path,
    )

    succeeded_plan = orchestrator.plan("slot-false-success")
    false_success = orchestrator._new_manifest(succeeded_plan)
    false_success["run_state"] = RunState.SUCCEEDED.value
    orchestrator.store.write_manifest(succeeded_plan.run_id, false_success)
    with pytest.raises(ManifestConflictError):
        orchestrator.execute_shadow("slot-false-success")

    dependency_plan = orchestrator.plan("slot-impossible-dependency")
    impossible_dependency = orchestrator._new_manifest(dependency_plan)
    impossible_dependency["run_state"] = RunState.RUNNING.value
    impossible_dependency["stages"]["child"] = StageStatus(
        "child", state=JobState.SUCCEEDED, attempts=1
    ).to_payload()
    orchestrator.store.write_manifest(dependency_plan.run_id, impossible_dependency)
    with pytest.raises(ManifestConflictError):
        orchestrator.execute_shadow("slot-impossible-dependency")

    attempts_plan = orchestrator.plan("slot-too-many-attempts")
    too_many_attempts = orchestrator._new_manifest(attempts_plan)
    too_many_attempts["run_state"] = RunState.RUNNING.value
    too_many_attempts["stages"]["parent"] = StageStatus(
        "parent", state=JobState.RUNNING, attempts=2
    ).to_payload()
    orchestrator.store.write_manifest(attempts_plan.run_id, too_many_attempts)
    with pytest.raises(ManifestConflictError):
        orchestrator.execute_shadow("slot-too-many-attempts")
