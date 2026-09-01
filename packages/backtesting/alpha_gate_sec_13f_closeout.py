from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation import (
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT,
)
from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation_v2 import (
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT,
    SEC_13F_ORIGINAL_EDGAR_V2_REPORT_RELATIVE,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings


SEC_13F_CLOSEOUT_CONTRACT = (
    "alpha-gate-sec-13f-closeout-v1-as-filed-cusip-source-integrity-failure-no-market-outcomes"
)
SEC_13F_CLOSEOUT_FINGERPRINT = (
    "0375d5567e0547c151f9fb140309aa568d17528246e611a68fa5984a1c481acd"
)
SEC_13F_SOURCE_DISPOSITION = "ACCEPTED_NEGATIVE_SOURCE_INTEGRITY_FAILURE"
SEC_13F_FAILURE_TAXONOMY = "SOURCE_INTEGRITY_FAIL"
SEC_13F_V1_LOCATOR_FAILURE_TAXONOMY = "IMPLEMENTATION_DEFECT_FIXED"
SEC_13F_EXPECTED_AFFECTED_ACCESSIONS = 374
SEC_13F_EXPECTED_BULK_MALFORMED_ROWS = 10_431
SEC_13F_EXPECTED_ORIGINAL_CUSIP_ROWS = 109_135
SEC_13F_EXPECTED_ORIGINAL_MALFORMED_ROWS = 10_431
SEC_13F_EXPECTED_ROW_COUNT_MATCH_ACCESSIONS = 374
SEC_13F_EXPECTED_EXACT_MULTISET_MATCH_ACCESSIONS = 374
SEC_13F_EXPECTED_EXACT_PRESERVED_MALFORMED_ROWS = 10_431
SEC_13F_EXPECTED_CLASSIFICATION = "AS_FILED_MALFORMED_CUSIP_CONFIRMED"
SEC_13F_EXPECTED_MASTER_INDEX_CIK_DIFFERENCES = 1
SEC_13F_EXPECTED_ORIGINAL_PAD_CANDIDATE_ROWS = 42
SEC_13F_CLOSEOUT_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_13f_source_integrity_closeout_v1/closeout.json"
)

_POST_RESULT_RESCUES_FORBIDDEN = (
    "LOWER_99_5_PERCENT_CUSIP_VALIDITY_GATE",
    "LEFT_ZERO_PAD_MALFORMED_CUSIP",
    "DROP_MALFORMED_ROWS",
    "DROP_MALFORMED_FILINGS",
    "INFER_CUSIP_FROM_ISSUER_OR_CLASS",
    "REDEFINE_VALID_CUSIP_LENGTH",
    "SELECT_ONLY_REPAIRABLE_ROWS",
    "OPEN_OUTCOMES_TO_JUDGE_SOURCE_REPAIR",
)


class SEC13FCloseoutError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": SEC_13F_CLOSEOUT_CONTRACT,
        "parent_reconciliation_contract": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT,
        "parent_reconciliation_fingerprint": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT,
        "source_disposition": SEC_13F_SOURCE_DISPOSITION,
        "failure_taxonomy": SEC_13F_FAILURE_TAXONOMY,
        "expected_affected_accessions": SEC_13F_EXPECTED_AFFECTED_ACCESSIONS,
        "expected_bulk_malformed_rows": SEC_13F_EXPECTED_BULK_MALFORMED_ROWS,
        "expected_row_count_match_accessions": SEC_13F_EXPECTED_ROW_COUNT_MATCH_ACCESSIONS,
        "expected_exact_cusip_multiset_match_accessions": SEC_13F_EXPECTED_EXACT_MULTISET_MATCH_ACCESSIONS,
        "expected_exact_preserved_malformed_rows": SEC_13F_EXPECTED_EXACT_PRESERVED_MALFORMED_ROWS,
        "expected_classification": SEC_13F_EXPECTED_CLASSIFICATION,
        "v1_locator_failure_taxonomy": SEC_13F_V1_LOCATOR_FAILURE_TAXONOMY,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "historical_supported_alpha": 0,
        "phase33_signal_to_trade_authority": False,
        "post_result_repair_allowed": False,
    }


def sec_13f_closeout_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload()).encode("utf-8")).hexdigest()


