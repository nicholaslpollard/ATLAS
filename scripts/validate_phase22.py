from __future__ import annotations

import ast
from pathlib import Path

from packages.execution.phase22_operator import (
    PHASE22_ARBITRARY_CASE_INPUT_ALLOWED,
    PHASE22_AUTOMATIC_BROKER_FAILOVER,
    PHASE22_BROWSER_EXECUTION_ENABLED,
    PHASE22_DEFAULT_BROKER,
    PHASE22_LIVE_EXECUTION_ENABLED,
    PHASE22_SCHEDULER_EXECUTION_ENABLED,
    phase22_policy_fingerprint,
    phase22_policy_payload,
)
from packages.jobs.phase20_policy import PHASE20_EXTERNAL_MUTATION_STAGE_REGISTRATION_ALLOWED
from packages.schemas.execution import BrokerName


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _raw_adapter_submit_count() -> tuple[int, list[str]]:
    total = 0
    paths: list[str] = []
    for path in sorted((ROOT / "packages").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        count = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "submit":
                continue
            owner = node.func.value
            if isinstance(owner, ast.Name) and owner.id == "adapter":
                count += 1
        if count:
            total += count
            paths.append(relative)
    return total, paths


def main() -> None:
    payload = phase22_policy_payload()
    fingerprint = phase22_policy_fingerprint()
    _require(len(fingerprint) == 64, "Phase 22 policy fingerprint must be sha256")
    _require(fingerprint == phase22_policy_fingerprint(), "Phase 22 policy fingerprint drifted")
    _require(PHASE22_DEFAULT_BROKER == BrokerName.WEBULL, "Webull must remain Phase 22 primary/default")
    _require(payload["environment"] == "paper", "Phase 22 must remain PAPER-only")
    _require(PHASE22_LIVE_EXECUTION_ENABLED is False, "Phase 22 cannot enable LIVE")
    _require(PHASE22_AUTOMATIC_BROKER_FAILOVER is False, "Phase 22 cannot enable automatic failover")
    _require(PHASE22_BROWSER_EXECUTION_ENABLED is False, "Phase 22 cannot give browser execution authority")
    _require(PHASE22_SCHEDULER_EXECUTION_ENABLED is False, "Phase 22 cannot give scheduler execution authority")
    _require(PHASE22_ARBITRARY_CASE_INPUT_ALLOWED is False, "Phase 22 cannot accept arbitrary trade cases")
    _require(
        PHASE20_EXTERNAL_MUTATION_STAGE_REGISTRATION_ALLOWED is False,
        "Phase 20 external mutation stages must remain disabled",
    )

    operator_source = _source("packages/execution/phase22_operator.py")
    _require("Phase15ExecutionRunEngine" in operator_source, "Phase 22 must delegate to Phase 15 run engine")
    _require("authorize_phase21_paper_execution(" in operator_source, "Phase 22 must compose Phase 21 authority")
    _require("require_phase21_paper_execution_authority(" in operator_source, "Phase 22 must prevalidate exact authority")
    _require("environment=PHASE22_ENVIRONMENT" in operator_source, "Phase 22 must hard-bind PAPER environment")
    _require("adapter.submit" not in operator_source, "Phase 22 must not create a provider-submit seam")
    _require("WebullSandboxBroker" not in operator_source, "Phase 22 must not instantiate broker adapters directly")
    _require("AlpacaPaperBroker" not in operator_source, "Phase 22 must not instantiate broker adapters directly")
    _require("Phase15LiveQuoteResolver" not in operator_source, "Phase 22 must not instantiate quote providers directly")

    cli = _source("scripts/run_phase22_paper.py")
    _require('choices=("prepare", "execute")' in cli, "Phase 22 CLI must expose prepare/execute only")
    _require('"--broker"' in cli and '"--as-of"' in cli, "Phase 22 CLI must bind broker and accepted date")
    _require('"--confirmation"' not in cli, "Phase 22 confirmation must not be accepted as a command-line argument")
    _require('"--ticker"' not in cli, "Phase 22 must not expose arbitrary ticker input")
    _require('"--quantity"' not in cli and '"--price"' not in cli, "Phase 22 must not expose order geometry inputs")
    _require("input(\"Type exact confirmation: \"" in cli, "Phase 22 execute must require interactive confirmation")
    _require("ExecutionEnvironment.LIVE" not in cli, "Phase 22 CLI must not expose LIVE")

    raw_count, submit_paths = _raw_adapter_submit_count()
    _require(raw_count == 1, f"expected one raw adapter.submit seam, found {raw_count}")
    _require(
        submit_paths == ["packages/execution/engine.py"],
        f"Phase 22 introduced a submit bypass: {submit_paths}",
    )

    control_plane_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "packages" / "control_plane").glob("*.py"))
    )
    _require(
        "phase22_operator" not in control_plane_source,
        "browser/control plane must not acquire Phase 22 operator authority",
    )

    print("Phase 22 operational PAPER runner validation passed.")
    print(f"policy_fingerprint={fingerprint}")
    print("default_broker=webull")
    print("environment=paper")
    print("confirmation_transport=interactive_stdin")
    print("arbitrary_case_input=false")
    print("live_execution=false")
    print("automatic_broker_failover=false")
    print("browser_execution=false")
    print("scheduler_execution=false")
    print("raw_adapter_submit_count=1")
    print("provider_calls=0")
    print("provider_writes=0")
    print("broker_writes=0")


if __name__ == "__main__":
    main()
