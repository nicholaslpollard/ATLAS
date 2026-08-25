from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate5_policy import phase25_gate5_policy_fingerprint  # noqa: E402
from packages.backtesting.phase25_gate6_policy import (  # noqa: E402
    ACCEPTED_GATE5_POLICY_FINGERPRINT,
    PHASE25_GATE6_OPERATIONAL_DISCOVERY_STATE_WRITES_ALLOWED,
    PHASE25_GATE6_OVERWRITE_EXISTING_ARTIFACTS_ALLOWED,
    PHASE25_GATE6_PROVIDER_READS,
    PHASE25_GATE6_PROVIDER_WRITES,
    PHASE25_GATE6_REGIME_ROUTING_ALLOWED,
    PHASE25_GATE6_STRATEGY_RETURNS_READ_ALLOWED,
    PHASE25_GATE6_STRATEGY_RULE_EVALUATION_ALLOWED,
    PHASE25_GATE6_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate6_policy_fingerprint,
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _imports(text: str) -> set[str]:
    tree = ast.parse(text)
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def main() -> int:
    gate6 = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate6.py"
    repair = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate6_repair.py"
    policy = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate6_policy.py"
    gate5_policy = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate5_policy.py"
    validation = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate6_validation.py"
    cli = PROJECT_ROOT / "scripts" / "run_phase25_gate6.py"
    tests = PROJECT_ROOT / "tests" / "unit" / "test_phase25_gate6.py"
    spec = PROJECT_ROOT / "docs" / "phase25_gate6_discovery_reconstruction.md"
    workflow = PROJECT_ROOT / ".github" / "workflows" / "atlas-tests.yml"
    required = (gate6, repair, policy, gate5_policy, validation, cli, tests, spec, workflow)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Phase25 Gate6 files missing: " + ", ".join(missing))

    gate6_text = _source(gate6)
    repair_text = _source(repair)
    policy_text = _source(policy)
    gate5_policy_text = _source(gate5_policy)
    validation_text = _source(validation)
    cli_text = _source(cli)
    tests_text = _source(tests)
    spec_text = _source(spec)
    workflow_text = _source(workflow)
    imports = _imports(gate6_text) | _imports(repair_text) | _imports(validation_text) | _imports(cli_text)

    forbidden_import_prefixes = (
        "packages.execution",
        "packages.brokers",
        "packages.ai",
        "packages.operations.phase21",
        "packages.operations.phase22",
        "packages.regimes",
        "packages.backtesting.historical_study",
        "packages.backtesting.strategy_evaluation",
    )
    forbidden_imports = sorted(item for item in imports if item.startswith(forbidden_import_prefixes))
    forbidden_tokens = (
        "provider.stock_snapshot(",
        "MassiveRESTClient(",
        "MassiveReferenceProvider(",
        "DiscoveryStateManager(",
        "TickerStateEngine(",
        "RegimeStateEngine(",
        "forward_return",
        "StrategyHistoricalStudy",
        "StrategyEvaluationEngine",
        "adapter.submit",
        "submit_authorized_plan",
    )
    combined = gate6_text + repair_text + validation_text + cli_text
    frozen_policy_text = policy_text + gate5_policy_text

    universe_existing_pos = repair_text.find("if universe_existing:")
    universe_build_pos = repair_text.find("UniverseManager(self.settings).build(session, force=False)")
    foundation_existing_pos = repair_text.find("if foundation_existing:")
    foundation_build_pos = repair_text.find("DiscoveryFoundationScanner(self.settings).build(session)")
    score_existing_pos = repair_text.find("if score_existing:")
    score_build_pos = repair_text.find("DiscoverySetupScanner(self.settings).build(session)")

    checks = {
        "gate6_policy_fingerprint_sha256": len(phase25_gate6_policy_fingerprint()) == 64,
        "accepted_gate5_fingerprint_stable": phase25_gate5_policy_fingerprint() == ACCEPTED_GATE5_POLICY_FINGERPRINT == "0e2060d91838c506d8b7c720fd38c06186dac8e4b4587385079b49cae519b8a0",
        "prior_fingerprints_literal_locked": all(value in frozen_policy_text for value in (
            "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604",
            "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207",
            "417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083",
            "d0e49829132c0c8f2a09c078863ea4871fe36da1067b04c3f367e880a24080b6",
            "e8ef1b2f0d020e579e4c8fc92dfa256fea307ce96ed89cee02c4a812b8398d16",
            "0e2060d91838c506d8b7c720fd38c06186dac8e4b4587385079b49cae519b8a0",
        )),
        "provider_activity_zero": PHASE25_GATE6_PROVIDER_READS == PHASE25_GATE6_PROVIDER_WRITES == 0,
        "overwrite_forbidden": PHASE25_GATE6_OVERWRITE_EXISTING_ARTIFACTS_ALLOWED is False and "force=True" not in repair_text,
        "operational_discovery_state_writes_forbidden": PHASE25_GATE6_OPERATIONAL_DISCOVERY_STATE_WRITES_ALLOWED is False and "DiscoveryStateManager(" not in repair_text,
        "regime_routing_forbidden": PHASE25_GATE6_REGIME_ROUTING_ALLOWED is False,
        "strategy_returns_forbidden": PHASE25_GATE6_STRATEGY_RETURNS_READ_ALLOWED is False,
        "strategy_rules_forbidden": PHASE25_GATE6_STRATEGY_RULE_EVALUATION_ALLOWED is False,
        "support_replacement_forbidden": PHASE25_GATE6_SUPPORT_REPLACEMENT_ALLOWED is False,
        "no_provider_broker_execution_regime_imports": not forbidden_imports,
        "no_provider_strategy_execution_tokens": not any(token in combined for token in forbidden_tokens),
        "cli_uses_safe_reconstruction": "Phase25Gate6SafeDiscoveryReconstruction" in cli_text and "Phase25Gate6DiscoveryReconstruction(settings).run" not in cli_text,
        "preflight_universe_before_builder": 0 <= universe_existing_pos < universe_build_pos,
        "preflight_foundation_before_builder": 0 <= foundation_existing_pos < foundation_build_pos,
        "preflight_score_before_builder": 0 <= score_existing_pos < score_build_pos,
        "existing_universe_read_validation": "source_reference_sha256" in repair_text and "routing_input_fingerprint" in repair_text and "snapshot_sha" in repair_text,
        "existing_foundation_read_validation": "_existing_current(" in repair_text and "Gate6 preflight refuses overwrite" in repair_text,
        "semantic_score_reconciliation_locked": "_score_interface_mismatch_count" in repair_text and "PRESERVE_STALE_HASH_IF_SCORING_INTERFACE_EXACT" in repair_text and "semantic mismatches=" in repair_text,
        "uses_production_phase7_for_missing_only": universe_build_pos >= 0,
        "uses_production_foundation_for_missing_only": foundation_build_pos >= 0,
        "uses_production_scoring_for_missing_only": score_build_pos >= 0,
        "uses_accepted_hysteresis_policy": "ACTIVE_DISCOVERY_PERSISTENCE_POLICY.bootstrap" in gate6_text and "ACTIVE_DISCOVERY_PERSISTENCE_POLICY.transition" in gate6_text,
        "research_population_only": "warm_hot_directional_population.parquet" in gate6_text and '"operational_discovery_state_writes": 0' in gate6_text,
        "binds_gate5_report_and_validation": "gate5_report_sha256" in gate6_text and "gate5_validation_sha256" in gate6_text,
        "partial_sets_fail_closed": "unreconciled partial" in gate6_text,
        "cli_has_no_authority_or_scope_override_args": all(token not in cli_text for token in ("--ticker", "--date", "--start", "--end", "--force", "--broker", "--confirm", "input(")),
        "tests_freeze_gate5": "0e2060d91838c506d8b7c720fd38c06186dac8e4b4587385079b49cae519b8a0" in tests_text,
        "spec_records_gate5_target": "15,430" in spec_text and "1,252" in spec_text and "11,027" in spec_text,
        "spec_locks_gate6_provider_free": "Gate 6" in spec_text and "provider-free" in spec_text.lower(),
        "workflow_runs_gate6_validator": "python scripts/validate_phase25_gate6.py" in workflow_text,
    }
    for name, passed in checks.items():
        print(f"{name}: {passed}")
    if forbidden_imports:
        print("forbidden_imports:", forbidden_imports)
    passed = all(checks.values())
    print(f"Pass: {passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
