from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_policy import (  # noqa: E402
    PHASE25_GATE2_DISCOVERY_OVERRIDES_ALLOWED,
    PHASE25_GATE2_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED,
    PHASE25_GATE2_REQUIRES_MATERIALIZED_UNIVERSE_EQUIVALENCE,
    PHASE25_PROVIDER_READS,
    PHASE25_PROVIDER_WRITES,
    phase25_gate0_policy_fingerprint,
    phase25_gate1_policy_fingerprint,
    phase25_gate2_policy_fingerprint,
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
    gate2 = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate2.py"
    cli = PROJECT_ROOT / "scripts" / "run_phase25_gate2.py"
    tests = PROJECT_ROOT / "tests" / "unit" / "test_phase25_gate2.py"
    spec = PROJECT_ROOT / "docs" / "phase25_historical_production_path_route_fidelity.md"
    workflow = PROJECT_ROOT / ".github" / "workflows" / "atlas-tests.yml"
    required = (gate2, cli, tests, spec, workflow)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Phase25 Gate2 files missing: " + ", ".join(missing))

    gate2_text = _source(gate2)
    cli_text = _source(cli)
    tests_text = _source(tests)
    spec_text = _source(spec)
    workflow_text = _source(workflow)
    imports = _imports(gate2_text) | _imports(cli_text)

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
        "MassiveRESTClient",
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
        "gate2_policy_fingerprint_sha256": len(phase25_gate2_policy_fingerprint()) == 64,
        "accepted_gate0_fingerprint_stable": phase25_gate0_policy_fingerprint() == "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604",
        "accepted_gate1_fingerprint_stable": phase25_gate1_policy_fingerprint() == "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207",
        "provider_authority_zero": PHASE25_PROVIDER_READS == PHASE25_PROVIDER_WRITES == 0,
        "gate2_acquisition_authority_forbidden": PHASE25_GATE2_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED is False,
        "discovery_overrides_forbidden": PHASE25_GATE2_DISCOVERY_OVERRIDES_ALLOWED is False,
        "materialized_equivalence_required": PHASE25_GATE2_REQUIRES_MATERIALIZED_UNIVERSE_EQUIVALENCE is True,
        "no_provider_broker_execution_imports": not forbidden_imports,
        "no_provider_or_strategy_return_tokens": not any(token in gate2_text for token in forbidden_tokens),
        "gate2_binds_gate1_report": "gate1_report_sha256" in gate2_text and "Gate1 policy fingerprint mismatch" in gate2_text,
        "gate2_requires_full_snapshot_for_proof": "include_inactive" in gate2_text and "requires a full active+inactive reference snapshot" in gate2_text,
        "gate2_filters_active_rows_locally": "active_rows = [row for row in rows if bool(row.get(\"active\"))]" in gate2_text,
        "gate2_compares_materialized_universe": "active_only_vs_materialized_mismatch_count" in gate2_text and "source_reference_sha256" in gate2_text,
        "gate2_preserves_provider_symbol_case": "upper(ticker)" not in gate2_text and "lower(ticker)" not in gate2_text,
        "gate2_output_has_no_acquisition_authority": '"active_only_reference_acquisition_authority": False' in gate2_text,
        "cli_requires_explicit_through": 'parser.add_argument("--through"' in cli_text and "required=True" in cli_text,
        "cli_has_no_trade_or_authority_inputs": all(token not in cli_text for token in ("--ticker", "--qty", "--price", "--entry", "--stop", "--target", "--broker", "--confirmation", "--authorize", "--execute")),
        "tests_freeze_prior_fingerprints": "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604" in tests_text and "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207" in tests_text,
        "spec_records_gate1_target": "11,329" in spec_text and "8,449" in spec_text and "2,400" in spec_text,
        "spec_locks_gate2_no_provider_authority": "Gate2 does not grant provider-read authority" in spec_text,
        "workflow_runs_gate2_validator": "python scripts/validate_phase25_gate2.py" in workflow_text,
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
