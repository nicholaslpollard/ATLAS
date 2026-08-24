from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.jobs.orchestrator import Phase20Orchestrator
from packages.jobs.phase20_policy import phase20_policy_fingerprint, validate_phase20_policy
from packages.jobs.registry import PipelineRegistry, StageDefinition


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_ROOT = REPO_ROOT / "data" / "runtime" / "phase20"


def _registry() -> PipelineRegistry:
    return PipelineRegistry(
        "phase20-local-shadow-rehearsal",
        "v1",
        (
            StageDefinition("foundation"),
            StageDefinition("living_docs", dependencies=("foundation",)),
            StageDefinition("shadow_summary", dependencies=("living_docs",)),
        ),
    )


def _handlers():
    def foundation(_context) -> None:
        validate_phase20_policy()

    def living_docs(_context) -> None:
        for relative in (
            "README.md",
            "docs/current_status.md",
            "docs/roadmap.md",
            "docs/phase20_run_orchestration.md",
        ):
            path = REPO_ROOT / relative
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError("required living document unavailable")

    def shadow_summary(_context) -> None:
        return None

    return {
        "foundation": foundation,
        "living_docs": living_docs,
        "shadow_summary": shadow_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATLAS Phase 20 provider-free deterministic orchestration runner"
    )
    parser.add_argument(
        "--slot",
        required=True,
        help="Explicit logical run slot/key; it is part of deterministic run identity.",
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=DEFAULT_STATE_ROOT,
        help="Local Phase 20 run-state root.",
    )
    parser.add_argument(
        "--execute-shadow",
        action="store_true",
        help="Execute the local-only shadow rehearsal. Omit for plan-only mode.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    registry = _registry()
    orchestrator = Phase20Orchestrator(
        registry,
        handlers=_handlers(),
        state_root=args.state_root,
    )
    plan = orchestrator.plan(args.slot)

    if args.execute_shadow:
        manifest = orchestrator.execute_shadow(args.slot)
        payload = {
            "mode": "LOCAL_SHADOW_REHEARSAL",
            "policy_fingerprint": phase20_policy_fingerprint(),
            "pipeline_version": registry.pipeline_version,
            "plan": plan.to_payload(),
            "run_state": manifest["run_state"],
            "stage_states": {
                stage_id: manifest["stages"][stage_id]["state"]
                for stage_id in plan.topological_order
            },
            "provider_calls_performed": manifest["provider_calls_performed"],
            "provider_writes_performed": manifest["provider_writes_performed"],
            "broker_writes_performed": manifest["broker_writes_performed"],
            "live_execution": "DISABLED",
            "automatic_cross_broker_failover": "DISABLED",
        }
    else:
        payload = {
            "mode": "PLAN_ONLY",
            "policy_fingerprint": phase20_policy_fingerprint(),
            "pipeline_version": registry.pipeline_version,
            "plan": plan.to_payload(),
            "local_state_writes_performed": 0,
            "provider_calls_performed": 0,
            "provider_writes_performed": 0,
            "broker_writes_performed": 0,
            "live_execution": "DISABLED",
            "automatic_cross_broker_failover": "DISABLED",
        }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("ATLAS Phase 20 deterministic run orchestration")
        print(f"Mode: {payload['mode']}")
        print(f"Run ID: {plan.run_id}")
        print(f"Pipeline: {plan.pipeline_id}@{registry.pipeline_version}")
        print(f"Logical slot: {plan.logical_slot}")
        print(f"Stage order: {' -> '.join(plan.topological_order)}")
        if args.execute_shadow:
            print(f"Run state: {payload['run_state']}")
        else:
            print("Local state writes performed: 0")
        print("Provider calls performed: 0")
        print("Provider writes performed: 0")
        print("Broker writes performed: 0")
        print("Live execution: DISABLED")
        print("Automatic cross-broker failover: DISABLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
