from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXPECTED_SOURCE_MERGE = "bf673ad82886e7172db0d54a33dd9612fa9ea29e"
EXPECTED_ENDPOINT = "/stocks/filings/vX/form-4"
EXPECTED_PLAN = "Stocks Starter"
EXPECTED_FAILED_TARGET_HEAD = "b59a64938eb84c0c1e7df3aaea390cc437326f94"
EXPECTED_FAILED_FINGERPRINT = "edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc"
EXPECTED_FAILED_CHECK = "transaction_dates_do_not_postdate_filings"
EXPECTED_WINDOWS = (
    ("research_boundary", "2021-08-16", "2021-08-20"),
    ("mid_history", "2023-08-14", "2023-08-18"),
    ("development_boundary", "2026-05-04", "2026-05-08"),
    ("protected_boundary", "2026-08-07", "2026-08-11"),
)


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _assert_parseable(path: str) -> None:
    ast.parse(_read(path), filename=path)


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    python_files = (
        "packages/providers/massive/phase31.py",
        "packages/backtesting/phase31_feasibility.py",
        "packages/backtesting/phase31_diagnostics.py",
        "scripts/run_phase31_form4_feasibility.py",
        "scripts/diagnose_phase31_form4_lag.py",
    )
    for path in python_files:
        _assert_parseable(path)

    provider = _read("packages/providers/massive/phase31.py")
    feasibility = _read("packages/backtesting/phase31_feasibility.py")
    diagnostic = _read("packages/backtesting/phase31_diagnostics.py")
    runner = _read("scripts/run_phase31_form4_feasibility.py")
    diagnostic_runner = _read("scripts/diagnose_phase31_form4_lag.py")
    phase_doc = _read("docs/phase31_sec_insider_transaction_alpha.md")
    incident_doc = _read("docs/phase31_form4_feasibility_incident.md")
    roadmap = _read("docs/roadmap.md")
    status = _read("docs/current_status.md")
    readme = _read("README.md")
    workflow = _read(".github/workflows/atlas-tests.yml")

    _require(provider, f'PHASE31_FORM4_ENDPOINT = "{EXPECTED_ENDPOINT}"', "Form-4 endpoint")
    _require(provider, 'PHASE31_FORM4_FORM_TYPE = "4"', "original Form-4 only")
    _require(provider, 'PHASE31_FORM4_SORT = "filing_date.asc"', "deterministic sort")
    _require(provider, "PHASE31_FORM4_PAGE_LIMIT = 10000", "page limit")
    _require(provider, '"filing_date.gte"', "lower filing-date bound")
    _require(provider, '"filing_date.lte"', "upper filing-date bound")
    _require(provider, '"form_type": PHASE31_FORM4_FORM_TYPE', "form-type query")
    _require(provider, "tuple(sorted(rows, key=_sort_key))", "deterministic provider sort")

    for bad in ("ticker.upper(", "ticker.lower(", ".str.upper(", ".str.lower(", "casefold("):
        _forbid(provider, bad, "ticker normalization")

    _require(feasibility, EXPECTED_SOURCE_MERGE, "Phase30 source merge")
    _require(feasibility, f'PHASE31_DECLARED_MASSIVE_PLAN = "{EXPECTED_PLAN}"', "declared Massive plan")
    _require(
        feasibility,
        'PHASE31_PUBLIC_AVAILABILITY_RULE = "NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE"',
        "conservative PIT rule",
    )
    _require(feasibility, "PHASE31_ALPHA_HYPOTHESES_FROZEN = False", "hypotheses not frozen")
    _require(feasibility, "PHASE31_TARGET_OUTCOME_READS_ALLOWED = False", "target outcomes forbidden")
    _require(feasibility, "PHASE31_PROTECTED_OUTCOME_READS_ALLOWED = False", "protected outcomes forbidden")
    _require(feasibility, f'"{EXPECTED_FAILED_CHECK}": negative_lag_rows == 0', "chronology gate retained")
    _require(feasibility, '"target_outcome_rows_read": 0', "zero target outcome reads")
    _require(feasibility, '"protected_candidate_rows_read": 0', "zero protected candidate reads")
    _require(feasibility, '"protected_return_rows_read": 0', "zero protected return reads")

    for label, start, end in EXPECTED_WINDOWS:
        _require(feasibility, f'Phase31ProbeWindow("{label}", "{start}", "{end}")', f"probe {label}")

    for forbidden in (
        "phase26_development",
        "phase27",
        "phase28",
        "phase29",
        "phase30_development",
        "forward_return",
        "directional_return",
        "future_close",
        "future_date",
        "packages.execution",
        "packages.brokers",
        "Webull",
        "AlpacaTrading",
    ):
        _forbid(feasibility, forbidden, "outcome/trading authority in feasibility")
        _forbid(diagnostic, forbidden, "outcome/trading authority in diagnostic")

    _require(diagnostic, EXPECTED_FAILED_TARGET_HEAD, "failed target head pinned")
    _require(diagnostic, EXPECTED_FAILED_FINGERPRINT, "failed feasibility fingerprint pinned")
    _require(diagnostic, EXPECTED_FAILED_CHECK, "failed check pinned")
    _require(diagnostic, "sha256_file(path)", "frozen evidence SHA verification")
    _require(diagnostic, '"provider_reads": 0', "diagnostic zero provider reads")
    _require(diagnostic, '"target_outcome_rows_read": 0', "diagnostic zero target outcomes")
    _require(diagnostic, '"protected_candidate_rows_read": 0', "diagnostic zero protected candidates")
    _require(diagnostic, '"protected_return_rows_read": 0', "diagnostic zero protected returns")
    _require(diagnostic, '"chronology_violation_population_reproduced": len(violations) > 0', "violation reproduction")
    _require(diagnostic, "violation_transaction_code_counts", "transaction-code diagnostics")
    _require(diagnostic, "violation_security_type_counts", "security-type diagnostics")
    _require(diagnostic, "violation_10b5_1_counts", "10b5-1 diagnostics")
    _require(diagnostic, "violation_transaction_after_filing_gap_days", "gap diagnostics")

    _forbid(diagnostic, "MassiveRESTClient", "provider call in frozen-evidence diagnostic")
    _forbid(diagnostic_runner, "MassiveRESTClient", "provider call in diagnostic runner")
    _require(diagnostic_runner, "Provider calls: DISABLED / ZERO", "diagnostic provider boundary")
    _require(diagnostic_runner, "Target/protected market outcomes: FORBIDDEN / UNREAD", "diagnostic outcome boundary")
    _require(diagnostic_runner, "Chronology acceptance rule: UNCHANGED", "diagnostic no-gate-weakening boundary")

    _require(runner, "Target/protected market outcomes: FORBIDDEN / UNREAD", "runner outcome boundary")
    _require(runner, "Broker/order/PAPER/LIVE activity: DISABLED", "runner trading boundary")

    _require(phase_doc, "first XNYS session", "conservative next-session explanation")
    _require(phase_doc, "strictly later", "strict later-session timing")
    _require(phase_doc, "transaction_date", "transaction-date warning")
    _require(phase_doc, "early-access/beta", "beta endpoint warning")
    _require(phase_doc, "No Phase31 market outcomes have been read", "no performance read")
    _require(phase_doc, EXPECTED_FAILED_TARGET_HEAD, "phase doc failed target head")
    _require(phase_doc, EXPECTED_FAILED_FINGERPRINT, "phase doc failed fingerprint")
    _require(phase_doc, EXPECTED_FAILED_CHECK, "phase doc failed chronology check")
    _require(phase_doc, "provider calls: 0", "phase doc provider-free diagnostic")

    _require(incident_doc, "FEASIBILITY_FAIL", "incident failed status")
    _require(incident_doc, EXPECTED_FAILED_TARGET_HEAD, "incident target head")
    _require(incident_doc, EXPECTED_FAILED_FINGERPRINT, "incident fingerprint")
    _require(incident_doc, EXPECTED_FAILED_CHECK, "incident failed check")
    _require(incident_doc, "chronology invariant remains intact", "incident gate retention")
    _require(incident_doc, "zero provider calls", "incident provider-free diagnostic")

    _require(roadmap, "Active Phase31 — SEC Form-4 Insider-Transaction Alpha", "roadmap Phase31 rebaseline")
    _require(roadmap, "Phase32 — Signal-to-Trade Construction", "shifted signal-to-trade phase")
    _require(roadmap, "Phase38 — Controlled LIVE Activation", "shifted LIVE phase")
    _require(status, "Stocks Starter", "subscription status")
    _require(status, "phase-31-sec-insider-transaction-alpha", "active branch status")
    _require(status, "FEASIBILITY_FAIL", "current failed feasibility status")
    _require(status, EXPECTED_FAILED_TARGET_HEAD, "status failed target head")
    _require(status, EXPECTED_FAILED_FINGERPRINT, "status failed fingerprint")
    _require(status, EXPECTED_FAILED_CHECK, "status failed check")
    _require(status, "scripts/diagnose_phase31_form4_lag.py", "status diagnostic handoff")
    _require(readme, "Active Phase31: SEC Form-4 Insider-Transaction Alpha", "README active phase")
    _require(readme, "phase31_form4_feasibility_incident.md", "README incident handoff")
    _require(readme, "Phase38", "README current downstream numbering")

    _require(workflow, "Validate Phase 31 Form-4 feasibility contracts", "CI Phase31 validator step")
    _require(workflow, "python scripts/validate_phase31.py", "CI Phase31 validator command")

    print("ATLAS Phase 31 Form-4 feasibility/repair contracts: PASS")
    print("- roadmap remains rebaselined after Phase30 accepted-negative closeout")
    print("- first target feasibility failure is preserved as NOT ACCEPTED evidence")
    print("- chronology gate remains unchanged")
    print("- root-cause diagnostic is frozen-evidence-only and makes zero provider calls")
    print("- target/protected market outcomes remain unread")
    print("- README/status/phase/incident handoff documents are synchronized")
    print("- broker/order/PAPER/LIVE/automatic-failover authority remains disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
