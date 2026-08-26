from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate7_policy import phase25_gate7_policy_fingerprint  # noqa: E402
from packages.backtesting.phase25_gate8_policy import (  # noqa: E402
    ACCEPTED_GATE7_POLICY_FINGERPRINT,
    PHASE25_GATE8_DEVELOPMENT_END,
    PHASE25_GATE8_PROTECTED_EVIDENCE_ALLOWED,
    PHASE25_GATE8_PROTECTED_START,
    PHASE25_GATE8_SUPPORT_REPLACEMENT_ALLOWED,
    PHASE25_GATE9_MULTIPLE_TESTING_METHOD,
    PHASE25_GATE9_PROTECTED_EVIDENCE_ALLOWED,
    PHASE25_GATE9_SUPPORT_REPLACEMENT_ALLOWED,
    PHASE25_GATE10_FINALISTS_ONLY,
    PHASE25_GATE10_PROTECTED_EVIDENCE_ALLOWED,
    PHASE25_GATE10_PROTECTED_EVIDENCE_FRESH,
    PHASE25_GATE10_SUPPORT_REPLACEMENT_ALLOWED,
    PHASE25_GATE10_ZERO_FINALISTS_ZERO_PROTECTED_READS,
    PHASE25_GATE11_FUTURE_PROSPECTIVE_REQUIRED_FOR_AUTHORITY,
    PHASE25_GATE11_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate8_policy_fingerprint,
    phase25_gate9_policy_fingerprint,
    phase25_gate10_policy_fingerprint,
    phase25_gate11_policy_fingerprint,
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
    files = {
        "policy": PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate8_policy.py",
        "gate8": PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate8.py",
        "gate8v": PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate8_validation.py",
        "gate9": PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate9.py",
        "gate9v": PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate9_validation.py",
        "gate10": PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate10.py",
        "gate10v": PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate10_validation.py",
        "gate11": PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate11.py",
        "gate11v": PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate11_validation.py",
        "cli": PROJECT_ROOT / "scripts" / "run_phase25_cumulative.py",
        "tests": PROJECT_ROOT / "tests" / "unit" / "test_phase25_remaining.py",
        "spec": PROJECT_ROOT / "docs" / "phase25_remaining_evidence.md",
        "workflow": PROJECT_ROOT / ".github" / "workflows" / "atlas-tests.yml",
    }
    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        raise SystemExit("Phase25 remaining-gate files missing: " + ", ".join(missing))
    text = {name: _source(path) for name, path in files.items()}
    code = "\n".join(text[name] for name in ("gate8", "gate8v", "gate9", "gate9v", "gate10", "gate10v", "gate11", "gate11v", "cli"))
    imports: set[str] = set()
    for name in ("gate8", "gate8v", "gate9", "gate9v", "gate10", "gate10v", "gate11", "gate11v", "cli"):
        imports |= _imports(text[name])
    forbidden_prefixes = (
        "packages.execution",
        "packages.brokers",
        "packages.ai",
        "packages.operations.phase21",
        "packages.operations.phase22",
        "packages.providers",
    )
    forbidden_imports = sorted(item for item in imports if item.startswith(forbidden_prefixes))
    forbidden_tokens = (
        "adapter.submit",
        "submit_authorized_plan",
        "MassiveRESTClient(",
        "MassiveReferenceProvider(",
        "provider.stock_snapshot(",
        "input(",
        "--broker",
        "--ticker",
        "--force",
        "--confirm",
    )
    checks = {
        "accepted_gate7_policy_exact": phase25_gate7_policy_fingerprint() == ACCEPTED_GATE7_POLICY_FINGERPRINT == "2800bd82670b8f763a9c5f5c080301e20ab6462f82dd949f7cec0a800e989c31",
        "gate7_fingerprint_literal_locked": "2800bd82670b8f763a9c5f5c080301e20ab6462f82dd949f7cec0a800e989c31" in text["policy"] and "2800bd82670b8f763a9c5f5c080301e20ab6462f82dd949f7cec0a800e989c31" in text["tests"],
        "all_policy_fingerprints_sha256": all(len(fn()) == 64 for fn in (phase25_gate8_policy_fingerprint, phase25_gate9_policy_fingerprint, phase25_gate10_policy_fingerprint, phase25_gate11_policy_fingerprint)),
        "gate8_development_precedes_protected": PHASE25_GATE8_DEVELOPMENT_END < PHASE25_GATE8_PROTECTED_START,
        "gate8_protected_forbidden": PHASE25_GATE8_PROTECTED_EVIDENCE_ALLOWED is False,
        "gate8_support_forbidden": PHASE25_GATE8_SUPPORT_REPLACEMENT_ALLOWED is False,
        "gate8_binds_gate7_routes_and_uses_fixed_rules": "gate7_routes_sha256" in text["gate8"] and "StrategyEvaluationEngine(" in text["gate8"] and "strategy_condition_sql(" in text["gate8"],
        "gate8_reports_source_coverage": all(token in text["gate8"] for token in ("research_source_matched_route_rows", "research_source_missing_route_rows", "research_source_route_coverage_fraction")),
        "gate9_protected_forbidden": PHASE25_GATE9_PROTECTED_EVIDENCE_ALLOWED is False,
        "gate9_support_forbidden": PHASE25_GATE9_SUPPORT_REPLACEMENT_ALLOWED is False,
        "gate9_global_holm_exact": PHASE25_GATE9_MULTIPLE_TESTING_METHOD == "HOLM_BONFERRONI_GLOBAL_8_INCUMBENTS" and "holm_bonferroni(" in text["gate9"],
        "gate9_uses_phase24_robustness": all(token in text["gate9"] for token in ("selection_checks(", "internal_checks(", "tranche_metrics(")),
        "gate9_locks_before_internal_and_protected": "internal_validation_has_not_influenced_selection" in text["gate9"] and "protected_confirmation_has_not_influenced_finalists" in text["gate9"],
        "gate10_finalists_only": PHASE25_GATE10_FINALISTS_ONLY is True and "finalist_strategy_ids" in text["gate10"],
        "gate10_zero_finalists_zero_reads": PHASE25_GATE10_ZERO_FINALISTS_ZERO_PROTECTED_READS is True and "SKIPPED_ZERO_FINALISTS" in text["gate10"] and "protected_evidence_reads\": 0" in text["gate10"],
        "gate10_protected_nonfresh": PHASE25_GATE10_PROTECTED_EVIDENCE_ALLOWED is True and PHASE25_GATE10_PROTECTED_EVIDENCE_FRESH is False,
        "gate10_support_forbidden": PHASE25_GATE10_SUPPORT_REPLACEMENT_ALLOWED is False,
        "gate11_support_forbidden": PHASE25_GATE11_SUPPORT_REPLACEMENT_ALLOWED is False and "phase11_support_map_unchanged" in text["gate11"],
        "gate11_future_prospective_required": PHASE25_GATE11_FUTURE_PROSPECTIVE_REQUIRED_FOR_AUTHORITY is True and "future_prospective_required_for_authority" in text["gate11"],
        "no_external_execution_imports": not forbidden_imports,
        "no_external_execution_tokens": not any(token in code for token in forbidden_tokens),
        "cumulative_cli_only_through_scope": "parser.add_argument(\"--through\"" in text["cli"] and text["cli"].count("parser.add_argument(") == 1,
        "cumulative_cli_runs_all_gates": all(token in text["cli"] for token in ("Phase25Gate8DevelopmentAttribution", "Phase25Gate9Robustness", "Phase25Gate10ProtectedConfirmation", "Phase25Gate11Closeout")),
        "spec_records_gate7_target": all(token in text["spec"] for token in ("23,177", "15,283", "61,132", "185,416")),
        "spec_preregisters_all_remaining_gates": all(token in text["spec"] for token in ("Gate8", "Gate9", "Gate10", "Gate11", "global Holm-Bonferroni", "NON-FRESH")),
        "workflow_runs_remaining_validator": "python scripts/validate_phase25_remaining.py" in text["workflow"],
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
