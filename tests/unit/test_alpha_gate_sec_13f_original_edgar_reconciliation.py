from __future__ import annotations

from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation import (
    SEC_13F_ORIGINAL_EDGAR_ATLAS_IDENTITY_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_CUSIP_REPAIR_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS,
    SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS,
    SEC_13F_ORIGINAL_EDGAR_PHASE33_AUTHORITY,
    SEC_13F_ORIGINAL_EDGAR_PROTECTED_OUTCOMES_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT,
    SEC_13F_ORIGINAL_EDGAR_SCIENTIFIC_FREEZE_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_TARGET_OUTCOMES_ALLOWED,
    extract_original_13f_cusips,
    reconcile_accession_cusips,
    sec_13f_original_edgar_reconciliation_fingerprint,
)


def _complete_submission(info_xml: str) -> str:
    return (
        "<SEC-DOCUMENT>0000000000-16-000001.txt : 20160216\n"
        "<DOCUMENT>\n<TYPE>INFORMATION TABLE\n<XML>\n"
        f"{info_xml}\n"
        "</XML>\n</DOCUMENT>\n</SEC-DOCUMENT>\n"
    )


def test_reconciliation_fingerprint_is_frozen() -> None:
    assert (
        sec_13f_original_edgar_reconciliation_fingerprint()
        == SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT
    )
    assert SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT == (
        "6b28e6e7eac599d1f795fed2de200c0886f49b91af29a699faa98a043521c91c"
    )


def test_reconciliation_scope_and_governance_are_source_only() -> None:
    assert SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS == 374
    assert SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS == 10_431
    assert not SEC_13F_ORIGINAL_EDGAR_CUSIP_REPAIR_ALLOWED
    assert not SEC_13F_ORIGINAL_EDGAR_ATLAS_IDENTITY_ALLOWED
    assert not SEC_13F_ORIGINAL_EDGAR_TARGET_OUTCOMES_ALLOWED
    assert not SEC_13F_ORIGINAL_EDGAR_PROTECTED_OUTCOMES_ALLOWED
    assert not SEC_13F_ORIGINAL_EDGAR_SCIENTIFIC_FREEZE_ALLOWED
    assert not SEC_13F_ORIGINAL_EDGAR_PHASE33_AUTHORITY


def test_extract_original_cusips_reads_xml_without_padding() -> None:
    text = _complete_submission(
        "<informationTable><infoTable><cusip>012345678</cusip></infoTable>"
        "<infoTable><cusip>12345678</cusip></infoTable></informationTable>"
    )
    parsed = extract_original_13f_cusips(text)
    assert parsed["xml_parse_errors"] == 0
    assert parsed["cusips"] == ["012345678", "12345678"]


def test_exact_malformed_original_is_classified_as_as_filed_defect() -> None:
    original = _complete_submission(
        "<informationTable><infoTable><cusip>12345678</cusip></infoTable>"
        "<infoTable><cusip>987654321</cusip></infoTable></informationTable>"
    )
    result = reconcile_accession_cusips(
        accession="0000000000-16-000001",
        cik="1",
        bulk_cusips=["12345678", "987654321"],
        original_text=original,
        source_url="https://www.sec.gov/Archives/edgar/data/1/0000000000-16-000001.txt",
        source_sha256="a" * 64,
        source_mode="TEST",
    )
    assert result["classification"] == "AS_FILED_MALFORMED_CUSIP_CONFIRMED"
    assert result["bulk_malformed_rows_exactly_preserved_in_original"] == 1


def test_valid_original_with_same_row_count_is_bulk_difference() -> None:
    original = _complete_submission(
        "<informationTable><infoTable><cusip>012345678</cusip></infoTable>"
        "<infoTable><cusip>987654321</cusip></infoTable></informationTable>"
    )
    result = reconcile_accession_cusips(
        accession="0000000000-16-000001",
        cik="1",
        bulk_cusips=["12345678", "987654321"],
        original_text=original,
        source_url="https://www.sec.gov/Archives/edgar/data/1/0000000000-16-000001.txt",
        source_sha256="b" * 64,
        source_mode="TEST",
    )
    assert result["classification"] == "BULK_FLATTENING_DIFFERS_FROM_VALID_ORIGINAL"
    assert result["bulk_short_rows_left_zero_pad_candidate_present_in_original"] == 1


def test_row_count_mismatch_fails_closed_as_source_difference() -> None:
    original = _complete_submission(
        "<informationTable><infoTable><cusip>012345678</cusip></infoTable></informationTable>"
    )
    result = reconcile_accession_cusips(
        accession="0000000000-16-000001",
        cik="1",
        bulk_cusips=["12345678", "987654321"],
        original_text=original,
        source_url="https://www.sec.gov/Archives/edgar/data/1/0000000000-16-000001.txt",
        source_sha256="c" * 64,
        source_mode="TEST",
    )
    assert result["classification"] == "CUSIP_ROW_COUNT_MISMATCH"


def test_runner_imports_current_settings_and_archive_api() -> None:
    from scripts.run_alpha_gate_sec_13f_original_edgar_reconciliation import main

    assert callable(main)
