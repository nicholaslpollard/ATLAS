from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_policy import (  # noqa: E402
    PHASE25_GATE4_BULK_ACQUISITION_ALLOWED,
    PHASE25_GATE4_MAX_PROBE_SESSIONS,
    PHASE25_GATE4_PROVIDER_READ_AUTHORITY_ALLOWED,
    PHASE25_GATE4_PROVIDER_WRITES_ALLOWED,
    phase25_gate0_policy_fingerprint,
    phase25_gate1_policy_fingerprint,
    phase25_gate2_policy_fingerprint,
    phase25_gate3_policy_fingerprint,
    phase25_gate4_policy_fingerprint,
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
    gate4 = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate4.py"
    validation = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate4_validation.py"
    cli = PROJECT_ROOT / "scripts" / "run_phase25_gate4.py"
    tests = PROJECT_ROOT / "tests" / "unit" / "test_phase25_gate4.py"
    spec = PROJECT_ROOT / "docs" / "phase25_historical_production_path_route_fidelity.md"
    workflow = PROJECT_ROOT / ".github" / "workflows" / "atlas-tests.yml"
    required = (gate4, validation, cli, tests, spec, workflow)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Phase25 Gate4 files missing: " + ", ".join(missing))

    gate4_text = _source(gate4)
    validation_text = _source(validation)
    cli_text = _source(cli)
    tests_text = _source(tests)
    spec_text = _source(spec)
    workflow_text = _source(workflow)
    imports = _imports(gate4_text) | _imports(validation_text) | _imports(cli_text)

    forbidden_import_prefixes = (
        "packages.execution",
        "packages.ai",
        "packages.brokers",
        "packages.operations.phase21",
        "packages.operations.phase22",
    )
    forbidden_imports = sorted(item for item in imports if item.startswith(forbidden_import_prefixes))
    forbidden_tokens = (
        "forward_return",
        "StrategyHistoricalStudy",
        "StrategyEvaluationEngine",
        "adapter.submit",
        "submit_authorized_plan",
        "Phase22PaperRunner",
    )

    checks = {
        "gate4_policy_fingerprint_sha256": len(phase25_gate4_policy_fingerprint()) == 64,
        "accepted_gate0_fingerprint_stable": phase25_gate0_policy_fingerprint() == "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604",
        "accepted_gate1_fingerprint_stable": phase25_gate1_policy_fingerprint() == "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207",
        "accepted_gate2_fingerprint_stable": phase25_gate2_policy_fingerprint() == "417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083",
        "accepted_gate3_fingerprint_stable": phase25_gate3_policy_fingerprint() == "d0e49829132c0c8f2a09c078863ea4871fe36da1067b04c3f367e880a24080b6",
        "provider_read_authority_probe_only": PHASE25_GATE4_PROVIDER_READ_AUTHORITY_ALLOWED is True and PHASE25_GATE4_MAX_PROBE_SESSIONS == 1,
        "provider_writes_forbidden": PHASE25_GATE4_PROVIDER_WRITES_ALLOWED is False,
        "bulk_acquisition_forbidden": PHASE25_GATE4_BULK_ACQUISITION_ALLOWED is False,
        "no_broker_execution_ai_imports": not forbidden_imports,
        "no_strategy_return_or_execution_tokens": not any(token in gate4_text + validation_text for token in forbidden_tokens),
        "gate4_binds_exact_gate3_plan": "gate3_report_sha256" in gate4_text and "gate3_source_fingerprint" in gate4_text,
        "gate4_uses_earliest_frozen_session": "acquisition_sessions[0]" in gate4_text and "entitlement_probe_session" in gate4_text,
        "gate4_exact_active_only_read": "provider.stock_snapshot" in gate4_text and "include_inactive=False" in gate4_text,
        "gate4_only_one_provider_stock_snapshot_call": gate4_text.count("provider.stock_snapshot(") == 1,
        "gate4_validates_rows_before_persistence": gate4_text.find("validate_gate4_probe_rows(rows)") < gate4_text.find("registry.sync_snapshot("),
        "gate4_rechecks_absence_before_persistence": gate4_text.count("_assert_probe_target_absent(preparation.entitlement_probe_session)") >= 2,
        "gate4_no_force_replace": "force=False" in gate4_text and "force=True" not in gate4_text,
        "gate4_persists_active_only": "registry.sync_snapshot" in gate4_text and "include_inactive=False" in gate4_text,
        "gate4_bulk_sessions_zero": '"bulk_acquisition_sessions": 0' in gate4_text,
        "independent_validator_invoked": "Phase25Gate4IndependentValidator" in cli_text and ".run(through_date=args.through)" in cli_text,
        "cli_prepare_and_probe_only": 'choices=("prepare", "probe")' in cli_text,
        "cli_exact_interactive_confirmation": "input(\"Type exact confirmation: \"" in cli_text,
        "cli_no_arbitrary_scope_inputs": all(token not in cli_text for token in ("--ticker", "--date", "--start", "--end", "--force", "--broker", "--limit", "--active")),
        "tests_freeze_prior_fingerprints": all(value in tests_text for value in (
            "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604",
            "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207",
            "417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083",
            "d0e49829132c0c8f2a09c078863ea4871fe36da1067b04c3f367e880a24080b6",
        )),
        "spec_records_gate3_target": "1,253" in spec_text and "2021-08-17" in spec_text and "15,036" in spec_text and "17,542" in spec_text,
        "spec_locks_gate4_probe_no_bulk": "Gate4" in spec_text and "bulk acquisition" in spec_text.lower(),
        "workflow_runs_gate4_validator": "python scripts/validate_phase25_gate4.py" in workflow_text,
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
