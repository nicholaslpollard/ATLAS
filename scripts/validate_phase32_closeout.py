from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_POLICY = "4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7"
EXPECTED_AUDIT = "c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e"
EXPECTED_PLAN = "2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344"
EXPECTED_ROWS_SHA = "b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703"
EXPECTED_COUNTS = (46, 33, 40)


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    closeout_path = "packages/backtesting/phase32_closeout.py"
    runner_path = "scripts/run_phase32_closeout.py"
    closeout_doc_path = "docs/phase32_closeout.md"
    phase_doc_path = "docs/phase32_sec_8k_material_event_alpha.md"
    status_path = "docs/current_status.md"
    roadmap_path = "docs/roadmap.md"
    flow_path = "docs/phase_flow.md"
    readme_path = "README.md"
    phase32_workflow_path = ".github/workflows/phase32-tests.yml"
    full_workflow_path = ".github/workflows/atlas-tests.yml"

    closeout = _read(closeout_path)
    runner = _read(runner_path)
    closeout_doc = _read(closeout_doc_path)
    phase_doc = _read(phase_doc_path)
    status = _read(status_path)
    roadmap = _read(roadmap_path)
    flow = _read(flow_path)
    readme = _read(readme_path)
    phase32_workflow = _read(phase32_workflow_path)
    full_workflow = _read(full_workflow_path)

    ast.parse(closeout, filename=closeout_path)
    ast.parse(runner, filename=runner_path)

    from packages.backtesting.phase32_closeout import (
        PHASE32_ACCEPTED_AUDIT_FINGERPRINT,
        PHASE32_ACCEPTED_PROTECTED_EVENT_ROWS,
        PHASE32_ACCEPTED_PROTECTED_PLAN_FINGERPRINT,
        PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256,
        PHASE32_ACCEPTED_PROTECTED_SIGNAL_SESSIONS,
        PHASE32_ACCEPTED_PROTECTED_UNIQUE_INSTRUMENTS,
        PHASE32_CLOSEOUT_REPORT_CONTRACT_VERSION,
        phase32_disposition_from_source_gate,
    )
    from packages.backtesting.phase32_policy import phase32_policy_fingerprint

    if phase32_policy_fingerprint() != EXPECTED_POLICY:
        raise AssertionError("Phase32 frozen policy fingerprint drifted")
    if PHASE32_ACCEPTED_AUDIT_FINGERPRINT != EXPECTED_AUDIT:
        raise AssertionError("Phase32 accepted finalist-audit fingerprint drifted")
    if PHASE32_ACCEPTED_PROTECTED_PLAN_FINGERPRINT != EXPECTED_PLAN:
        raise AssertionError("Phase32 accepted protected-plan fingerprint drifted")
    if PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256 != EXPECTED_ROWS_SHA:
        raise AssertionError("Phase32 accepted protected-plan rows SHA drifted")
    if (
        PHASE32_ACCEPTED_PROTECTED_EVENT_ROWS,
        PHASE32_ACCEPTED_PROTECTED_SIGNAL_SESSIONS,
        PHASE32_ACCEPTED_PROTECTED_UNIQUE_INSTRUMENTS,
    ) != EXPECTED_COUNTS:
        raise AssertionError("Phase32 accepted protected source-only counts drifted")
    if phase32_disposition_from_source_gate(event_rows=46, signal_sessions=33, unique_instruments=40) != (
        "ACCEPTED_NEGATIVE",
        False,
    ):
        raise AssertionError("Phase32 negative disposition semantics drifted")
    if phase32_disposition_from_source_gate(event_rows=50, signal_sessions=20, unique_instruments=20)[0] != (
        "PENDING_PROTECTED_CONFIRMATION"
    ):
        raise AssertionError("Phase32 closeout would incorrectly close a source-eligible protected population")

    for token in (
        PHASE32_CLOSEOUT_REPORT_CONTRACT_VERSION,
        EXPECTED_AUDIT,
        EXPECTED_PLAN,
        EXPECTED_ROWS_SHA,
        "PHASE32_ACCEPTED_PROTECTED_EVENT_ROWS = 46",
        "PHASE32_ACCEPTED_PROTECTED_SIGNAL_SESSIONS = 33",
        "PHASE32_ACCEPTED_PROTECTED_UNIQUE_INSTRUMENTS = 40",
        '"ACCEPTED_NEGATIVE"',
        '"protected_returns_unread"',
        '"protected_holdout_unconsumed"',
        '"phase33_authority_blocked"',
        '"no_protected_performance_artifacts"',
    ):
        _require(closeout, token, "negative closeout invariant")

    for forbidden in (
        "read_parquet",
        "forward_return",
        "future_close",
        "MassiveRESTClient",
        "SECSubmissionsClient",
        ".place_order(",
        ".submit_order(",
        "packages.execution",
        "packages.brokers",
    ):
        _forbid(closeout, forbidden, "protected-performance/provider/trading dependency in closeout")

    _require(runner, "Protected stock/SPY returns: FORBIDDEN / UNREAD", "runner protected boundary")
    _require(runner, "Phase33 entry satisfied", "runner downstream authority output")
    _require(runner, "open only a materially different alpha mechanism next", "runner next-mechanism rule")

    for doc_name, doc in (
        ("closeout doc", closeout_doc),
        ("phase doc", phase_doc),
        ("status", status),
        ("roadmap", roadmap),
        ("flow", flow),
        ("README", readme),
    ):
        _require(doc, "ACCEPTED_NEGATIVE", f"{doc_name} final disposition")
        _require(doc, "46", f"{doc_name} protected event-row evidence")
        _require(doc, "33", f"{doc_name} protected session evidence")
        _require(doc, "40", f"{doc_name} protected instrument evidence")
        _require(doc, "protected", f"{doc_name} protected boundary")
        _require(doc, "Phase33", f"{doc_name} downstream gate")

    _require(closeout_doc, EXPECTED_AUDIT, "closeout doc audit fingerprint")
    _require(closeout_doc, EXPECTED_PLAN, "closeout doc plan fingerprint")
    _require(closeout_doc, EXPECTED_ROWS_SHA, "closeout doc plan rows SHA")
    _require(closeout_doc, "Protected return rows read: **0**", "closeout protected return proof")
    _require(closeout_doc, "Protected holdout consumed: **false**", "closeout holdout proof")
    _require(closeout_doc, "Historical supported alpha remains **0**", "closeout authority result")

    # Living roadmap language may advance to a named later mechanism, but it must
    # continue proving the Phase32 anti-retuning boundary rather than merely saying
    # that "something different" follows.
    _require(
        roadmap,
        "materially different point-in-time fundamental-information mechanism",
        "roadmap materially different mechanism continuation",
    )
    _require(
        roadmap,
        "may not reuse Phase32 candidate labels, directions, event taxonomy, development performance, finalist choice, or protected result",
        "roadmap Phase32 anti-retuning continuation",
    )
    _require(status, "Phase32 is closed", "status closed state")
    _require(readme, "Phase32 is `ACCEPTED_NEGATIVE`", "README closed state")
    _require(flow, "Accepted project foundation: **through Phase32**", "flow accepted boundary")

    _require(phase32_workflow, "Validate Phase 32 negative closeout contracts", "Phase32 CI closeout step")
    _require(phase32_workflow, "python scripts/validate_phase32_closeout.py", "Phase32 CI closeout command")
    _require(phase32_workflow, "tests/unit/test_phase32_closeout.py", "Phase32 focused closeout test")
    _require(full_workflow, "Validate Phase 32 independent negative closeout contracts", "full CI retained closeout step")
    _require(full_workflow, "python scripts/validate_phase32_closeout.py", "full CI retained closeout command")

    print("ATLAS Phase 32 independent negative closeout contracts: PASS")
    print(f"- frozen policy fingerprint: {EXPECTED_POLICY}")
    print(f"- finalist audit fingerprint: {EXPECTED_AUDIT}")
    print(f"- protected plan fingerprint: {EXPECTED_PLAN}")
    print(f"- protected plan rows SHA-256: {EXPECTED_ROWS_SHA}")
    print("- protected source-only population is frozen at 46 rows / 33 sessions / 40 instruments")
    print("- the preregistered 50-row minimum fails before protected returns are opened")
    print("- protected return reads remain zero and the holdout remains unconsumed")
    print("- current roadmap still proves a materially different mechanism and forbids Phase32 scientific reuse")
    print("- Phase32 closes ACCEPTED_NEGATIVE; supported alpha remains zero; Phase33 remains blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
