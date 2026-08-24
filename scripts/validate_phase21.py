from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from packages.execution.phase21_authority import (
    PHASE21_AUTOMATIC_BROKER_FAILOVER,
    PHASE21_LIVE_EXECUTION_ENABLED,
    PHASE21_PAPER_PROVIDER_SUBMIT_ENABLED_BY_DEFAULT,
    Phase21PaperExecutionAuthority,
    phase21_policy_fingerprint,
    phase21_policy_payload,
)
from packages.jobs.registry import (
    PipelineRegistry,
    StageAuthority,
    StageAuthorityError,
    StageDefinition,
)
from packages.jobs.phase20_policy import PHASE20_EXTERNAL_MUTATION_STAGE_REGISTRATION_ALLOWED


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _adapter_submit_calls(relative: str) -> int:
    tree = ast.parse(_source(relative), filename=relative)
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "submit":
            continue
        owner = node.func.value
        if isinstance(owner, ast.Name) and owner.id == "adapter":
            count += 1
    return count


def main() -> None:
    payload = phase21_policy_payload()
    fingerprint = phase21_policy_fingerprint()
    _require(len(fingerprint) == 64, "Phase 21 policy fingerprint must be sha256")
    _require(fingerprint == phase21_policy_fingerprint(), "Phase 21 policy fingerprint is not deterministic")
    _require(
        PHASE21_PAPER_PROVIDER_SUBMIT_ENABLED_BY_DEFAULT is False,
        "Phase 21 PAPER provider submit must remain default-deny",
    )
    _require(PHASE21_LIVE_EXECUTION_ENABLED is False, "Phase 21 cannot enable LIVE")
    _require(
        PHASE21_AUTOMATIC_BROKER_FAILOVER is False,
        "Phase 21 cannot enable automatic broker failover",
    )
    _require(payload["environment"] == "paper", "Phase 21 authority must be PAPER-only")
    _require(
        payload["existing_idempotent_order"] == "NO_NEW_MUTATION_AUTHORITY_REQUIRED",
        "idempotent no-write reconciliation invariant drifted",
    )

    engine = _source("packages/execution/engine.py")
    gate_index = engine.index("require_phase21_paper_execution_authority(")
    submit_index = engine.index("submitted = adapter.submit(plan)")
    _require(gate_index < submit_index, "Phase 21 gate must run before adapter.submit(plan)")
    _require(
        'stage="paper_authority"' in engine,
        "central execution engine must expose a deterministic paper_authority failure stage",
    )

    operational_adapter_submit_paths: list[str] = []
    for path in sorted((ROOT / "packages").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        if _adapter_submit_calls(relative):
            operational_adapter_submit_paths.append(relative)
    _require(
        operational_adapter_submit_paths == ["packages/execution/engine.py"],
        f"adapter.submit mutation seam is not centralized: {operational_adapter_submit_paths}",
    )

    phase15 = _source("packages/execution/phase15_run.py")
    _require(
        "def prepare_paper_execution_challenge(" in phase15,
        "Phase 15 must expose a read-only PAPER execution challenge",
    )
    phase15_auth_index = phase15.index("validated_authority = require_phase21_paper_execution_authority(")
    quote_init_index = phase15.index(
        "quote_resolver = self._quote_resolver or Phase15LiveQuoteResolver(self.settings)"
    )
    _require(
        phase15_auth_index < quote_init_index,
        "Phase 15 PAPER authority must fail closed before live quote/provider initialization",
    )
    _require(
        "execution_scope_id=execution_scope_id" in phase15
        and "paper_authority=paper_authority" in phase15,
        "Phase 15 must pass exact scope and authority into the central execution engine",
    )

    phase18 = _source("packages/execution/phase18_lifecycle.py")
    phase18_outer_index = phase18.index("auth = require_phase18_mutation_authorization(authorization)")
    phase18_compat_index = phase18.index(
        "phase21_challenge = build_phase18_paper_execution_challenge(intent)"
    )
    phase18_engine_index = phase18.index("attempt = ExecutionEngine().attempt(")
    _require(
        phase18_outer_index < phase18_compat_index < phase18_engine_index,
        "Phase 18 original certification authorization must precede Phase 21 compatibility authority",
    )
    _require(
        "execution_scope_id=phase21_challenge.execution_scope_id" in phase18
        and "paper_authority=phase21_authority" in phase18,
        "Phase 18 certification submit must cross the central Phase 21 gate",
    )

    control_plane = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "packages" / "control_plane").glob("*.py"))
    )
    _require(
        "packages.execution.phase21_authority" not in control_plane,
        "browser/control plane must not acquire Phase 21 execution authority",
    )
    _require(
        "ExecutionEngine" not in control_plane,
        "browser/control plane must not gain direct execution-engine authority",
    )

    _require(
        PHASE20_EXTERNAL_MUTATION_STAGE_REGISTRATION_ALLOWED is False,
        "Phase 20 external mutation-stage registration must remain disabled",
    )
    try:
        PipelineRegistry(
            "phase21-validator",
            "v1",
            (
                StageDefinition(
                    "provider_write",
                    authority=StageAuthority.EXTERNAL_MUTATION,
                ),
            ),
        )
    except StageAuthorityError:
        pass
    else:
        raise RuntimeError("Phase 20 mutation-stage registration unexpectedly succeeded")

    authority_fields = {item.name.lower() for item in fields(Phase21PaperExecutionAuthority)}
    forbidden = (
        "credential",
        "password",
        "secret",
        "token",
        "account_id",
        "provider_order_id",
        "raw_broker",
        "api_key",
    )
    _require(
        not any(term in field for field in authority_fields for term in forbidden),
        f"Phase 21 authority contains forbidden secret/provider identity field: {authority_fields}",
    )

    print("Phase 21 unified paper execution authority validation passed.")
    print(f"policy_fingerprint={fingerprint}")
    print("paper_provider_submit_default=false")
    print("live_execution=false")
    print("automatic_broker_failover=false")
    print("adapter_submit_seam=packages/execution/engine.py")
    print("provider_calls=0")
    print("provider_writes=0")
    print("broker_writes=0")


if __name__ == "__main__":
    main()