def _load_json_with_sha(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise SEC13FCloseoutError(f"required SEC 13F closeout evidence is missing: {path}")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SEC13FCloseoutError(
            f"SEC 13F closeout evidence is not valid UTF-8 JSON: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise SEC13FCloseoutError(f"SEC 13F closeout evidence root is not an object: {path}")
    return value, digest


def validate_sec_13f_reconciliation_for_closeout(
    reconciliation: dict[str, Any],
) -> dict[str, bool]:
    governance = (
        reconciliation.get("governance")
        if isinstance(reconciliation.get("governance"), dict)
        else {}
    )
    expected_classifications = {SEC_13F_EXPECTED_CLASSIFICATION: SEC_13F_EXPECTED_AFFECTED_ACCESSIONS}
    expected_classification_rows = {
        SEC_13F_EXPECTED_CLASSIFICATION: SEC_13F_EXPECTED_BULK_MALFORMED_ROWS
    }
    return {
        "parent_contract_exact": (
            reconciliation.get("contract_version")
            == SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT
        ),
        "parent_fingerprint_exact": (
            reconciliation.get("policy_fingerprint")
            == SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT
        ),
        "reconciliation_complete": (
            reconciliation.get("status") == "RECONCILIATION_COMPLETE"
            and reconciliation.get("complete") is True
        ),
        "v1_contract_preserved": (
            reconciliation.get("v1_contract_preserved")
            == SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT
        ),
        "v1_fingerprint_preserved": (
            reconciliation.get("v1_fingerprint_preserved")
            == SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT
        ),
        "v1_locator_failure_preserved": (
            "PARTIAL_SOURCE_ACQUISITION_STOPPED_ON_DERIVED_ARCHIVE_PATH_HTTP_404"
            in str(reconciliation.get("v1_failure_boundary") or "")
        ),
        "population_exact": (
            reconciliation.get("affected_accessions") == SEC_13F_EXPECTED_AFFECTED_ACCESSIONS
            and reconciliation.get("bulk_malformed_rows") == SEC_13F_EXPECTED_BULK_MALFORMED_ROWS
            and reconciliation.get("master_index_resolved_accessions")
            == SEC_13F_EXPECTED_AFFECTED_ACCESSIONS
        ),
        "original_row_counts_exact": (
            reconciliation.get("original_cusip_rows") == SEC_13F_EXPECTED_ORIGINAL_CUSIP_ROWS
            and reconciliation.get("original_malformed_cusip_rows")
            == SEC_13F_EXPECTED_ORIGINAL_MALFORMED_ROWS
        ),
        "row_count_match_all_accessions": (
            reconciliation.get("row_count_match_accessions")
            == SEC_13F_EXPECTED_ROW_COUNT_MATCH_ACCESSIONS
        ),
        "exact_cusip_multiset_match_all_accessions": (
            reconciliation.get("exact_cusip_multiset_match_accessions")
            == SEC_13F_EXPECTED_EXACT_MULTISET_MATCH_ACCESSIONS
        ),
        "all_malformed_rows_exactly_as_filed": (
            reconciliation.get("bulk_malformed_rows_exactly_preserved_in_original")
            == SEC_13F_EXPECTED_EXACT_PRESERVED_MALFORMED_ROWS
        ),
        "classification_exact": (
            reconciliation.get("classification_counts") == expected_classifications
            and reconciliation.get("classification_bulk_malformed_rows")
            == expected_classification_rows
        ),
        "locator_defect_quantified": (
            reconciliation.get("master_index_archive_cik_differs_from_bulk_cik_accessions")
            == SEC_13F_EXPECTED_MASTER_INDEX_CIK_DIFFERENCES
        ),
        "original_padding_signal_exact": (
            reconciliation.get("bulk_short_rows_left_zero_pad_candidate_present_in_original")
            == SEC_13F_EXPECTED_ORIGINAL_PAD_CANDIDATE_ROWS
        ),
        "cusip_repair_never_performed": governance.get("cusip_repair_performed") is False,
        "atlas_identity_never_granted": governance.get("atlas_identity_granted") is False,
        "target_outcomes_unread": governance.get("target_outcome_rows_read") == 0,
        "protected_returns_unread": governance.get("protected_return_rows_read") == 0,
        "protected_holdout_unconsumed": governance.get("protected_holdout_consumed") is False,
        "scientific_freeze_never_granted": governance.get("scientific_freeze_allowed") is False,
        "phase33_authority_false": governance.get("phase33_signal_to_trade_authority") is False,
    }


def _existing_closeout(
    report_path: Path,
    parent_sha256: str,
) -> dict[str, Any] | None:
    if not report_path.is_file():
        return None
    report, _ = _load_json_with_sha(report_path)
    checks = {
        "contract": report.get("contract_version") == SEC_13F_CLOSEOUT_CONTRACT,
        "fingerprint": report.get("closeout_fingerprint") == SEC_13F_CLOSEOUT_FINGERPRINT,
        "parent_sha": report.get("reconciliation_report_sha256") == parent_sha256,
        "source_disposition": report.get("source_disposition") == SEC_13F_SOURCE_DISPOSITION,
        "failure_taxonomy": report.get("failure_taxonomy") == SEC_13F_FAILURE_TAXONOMY,
        "target_outcomes": report.get("target_outcome_rows_read") == 0,
        "protected_returns": report.get("protected_return_rows_read") == 0,
        "holdout": report.get("protected_holdout_consumed") is False,
        "phase33": report.get("phase33_signal_to_trade_authority") is False,
    }
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SEC13FCloseoutError(
            "existing SEC 13F closeout report drifted: " + ", ".join(failed)
        )
    return report


def close_sec_13f_source_only(settings: AtlasSettings) -> dict[str, Any]:
    """Close the frozen 13F family from the persisted source-only V2 reconciliation.

    This function performs no provider, market-price, benchmark, broker, order,
    PAPER, LIVE, or automation access.
    """
    if sec_13f_closeout_fingerprint() != SEC_13F_CLOSEOUT_FINGERPRINT:
        raise SEC13FCloseoutError("frozen SEC 13F closeout fingerprint drifted")

    derived_root = settings.resolved_path(settings.data.paths.derived)
    reconciliation_path = derived_root / SEC_13F_ORIGINAL_EDGAR_V2_REPORT_RELATIVE
    reconciliation, reconciliation_sha256 = _load_json_with_sha(reconciliation_path)
    checks = validate_sec_13f_reconciliation_for_closeout(reconciliation)
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SEC13FCloseoutError(
            "SEC 13F source-only closeout evidence failed: " + ", ".join(failed)
        )

    report_path = derived_root / SEC_13F_CLOSEOUT_REPORT_RELATIVE
    existing = _existing_closeout(report_path, reconciliation_sha256)
    if existing is not None:
        return existing

    report = {
        "contract_version": SEC_13F_CLOSEOUT_CONTRACT,
        "closeout_fingerprint": SEC_13F_CLOSEOUT_FINGERPRINT,
        "status": "CLOSED",
        "disposition": "ACCEPTED_NEGATIVE",
        "source_disposition": SEC_13F_SOURCE_DISPOSITION,
        "failure_taxonomy": SEC_13F_FAILURE_TAXONOMY,
        "mechanism": "PIT_SEC_FORM13F_INSTITUTIONAL_POSITIONING_CHANGE_AND_CONSENSUS_ACCUMULATION",
        "reconciliation_contract": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT,
        "reconciliation_fingerprint": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT,
        "reconciliation_report_sha256": reconciliation_sha256,
        "affected_accessions": SEC_13F_EXPECTED_AFFECTED_ACCESSIONS,
        "bulk_malformed_rows": SEC_13F_EXPECTED_BULK_MALFORMED_ROWS,
        "original_cusip_rows": SEC_13F_EXPECTED_ORIGINAL_CUSIP_ROWS,
        "original_malformed_cusip_rows": SEC_13F_EXPECTED_ORIGINAL_MALFORMED_ROWS,
        "row_count_match_accessions": SEC_13F_EXPECTED_ROW_COUNT_MATCH_ACCESSIONS,
        "exact_cusip_multiset_match_accessions": SEC_13F_EXPECTED_EXACT_MULTISET_MATCH_ACCESSIONS,
        "bulk_malformed_rows_exactly_preserved_in_original": (
            SEC_13F_EXPECTED_EXACT_PRESERVED_MALFORMED_ROWS
        ),
        "classification_counts": {
            SEC_13F_EXPECTED_CLASSIFICATION: SEC_13F_EXPECTED_AFFECTED_ACCESSIONS
        },
        "classification_bulk_malformed_rows": {
            SEC_13F_EXPECTED_CLASSIFICATION: SEC_13F_EXPECTED_BULK_MALFORMED_ROWS
        },
        "v1_locator_failure_taxonomy": SEC_13F_V1_LOCATOR_FAILURE_TAXONOMY,
        "v1_locator_failure_boundary": reconciliation.get("v1_failure_boundary"),
        "master_index_archive_cik_differs_from_bulk_cik_accessions": (
            SEC_13F_EXPECTED_MASTER_INDEX_CIK_DIFFERENCES
        ),
        "source_conclusion": (
            "Every malformed 2016Q1 bulk CUSIP row in the frozen affected population is "
            "reproduced exactly in the authoritative original as-filed EDGAR information-table "
            "XML. The frozen Gate0 source-integrity failure is therefore not a bulk-flattening "
            "artifact and cannot be repaired inside this experiment without changing source rules."
        ),
        "post_result_rescues_forbidden": list(_POST_RESULT_RESCUES_FORBIDDEN),
        "post_result_repair_allowed": False,
        "checks": checks,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "historical_supported_alpha": 0,
        "phase33_signal_to_trade_authority": False,
        "provider_reads_performed": 0,
        "provider_writes_performed": 0,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "automation_writes_performed": 0,
        "next_scientific_action": (
            "Preregister a materially different economic/information alpha mechanism. A future "
            "Form 13F successor is permitted only as a new version whose authoritative CUSIP/"
            "instrument canonicalization and treatment of malformed as-filed holdings are frozen "
            "before any market outcome is opened."
        ),
        "report_path": str(report_path),
    }
    atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
