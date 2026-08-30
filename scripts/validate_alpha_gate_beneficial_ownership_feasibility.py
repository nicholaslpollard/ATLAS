from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_FINGERPRINT = "f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb"
EXPECTED_SOURCE_MERGE = "083c0a5742b161cf4b7c04d5bf0246f3057f6c19"
EXPECTED_CONTRACT = (
    "alpha-gate-sec-beneficial-ownership-feasibility-v1-schedule13d13g-source-only-no-market-outcomes"
)
EXPECTED_MECHANISM = "PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE"


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def main() -> int:
    provider_path = "packages/providers/sec_edgar_archive.py"
    feasibility_path = "packages/backtesting/alpha_gate_beneficial_ownership_feasibility.py"
    runner_path = "scripts/run_alpha_gate_beneficial_ownership_feasibility.py"
    doc_path = "docs/alpha_gate_sec_beneficial_ownership_feasibility.md"
    status_path = "docs/current_status.md"
    roadmap_path = "docs/roadmap.md"
    flow_path = "docs/phase_flow.md"
    readme_path = "README.md"
    focused_workflow_path = ".github/workflows/beneficial-ownership-alpha-gate-tests.yml"
    full_workflow_path = ".github/workflows/atlas-tests.yml"
    test_path = "tests/unit/test_alpha_gate_beneficial_ownership_feasibility.py"

    provider = _read(provider_path)
    feasibility = _read(feasibility_path)
    runner = _read(runner_path)
    doc = _read(doc_path)
    status = _read(status_path)
    roadmap = _read(roadmap_path)
    flow = _read(flow_path)
    readme = _read(readme_path)
    focused = _read(focused_workflow_path)
    full = _read(full_workflow_path)
    tests = _read(test_path)

    parsed: dict[str, ast.AST] = {}
    for path, text in (
        (provider_path, provider),
        (feasibility_path, feasibility),
        (runner_path, runner),
        (test_path, tests),
    ):
        parsed[path] = ast.parse(text, filename=path)

    from packages.backtesting.alpha_gate_beneficial_ownership_feasibility import (
        BENEFICIAL_OWNERSHIP_ALLOWED_FORMS,
        BENEFICIAL_OWNERSHIP_ALPHA_HYPOTHESES_FROZEN,
        BENEFICIAL_OWNERSHIP_AUTOMATIC_BROKER_FAILOVER,
        BENEFICIAL_OWNERSHIP_AUTOMATION_WRITES,
        BENEFICIAL_OWNERSHIP_BROKER_READS,
        BENEFICIAL_OWNERSHIP_BROKER_WRITES,
        BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT,
        BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT,
        BENEFICIAL_OWNERSHIP_LIVE_WRITES,
        BENEFICIAL_OWNERSHIP_MECHANISM,
        BENEFICIAL_OWNERSHIP_MIN_ACCEPTANCE_DECISIONS,
        BENEFICIAL_OWNERSHIP_MIN_ACCESSION_RECONCILED,
        BENEFICIAL_OWNERSHIP_MIN_DISCOVERED_PER_STRATUM,
        BENEFICIAL_OWNERSHIP_MIN_FILING_DATE_RECONCILED,
        BENEFICIAL_OWNERSHIP_MIN_FORM_RECONCILED,
        BENEFICIAL_OWNERSHIP_MIN_LEGACY_CUSIP_MARKERS,
        BENEFICIAL_OWNERSHIP_MIN_PARSED_PER_STRATUM,
        BENEFICIAL_OWNERSHIP_MIN_STRUCTURED_XML_MARKERS,
        BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED,
        BENEFICIAL_OWNERSHIP_MIN_SUBMISSION_SUCCESS,
        BENEFICIAL_OWNERSHIP_MIN_UNAMBIGUOUS_COMMON_STOCK_MAPPINGS,
        BENEFICIAL_OWNERSHIP_MIN_UNIQUE_SUBJECT_CIKS,
        BENEFICIAL_OWNERSHIP_ORDER_WRITES,
        BENEFICIAL_OWNERSHIP_PAPER_SUBMITS,
        BENEFICIAL_OWNERSHIP_PROTECTED_OUTCOME_READS_ALLOWED,
        BENEFICIAL_OWNERSHIP_PROVIDER_READS_ALLOWED,
        BENEFICIAL_OWNERSHIP_PROVIDER_WRITES,
        BENEFICIAL_OWNERSHIP_QUARTERS,
        BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT,
        BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM,
        BENEFICIAL_OWNERSHIP_SAMPLE_SIZE,
        BENEFICIAL_OWNERSHIP_SOURCE_CUTOFF,
        BENEFICIAL_OWNERSHIP_SOURCE_START,
        BENEFICIAL_OWNERSHIP_SOURCE_XBRL_MERGE,
        BENEFICIAL_OWNERSHIP_STRATA,
        BENEFICIAL_OWNERSHIP_STRUCTURED_COMPLIANCE_DATE,
        BENEFICIAL_OWNERSHIP_TARGET_OUTCOME_READS_ALLOWED,
        beneficial_ownership_feasibility_fingerprint,
    )

    exact = {
        "contract": (BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT, EXPECTED_CONTRACT),
        "fingerprint constant": (BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT, EXPECTED_FINGERPRINT),
        "fingerprint function": (beneficial_ownership_feasibility_fingerprint(), EXPECTED_FINGERPRINT),
        "source merge": (BENEFICIAL_OWNERSHIP_SOURCE_XBRL_MERGE, EXPECTED_SOURCE_MERGE),
        "mechanism": (BENEFICIAL_OWNERSHIP_MECHANISM, EXPECTED_MECHANISM),
    }
    for label, (actual, expected) in exact.items():
        if actual != expected:
            raise AssertionError(f"beneficial-ownership {label} drifted: {actual!r}")

    if BENEFICIAL_OWNERSHIP_SOURCE_START.isoformat() != "2016-01-01":
        raise AssertionError("source start drifted")
    if BENEFICIAL_OWNERSHIP_SOURCE_CUTOFF.isoformat() != "2026-08-11":
        raise AssertionError("source cutoff drifted")
    if BENEFICIAL_OWNERSHIP_STRUCTURED_COMPLIANCE_DATE.isoformat() != "2024-12-18":
        raise AssertionError("structured compliance boundary drifted")
    if BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT != 43:
        raise AssertionError("quarter index count drifted")
    if BENEFICIAL_OWNERSHIP_QUARTERS[0] != (2016, 1) or BENEFICIAL_OWNERSHIP_QUARTERS[-1] != (2026, 3):
        raise AssertionError("quarter index endpoints drifted")
    if BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM != 25 or BENEFICIAL_OWNERSHIP_SAMPLE_SIZE != 200:
        raise AssertionError("frozen sample geometry drifted")
    if len(BENEFICIAL_OWNERSHIP_STRATA) != 8:
        raise AssertionError("frozen strata count drifted")
    if len(BENEFICIAL_OWNERSHIP_ALLOWED_FORMS) != 8:
        raise AssertionError("accepted form-alias family drifted")

    thresholds = {
        "min discovered per stratum": (BENEFICIAL_OWNERSHIP_MIN_DISCOVERED_PER_STRATUM, 50),
        "min submission success": (BENEFICIAL_OWNERSHIP_MIN_SUBMISSION_SUCCESS, 190),
        "min accession reconciled": (BENEFICIAL_OWNERSHIP_MIN_ACCESSION_RECONCILED, 190),
        "min form reconciled": (BENEFICIAL_OWNERSHIP_MIN_FORM_RECONCILED, 190),
        "min filing date reconciled": (BENEFICIAL_OWNERSHIP_MIN_FILING_DATE_RECONCILED, 190),
        "min subject CIK reconciled": (BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED, 185),
        "min acceptance decisions": (BENEFICIAL_OWNERSHIP_MIN_ACCEPTANCE_DECISIONS, 190),
        "min unique subject CIKs": (BENEFICIAL_OWNERSHIP_MIN_UNIQUE_SUBJECT_CIKS, 140),
        "min structured XML markers": (BENEFICIAL_OWNERSHIP_MIN_STRUCTURED_XML_MARKERS, 90),
        "min legacy CUSIP markers": (BENEFICIAL_OWNERSHIP_MIN_LEGACY_CUSIP_MARKERS, 90),
        "min common-stock mappings": (BENEFICIAL_OWNERSHIP_MIN_UNAMBIGUOUS_COMMON_STOCK_MAPPINGS, 130),
        "min parsed per stratum": (BENEFICIAL_OWNERSHIP_MIN_PARSED_PER_STRATUM, 22),
    }
    for label, (actual, expected) in thresholds.items():
        if actual != expected:
            raise AssertionError(f"{label} drifted: {actual}")

    if BENEFICIAL_OWNERSHIP_ALPHA_HYPOTHESES_FROZEN is not False:
        raise AssertionError("alpha hypotheses were frozen during source feasibility")
    if BENEFICIAL_OWNERSHIP_TARGET_OUTCOME_READS_ALLOWED is not False:
        raise AssertionError("target outcomes were authorized during source feasibility")
    if BENEFICIAL_OWNERSHIP_PROTECTED_OUTCOME_READS_ALLOWED is not False:
        raise AssertionError("protected outcomes were authorized during source feasibility")
    if BENEFICIAL_OWNERSHIP_PROVIDER_READS_ALLOWED is not True:
        raise AssertionError("source feasibility lost its bounded provider-read authority")
    if any(
        value != 0
        for value in (
            BENEFICIAL_OWNERSHIP_PROVIDER_WRITES,
            BENEFICIAL_OWNERSHIP_BROKER_READS,
            BENEFICIAL_OWNERSHIP_BROKER_WRITES,
            BENEFICIAL_OWNERSHIP_ORDER_WRITES,
            BENEFICIAL_OWNERSHIP_PAPER_SUBMITS,
            BENEFICIAL_OWNERSHIP_LIVE_WRITES,
            BENEFICIAL_OWNERSHIP_AUTOMATION_WRITES,
        )
    ):
        raise AssertionError("source feasibility gained external mutation/trading authority")
    if BENEFICIAL_OWNERSHIP_AUTOMATIC_BROKER_FAILOVER is not False:
        raise AssertionError("automatic broker failover was enabled")

    for token in (
        'SEC_ARCHIVE_ALLOWED_HOST = "www.sec.gov"',
        'SEC_ARCHIVE_PREFIX = "/Archives/edgar/"',
        '"/full-index/"',
        '"/data/"',
        "SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND",
        "SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS",
        "SEC_EDGAR_MAX_ATTEMPTS",
        "sec_declared_user_agent",
        "persist-credentials: false",
    ):
        target = provider if token != "persist-credentials: false" else focused
        _require(target, token, "bounded SEC Archive provider/CI invariant")

    provider_import_roots = _import_roots(parsed[provider_path])
    forbidden_http_or_parallel_imports = {"requests", "httpx", "aiohttp", "asyncio", "concurrent", "threading"}
    imported_forbidden = sorted(provider_import_roots & forbidden_http_or_parallel_imports)
    if imported_forbidden:
        raise AssertionError(
            "parallel/alternate HTTP authority added to SEC Archive provider: "
            + ", ".join(imported_forbidden)
        )

    for forbidden in (
        "read_parquet",
        "forward_return",
        "future_close",
        "packages.execution",
        "packages.brokers",
        ".place_order(",
        ".submit_order(",
    ):
        _forbid(feasibility, forbidden, "market-outcome/trading dependency in feasibility")
        _forbid(runner, forbidden, "market-outcome/trading dependency in feasibility runner")

    _require(feasibility, "tradable_common_stock_snapshot", "active common-stock PIT reference lookup")
    _require(feasibility, "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE", "strict decision-session rule")
    _require(feasibility, "AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS", "identity ambiguity fail-closed state")
    _require(feasibility, "PRIMARY_DOC.XML", "structured-era diagnostic")
    _require(feasibility, "CUSIP", "legacy source diagnostic")
    _require(runner, "Alpha hypotheses: NOT YET FROZEN", "runner source-only boundary")
    _require(runner, "FORBIDDEN / UNREAD", "runner outcome boundary")
    _require(runner, "Provider writes / broker / order / PAPER / LIVE / automation: DISABLED", "runner authority boundary")
    _forbid(runner, "argparse", "runtime scientific-threshold override surface")

    for doc_name, text in (
        ("feasibility doc", doc),
        ("status", status),
        ("roadmap", roadmap),
        ("flow", flow),
        ("README", readme),
    ):
        _require(text, EXPECTED_FINGERPRINT, f"{doc_name} frozen feasibility fingerprint")
        _require(text, EXPECTED_MECHANISM, f"{doc_name} mechanism")
        _require(text, "Phase33", f"{doc_name} downstream block")

    _require(doc, "Alpha hypotheses are **not frozen**", "feasibility doc no-alpha boundary")
    _require(doc, "zero market outcomes", "feasibility doc zero-outcome boundary")
    _require(doc, "2016-01-01..2026-08-11", "feasibility doc source window")
    _require(doc, "2024-12-18", "feasibility doc structured boundary")
    _require(doc, "25 filings in each of eight strata", "feasibility doc sample rule")
    _require(doc, "130", "feasibility doc identity gate")

    _require(focused, "Validate SEC beneficial-ownership source feasibility contracts", "focused validator step")
    _require(focused, "python scripts/validate_alpha_gate_beneficial_ownership_feasibility.py", "focused validator command")
    _require(focused, "tests/unit/test_alpha_gate_beneficial_ownership_feasibility.py", "focused tests")
    _require(full, "Validate pre-Phase33 SEC beneficial-ownership source feasibility", "full regression validator step")
    _require(full, "python scripts/validate_alpha_gate_beneficial_ownership_feasibility.py", "full regression validator command")

    print("ATLAS SEC Schedule 13D/13G source-only feasibility contracts: PASS")
    print(f"- frozen feasibility fingerprint: {EXPECTED_FINGERPRINT}")
    print(f"- source lineage begins after XBRL closeout merge: {EXPECTED_SOURCE_MERGE}")
    print("- exact 2016-01-01..2026-08-11 SEC quarterly-index source window and eight form/era strata are frozen")
    print("- 200-file source sample, header chronology, structured/legacy diagnostics and PIT common-stock identity gates are frozen")
    print("- alpha hypotheses and all target/protected market outcomes remain unopened")
    print("- provider writes, broker/order/PAPER/LIVE/automation authority remain zero; automatic failover remains disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
