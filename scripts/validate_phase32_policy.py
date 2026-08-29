from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_POLICY_FINGERPRINT = "0cac8c9cc05afd031c10d29ef83d3f49eb5de8bad864f18027d2a8a9585a2b88"
EXPECTED_CORE_SOURCE_FINGERPRINT = "978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4"
EXPECTED_SEMANTIC_SOURCE_FINGERPRINT = "eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566"
EXPECTED_CENSUS_CONTRACT = "phase32-semantic-v2-source-census-v1-no-market-outcomes"
EXPECTED_CANDIDATES = (
    "equity_issuance_short",
    "share_repurchase_long",
    "financial_integrity_adverse_short",
    "listing_distress_short",
    "solvency_distress_short",
)


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    policy_path = "packages/backtesting/phase32_policy.py"
    scientific_path = "docs/phase32_scientific_contract.md"
    phase_path = "docs/phase32_sec_8k_material_event_alpha.md"
    semantic_path = "docs/phase32_semantic_source_qualification.md"
    status_path = "docs/current_status.md"
    roadmap_path = "docs/roadmap.md"
    readme_path = "README.md"
    workflow_path = ".github/workflows/phase32-tests.yml"

    policy = _read(policy_path)
    ast.parse(policy, filename=policy_path)
    scientific = _read(scientific_path)
    phase_doc = _read(phase_path)
    semantic_doc = _read(semantic_path)
    status = _read(status_path)
    roadmap = _read(roadmap_path)
    readme = _read(readme_path)
    workflow = _read(workflow_path)

    from packages.backtesting.phase32_policy import (
        PHASE32_CANDIDATES,
        PHASE32_CENSUS_DISCLOSURE_ROWS,
        PHASE32_CENSUS_PROTECTED_RETURN_ROWS_READ,
        PHASE32_CENSUS_TARGET_OUTCOME_ROWS_READ,
        PHASE32_DEVELOPMENT_LAST_SIGNAL,
        PHASE32_INTERNAL_PURGE_SESSIONS,
        PHASE32_MULTIPLE_TESTING_METHOD,
        PHASE32_OUTCOME_HORIZON_SESSIONS,
        PHASE32_PROTECTED_LAST_SIGNAL,
        PHASE32_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED,
        phase32_candidate_ids,
        phase32_policy_fingerprint,
    )

    if phase32_policy_fingerprint() != EXPECTED_POLICY_FINGERPRINT:
        raise AssertionError("Phase32 scientific policy fingerprint drifted")
    if phase32_candidate_ids() != EXPECTED_CANDIDATES:
        raise AssertionError("Phase32 finite candidate family drifted")
    if len(PHASE32_CANDIDATES) != 5:
        raise AssertionError("Phase32 candidate family must remain exactly five")
    if PHASE32_CENSUS_DISCLOSURE_ROWS != 7468:
        raise AssertionError("Phase32 source-census lineage drifted")
    if PHASE32_CENSUS_TARGET_OUTCOME_ROWS_READ != 0 or PHASE32_CENSUS_PROTECTED_RETURN_ROWS_READ != 0:
        raise AssertionError("Phase32 contract was not frozen from zero-outcome source evidence")
    if PHASE32_OUTCOME_HORIZON_SESSIONS != 5 or PHASE32_INTERNAL_PURGE_SESSIONS != 5:
        raise AssertionError("Phase32 five-session horizon/purge drifted")
    if PHASE32_DEVELOPMENT_LAST_SIGNAL != "2026-05-04":
        raise AssertionError("Phase32 development outer boundary drifted")
    if PHASE32_PROTECTED_LAST_SIGNAL != "2026-08-04":
        raise AssertionError("Phase32 protected eligible-signal boundary drifted")
    if PHASE32_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_GLOBAL_5":
        raise AssertionError("Phase32 global multiplicity rule drifted")
    if PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED is not False:
        raise AssertionError("Phase32 no-runner-up rule drifted")
    if PHASE32_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED is not False:
        raise AssertionError("Phase32 protected blindness rule drifted")

    _require(policy, EXPECTED_CORE_SOURCE_FINGERPRINT, "accepted core source lineage")
    _require(policy, EXPECTED_SEMANTIC_SOURCE_FINGERPRINT, "accepted semantic source lineage")
    _require(policy, EXPECTED_CENSUS_CONTRACT, "accepted source-census lineage")
    for candidate in EXPECTED_CANDIDATES:
        _require(policy, candidate, "frozen candidate")
    for token in (
        'PHASE32_PUBLIC_AVAILABILITY_RULE = (',
        '"FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME"',
        'PHASE32_ENTRY_RULE = "DECISION_SESSION_OPEN"',
        'PHASE32_EXIT_RULE = "CLOSE_5_XNYS_SESSIONS_AFTER_DECISION"',
        'PHASE32_BENCHMARK_TICKER = "SPY"',
        'PHASE32_INSTRUMENT_FALLBACK_TICKER_SNAPSHOT_ALLOWED = False',
        'PHASE32_CURRENT_UNIVERSE_BACKPROJECTION_ALLOWED = False',
        'PHASE32_TICKER_ALIAS_BACKFILL_ALLOWED = False',
        'PHASE32_PRIMARY_COST_BPS = 10.0',
        'PHASE32_STRESS_COST_BPS = 25.0',
        'PHASE32_BOOTSTRAP_BLOCK_SESSIONS = 5',
        'PHASE32_SELECTION_MIN_EVENT_ROWS = 500',
        'PHASE32_INTERNAL_MIN_EVENT_ROWS = 150',
        'PHASE32_PROTECTED_MIN_EVENT_ROWS = 50',
        'PHASE32_PHASE33_SIGNAL_TO_TRADE_AUTHORITY = False',
    ):
        _require(policy, token, "frozen Phase32 policy invariant")

    for forbidden in (
        "forward_return",
        "future_close",
        "read_parquet",
        "packages.execution",
        "packages.brokers",
        "Webull",
        "AlpacaTrading",
    ):
        _forbid(policy, forbidden, "market-outcome/trading dependency in policy freeze")

    _require(scientific, EXPECTED_POLICY_FINGERPRINT, "scientific fingerprint")
    _require(scientific, "Exactly five hypotheses", "finite family heading")
    for candidate in EXPECTED_CANDIDATES:
        _require(scientific, candidate, "scientific candidate")
    _require(scientific, "regular-session open timestamp", "acceptance-time operational meaning")
    _require(scientific, "CLOSE_5_XNYS_SESSIONS_AFTER_DECISION", "scientific horizon")
    _require(scientific, "HOLM_BONFERRONI_GLOBAL_5", "scientific global Holm")
    _require(scientific, "no runner-up substitution", "scientific winner freeze")
    _require(scientific, "2026-05-04", "development label boundary")
    _require(scientific, "2026-08-04", "protected signal boundary")
    _require(scientific, "zero target/protected outcome reads", "pre-performance source freeze")
    _require(scientific, "full-history Phase32 source/predictor acquisition", "next scientific target")

    for doc_name, doc in (
        ("phase spec", phase_doc),
        ("semantic qualification", semantic_doc),
        ("current status", status),
        ("roadmap", roadmap),
        ("README", readme),
    ):
        _require(doc, EXPECTED_POLICY_FINGERPRINT, f"{doc_name} policy fingerprint")
        _require(doc, "five hypotheses", f"{doc_name} finite family status")
        _require(doc, "full-history", f"{doc_name} next source/predictor target")

    _require(status, "Phase32 market outcomes remain unread", "status blindness boundary")
    _require(roadmap, "Phase33", "roadmap downstream block")
    _require(phase_doc, "Phase33 remains blocked", "phase spec downstream block")
    _require(semantic_doc, "7,468", "semantic census accepted disclosure count")

    _require(workflow, "Validate Phase 32 frozen scientific policy", "CI policy step")
    _require(workflow, "python scripts/validate_phase32_policy.py", "CI policy validator command")
    _require(workflow, "tests/unit/test_phase32_policy.py", "CI policy unit test")

    print("ATLAS Phase 32 frozen scientific policy contracts: PASS")
    print(f"- frozen policy fingerprint: {EXPECTED_POLICY_FINGERPRINT}")
    print("- exactly five source-semantic hypotheses are frozen before performance")
    print("- SEC acceptance-time decision session, 5-session horizon, PIT CIK-bound identity, SPY-relative outcome and costs are frozen")
    print("- sample/concentration gates, 5-session block inference, global Holm-5 and no-runner-up selection are frozen")
    print("- protected returns remain forbidden until finalists and blindness audit")
    print("- Phase33 and all broker/order/PAPER/LIVE authority remain blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
