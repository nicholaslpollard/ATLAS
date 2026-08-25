from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.operations.phase23_handoff import PHASE23_ANALYSIS_HANDOFF_CONTRACT_VERSION
from packages.operations.phase23_policy import (
    MASSIVE_MARKET_REFERENCE_READS,
    PHASE23_ALLOWED_BROKERS,
    PHASE23_ARBITRARY_CASE_INPUT_ALLOWED,
    PHASE23_AUTOMATIC_BROKER_FAILOVER,
    PHASE23_BROKER_MUTATIONS_ALLOWED,
    PHASE23_BROWSER_EXECUTION_ENABLED,
    PHASE23_DEFAULT_BROKER,
    PHASE23_EXTERNAL_READ_CLASSES,
    PHASE23_FROZEN_SUPPORTED_STRATEGIES,
    PHASE23_LIVE_EXECUTION_ENABLED,
    PHASE23_ORDER_WRITES_ALLOWED,
    PHASE23_PAPER_SUBMIT_AUTHORITY_ALLOWED,
    PHASE23_POSTGRES_RUNTIME_REQUIRED,
    PHASE23_SCHEDULER_EXECUTION_ENABLED,
    phase23_policy_fingerprint,
    phase23_policy_payload,
)
from packages.operations.phase23_strategy import PHASE23_CURRENT_STRATEGY_HANDOFF_CONTRACT_VERSION
from packages.operations.phase23_validation import PHASE23_INDEPENDENT_VALIDATION_CONTRACT_VERSION
from packages.schemas.execution import BrokerName


