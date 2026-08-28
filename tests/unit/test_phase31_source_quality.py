from __future__ import annotations

import pytest

from packages.backtesting.phase31_source_quality import (
    Phase31SourceQualityError,
    classify_form4_source_quality,
    phase31_source_quality_fingerprint,
)


def _row(
    accession: str | None,
    *,
    filing: str,
    transaction: str | None,
    code: str = "P",
    ticker: str = "BrK.B",
    record_type: str = "transaction",
) -> dict[str, object]:
    row: dict[str, object] = {
        "accession_number": accession,
        "filing_date": filing,
        "record_type": record_type,
        "tickers": [ticker],
        "issuer_cik": "0000000001",
        "owner_cik": "0000000002",
    }
    if record_type == "transaction":
        row["transaction_date"] = transaction
        row["transaction_code"] = code
    return row


def test_source_quality_quarantines_entire_contaminated_accession() -> None:
    rows = (
        _row("A", filing="2023-08-17", transaction="2023-09-15", code="M"),
        _row("A", filing="2023-08-17", transaction=None, record_type="holding"),
        _row("B", filing="2023-08-17", transaction="2023-08-16", code="P", ticker="BrK.B"),
        _row("C", filing="2023-08-17", transaction="2023-08-17", code="S", ticker="brk.b"),
    )

    classified = classify_form4_source_quality(rows)

    assert classified.contaminated_accessions == ("A",)
    assert len(classified.violating_seed_rows) == 1
    assert {row["accession_number"] for row in classified.quarantined_rows} == {"A"}
    assert len(classified.quarantined_rows) == 2
    assert {row["accession_number"] for row in classified.authoritative_rows} == {"B", "C"}
    authoritative_tickers = {
        ticker
        for row in classified.authoritative_rows
        for ticker in row.get("tickers", [])
    }
    assert authoritative_tickers == {"BrK.B", "brk.b"}


def test_source_quality_does_not_quarantine_valid_derivative_or_code_m_by_category() -> None:
    valid_m = _row("VALID-M", filing="2023-09-19", transaction="2023-09-15", code="M")
    classified = classify_form4_source_quality((valid_m,))

    assert classified.contaminated_accessions == ()
    assert classified.quarantined_rows == ()
    assert len(classified.authoritative_rows) == 1


def test_source_quality_fails_closed_when_violating_row_has_no_accession() -> None:
    bad = _row(None, filing="2023-08-17", transaction="2023-09-15", code="P")
    with pytest.raises(Phase31SourceQualityError, match="missing accession_number"):
        classify_form4_source_quality((bad,))


def test_source_quality_fingerprint_is_frozen() -> None:
    assert phase31_source_quality_fingerprint() == (
        "2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83"
    )
