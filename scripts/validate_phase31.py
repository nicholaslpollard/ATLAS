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
EXPECTED_DIAGNOSTIC_HEAD = "80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7"
EXPECTED_VIOLATION_SHA = "3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044"
EXPECTED_SOURCE_QUALITY_FINGERPRINT = "2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83"
EXPECTED_SOURCE_QUALITY_POLICY = "RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE"
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
        "packages/backtesting/phase31_source_quality.py",
        "scripts/run_phase31_form4_feasibility.py",
        "scripts/diagnose_phase31_form4_lag.py",
        "scripts/run_phase31_form4_source_quality_repair.py",
    )
    for path in python_files:
        _assert_parseable(path)

    provider = _read("packages/providers/massive/phase31.py")
    feasibility = _read("packages/backtesting/phase31_feasibility.py")
    diagnostic = _read("packages/backtesting/phase31_diagnostics.py")
    source_quality = _read("packages/backtesting/phase31_source_quality.py")
    runner = _read("scripts/run_phase31_form4_feasibility.py")
    diagnostic_runner = _read("scripts/diagnose_phase31_form4_lag.py")
    repair_runner = _read("scripts/run_phase31_form4_source_quality_repair.py")
    phase_doc = _read("docs/phase31_sec_insider_transaction_alpha.md")
    incident_doc = _read("docs/phase31_form4_feasibility_incident.md")
    repair_doc = _read("docs/phase31_form4_source_quality_repair.md")
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
    _require(feasibility, 'PHASE31_PUBLIC_AVAILABILITY_RULE = "NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE"', "conservative PIT rule")
    _require(feasibility, "PHASE31_ALPHA_HYPOTHESES_FROZEN = False", "hypotheses not frozen")
    _require(feasibility, "PHASE31_TARGET_OUTCOME_READS_ALLOWED = False", "target outcomes forbidden")
    _require(feasibility, "PHASE31_PROTECTED_OUTCOME_READS_ALLOWED = False", "protected outcomes forbidden")
    _require(feasibility, f'"{EXPECTED_FAILED_CHECK}": negative_lag_rows == 0', "original chronology gate retained")
    _require(feasibility, '"target_outcome_rows_read": 0', "zero target outcome reads")
    _require(feasibility, '"protected_candidate_rows_read": 0', "zero protected candidate reads")
    _require(feasibility, '"protected_return_rows_read": 0', "zero protected return reads")

    for label, start, end in EXPECTED_WINDOWS:
        _require(feasibility, f'Phase31ProbeWindow("{label}", "{start}", "{end}")', f"probe {label}")

    forbidden_research_authority = (
        "phase26_development", "phase27", "phase28", "phase29", "phase30_development",
        "forward_return", "directional_return", "future_close", "packages.execution",
        "packages.brokers", "Webull", "AlpacaTrading",
    )
    for forbidden in forbidden_research_authority:
        _forbid(feasibility, forbidden, "outcome/trading authority in feasibility")
        _forbid(diagnostic, forbidden, "outcome/trading authority in diagnostic")
        _forbid(source_quality, forbidden, "outcome/trading authority in source-quality repair")

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
    _require(diagnostic, "violation_security_type_counts", "transaction-code diagnostics")
    _require(diagnostic, "violation_10b5_1_counts", "10b5-1 diagnostics")
    _require(diagnostic, "violation_transaction_after_filing_gap_days", "gap diagnostics")

    _forbid(diagnostic, "MassiveRESTClient", "provider call in frozen-evidence diagnostic")
    _forbid(diagnostic_runner, "MassiveRESTClient", "provider call in diagnostic runner")
    _require(diagnostic_runner, "Provider calls: DISABLED / ZERO", "diagnostic provider boundary")
    _require(diagnostic_runner, "Target/protected market outcomes: FORBIDDEN / UNREAD", "diagnostic outcome boundary")
    _require(diagnostic_runner, "Chronology acceptance rule: UNCHANGED", "diagnostic no-gate-weakening boundary")

    _require(source_quality, EXPECTED_FAILED_TARGET_HEAD, "repair failed target lineage")
    _require(source_quality, EXPECTED_FAILED_FINGERPRINT, "repair failed fingerprint lineage")
    _require(source_quality, EXPECTED_VIOLATION_SHA, "repair exact diagnostic evidence SHA")
    _require(source_quality, EXPECTED_SOURCE_QUALITY_POLICY, "frozen source-quality policy")
    _require(source_quality, "transaction > filing", "general chronology trigger")
    _require(source_quality, '"quarantine_scope": "ENTIRE_ACCESSION"', "accession-level quarantine")
    _require(source_quality, "contaminated.add(accession)", "generic contaminated-accession classifier")
    _require(source_quality, "authoritative_corpus_has_zero_post_filing_transactions", "zero-invalid authoritative corpus")
    _require(source_quality, "raw_row_conservation_exact", "raw row conservation")
    _require(source_quality, "all_original_nonchronology_checks_remain_pass", "retained original feasibility checks")
    _require(source_quality, '"provider_reads": 0', "repair zero provider reads")
    _require(source_quality, '"target_outcome_rows_read": 0', "repair zero target outcomes")
    _require(source_quality, '"protected_return_rows_read": 0', "repair zero protected returns")
    _require(source_quality, '"alpha_support_granted": False', "repair grants no alpha")
    _require(source_quality, '"phase32_entry_satisfied": False', "repair does not unlock Phase32")
    _require(source_quality, '"scientific_policy_freeze_authorized": all(checks.values())', "repair authority boundary")
    _forbid(source_quality, "WISH", "ticker-specific quarantine")
    _forbid(source_quality, "0000950170-23-043337", "accession-specific quarantine")
    _forbid(source_quality, "MassiveRESTClient", "provider call in repair")
    _forbid(repair_runner, "MassiveRESTClient", "provider call in repair runner")

    from packages.backtesting.phase31_source_quality import phase31_source_quality_fingerprint
    if phase31_source_quality_fingerprint() != EXPECTED_SOURCE_QUALITY_FINGERPRINT:
        raise AssertionError("Phase31 source-quality fingerprint drifted")

    _require(repair_runner, "Provider calls: DISABLED / ZERO", "repair runner provider boundary")
    _require(repair_runner, "Chronology rule: UNCHANGED", "repair runner chronology boundary")
    _require(repair_runner, "Raw provider evidence: PRESERVED", "repair runner raw preservation")
    _require(repair_runner, "entire accession", "repair runner accession quarantine")
    _require(repair_runner, "Scientific-policy freeze authorized", "repair runner next authority")
    _require(repair_runner, "Phase32 entry satisfied", "repair runner downstream lock")
    _require(runner, "Target/protected market outcomes: FORBIDDEN / UNREAD", "original runner outcome boundary")
    _require(runner, "Broker/order/PAPER/LIVE activity: DISABLED", "original runner trading boundary")

    # Frozen Phase31 phase/incident/repair records retain exact feasibility-era evidence.
    _require(phase_doc, "first XNYS session", "conservative next-session explanation")
    _require(phase_doc, "strictly later", "strict later-session timing")
    _require(phase_doc, "transaction_date", "transaction-date warning")
    _require(phase_doc, "early-access/beta", "beta endpoint warning")
    _require(phase_doc, "No Phase31 market outcomes have been read", "no performance read")
    _require(phase_doc, EXPECTED_FAILED_TARGET_HEAD, "phase doc failed target head")
    _require(phase_doc, EXPECTED_FAILED_FINGERPRINT, "phase doc failed fingerprint")
    _require(phase_doc, EXPECTED_VIOLATION_SHA, "phase doc diagnostic evidence")
    _require(phase_doc, EXPECTED_SOURCE_QUALITY_FINGERPRINT, "phase doc repair fingerprint")
    _require(phase_doc, EXPECTED_SOURCE_QUALITY_POLICY, "phase doc repair policy")
    _require(phase_doc, "Massive beta source-association/data-quality defect", "phase doc root-cause classification")
    _require(phase_doc, "provider calls = 0", "phase doc provider-free diagnostic")

    _require(incident_doc, "FEASIBILITY_FAIL", "incident failed status")
    _require(incident_doc, EXPECTED_FAILED_TARGET_HEAD, "incident target head")
    _require(incident_doc, EXPECTED_FAILED_FINGERPRINT, "incident fingerprint")
    _require(incident_doc, EXPECTED_VIOLATION_SHA, "incident diagnostic artifact")
    _require(incident_doc, EXPECTED_SOURCE_QUALITY_FINGERPRINT, "incident repair fingerprint")
    _require(incident_doc, "Massive early-access/beta source-association/data-quality defect", "incident classification")
    _require(incident_doc, "chronology invariant remains intact", "incident gate retention")
    _require(incident_doc, "There is **no** \"one bad row is acceptable\" tolerance", "incident no numeric exception")

    _require(repair_doc, EXPECTED_VIOLATION_SHA, "repair doc diagnostic artifact")
    _require(repair_doc, EXPECTED_SOURCE_QUALITY_FINGERPRINT, "repair doc fingerprint")
    _require(repair_doc, EXPECTED_SOURCE_QUALITY_POLICY, "repair doc policy")
    _require(repair_doc, "quarantine the **entire accession_number**", "repair doc accession scope")
    _require(repair_doc, "There is no numeric anomaly tolerance", "repair doc no threshold weakening")
    _require(repair_doc, "zero provider calls", "repair doc provider-free target")
    _require(repair_doc, "does **not** erase or reinterpret the original failed feasibility run", "repair doc provenance")

    # Living continuation docs may advance beyond Phase31 and Phase32. They must preserve
    # the accepted Phase31 result while accurately naming the current authority boundary.
    for doc_name, doc in (("roadmap", roadmap), ("current status", status), ("README", readme)):
        _require(doc, "Phase31", f"{doc_name} Phase31 provenance")
        _require(doc, "ACCEPTED_NEGATIVE", f"{doc_name} accepted-negative history")
        _require(doc, "Phase32", f"{doc_name} Phase32 continuation provenance")
        _require(doc, "Phase33", f"{doc_name} downstream authority boundary")

    _require(roadmap, "Accepted foundation through Phase32", "roadmap current accepted foundation")
    _require(roadmap, "Historical supported alpha remains **zero**", "roadmap authority continuity")
    _require(roadmap, "Phase33 — Signal-to-Trade Construction", "roadmap current downstream gate")

    _require(status, "Stocks Starter", "subscription status")
    _require(status, "phase-32-sec-8k-material-event-alpha", "current closeout branch status")
    _require(status, "FEASIBILITY_FAIL", "retained original feasibility status")
    _require(status, EXPECTED_SOURCE_QUALITY_FINGERPRINT, "retained Phase31 source repair fingerprint")
    _require(status, EXPECTED_SOURCE_QUALITY_POLICY, "retained Phase31 source repair policy")
    _require(status, "Massive beta source-association/data-quality defect", "retained Phase31 root cause")
    _require(status, "Phase31 produced zero survivors/winners/finalists/support and zero protected reads", "Phase31 final evidence")
    _require(status, "Phase32 remains closed", "current Phase32 closeout state")

    _require(readme, "Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is `ACCEPTED_NEGATIVE` as well", "README retained modern alpha dispositions")
    _require(readme, "Phase33 signal-to-trade remains blocked", "README downstream authority block")
    _require(readme, "LIVE and automatic broker failover remain disabled", "README live authority block")

    _require(workflow, "Validate Phase 31 Form-4 feasibility contracts", "CI Phase31 validator step")
    _require(workflow, "python scripts/validate_phase31.py", "CI Phase31 validator command")

    print("ATLAS Phase 31 Form-4 feasibility/diagnostic/source-quality contracts: PASS")
    print("- original target FEASIBILITY_FAIL remains preserved as historical evidence")
    print("- chronology rule remains unchanged and correctly detected a provider-beta defect")
    print("- root cause is classified before repair; no performance evidence was consulted")
    print("- source-quality repair preserves raw rows and quarantines contaminated accessions fail-closed")
    print("- repair classifier has no ticker/accession-specific exception and no numeric bad-row tolerance")
    print("- Phase31 evidence stays immutable while living continuation docs accurately advance through Phase32 closeout")
    print("- Phase31 final ACCEPTED_NEGATIVE disposition and zero protected reads remain preserved")
    print("- Phase33/trading/LIVE authority remain blocked by the current continuation docs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