def _text(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _raw_submit_sites() -> list[str]:
    sites: list[str] = []
    needle = "adapter.submit(plan)"
    for path in sorted((PROJECT_ROOT / "packages").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if needle in text:
            sites.extend([str(path.relative_to(PROJECT_ROOT))] * text.count(needle))
    return sites


def _phase23_call_names() -> set[str]:
    names: set[str] = set()
    for relative in (
        "packages/operations/phase23_current_run.py",
        "packages/operations/phase23_handoff.py",
        "packages/operations/phase23_policy.py",
        "packages/operations/phase23_strategy.py",
    ):
        tree = ast.parse(_text(relative), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    names.add(node.func.attr)
                elif isinstance(node.func, ast.Name):
                    names.add(node.func.id)
    return names


def main() -> None:
    policy = phase23_policy_payload()
    current_run = _text("packages/operations/phase23_current_run.py")
    handoff = _text("packages/operations/phase23_handoff.py")
    strategy = _text("packages/operations/phase23_strategy.py")
    persisted_validation = _text("packages/operations/phase23_validation.py")
    phase12_source = _text("packages/analogues/source.py")
    phase12_closeout = _text("packages/analogues/phase12_closeout.py")
    phase15_source = _text("packages/execution/phase15_source.py")
    cli = _text("scripts/run_phase23_analysis.py")
    call_names = _phase23_call_names()
    raw_submit_sites = _raw_submit_sites()

    forbidden_phase23_mutation_calls = {"submit", "cancel", "close_position", "replace_order"}
    phase12_uses_phase23_handoff = (
        "Phase23CurrentStrategyHandoffStore" in phase12_source
        and "self.phase23_strategy.resolve(as_of_date)" in phase12_source
        and "requested post-Phase11 date requires an accepted Phase 23 current-strategy handoff"
        in phase12_source
        and "PHASE23_CURRENT_STRATEGY_HANDOFF_CONTRACT_VERSION" in phase12_closeout
    )
    persisted_validator_is_readonly = all(
        token not in persisted_validation
        for token in (
            ".submit(",
            ".cancel(",
            ".close_position(",
            "MassiveRESTClient(",
            "WebullSandboxBroker(",
            "AlpacaPaperBroker(",
            "Phase14AuditEngine(",
        )
    )
    checks = {
        "policy_fingerprint_present": len(phase23_policy_fingerprint()) == 64,
        "webull_primary": PHASE23_DEFAULT_BROKER == BrokerName.WEBULL,
        "alpaca_manual_secondary_only": PHASE23_ALLOWED_BROKERS
        == (BrokerName.WEBULL, BrokerName.ALPACA),
        "external_read_scope_narrowed_to_market_reference_only": PHASE23_EXTERNAL_READ_CLASSES
        == (MASSIVE_MARKET_REFERENCE_READS,),
        "downstream_external_reads_unreachable_under_frozen_support": policy.get(
            "downstream_external_reads_reachable"
        )
        is False,
        "live_disabled": PHASE23_LIVE_EXECUTION_ENABLED is False,
        "automatic_failover_disabled": PHASE23_AUTOMATIC_BROKER_FAILOVER is False,
        "browser_execution_disabled": PHASE23_BROWSER_EXECUTION_ENABLED is False,
        "scheduler_execution_disabled": PHASE23_SCHEDULER_EXECUTION_ENABLED is False,
        "postgres_runtime_not_required": PHASE23_POSTGRES_RUNTIME_REQUIRED is False,
        "broker_mutations_disabled": PHASE23_BROKER_MUTATIONS_ALLOWED is False,
        "order_writes_disabled": PHASE23_ORDER_WRITES_ALLOWED is False,
        "paper_submit_authority_disabled": PHASE23_PAPER_SUBMIT_AUTHORITY_ALLOWED is False,
        "arbitrary_case_input_disabled": PHASE23_ARBITRARY_CASE_INPUT_ALLOWED is False,
        "zero_supported_strategies_frozen": PHASE23_FROZEN_SUPPORTED_STRATEGIES == (),
        "zero_promotion_expected_under_frozen_support": policy.get(
            "zero_promotion_is_expected_under_frozen_support"
        )
        is True,
        "routine_historical_study_rerun_disabled": policy.get(
            "historical_strategy_study_rerun_in_routine_cycle"
        )
        is False
        and "study.run(" not in current_run,
        "current_cycle_uses_existing_historical_study_only": "StrategyHistoricalStudy(self.settings)"
        in current_run
        and "verify_frozen_study(study.report_path)" in current_run,
        "phase23_has_no_broker_mutation_calls": not bool(
            call_names.intersection(forbidden_phase23_mutation_calls)
        ),
        "phase23_does_not_import_phase22_executor": "phase22_operator" not in current_run.lower()
        and "Phase22PaperOperator" not in current_run,
        "phase23_does_not_acquire_phase21_submit_authority": "phase21_authority" not in current_run.lower()
        and "submit_authorized_plan" not in current_run,
        "exactly_one_raw_submit_seam_remains": raw_submit_sites
        == ["packages/execution/engine.py"],
        "handoff_allows_local_analytical_persistence": '"local_analytical_writes_allowed": True'
        in handoff,
        "handoff_forbids_external_mutations": '"external_provider_mutation_writes": 0'
        in handoff
        and '"broker_writes": 0' in handoff
        and '"order_writes": 0' in handoff
        and '"paper_submits": 0' in handoff
        and '"live_writes": 0' in handoff,
        "handoff_does_not_mislabel_local_canonical_writes_zero": '"canonical_writes": 0'
        not in handoff,
        "strategy_handoff_contract_present": PHASE23_CURRENT_STRATEGY_HANDOFF_CONTRACT_VERSION
        in strategy,
        "analysis_handoff_contract_present": PHASE23_ANALYSIS_HANDOFF_CONTRACT_VERSION in handoff,
        "phase12_accepts_phase23_strategy_authority": phase12_uses_phase23_handoff,
        "phase15_requires_phase23_extension_after_frozen_endpoint": "Phase23AnalysisHandoffStore"
        in phase15_source
        and "phase23_handoff" in phase15_source,
        "independent_persisted_validator_contract_present": PHASE23_INDEPENDENT_VALIDATION_CONTRACT_VERSION
        in persisted_validation,
        "independent_persisted_validator_readonly": persisted_validator_is_readonly,
        "cli_runs_independent_validation_after_execute": "Phase23RunIndependentValidator(settings).run("
        in cli,
        "validator_entrypoint_bootstraps_project_root": "sys.path.insert(0, str(PROJECT_ROOT))" in _text(
            "scripts/validate_phase23.py"
        ),
        "cli_entrypoint_bootstraps_project_root": "sys.path.insert(0, str(PROJECT_ROOT))" in cli,
        "cli_prepare_execute_only": 'choices=("prepare", "execute")' in cli,
        "cli_confirmation_not_shell_argument": "--confirmation" not in cli and "input(" in cli,
        "cli_no_arbitrary_trade_inputs": all(
            token not in cli
            for token in ("--ticker", "--quantity", "--price", "--entry", "--stop", "--target")
        ),
    }

    print(f"Phase 23 policy fingerprint: {phase23_policy_fingerprint()}")
    print(f"Phase 23 current strategy handoff: {PHASE23_CURRENT_STRATEGY_HANDOFF_CONTRACT_VERSION}")
    print(f"Phase 23 analysis handoff: {PHASE23_ANALYSIS_HANDOFF_CONTRACT_VERSION}")
    print(f"Phase 23 independent validation: {PHASE23_INDEPENDENT_VALIDATION_CONTRACT_VERSION}")
    print(f"Phase 23 raw adapter.submit(plan) sites: {raw_submit_sites}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise SystemExit("Phase 23 static validation failed: " + ", ".join(failed))
    print("Phase 23 Operational Current Analysis Cycle static contracts: PASS")


if __name__ == "__main__":
    main()
