from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate6_policy import phase25_gate6_policy_fingerprint  # noqa: E402
from packages.backtesting.phase25_gate7_policy import (  # noqa: E402
    ACCEPTED_GATE6_POLICY_FINGERPRINT,
    PHASE25_GATE7_OPERATIONAL_REGIME_WRITES_ALLOWED,
    PHASE25_GATE7_PROVIDER_READS,
    PHASE25_GATE7_PROVIDER_WRITES,
    PHASE25_GATE7_SECTOR_MAPPING_AUTHORITY,
    PHASE25_GATE7_STRATEGY_RETURNS_READ_ALLOWED,
    PHASE25_GATE7_STRATEGY_ROUTING_ALLOWED,
    PHASE25_GATE7_STRATEGY_RULE_EVALUATION_ALLOWED,
    PHASE25_GATE7_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate7_policy_fingerprint,
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
    gate7 = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate7.py"
    policy = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate7_policy.py"
    validation = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate7_validation.py"
    cli = PROJECT_ROOT / "scripts" / "run_phase25_gate7.py"
    tests = PROJECT_ROOT / "tests" / "unit" / "test_phase25_gate7.py"
    spec = PROJECT_ROOT / "docs" / "phase25_gate7_route_context.md"
    workflow = PROJECT_ROOT / ".github" / "workflows" / "atlas-tests.yml"
    required = (gate7, policy, validation, cli, tests, spec, workflow)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Phase25 Gate7 files missing: " + ", ".join(missing))

    gate7_text = _source(gate7)
    policy_text = _source(policy)
    validation_text = _source(validation)
    cli_text = _source(cli)
    tests_text = _source(tests)
    spec_text = _source(spec)
    workflow_text = _source(workflow)
    imports = _imports(gate7_text) | _imports(validation_text) | _imports(cli_text)

    forbidden_import_prefixes = (
        "packages.execution",
        "packages.brokers",
        "packages.ai",
        "packages.operations.phase21",
        "packages.operations.phase22",
        "packages.backtesting.historical_study",
        "packages.backtesting.strategy_evaluation",
    )
    forbidden_imports = sorted(item for item in imports if item.startswith(forbidden_import_prefixes))
    forbidden_tokens = (
        "provider.stock_snapshot(",
        "MassiveRESTClient(",
        "MassiveReferenceProvider(",
        "adapter.submit",
        "submit_authorized_plan",
        "forward_return",
        "StrategyHistoricalStudy",
        "StrategyEvaluationEngine",
        ".evaluate(strategy_context)",
        "strategy.evaluate(",
    )
    combined = gate7_text + validation_text + cli_text

    checks = {
        "gate7_policy_fingerprint_sha256": len(phase25_gate7_policy_fingerprint()) == 64,
        "accepted_gate6_fingerprint_stable": phase25_gate6_policy_fingerprint() == ACCEPTED_GATE6_POLICY_FINGERPRINT == "5ee92c766031fcf02bf8b80d9a1f4366e7bb6faa8c3634236ad438ef11f52da0",
        "gate6_fingerprint_literal_locked": "5ee92c766031fcf02bf8b80d9a1f4366e7bb6faa8c3634236ad438ef11f52da0" in policy_text and "5ee92c766031fcf02bf8b80d9a1f4366e7bb6faa8c3634236ad438ef11f52da0" in tests_text,
        "provider_activity_zero": PHASE25_GATE7_PROVIDER_READS == PHASE25_GATE7_PROVIDER_WRITES == 0,
        "operational_regime_writes_forbidden": PHASE25_GATE7_OPERATIONAL_REGIME_WRITES_ALLOWED is False,
        "sector_mapping_forbidden": PHASE25_GATE7_SECTOR_MAPPING_AUTHORITY is False and '"sector_state"] = None' in gate7_text,
        "strategy_routing_enabled": PHASE25_GATE7_STRATEGY_ROUTING_ALLOWED is True and "StrategyRouter(" in gate7_text,
        "strategy_rules_forbidden": PHASE25_GATE7_STRATEGY_RULE_EVALUATION_ALLOWED is False,
        "strategy_returns_forbidden": PHASE25_GATE7_STRATEGY_RETURNS_READ_ALLOWED is False,
        "support_replacement_forbidden": PHASE25_GATE7_SUPPORT_REPLACEMENT_ALLOWED is False,
        "no_provider_broker_execution_imports": not forbidden_imports,
        "no_provider_rule_return_execution_tokens": not any(token in combined for token in forbidden_tokens),
        "binds_gate6_report_validation_population": all(token in gate7_text for token in ("gate6_report_sha256", "gate6_validation_sha256", "gate6_population_sha256")),
        "uses_exact_pit_reference_glob": "reference_snapshot_glob()" in gate7_text and "coalesce(r.active, FALSE) = TRUE" in gate7_text,
        "exact_interval_resets_on_gap": "session_ordinal <> previous_ordinal + 1" in gate7_text,
        "uses_split_origin_market_policy": "MARKET_SECTOR_HISTORY_ORIGIN_DATE" in gate7_text and "compute_regime_state_history" in gate7_text,
        "uses_accepted_ticker_confirmation": "TICKER_SELECTED_CONFIRMATION_SESSIONS" in gate7_text and "confirm_states(" in gate7_text,
        "uses_production_router": "StrategyRoutingContext(" in gate7_text and "self.router.route(" in gate7_text,
        "sector_unavailable_nonblocking_tested": "sector_unavailable_is_nonblocking" in tests_text,
        "cli_has_no_authority_or_scope_override_args": all(token not in cli_text for token in ("--ticker", "--date", "--start", "--end", "--force", "--broker", "--confirm", "input(")),
        "spec_records_gate6_target": "23,177" in spec_text and "1,260" in spec_text and "Reconciliation events: **1**" in spec_text,
        "spec_locks_no_strategy_rules_returns": "strategy-rule evaluation" in spec_text.lower() and "forward returns" in spec_text.lower(),
        "workflow_runs_gate7_validator": "python scripts/validate_phase25_gate7.py" in workflow_text,
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
