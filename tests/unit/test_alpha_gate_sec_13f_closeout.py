from __future__ import annotations

from copy import deepcopy

import pytest

from packages.backtesting.alpha_gate_sec_13f_closeout import (
    SEC_13F_CLOSEOUT_FINGERPRINT,
    SEC_13F_EXPECTED_AFFECTED_ACCESSIONS,
    SEC_13F_EXPECTED_BULK_MALFORMED_ROWS,
    SEC_13F_FAILURE_TAXONOMY,
    SEC_13F_SOURCE_DISPOSITION,
    sec_13f_closeout_fingerprint,
    validate_sec_13f_reconciliation_for_closeout,
)
from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation import (
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT,
)
from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation_v2 import (
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT,
)


def _accepted_reconciliation() -> dict:
    return {
        "contract_version": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT,
        "policy_fingerprint": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT,
        "status": "RECONCILIATION_COMPLETE",
        "complete": True,
        "v1_contract_preserved": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT,
        "v1_fingerprint_preserved": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT,
        "v1_failure_boundary": (
            "PARTIAL_SOURCE_ACQUISITION_STOPPED_ON_DERIVED_ARCHIVE_PATH_HTTP_404; "
            "NO_FINAL_V1_REPORT; RAW_ORIGINAL_FILINGS_PRESERVED"
        ),
        "affected_accessions": 374,
        "bulk_malformed_rows": 10431,
        "master_index_resolved_accessions": 374,
        "master_index_archive_cik_differs_from_bulk_cik_accessions": 1,
        "original_cusip_rows": 109135,
        "original_malformed_cusip_rows": 10431,
        "row_count_match_accessions": 374,
        "exact_cusip_multiset_match_accessions": 374,
        "bulk_malformed_rows_exactly_preserved_in_original": 10431,
        "bulk_short_rows_left_zero_pad_candidate_present_in_original": 42,
        "classification_counts": {"AS_FILED_MALFORMED_CUSIP_CONFIRMED": 374},
        "classification_bulk_malformed_rows": {
            "AS_FILED_MALFORMED_CUSIP_CONFIRMED": 10431
        },
        "governance": {
            "cusip_repair_performed": False,
            "atlas_identity_granted": False,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "scientific_freeze_allowed": False,
            "phase33_signal_to_trade_authority": False,
        },
    }


def test_closeout_fingerprint_is_frozen() -> None:
    assert sec_13f_closeout_fingerprint() == SEC_13F_CLOSEOUT_FINGERPRINT
    assert SEC_13F_CLOSEOUT_FINGERPRINT == (
        "0375d5567e0547c151f9fb140309aa568d17528246e611a68fa5984a1c481acd"
    )


def test_closeout_disposition_and_population_are_frozen() -> None:
    assert SEC_13F_SOURCE_DISPOSITION == "ACCEPTED_NEGATIVE_SOURCE_INTEGRITY_FAILURE"
    assert SEC_13F_FAILURE_TAXONOMY == "SOURCE_INTEGRITY_FAIL"
    assert SEC_13F_EXPECTED_AFFECTED_ACCESSIONS == 374
    assert SEC_13F_EXPECTED_BULK_MALFORMED_ROWS == 10_431


def test_accepted_reconciliation_satisfies_every_closeout_check() -> None:
    checks = validate_sec_13f_reconciliation_for_closeout(_accepted_reconciliation())
    assert checks
    assert all(checks.values())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("exact_cusip_multiset_match_accessions", 373),
        ("bulk_malformed_rows_exactly_preserved_in_original", 10430),
        ("classification_counts", {"BULK_FLATTENING_DIFFERS_FROM_VALID_ORIGINAL": 374}),
    ],
)
def test_closeout_rejects_source_result_drift(field: str, value: object) -> None:
    report = deepcopy(_accepted_reconciliation())
    report[field] = value
    checks = validate_sec_13f_reconciliation_for_closeout(report)
    assert not all(checks.values())


def test_closeout_rejects_any_identity_or_outcome_authority() -> None:
    report = _accepted_reconciliation()
    report["governance"]["atlas_identity_granted"] = True
    report["governance"]["target_outcome_rows_read"] = 1
    checks = validate_sec_13f_reconciliation_for_closeout(report)
    assert checks["atlas_identity_never_granted"] is False
    assert checks["target_outcomes_unread"] is False


def test_runner_imports_without_provider_access() -> None:
    from scripts.run_alpha_gate_sec_13f_source_only_closeout import main

    assert callable(main)
