from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_policy import (  # noqa: E402
    PHASE25_GATE3_ACTIVE,
    PHASE25_GATE3_EARLIEST_SESSION_ENTITLEMENT_PROBE_REQUIRED,
    PHASE25_GATE3_ENDPOINT,
    PHASE25_GATE3_EXISTING_VALID_REFERENCE_PRESERVED,
    PHASE25_GATE3_FORCE_REPLACE_EXISTING_REFERENCE,
    PHASE25_GATE3_INCLUDE_INACTIVE,
    PHASE25_GATE3_MARKET,
    PHASE25_GATE3_PAGE_LIMIT,
    PHASE25_GATE3_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED,
    PHASE25_PROVIDER_READS,
    PHASE25_PROVIDER_WRITES,
    phase25_gate0_policy_fingerprint,
    phase25_gate1_policy_fingerprint,
    phase25_gate2_policy_fingerprint,
    phase25_gate3_policy_fingerprint,
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
    gate3 = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate3.py"
    cli = PROJECT_ROOT / "scripts" / "run_phase25_gate3.py"
    tests = PROJECT_ROOT / "tests" / "unit" / "test_phase25_gate3.py"
    spec = PROJECT_ROOT / "docs" / "phase25_historical_production_path_route_fidelity.md"
    workflow = PROJECT_ROOT / ".github" / "workflows" / "atlas-tests.yml"
    required = (gate3, cli, tests, spec, workflow)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Phase25 Gate3 files missing: " + ", ".join(missing))

    gate3_text = _source(gate3)
    cli_text = _source(cli)
    tests_text = _source(tests)
    spec_text = _source(spec)
    workflow_text = _source(workflow)
    imports = _imports(gate3_text) | _imports(cli_text)

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
        "InstrumentRegistryStore",
        "stock_snapshot(",
        "list_tickers(",
        "get_json(",
        "forward_return",
        "StrategyHistoricalStudy",
        "StrategyEvaluationEngine",
        "adapter.submit",
        "submit_authorized_plan",
        "Phase22PaperRunner",
    )

    checks = {
        "gate3_policy_fingerprint_sha256": len(phase25_gate3_policy_fingerprint()) == 64,
        "accepted_gate0_fingerprint_stable": phase25_gate0_policy_fingerprint() == "994b05f2bc7fd8329578e0ca2a621de2602d2d71e7f8c06101a22b9ca9468604",
        "accepted_gate1_fingerprint_stable": phase25_gate1_policy_fingerprint() == "1c134efdb64ad8ccd527be2ca870d5f3eddba3f6538654e68ca06f0aa4f64207",
        "accepted_gate2_fingerprint_stable": phase25_gate2_policy_fingerprint() == "417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083",
        "provider_authority_zero": PHASE25_PROVIDER_READS == PHASE25_PROVIDER_WRITES == 0,
        "gate3_acquisition_authority_forbidden": PHASE25_GATE3_PROVIDER_ACQUISITION_AUTHORITY_ALLOWED is False,
        "exact_endpoint_locked": PHASE25_GATE3_ENDPOINT == "/v3/reference/tickers",
        "exact_market_active_locked": PHASE25_GATE3_MARKET == "stocks" and PHASE25_GATE3_ACTIVE is True,
        "max_page_limit_locked": PHASE25_GATE3_PAGE_LIMIT == 1000,
        "inactive_rows_not_requested": PHASE25_GATE3_INCLUDE_INACTIVE is False,
        "existing_pairs_preserved": PHASE25_GATE3_EXISTING_VALID_REFERENCE_PRESERVED is True,
        "force_replace_forbidden": PHASE25_GATE3_FORCE_REPLACE_EXISTING_REFERENCE is False,
        "entitlement_probe_preregistered": PHASE25_GATE3_EARLIEST_SESSION_ENTITLEMENT_PROBE_REQUIRED is True,
        "no_provider_broker_execution_imports": not forbidden_imports,
        "no_provider_or_strategy_return_tokens": not any(token in gate3_text for token in forbidden_tokens),
        "gate3_binds_gate2_report": "gate2_report_sha256" in gate3_text and "Gate2 policy fingerprint mismatch" in gate3_text,
        "gate3_enumerates_exact_exchange_sessions": "sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, through_date)" in gate3_text,
        "partial_reference_state_fails_closed": "partial reference state requires manual reconciliation" in gate3_text,
        "exact_active_only_query_persisted": '"endpoint": PHASE25_GATE3_ENDPOINT' in gate3_text and '"date": "EXACT_SESSION_DATE"' in gate3_text,
        "gate4_separate_authority_required": '"separate_explicit_run_scoped_read_authority": True' in gate3_text,
        "entitlement_probe_first": '"earliest_missing_session_entitlement_probe_first"' in gate3_text,
        "no_blind_partial_retry": '"no_blind_retry_after_unreconciled_partial_session": True' in gate3_text,
        "cli_requires_explicit_through": 'parser.add_argument("--through"' in cli_text and "required=True" in cli_text,
        "cli_has_no_execute_or_authority_inputs": all(token not in cli_text for token in ("--ticker", "--broker", "--confirmation", "--authorize", "--execute", "--force")),
        "tests_freeze_gate2_fingerprint": "417ef8af0b463a6983e6b54cfb510d8f556245c87818f8b8e24d90737049f083" in tests_text,
        "spec_records_gate2_target": "63.61%" in spec_text and "246,631" in spec_text and "89,755" in spec_text,
        "spec_locks_gate3_provider_free": "Gate3 does not grant provider-read authority" in spec_text,
        "workflow_runs_gate3_validator": "python scripts/validate_phase25_gate3.py" in workflow_text,
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
