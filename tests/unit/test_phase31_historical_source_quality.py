from __future__ import annotations

from datetime import date

from packages.backtesting.phase31_acquisition import PHASE31_ACQUISITION_CONTRACT_VERSION
from packages.backtesting.phase31_acquisition_v3 import PHASE31_ACQUISITION_V3_CONTRACT_VERSION
from packages.backtesting.phase31_historical_source_quality import (
    PHASE31_HISTORICAL_SOURCE_QUALITY_CONTRACT_VERSION,
    PHASE31_MISSING_TRANSACTION_CODE_REASON,
    classify_form4_historical_source_quality,
    required_transaction_code_violation_count,
)
from packages.providers.massive.phase31 import validate_form4_row


def _transaction(
    accession: str,
    *,
    filing_date: str = "2025-01-10",
    transaction_date: str = "2025-01-09",
    transaction_code: str | None = "P",
) -> dict[str, object]:
    row: dict[str, object] = {
        "accession_number": accession,
        "filing_date": filing_date,
        "form_type": "4",
        "issuer_cik": "100",
        "owner_cik": "200",
        "record_type": "transaction",
        "transaction_date": transaction_date,
        "tickers": ["TEST"],
    }
    if transaction_code is not None:
        row["transaction_code"] = transaction_code
    return row


def test_provider_transport_preserves_missing_transaction_code_for_downstream_quarantine() -> None:
    row = _transaction("A", transaction_code=None)
    validate_form4_row(row, start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
    assert "transaction_code" not in row


def test_missing_transaction_code_quarantines_entire_accession() -> None:
    rows = (
        _transaction("A", transaction_code="P"),
        _transaction("A", transaction_code=None),
        _transaction("B", transaction_code="S"),
    )
    classified = classify_form4_historical_source_quality(rows)
    assert classified.contaminated_accessions == ("A",)
    assert len(classified.missing_transaction_code_seed_rows) == 1
    assert [row["accession_number"] for row in classified.authoritative_rows] == ["B"]
    assert [row["accession_number"] for row in classified.quarantined_rows] == ["A", "A"]
    assert dict(classified.accession_reasons)["A"] == (PHASE31_MISSING_TRANSACTION_CODE_REASON,)


def test_chronology_and_required_code_reasons_union_deterministically() -> None:
    rows = (
        _transaction(
            "A",
            filing_date="2025-01-10",
            transaction_date="2025-01-11",
            transaction_code="P",
        ),
        _transaction("A", transaction_code=None),
    )
    classified = classify_form4_historical_source_quality(rows)
    reasons = dict(classified.accession_reasons)["A"]
    assert reasons == tuple(sorted(reasons))
    assert PHASE31_MISSING_TRANSACTION_CODE_REASON in reasons
    assert len(reasons) == 2
    assert len(classified.chronology_seed_rows) == 1
    assert required_transaction_code_violation_count(classified.authoritative_rows) == 0


def test_v3_changes_authoritative_admission_without_invalidating_v2_raw_sidecars() -> None:
    assert PHASE31_ACQUISITION_CONTRACT_VERSION == (
        "phase31-form4-acquisition-v2-monthly-memory-bounded-global-accession-quarantine"
    )
    assert PHASE31_ACQUISITION_V3_CONTRACT_VERSION == (
        "phase31-form4-acquisition-v3-v2-raw-resume-global-historical-admissibility-quarantine"
    )
    assert PHASE31_HISTORICAL_SOURCE_QUALITY_CONTRACT_VERSION == (
        "phase31-form4-historical-source-quality-v1-chronology-required-code-global-accession-quarantine"
    )
