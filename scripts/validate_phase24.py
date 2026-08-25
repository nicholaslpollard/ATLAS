from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase24_gate0 import PHASE24_GATE0_CONTRACT_VERSION
from packages.backtesting.phase24_policy import (
    PHASE24_AUTOMATIC_BROKER_FAILOVER,
    PHASE24_BROKER_READS,
    PHASE24_BROKER_WRITES,
    PHASE24_BROWSER_EXECUTION,
    PHASE24_COUNTERFACTUAL_CURRENT_RULES_ARE_AUTHORITY,
    PHASE24_EXTERNAL_PROVIDER_READS,
    PHASE24_EXTERNAL_PROVIDER_WRITES,
    PHASE24_GATE0_EXPOSE_PROTECTED_CONFIRMATION,
    PHASE24_LIVE_WRITES,
    PHASE24_ORDER_WRITES,
    PHASE24_PAPER_SUBMITS,
    PHASE24_PHASE11_SUPPORT_REPLACEMENT_AUTHORITY,
    PHASE24_POSTGRES_RUNTIME_PROMOTION,
    PHASE24_PRODUCTION_ML_WRITES,
    PHASE24_SCHEDULER_EXECUTION,
    phase24_policy_fingerprint,
)


def _text(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _call_names(path: str) -> set[str]:
    tree = ast.parse(_text(path), filename=path)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
            elif isinstance(node.func, ast.Name):
                names.add(node.func.id)
    return names


def main() -> None:
    diagnostic_path = "packages/backtesting/phase24_gate0.py"
    policy_path = "packages/backtesting/phase24_policy.py"
    cli_path = "scripts/run_phase24_gate0.py"
    diagnostic = _text(diagnostic_path)
    cli = _text(cli_path)
    calls = _call_names(diagnostic_path) | _call_names(cli_path)
    forbidden_calls = {
        "submit",
        "cancel",
        "replace_order",
        "close_position",
        "authorize_phase23_reads",
        "submit_authorized_plan",
    }
    forbidden_import_tokens = (
        "MassiveRESTClient",
        "WebullSandboxBroker",
        "AlpacaPaperBroker",
        "Phase14AuditEngine",
        "Phase22PaperOperator",
    )
    checks = {
        "policy_fingerprint_present": len(phase24_policy_fingerprint()) == 64,
        "provider_reads_disabled": PHASE24_EXTERNAL_PROVIDER_READS is False,
        "provider_writes_disabled": PHASE24_EXTERNAL_PROVIDER_WRITES is False,
        "broker_reads_disabled": PHASE24_BROKER_READS is False,
        "broker_writes_disabled": PHASE24_BROKER_WRITES is False,
        "order_writes_disabled": PHASE24_ORDER_WRITES is False,
        "paper_submits_disabled": PHASE24_PAPER_SUBMITS is False,
        "live_writes_disabled": PHASE24_LIVE_WRITES is False,
        "automatic_failover_disabled": PHASE24_AUTOMATIC_BROKER_FAILOVER is False,
        "browser_execution_disabled": PHASE24_BROWSER_EXECUTION is False,
        "scheduler_execution_disabled": PHASE24_SCHEDULER_EXECUTION is False,
        "postgres_runtime_promotion_disabled": PHASE24_POSTGRES_RUNTIME_PROMOTION is False,
        "production_ml_writes_disabled": PHASE24_PRODUCTION_ML_WRITES is False,
        "phase11_support_replacement_disabled": PHASE24_PHASE11_SUPPORT_REPLACEMENT_AUTHORITY is False,
        "counterfactual_is_non_authoritative": PHASE24_COUNTERFACTUAL_CURRENT_RULES_ARE_AUTHORITY is False,
        "protected_confirmation_exposure_disabled": PHASE24_GATE0_EXPOSE_PROTECTED_CONFIRMATION is False,
        "gate0_contract_present": PHASE24_GATE0_CONTRACT_VERSION in diagnostic,
        "accepted_phase23_strategy_handoff_required": "Phase23CurrentStrategyHandoffStore" in diagnostic
        and "self.phase23.resolve(as_of_date)" in diagnostic,
        "frozen_phase11_study_required": "verify_frozen_study(self.study.report_path)" in diagnostic,
        "candidate_manifest_hash_bound": "handoff.current_candidate_manifest_sha256" in diagnostic
        and "sha256_file(manifest_path)" in diagnostic,
        "current_population_hash_bound": 'manifest.get("all_sha256")' in diagnostic,
        "counterfactual_evaluates_only_eligible_routes": "if not route.eligible" in diagnostic,
        "counterfactual_rows_marked_non_authoritative": '"authoritative": False' in diagnostic,
        "report_records_zero_external_and_execution_writes": all(
            token in diagnostic
            for token in (
                '"external_provider_reads": 0',
                '"external_provider_writes": 0',
                '"broker_reads": 0',
                '"broker_writes": 0',
                '"order_writes": 0',
                '"paper_submits": 0',
                '"live_writes": 0',
                '"phase11_support_writes": 0',
            )
        ),
        "no_forbidden_mutation_calls": not bool(calls.intersection(forbidden_calls)),
        "no_provider_broker_ai_executor_imports": all(token not in diagnostic and token not in cli for token in forbidden_import_tokens),
        "cli_bootstraps_project_root": "sys.path.insert(0, str(PROJECT_ROOT))" in cli,
        "cli_has_no_authority_or_trade_inputs": all(
            token not in cli
            for token in (
                "--confirmation",
                "--broker",
                "--ticker",
                "--quantity",
                "--price",
                "--entry",
                "--stop",
                "--target",
            )
        ),
        "phase24_policy_is_local_readonly": "gate0-local-readonly" in _text(policy_path),
    }
    print(f"Phase 24 policy fingerprint: {phase24_policy_fingerprint()}")
    print(f"Phase 24 Gate 0 contract: {PHASE24_GATE0_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise SystemExit("Phase 24 static validation failed: " + ", ".join(failed))
    print("Phase 24 Strategy Evidence Challenger Gate 0 static contracts: PASS")


if __name__ == "__main__":
    main()
