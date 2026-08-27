from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate5_policy import (  # noqa: E402
    ACCEPTED_GATE0_POLICY_FINGERPRINT,
    ACCEPTED_GATE1_POLICY_FINGERPRINT,
    ACCEPTED_GATE2_POLICY_FINGERPRINT,
    ACCEPTED_GATE3_POLICY_FINGERPRINT,
    ACCEPTED_GATE4_POLICY_FINGERPRINT,
    PHASE25_GATE5_AUTHORIZATION_MODE,
    PHASE25_GATE5_BULK_ACQUISITION_ALLOWED,
    PHASE25_GATE5_DEFER_REGISTRY_REBUILD_UNTIL_COMPLETE,
    PHASE25_GATE5_FORCE_REPLACE_ALLOWED,
    PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED,
    PHASE25_GATE5_PARTIAL_PAIR_FAILS_CLOSED,
    PHASE25_GATE5_PROBE_REFETCH_ALLOWED,
    PHASE25_GATE5_PROVIDER_READ_AUTHORITY_ALLOWED,
    PHASE25_GATE5_PROVIDER_WRITES_ALLOWED,
    PHASE25_GATE5_RESUMABLE_SAME_COMMAND,
    phase25_gate5_policy_fingerprint,
)
from packages.backtesting.phase25_policy import (  # noqa: E402
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
    policy = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate5_policy.py"
    gate5 = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate5.py"
    validation = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate5_validation.py"
    cli = PROJECT_ROOT / "scripts" / "run_phase25_gate5.py"
    tests = PROJECT_ROOT / "tests" / "unit" / "test_phase25_gate5.py"
    spec = PROJECT_ROOT / "docs" / "phase25_historical_production_path_route_fidelity.md"
    workflow = PROJECT_ROOT / ".github" / "workflows" / "atlas-tests.yml"
    required = (policy, gate5, validation, cli, tests, spec, workflow)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Phase25 Gate5 files missing: " + ", ".join(missing))

    policy_text = _source(policy)
    gate5_text = _source(gate5)
    validation_text = _source(validation)
    cli_text = _source(cli)
    tests_text = _source(tests)
    spec_text = _source(spec)
    workflow_text = _source(workflow)
    imports = _imports(gate5_text) | _imports(validation_text) | _imports(cli_text)

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
        "gate5_policy_fingerprint_sha256": len(phase25_gate5_policy_fingerprint()) == 64,
        "accepted_gate0_fingerprint_stable": phase25_gate0_policy_fingerprint() == ACCEPTED_GATE0_POLICY_FINGERPRINT,
        "accepted_gate1_fingerprint_stable": phase25_gate1_policy_fingerprint() == ACCEPTED_GATE1_POLICY_FINGERPRINT,
        "accepted_gate2_fingerprint_stable": phase25_gate2_policy_fingerprint() == ACCEPTED_GATE2_POLICY_FINGERPRINT,
        "accepted_gate3_fingerprint_stable": phase25_gate3_policy_fingerprint() == ACCEPTED_GATE3_POLICY_FINGERPRINT,
        "accepted_gate4_fingerprint_stable": phase25_gate4_policy_fingerprint() == ACCEPTED_GATE4_POLICY_FINGERPRINT,
        "gate5_policy_is_separate_from_prior_policy": "phase25_gate5_policy.py" in str(policy) and "Phase25Gate5Policy" in policy_text,
        "provider_read_authority_bulk_only": PHASE25_GATE5_PROVIDER_READ_AUTHORITY_ALLOWED is True and PHASE25_GATE5_BULK_ACQUISITION_ALLOWED is True,
        "provider_writes_forbidden": PHASE25_GATE5_PROVIDER_WRITES_ALLOWED is False,
        "explicit_cli_is_authorization": PHASE25_GATE5_AUTHORIZATION_MODE == "EXPLICIT_CLI_SUBCOMMAND",
        "interactive_confirmation_removed": PHASE25_GATE5_INTERACTIVE_CONFIRMATION_REQUIRED is False and "input(" not in cli_text,
        "probe_refetch_forbidden": PHASE25_GATE5_PROBE_REFETCH_ALLOWED is False and '"probe_refetch_sessions": 0' in gate5_text,
        "force_replace_forbidden": PHASE25_GATE5_FORCE_REPLACE_ALLOWED is False and "force=True" not in gate5_text,
        "partial_pair_fails_closed_or_reconciles_owned_inflight": PHASE25_GATE5_PARTIAL_PAIR_FAILS_CLOSED is True and "_reconcile_inflight" in gate5_text and "unreconciled partial reference pair" in gate5_text,
        "resumable_same_command": PHASE25_GATE5_RESUMABLE_SAME_COMMAND is True and "resumable_same_command" in gate5_text,
        "registry_rebuild_deferred": PHASE25_GATE5_DEFER_REGISTRY_REBUILD_UNTIL_COMPLETE is True and gate5_text.count(".rebuild_registry()") == 1,
        "does_not_use_per_session_sync_snapshot": "sync_snapshot(" not in gate5_text,
        "uses_atomic_snapshot_and_manifest_primitives": "_write_snapshot(" in gate5_text and "atomic_write_text(" in gate5_text,
        "no_broker_execution_ai_imports": not forbidden_imports,
        "no_strategy_return_or_execution_tokens": not any(token in gate5_text + validation_text for token in forbidden_tokens),
        "gate5_binds_gate3_gate4_and_validation": all(token in gate5_text for token in ("gate3_report_sha256", "gate4_report_sha256", "gate4_validation_sha256")),
        "gate5_excludes_accepted_probe_from_bulk": "bulk_sessions = acquisition_sessions[1:]" in gate5_text and "probe_session in preparation.missing_bulk_sessions" in gate5_text,
        "gate5_active_only_read": "provider.stock_snapshot(session, include_inactive=False)" in gate5_text,
        "gate5_uses_frozen_bulk_scope_only": "for index, session in enumerate(preparation.missing_bulk_sessions" in gate5_text,
        "independent_validator_checks_all_frozen_sessions": "for session in acquisition_sessions" in validation_text and "reference_snapshot_glob" in validation_text,
        "independent_validator_invoked": "Phase25Gate5IndependentValidator" in cli_text and ".run(through_date=args.through)" in cli_text,
        "cli_status_and_acquire_only": 'choices=("status", "acquire")' in cli_text,
        "cli_no_arbitrary_scope_or_confirmation_inputs": all(token not in cli_text for token in ("--ticker", "--date", "--start", "--end", "--force", "--broker", "--limit", "--active", "--confirmation", "--authorize", "--max-sessions")),
        "tests_freeze_all_prior_fingerprints": all(value in tests_text for value in (
            ACCEPTED_GATE0_POLICY_FINGERPRINT,
            ACCEPTED_GATE1_POLICY_FINGERPRINT,
            ACCEPTED_GATE2_POLICY_FINGERPRINT,
            ACCEPTED_GATE3_POLICY_FINGERPRINT,
            ACCEPTED_GATE4_POLICY_FINGERPRINT,
        )),
        "spec_records_gate4_target": all(token in spec_text for token in ("11,027", "12 provider page", "1,252")),
        "spec_locks_no_interactive_for_gate5_reads": "no pasted confirmation" in spec_text.lower() and "EXPLICIT_CLI_SUBCOMMAND" in spec_text,
        "workflow_runs_gate5_validator": "python scripts/validate_phase25_gate5.py" in workflow_text,
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
