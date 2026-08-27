from __future__ import annotations

import ast
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_policy import (  # noqa: E402
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_MARKET_DAILY_ORIGIN,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PRE_ORIGIN_INTRADAY_FABRICATION_ALLOWED,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_PROVIDER_READS,
    PHASE25_PROVIDER_WRITES,
    PHASE25_ROUTE_REPLAY_ORIGIN,
    PHASE25_SECTOR_FABRICATION_ALLOWED,
    PHASE25_STRATEGY_RULE_CHANGES_ALLOWED,
    PHASE25_OUTCOME_DEFINITION_CHANGES_ALLOWED,
    phase25_gate0_policy_fingerprint,
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
    gate0 = PROJECT_ROOT / "packages" / "backtesting" / "phase25_gate0.py"
    cli = PROJECT_ROOT / "scripts" / "run_phase25_gate0.py"
    spec = PROJECT_ROOT / "docs" / "phase25_historical_production_path_route_fidelity.md"
    workflow = PROJECT_ROOT / ".github" / "workflows" / "atlas-tests.yml"
    required = (gate0, cli, spec, workflow)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Phase25 files missing: " + ", ".join(missing))

    gate0_text = _source(gate0)
    cli_text = _source(cli)
    spec_text = _source(spec)
    workflow_text = _source(workflow)
    imports = _imports(gate0_text) | _imports(cli_text)

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

    forbidden_gate0_tokens = (
        "forward_return",
        "StrategyEvaluationEngine",
        "adapter.submit",
        "submit_authorized_plan",
        "Phase22PaperRunner",
    )

    checks = {
        "policy_fingerprint_sha256": len(phase25_gate0_policy_fingerprint()) == 64,
        "replay_origin_exact": PHASE25_ROUTE_REPLAY_ORIGIN == date(2021, 8, 16),
        "market_daily_origin_exact": PHASE25_MARKET_DAILY_ORIGIN == date(2016, 1, 4),
        "provider_reads_writes_zero": PHASE25_PROVIDER_READS == PHASE25_PROVIDER_WRITES == 0,
        "broker_reads_writes_zero": PHASE25_BROKER_READS == PHASE25_BROKER_WRITES == 0,
        "order_paper_live_zero": PHASE25_ORDER_WRITES == PHASE25_PAPER_SUBMITS == PHASE25_LIVE_WRITES == 0,
        "support_writes_zero": PHASE25_PHASE11_SUPPORT_WRITES == 0,
        "protected_strategy_reads_zero": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS == 0,
        "strategy_rule_changes_forbidden": PHASE25_STRATEGY_RULE_CHANGES_ALLOWED is False,
        "outcome_changes_forbidden": PHASE25_OUTCOME_DEFINITION_CHANGES_ALLOWED is False,
        "sector_fabrication_forbidden": PHASE25_SECTOR_FABRICATION_ALLOWED is False,
        "preorigin_intraday_fabrication_forbidden": PHASE25_PRE_ORIGIN_INTRADAY_FABRICATION_ALLOWED is False,
        "no_provider_broker_execution_imports": not forbidden_imports,
        "no_strategy_return_or_submit_tokens": not any(token in gate0_text for token in forbidden_gate0_tokens),
        "cli_requires_explicit_through": 'parser.add_argument("--through"' in cli_text and "required=True" in cli_text,
        "cli_has_no_trade_inputs": all(token not in cli_text for token in ("--ticker", "--qty", "--price", "--entry", "--stop", "--target", "--broker", "--confirmation")),
        "spec_locks_no_provider": "provider reads or writes" in spec_text,
        "spec_locks_origin": "2021-08-16" in spec_text,
        "spec_locks_no_fabrication": "may not be synthesized" in spec_text,
        "workflow_runs_phase25_validator": "python scripts/validate_phase25.py" in workflow_text,
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
