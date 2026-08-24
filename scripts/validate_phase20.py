from __future__ import annotations

import json
import tempfile
from pathlib import Path

from packages.jobs.orchestrator import ManifestConflictError, Phase20Orchestrator
from packages.jobs.phase20_policy import (
    PHASE20_POLICY_CONTRACT_VERSION,
    phase20_policy_fingerprint,
    validate_phase20_policy,
)
from packages.jobs.registry import (
    PipelineRegistry,
    StageAuthority,
    StageAuthorityError,
    StageDefinition,
)
from packages.jobs.status import JobState, RunState, StageStatus


def main() -> int:
    validate_phase20_policy()

    registry = PipelineRegistry(
        "phase20-validation",
        "v1",
        (
            StageDefinition("foundation"),
            StageDefinition("inventory", dependencies=("foundation",)),
            StageDefinition("summary", dependencies=("inventory",)),
        ),
    )
    replay_registry = PipelineRegistry(
        "phase20-validation",
        "v1",
        tuple(reversed(registry.stages)),
    )
    assert registry.topological_order() == ("foundation", "inventory", "summary")
    assert replay_registry.fingerprint() == registry.fingerprint()
    assert PipelineRegistry(
        "phase20-validation",
        "v2",
        registry.stages,
    ).fingerprint() != registry.fingerprint()

    try:
        PipelineRegistry(
            "phase20-invalid",
            "v1",
            (StageDefinition("mutation", authority=StageAuthority.EXTERNAL_MUTATION),),
        )
    except StageAuthorityError:
        mutation_registration_blocked = True
    else:
        mutation_registration_blocked = False
    assert mutation_registration_blocked

    calls: list[str] = []

    def record(context) -> None:
        calls.append(context.stage_id)

    with tempfile.TemporaryDirectory(prefix="atlas-phase20-") as temp_dir:
        state_root = Path(temp_dir) / "state"
        orchestrator = Phase20Orchestrator(
            registry,
            handlers={stage_id: record for stage_id in registry.topological_order()},
            state_root=state_root,
        )
        plan_one = orchestrator.plan("validator-slot")
        plan_two = orchestrator.plan("validator-slot")
        assert plan_one == plan_two
        assert not state_root.exists()

        manifest = orchestrator.execute_shadow("validator-slot")
        assert manifest["run_state"] == RunState.SUCCEEDED.value
        assert calls == ["foundation", "inventory", "summary"]
        assert manifest["provider_calls_performed"] == 0
        assert manifest["provider_writes_performed"] == 0
        assert manifest["broker_writes_performed"] == 0
        for stage_id in registry.topological_order():
            assert StageStatus.from_payload(manifest["stages"][stage_id]).state is JobState.SUCCEEDED

        replay = orchestrator.execute_shadow("validator-slot")
        assert replay == manifest
        assert calls == ["foundation", "inventory", "summary"]

        journal_text = (
            state_root / str(manifest["run_id"]) / "journal.jsonl"
        ).read_text(encoding="utf-8")
        for line in journal_text.splitlines():
            json.loads(line)
        assert "credential" not in journal_text.lower()

        conflict_plan = orchestrator.plan("validator-false-success")
        false_success = orchestrator._new_manifest(conflict_plan)
        false_success["run_state"] = RunState.SUCCEEDED.value
        orchestrator.store.write_manifest(conflict_plan.run_id, false_success)
        try:
            orchestrator.execute_shadow("validator-false-success")
        except ManifestConflictError:
            semantic_conflict_blocked = True
        else:
            semantic_conflict_blocked = False
        assert semantic_conflict_blocked

    print("ATLAS Phase 20 deterministic run orchestration validation")
    print(f"  policy contract: {PHASE20_POLICY_CONTRACT_VERSION}")
    print(f"  policy fingerprint: {phase20_policy_fingerprint()}")
    print(f"  pipeline version: {registry.pipeline_version}")
    print(f"  pipeline fingerprint deterministic: {registry.fingerprint()}")
    print(f"  topological order: {','.join(registry.topological_order())}")
    print("  external mutation-stage registration: BLOCKED")
    print("  persisted semantic conflict: BLOCKED")
    print("  plan-only local state writes: 0")
    print("  provider calls performed: 0")
    print("  provider writes performed: 0")
    print("  broker writes performed: 0")
    print("  deterministic resume/idempotency: PASS")
    print("Phase 20 deterministic run orchestration contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
