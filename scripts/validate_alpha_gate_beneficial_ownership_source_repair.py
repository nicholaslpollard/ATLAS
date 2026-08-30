from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_PARENT_FINGERPRINT = "f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb"
EXPECTED_REPAIR_FINGERPRINT = "78bf3f18368114a5a6073e8a4d66a0c13ee29a5da78b8adeb1d71b1f10c6f78c"
EXPECTED_REPAIR_CONTRACT = (
    "alpha-gate-sec-beneficial-ownership-source-repair-v2-master-index-role-bounded-index-size-no-market-outcomes"
)
EXPECTED_V1_HEAD = "37194556012bc6df3f5e5579f2dacdcb5bed738b"
EXPECTED_V1_ACCESSION = "0001193125-16-687002"
EXPECTED_MECHANISM = "PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE"


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    provider_path = "packages/providers/sec_edgar_archive.py"
    parent_path = "packages/backtesting/alpha_gate_beneficial_ownership_feasibility.py"
    repair_path = "packages/backtesting/alpha_gate_beneficial_ownership_source_repair.py"
    runner_path = "scripts/run_alpha_gate_beneficial_ownership_source_repair.py"
    doc_path = "docs/alpha_gate_sec_beneficial_ownership_source_repair.md"
    parent_doc_path = "docs/alpha_gate_sec_beneficial_ownership_feasibility.md"
    test_path = "tests/unit/test_alpha_gate_beneficial_ownership_source_repair.py"
    focused_workflow_path = ".github/workflows/beneficial-ownership-alpha-gate-tests.yml"

    provider = _read(provider_path)
    parent = _read(parent_path)
    repair = _read(repair_path)
    runner = _read(runner_path)
    doc = _read(doc_path)
    parent_doc = _read(parent_doc_path)
    tests = _read(test_path)
    focused = _read(focused_workflow_path)

    for path, text in (
        (provider_path, provider),
        (parent_path, parent),
        (repair_path, repair),
        (runner_path, runner),
        (test_path, tests),
    ):
        ast.parse(text, filename=path)

    from packages.backtesting.alpha_gate_beneficial_ownership_feasibility import (
        BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT,
        BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED,
        BENEFICIAL_OWNERSHIP_PROTECTED_OUTCOME_READS_ALLOWED,
        BENEFICIAL_OWNERSHIP_PROVIDER_WRITES,
        BENEFICIAL_OWNERSHIP_TARGET_OUTCOME_READS_ALLOWED,
        beneficial_ownership_feasibility_fingerprint,
    )
    from packages.backtesting.alpha_gate_beneficial_ownership_source_repair import (
        BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_EXTRACTED,
        BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_CONTRACT,
        BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT,
        BENEFICIAL_OWNERSHIP_V1_FAILED_HEAD,
        BENEFICIAL_OWNERSHIP_V1_FAILURE_ACCESSION,
        beneficial_ownership_source_repair_fingerprint,
    )
    from packages.providers.sec_edgar_archive import (
        SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES,
        SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND,
        SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS,
        SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
    )

    if BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT != EXPECTED_PARENT_FINGERPRINT:
        raise AssertionError("parent v1 feasibility fingerprint constant drifted")
    if beneficial_ownership_feasibility_fingerprint() != EXPECTED_PARENT_FINGERPRINT:
        raise AssertionError("parent v1 feasibility fingerprint function drifted")
    if BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_CONTRACT != EXPECTED_REPAIR_CONTRACT:
        raise AssertionError("beneficial-ownership source repair contract drifted")
    if BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT != EXPECTED_REPAIR_FINGERPRINT:
        raise AssertionError("beneficial-ownership source repair fingerprint constant drifted")
    if beneficial_ownership_source_repair_fingerprint() != EXPECTED_REPAIR_FINGERPRINT:
        raise AssertionError("beneficial-ownership source repair fingerprint function drifted")
    if BENEFICIAL_OWNERSHIP_V1_FAILED_HEAD != EXPECTED_V1_HEAD:
        raise AssertionError("v1 failed target head was not preserved")
    if BENEFICIAL_OWNERSHIP_V1_FAILURE_ACCESSION != EXPECTED_V1_ACCESSION:
        raise AssertionError("v1 failed accession was not preserved")

    if SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES != 64_000_000:
        raise AssertionError("quarterly-index response bound drifted")
    if SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES != 20_000_000:
        raise AssertionError("complete-submission response bound drifted")
    if SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND != 5:
        raise AssertionError("SEC archive fair-access cadence drifted")
    if SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS != 0.2:
        raise AssertionError("SEC archive minimum call interval drifted")
    if BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_EXTRACTED != 185:
        raise AssertionError("repaired subject CIK extraction threshold drifted")
    if BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_EXTRACTED != BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED:
        raise AssertionError("v2 reduced the v1 numeric subject-CIK gate")
    if BENEFICIAL_OWNERSHIP_TARGET_OUTCOME_READS_ALLOWED is not False:
        raise AssertionError("target market outcomes were authorized during source repair")
    if BENEFICIAL_OWNERSHIP_PROTECTED_OUTCOME_READS_ALLOWED is not False:
        raise AssertionError("protected outcomes were authorized during source repair")
    if BENEFICIAL_OWNERSHIP_PROVIDER_WRITES != 0:
        raise AssertionError("provider writes were authorized during source repair")

    for token in (
        'SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES = 64_000_000',
        'SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES = 20_000_000',
        "response_limit = self._response_limit(url)",
        "SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND = 5",
        "SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS",
        "SEC_EDGAR_MAX_ATTEMPTS",
        "sec_declared_user_agent",
    ):
        _require(provider, token, "bounded SEC transport repair")

    for token in (
        "INDEXED_ARCHIVE_ENTITY_NOT_SUBJECT_SECURITY_IDENTITY",
        "SEC_COMPLETE_SUBMISSION_HEADER_SUBJECT_COMPANY",
        "SAME_ACCESSION_REQUIRES_EXACT_FORM_DATE_ERA_FORM_CLASS_STRATUM",
        "subject_cik_extracted_min",
        "identity_subject_cik",
        "numeric_thresholds_changed",
        EXPECTED_V1_HEAD,
        EXPECTED_V1_ACCESSION,
    ):
        _require(repair, token, "source-repair semantic invariant")

    _require(repair, "reference_rows = self._cached_reference(cik=subject_cik", "header subject-CIK identity lookup")
    _require(repair, "subject_cik=subject_cik", "header subject-CIK identity resolution")
    _require(repair, "subject_cik == row.index_cik", "subject/index equality diagnostic only")
    _require(repair, "subject_cik_equals_index_cik_diagnostic", "subject/index diagnostic labeling")
    for forbidden in (
        "read_parquet",
        "forward_return",
        "future_close",
        "packages.execution",
        "packages.brokers",
        ".place_order(",
        ".submit_order(",
    ):
        _forbid(repair, forbidden, "market-outcome/trading dependency in source repair")
        _forbid(runner, forbidden, "market-outcome/trading dependency in source-repair runner")

    _require(
        runner,
        "BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT",
        "runner imported frozen repair fingerprint constant",
    )
    _require(runner, "Expected repair fingerprint:", "runner fingerprint reporting")
    _require(runner, "Alpha hypotheses: NOT YET FROZEN", "runner source-only boundary")
    _require(runner, "FORBIDDEN / UNREAD", "runner outcome boundary")
    _require(runner, "Provider writes / broker / order / PAPER / LIVE / automation: DISABLED", "runner authority boundary")
    _forbid(runner, "argparse", "runtime threshold override surface")

    for text, label in ((doc, "repair doc"), (parent_doc, "parent v1 doc")):
        _require(text, EXPECTED_PARENT_FINGERPRINT, f"{label} parent fingerprint")
        _require(text, EXPECTED_MECHANISM, f"{label} mechanism")
    _require(doc, EXPECTED_REPAIR_FINGERPRINT, "repair doc fingerprint")
    _require(doc, EXPECTED_V1_HEAD, "repair doc v1 failed head")
    _require(doc, EXPECTED_V1_ACCESSION, "repair doc v1 failed accession")
    _require(doc, "All numeric thresholds are retained", "repair doc no-threshold-relaxation boundary")
    _require(doc, "zero stock forward returns", "repair doc zero-outcome boundary")

    _require(tests, "test_duplicate_accession_entity_associations_collapse_when_filing_semantics_match", "duplicate-association unit test")
    _require(tests, "test_duplicate_accession_filing_semantic_conflict_still_fails_closed", "semantic-conflict fail-closed unit test")
    _require(tests, "test_authoritative_security_identity_uses_submission_subject_cik_not_index_cik", "subject-CIK authority unit test")

    _require(focused, "Validate SEC beneficial-ownership targeted source repair", "focused repair validator step")
    _require(focused, "scripts/validate_alpha_gate_beneficial_ownership_source_repair.py", "focused repair validator command")
    _require(focused, "tests/unit/test_alpha_gate_beneficial_ownership_source_repair.py", "focused repair unit tests")

    print("ATLAS SEC Schedule 13D/13G targeted source repair v2 contracts: PASS")
    print(f"- parent v1 failure retained at head {EXPECTED_V1_HEAD}")
    print(f"- frozen repair fingerprint: {EXPECTED_REPAIR_FINGERPRINT}")
    print("- SEC quarterly-index transport is bounded at 64 MB while submission transport remains bounded at 20 MB")
    print("- SEC archive pacing is capped at 5 calls/second (0.2-second minimum interval)")
    print("- master-index CIK is provenance only; official SEC-header SUBJECT COMPANY CIK is the security identity authority")
    print("- duplicate accession associations are collapsed only when filing-level semantics agree exactly")
    print("- all numeric source gates are retained; alpha hypotheses and target/protected outcomes remain unopened")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())