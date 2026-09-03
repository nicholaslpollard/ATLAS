from __future__ import annotations

import ast
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_POLICY_FINGERPRINT = "26a6aae124b1a5d2b14b8a11a72671b06ac34d3cf94eb7ac47f16d2cfb94a8b3"
EXPECTED_AUTHORITY_FINGERPRINT = "a23ec27367ae540b869abc428d118241e84436719a8a543cbdbc3f3b678c69c5"
EXPECTED_FEATURE_FINGERPRINT = "26a2892a4c4bb5597d2e688e78be8cb7da4fc656872a30fe887cf60669476cb8"


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise AssertionError(f"missing {label}: {token}")


def main() -> int:
    from packages.backtesting.reference_strategy_runner import (
        PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_END,
        PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_START,
        REFERENCE_STRATEGY_RUNNER_BROKER_WRITES,
        REFERENCE_STRATEGY_RUNNER_LIVE_WRITES,
        REFERENCE_STRATEGY_RUNNER_PAPER_SUBMITS,
    )
    from packages.features.feature_registry import CORE_FEATURE_REGISTRY
    from packages.features.reference_daily import (
        REFERENCE_DAILY_FEATURE_FINGERPRINT,
        reference_daily_feature_fingerprint,
    )
    from packages.performance.ledger import STRATEGY_TRIAL_LEDGER_CONTRACT_VERSION
    from packages.schemas.strategy_policy import (
        StrategyAuthority,
        StrategyExecutionEnvironment,
    )
    from packages.schemas.strategy import StrategyFamily
    from packages.strategies.read_models import reference_strategy_catalog_read_model
    from packages.strategies.reference_library import (
        REFERENCE_STRATEGY_AUTHORITIES,
        REFERENCE_STRATEGY_AUTHORITY_FINGERPRINT,
        REFERENCE_STRATEGY_CATALOG,
        REFERENCE_STRATEGY_POLICY_FINGERPRINT,
        reference_authority_fingerprint,
    )
    from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY
    from packages.strategies.research_catalog import (
        DEFAULT_REFERENCE_SPECIFICATION_REGISTRY,
    )

    if REFERENCE_STRATEGY_POLICY_FINGERPRINT != EXPECTED_POLICY_FINGERPRINT:
        raise AssertionError("reference strategy policy fingerprint constant drifted")
    if REFERENCE_STRATEGY_CATALOG.fingerprint() != EXPECTED_POLICY_FINGERPRINT:
        raise AssertionError("reference strategy catalog content drifted")
    if REFERENCE_STRATEGY_AUTHORITY_FINGERPRINT != EXPECTED_AUTHORITY_FINGERPRINT:
        raise AssertionError("reference strategy authority fingerprint constant drifted")
    if reference_authority_fingerprint() != EXPECTED_AUTHORITY_FINGERPRINT:
        raise AssertionError("reference strategy authority content drifted")
    if REFERENCE_DAILY_FEATURE_FINGERPRINT != EXPECTED_FEATURE_FINGERPRINT:
        raise AssertionError("reference feature fingerprint constant drifted")
    if reference_daily_feature_fingerprint() != EXPECTED_FEATURE_FINGERPRINT:
        raise AssertionError("reference feature content drifted")
    if len(REFERENCE_STRATEGY_CATALOG.all()) != 9:
        raise AssertionError("reference catalog must contain nine direction-specific policies")
    if len(REFERENCE_STRATEGY_CATALOG.family_ids()) != 6:
        raise AssertionError("reference catalog must contain six materially different families")
    if len(DEFAULT_STRATEGY_REGISTRY.all()) != 8:
        raise AssertionError("accepted Phase 11 eight-rule registry was changed")
    if {item.value for item in StrategyFamily} != {
        "trend_following",
        "momentum",
        "breakout",
        "pullback",
    }:
        raise AssertionError("accepted Phase 11 four-family runtime enum was changed")
    seed_specifications = DEFAULT_REFERENCE_SPECIFICATION_REGISTRY.all()
    if len(seed_specifications) != 6:
        raise AssertionError("accepted PR 45 six-specification seed catalog was changed")
    if any(item.outcome_access_permitted for item in seed_specifications):
        raise AssertionError("accepted PR 45 seed catalog opened outcome access")
    if CORE_FEATURE_REGISTRY.fingerprint() != "31f9e3a72962c24039aa926a36bb769d451a25035709566912681e1f039eaf6a":
        raise AssertionError("accepted 33-feature core registry was changed")

    for authority in REFERENCE_STRATEGY_AUTHORITIES:
        if authority.authority != StrategyAuthority.RESEARCH:
            raise AssertionError("reference strategy gained authority before historical evidence")
        if authority.allowed_environments != (StrategyExecutionEnvironment.RESEARCH_REPLAY,):
            raise AssertionError("reference strategy gained PAPER or LIVE permission")
    if any(
        value != 0
        for value in (
            REFERENCE_STRATEGY_RUNNER_BROKER_WRITES,
            REFERENCE_STRATEGY_RUNNER_PAPER_SUBMITS,
            REFERENCE_STRATEGY_RUNNER_LIVE_WRITES,
        )
    ):
        raise AssertionError("reference historical runner gained external trading authority")
    if PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_START.isoformat() != "2026-05-12":
        raise AssertionError("master protected start changed")
    if PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_END.isoformat() != "2026-08-11":
        raise AssertionError("master protected end changed")

    runner_text = _read("packages/backtesting/reference_strategy_runner.py")
    runner_tree = ast.parse(runner_text)
    imported = {
        node.module or ""
        for node in ast.walk(runner_tree)
        if isinstance(node, ast.ImportFrom)
    }
    forbidden_imports = sorted(
        name
        for name in imported
        if name.startswith("packages.providers")
        or name.startswith("packages.brokers")
        or name.startswith("packages.execution")
    )
    if forbidden_imports:
        raise AssertionError(f"reference runner imported provider/broker execution: {forbidden_imports}")
    for token in ("submit_order", "place_order", "read_parquet", "forward_return"):
        if token in runner_text:
            raise AssertionError(f"reference runner gained forbidden outcome/trading token: {token}")

    read_model = reference_strategy_catalog_read_model()
    if read_model["family_count"] != 6 or read_model["strategy_count"] != 9:
        raise AssertionError("reference API read model counts drifted")
    boundaries = dict(read_model["execution_boundaries"])
    if boundaries != {
        "research_replay_allowed": True,
        "operational_paper_allowed": False,
        "qualifying_paper_allowed": False,
        "live_allowed": False,
        "broker_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
    }:
        raise AssertionError("reference API authority boundary drifted")
    if "append-only-hash-chain-protected-zero" not in STRATEGY_TRIAL_LEDGER_CONTRACT_VERSION:
        raise AssertionError("strategy trial ledger contract drifted")

    for path in ("README.md", "docs/roadmap.md"):
        text = _read(path)
        for fingerprint in (
            EXPECTED_POLICY_FINGERPRINT,
            EXPECTED_AUTHORITY_FINGERPRINT,
            EXPECTED_FEATURE_FINGERPRINT,
        ):
            _require(text, fingerprint, f"{path} A33/B33 frozen fingerprint")
        _require(text, "nine direction-specific", f"{path} catalog count")
        _require(text, "protected return rows read: **0**", f"{path} protected boundary")

    workflow = _read(".github/workflows/a33-b33-reference-strategy-tests.yml")
    _require(workflow, "persist-credentials: false", "focused workflow credential boundary")
    _require(workflow, "validate_a33_b33_reference_foundation.py", "focused validator step")
    _require(workflow, "test_a33_b33_foundations.py", "accepted PR 45 foundation tests")
    _require(workflow, "test_reference_strategy_runner.py", "focused runner tests")

    print("ATLAS A33/B33 reference strategy foundation contracts: PASS")
    print(f"- policy fingerprint: {EXPECTED_POLICY_FINGERPRINT}")
    print(f"- authority fingerprint: {EXPECTED_AUTHORITY_FINGERPRINT}")
    print(f"- feature fingerprint: {EXPECTED_FEATURE_FINGERPRINT}")
    print("- six families / nine direction-specific policies remain RESEARCH_REPLAY only")
    print("- accepted Phase 11 registry/families, PR 45 seed, and 33-feature core are unchanged")
    print("- master protected window is rejected; protected return reads remain zero")
    print("- provider, broker, PAPER, and LIVE writes remain zero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
