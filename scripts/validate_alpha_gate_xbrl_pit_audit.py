from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_pit_audit import (
    XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT,
    XBRL_PIT_AUDIT_CONTRACT,
    XBRL_PIT_AUDIT_FINGERPRINT,
    xbrl_pit_audit_fingerprint,
)


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def _require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise SystemExit(f"XBRL PIT audit contract validation failed: missing {label}: {token}")


def _forbid(text: str, token: str, label: str) -> None:
    if token in text:
        raise SystemExit(f"XBRL PIT audit contract validation failed: forbidden {label}: {token}")


def main() -> int:
    if xbrl_pit_audit_fingerprint() != XBRL_PIT_AUDIT_FINGERPRINT:
        raise SystemExit("XBRL PIT audit contract validation failed: frozen fingerprint drifted")

    audit = _read("packages/backtesting/alpha_gate_xbrl_pit_audit.py")
    sec_provider = _read("packages/providers/sec_xbrl_pit.py")
    massive_provider = _read("packages/providers/massive/xbrl_pit.py")
    runner = _read("scripts/run_alpha_gate_xbrl_pit_audit.py")
    tests = _read("tests/unit/test_alpha_gate_xbrl_pit_audit.py")
    doc = _read("docs/alpha_gate_sec_xbrl_pit_audit.md")
    phase_doc = _read("docs/alpha_gate_sec_xbrl_fundamental_quality.md")
    status = _read("docs/current_status.md")
    roadmap = _read("docs/roadmap.md")
    readme = _read("README.md")
    flow = _read("docs/phase_flow.md")
    focused_workflow = _read(".github/workflows/xbrl-alpha-gate-tests.yml")
    full_workflow = _read(".github/workflows/atlas-tests.yml")

    for path, text in (
        ("packages/backtesting/alpha_gate_xbrl_pit_audit.py", audit),
        ("packages/providers/sec_xbrl_pit.py", sec_provider),
        ("packages/providers/massive/xbrl_pit.py", massive_provider),
        ("scripts/run_alpha_gate_xbrl_pit_audit.py", runner),
        ("tests/unit/test_alpha_gate_xbrl_pit_audit.py", tests),
    ):
        ast.parse(text, filename=path)

    for text, label in ((audit, "audit module"), (runner, "audit runner"), (doc, "audit doc")):
        _require(text, XBRL_PIT_AUDIT_CONTRACT, f"{label} contract")
        _require(text, XBRL_PIT_AUDIT_FINGERPRINT, f"{label} fingerprint")
        _require(
            text,
            XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT,
            f"{label} accepted feasibility evidence fingerprint",
        )

    for token in (
        "XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE = 40",
        "XBRL_PIT_MAX_ACCESSIONS_PER_ISSUER = 5",
        "XBRL_PIT_MIN_COMPANYFACTS_SUCCESS = 36",
        "XBRL_PIT_MIN_SELECTED_ORIGINAL_FILINGS = 180",
        "XBRL_PIT_MIN_SEC_METADATA_RECONCILED = 170",
        "XBRL_PIT_MIN_ACCEPTANCE_DECISIONS = 170",
        "XBRL_PIT_MIN_UNAMBIGUOUS_IDENTITY_MAPPINGS = 120",
        "XBRL_PIT_MIN_ISSUERS_WITH_3_UNAMBIGUOUS_MAPPINGS = 30",
        "XBRL_PIT_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS = 0",
        "EXACT_ACCESSION_VERSIONED_NEVER_OVERWRITE_ACROSS_ACCESSIONS",
        "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE",
        "instrument-identity-v4-no-issuer-level-medium-collapse",
        "UNAMBIGUOUS_PIT_INSTRUMENT",
        "AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS",
        '"target_outcome_rows_read": 0',
        '"protected_return_rows_read": 0',
        '"protected_holdout_consumed": False',
        '"provider_writes_performed": 0',
        '"broker_reads_performed": 0',
        '"broker_writes_performed": 0',
        '"order_writes_performed": 0',
        '"paper_submits_performed": 0',
        '"live_writes_performed": 0',
        '"automation_writes_performed": 0',
    ):
        _require(audit, token, "frozen source-only audit invariant")

    for forbidden in (
        "packages.data.market",
        "packages.execution",
        "packages.brokers",
        "packages.portfolio",
        "read_parquet",
        "forward_return",
        "future_close",
        "stock_return",
        "spy_return",
        ".place_order(",
        ".submit_order(",
    ):
        _forbid(audit, forbidden, "market outcome/trading dependency")

    _require(sec_provider, "class SECXBRLPITMetadataClient(SECEDGARClient)", "accepted SEC network seam")
    _require(sec_provider, 'XBRL_PIT_ALLOWED_FORMS = ("10-Q", "10-K")', "original form scope")
    _require(sec_provider, "allowed original forms", "amendment/form fail-closed rule")
    _forbid(sec_provider, "urlopen", "parallel SEC HTTP authority")

    _require(massive_provider, '"/v3/reference/tickers"', "Massive reference route")
    _require(massive_provider, '"cik": expected_cik', "exact CIK filter")
    _require(massive_provider, '"date": as_of_date.isoformat()', "point-in-time date filter")
    _require(massive_provider, "states = (True, False)", "active/inactive coverage")
    _forbid(massive_provider, "urlopen", "parallel Massive HTTP authority")

    for token in (
        "test_accepted_feasibility_evidence_fingerprint_is_exact",
        "test_pit_audit_fingerprint_is_frozen",
        "test_evenly_spaced_accession_selection_includes_history_endpoints",
        "test_cross_accession_revision_is_versioned_not_overwritten",
        "test_same_accession_conflict_fails_but_exact_duplicate_does_not",
        "test_sec_pit_metadata_client_accepts_original_10q_and_rejects_amendment",
        "test_massive_cik_pit_provider_uses_exact_cik_and_date_filters",
        "test_source_only_pit_audit_passes_without_market_outcomes",
    ):
        _require(tests, token, "focused regression test")

    for living_name, living in (
        ("fundamental gate doc", phase_doc),
        ("current status", status),
        ("roadmap", roadmap),
        ("README", readme),
        ("phase flow", flow),
    ):
        _require(living, "FEASIBILITY_PASS", f"{living_name} accepted feasibility state")
        _require(living, "200", f"{living_name} successful Company Facts evidence")
        _require(living, "170", f"{living_name} accrual readiness evidence")
        _require(living, "92", f"{living_name} profitability readiness evidence")
        _require(
            living,
            XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT,
            f"{living_name} accepted feasibility evidence fingerprint",
        )
        _require(living, XBRL_PIT_AUDIT_FINGERPRINT, f"{living_name} frozen PIT audit fingerprint")
        _require(living, "Phase33", f"{living_name} downstream block")

    _require(doc, "same-accession semantic-context conflicts <= **0**", "audit conflict gate")
    _require(doc, "unambiguous PIT instrument mappings >= **120**", "audit identity gate")
    _require(doc, "no market outcome is authorized", "audit blindness declaration")
    _require(doc, "EXACT_ACCESSION_VERSIONED_NEVER_OVERWRITE_ACROSS_ACCESSIONS", "versioning rule")
    _require(doc, "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE", "decision rule")

    _require(runner, "Alpha hypotheses: NOT YET FROZEN", "runner pre-performance boundary")
    _require(
        runner,
        "Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD",
        "runner outcome boundary",
    )
    _require(runner, "Provider writes / broker / order / PAPER / LIVE / automation: DISABLED", "runner authority boundary")
    _forbid(runner, "argparse", "operator scope override")

    _require(focused_workflow, "Validate XBRL source-only feasibility contracts", "retained feasibility validation")
    _require(focused_workflow, "Validate XBRL PIT source/chronology/identity contracts", "focused audit validation")
    _require(focused_workflow, "python scripts/validate_alpha_gate_xbrl_pit_audit.py", "focused audit validator command")
    _require(focused_workflow, "tests/unit/test_alpha_gate_xbrl_pit_audit.py", "focused audit unit tests")
    _require(focused_workflow, "windows-latest", "focused Windows parity")
    _require(focused_workflow, "ubuntu-latest", "focused Ubuntu parity")
    _require(full_workflow, "Validate pre-Phase33 SEC XBRL source-only feasibility contracts", "full retained feasibility")
    _require(full_workflow, "Validate pre-Phase33 SEC XBRL PIT source audit contracts", "full PIT audit step")
    _require(full_workflow, "python scripts/validate_alpha_gate_xbrl_pit_audit.py", "full PIT audit validator command")

    print("ATLAS pre-Phase33 SEC XBRL PIT source/chronology/identity contracts: PASS")
    print(f"- accepted feasibility evidence fingerprint: {XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT}")
    print(f"- frozen PIT audit fingerprint: {XBRL_PIT_AUDIT_FINGERPRINT}")
    print("- original 10-Q/10-K accession versions remain isolated and amendments are excluded")
    print("- exact SEC acceptance time controls the first eligible XNYS decision session")
    print("- Massive identity uses exact CIK + point-in-time date and fails closed on multiple instruments")
    print("- market outcomes, protected returns, broker/order/PAPER/LIVE authority remain absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
