from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_policy import (  # noqa: E402
    PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY,
    PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED,
    PHASE25_PROVIDER_READS,
    PHASE25_PROVIDER_WRITES,
    PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED,
    phase25_gate1_policy_fingerprint,
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
    gate1 = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate1.py"
    cli = PROJECT_ROOT / "scripts" / "run_phase25_gate1.py"
    tests = PROJECT_ROOT / "tests" / "unit" / "test_phase25_gate1.py"
    spec = PROJECT_ROOT / "docs" / "phase25_historical_production_path_route_fidelity.md"
    workflow = PROJECT_ROOT / ".github" / "workflows" / "atlas-tests.yml"
    required = (gate1, cli, tests, spec, workflow)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Phase25 Gate1 files missing: " + ", ".join(missing))

    gate1_text = _source(gate1)
    cli_text = _source(cli)
    test_text = _source(tests)
    spec_text = _source(spec)
    workflow_text = _source(workflow)
    imports = _imports(gate1_text) | _imports(cli_text)

    forbidden_import_prefixes = (
        "packages.providers",
        "packages.execution",
        "packages.ai",
        "packages.brokers",
        "packages.operations.phase21",
        "packages.operations.phase22",
    )
    forbidden_imports = sorted(
        item for item in imports if item.startswith(forbidden_import_prefixes)
    )
    forbidden_tokens = (
        "MassiveReferenceProvider",
        "stock_snapshot(",
        "ticker_overview(",
        "ticker_events(",
        "forward_return",
        "StrategyHistoricalStudy",
        "StrategyEvaluationEngine",
        "adapter.submit",
        "submit_authorized_plan",
        "Phase22PaperRunner",
    )

    checks = {
        "gate1_policy_fingerprint_sha256": len(phase25_gate1_policy_fingerprint()) == 64,
        "provider_authority_zero": PHASE25_PROVIDER_READS == PHASE25_PROVIDER_WRITES == 0,
        "future_metadata_authority_forbidden": PHASE25_FUTURE_REFERENCE_METADATA_AUTHORITY_ALLOWED is False,
        "proxy_support_authority_forbidden": PHASE25_PROXY_UNIVERSE_SUPPORT_AUTHORITY_ALLOWED is False,
        "exact_pit_required_for_authoritative_replay": PHASE25_EXACT_PIT_REFERENCE_REQUIRED_FOR_AUTHORITATIVE_PHASE7_REPLAY is True,
        "no_provider_broker_execution_imports": not forbidden_imports,
        "no_provider_or_strategy_return_tokens": not any(token in gate1_text for token in forbidden_tokens),
        "gate1_binds_gate0_report": "gate0_report_sha256" in gate1_text and "Gate0 report contract mismatch" in gate1_text,
        "gate1_uses_gate0_report_policy_field": 'report.get("policy_fingerprint")' in gate1_text and 'report.get("phase25_gate0_policy_fingerprint")' not in gate1_text,
        "gate1_binding_regression_test_present": "test_gate1_binds_to_gate0_report_policy_fingerprint_field" in test_text and '"policy_fingerprint": phase25_gate0_policy_fingerprint()' in test_text,
        "gate1_preserves_provider_symbol_case": "upper(symbol)" not in gate1_text and "lower(symbol)" not in gate1_text,
        "gate1_future_only_is_non_authoritative": "FUTURE_ONLY_REFERENCE" in gate1_text and "bounded_invariant_metadata_proxy_authority" in gate1_text,
        "cli_requires_explicit_through": 'parser.add_argument("--through"' in cli_text and "required=True" in cli_text,
        "cli_has_no_trade_or_authority_inputs": all(token not in cli_text for token in ("--ticker", "--qty", "--price", "--entry", "--stop", "--target", "--broker", "--confirmation", "--authorize")),
        "spec_records_gate0_target_blocker": "1,253" in spec_text and "7 / 1,260" in spec_text,
        "spec_locks_gate1_no_future_authority": "Future-only reference observations may be measured but never treated as PIT authority" in spec_text,
        "workflow_runs_gate1_validator": "python scripts/validate_phase25_gate1.py" in workflow_text,
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
