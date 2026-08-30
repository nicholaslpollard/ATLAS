from __future__ import annotations

from datetime import date

import pytest

from packages.backtesting.alpha_gate_beneficial_ownership_feasibility import (
    BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT,
    BENEFICIAL_OWNERSHIP_QUARTERS,
    BeneficialOwnershipIndexRow,
    _decision_session,
    _resolve_identity,
    beneficial_ownership_feasibility_fingerprint,
    parse_master_index,
    parse_submission_metadata,
    select_stratified_sample,
)
from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar_archive import (
    SECEDGARArchiveClient,
    sec_archive_submission_url,
    sec_quarter_master_index_url,
)


def test_frozen_feasibility_fingerprint_and_quarter_scope() -> None:
    assert beneficial_ownership_feasibility_fingerprint() == BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT
    assert BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT == (
        "f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb"
    )
    assert len(BENEFICIAL_OWNERSHIP_QUARTERS) == 43
    assert BENEFICIAL_OWNERSHIP_QUARTERS[0] == (2016, 1)
    assert BENEFICIAL_OWNERSHIP_QUARTERS[-1] == (2026, 3)


def test_master_index_parses_old_new_aliases_and_filters_source_cutoff() -> None:
    text = """Description
Last Data Received
CIK|Company Name|Form Type|Date Filed|Filename
--------------------------------------------------------------------------------
1009759|Legacy Issuer|SC 13D|2024-12-17|edgar/data/1009759/0001213900-24-123456.txt
1529113|Structured Issuer|SCHEDULE 13D/A|2025-05-15|edgar/data/1529113/0001213900-25-057989.txt
1351636|Structured Passive|SCHEDULE 13G|2026-08-11|edgar/data/1351636/0001772351-26-000005.txt
1351636|After Cutoff|SCHEDULE 13G/A|2026-08-12|edgar/data/1351636/0001772351-26-000006.txt
1351636|Other Form|8-K|2026-08-11|edgar/data/1351636/0001772351-26-000007.txt
"""
    rows = parse_master_index(text)
    assert len(rows) == 3
    assert rows[0].stratum == "legacy:13D_INITIAL"
    assert rows[1].stratum == "structured:13D_AMENDMENT"
    assert rows[2].stratum == "structured:13G_INITIAL"
    assert rows[2].index_cik == "0001351636"


def _synthetic_row(*, index: int, era: str, form_class: str) -> BeneficialOwnershipIndexRow:
    form_map = {
        ("legacy", "13D_INITIAL"): "SC 13D",
        ("legacy", "13D_AMENDMENT"): "SC 13D/A",
        ("legacy", "13G_INITIAL"): "SC 13G",
        ("legacy", "13G_AMENDMENT"): "SC 13G/A",
        ("structured", "13D_INITIAL"): "SCHEDULE 13D",
        ("structured", "13D_AMENDMENT"): "SCHEDULE 13D/A",
        ("structured", "13G_INITIAL"): "SCHEDULE 13G",
        ("structured", "13G_AMENDMENT"): "SCHEDULE 13G/A",
    }
    year = 2023 if era == "legacy" else 2025
    accession = f"0000000001-{year % 100:02d}-{index:06d}"
    cik = f"{(index % 9000000000) + 1:010d}"
    return BeneficialOwnershipIndexRow(
        index_cik=cik,
        company_name=f"Issuer {index}",
        form=form_map[(era, form_class)],
        filing_date=f"{year}-06-15",
        filename=f"edgar/data/{int(cik)}/{accession}.txt",
        accession_number=accession,
        era=era,
        form_class=form_class,
        stratum=f"{era}:{form_class}",
    )


def test_stratified_sample_is_exact_and_deterministic() -> None:
    rows = []
    counter = 1
    for era in ("legacy", "structured"):
        for form_class in ("13D_INITIAL", "13D_AMENDMENT", "13G_INITIAL", "13G_AMENDMENT"):
            for _ in range(30):
                rows.append(_synthetic_row(index=counter, era=era, form_class=form_class))
                counter += 1
    first = select_stratified_sample(rows)
    second = select_stratified_sample(reversed(rows))
    assert first == second
    assert len(first) == 200
    counts: dict[str, int] = {}
    for row in first:
        counts[row.stratum] = counts.get(row.stratum, 0) + 1
    assert set(counts.values()) == {25}
    assert len(counts) == 8


def test_legacy_submission_header_parses_subject_and_acceptance() -> None:
    text = """<SEC-DOCUMENT>0001213900-24-123456.txt : 20241217
<SEC-HEADER>
<ACCEPTANCE-DATETIME>20241217163510
ACCESSION NUMBER:        0001213900-24-123456
CONFORMED SUBMISSION TYPE: SC 13D
FILED AS OF DATE:        20241217
SUBJECT COMPANY:
    COMPANY DATA:
        COMPANY CONFORMED NAME: Example Target Corp
        CENTRAL INDEX KEY: 0001009759
FILED BY:
    COMPANY DATA:
        COMPANY CONFORMED NAME: Example Activist LLC
        CENTRAL INDEX KEY: 0001999999
</SEC-HEADER>
<DOCUMENT>
<TYPE>SC 13D
<TEXT>
CUSIP No. 123456789
Date of Event Which Requires Filing of this Statement
Item 4. Purpose of Transaction
</TEXT>
</DOCUMENT>
"""
    metadata = parse_submission_metadata(text)
    assert metadata.accession_number == "0001213900-24-123456"
    assert metadata.form == "SC 13D"
    assert metadata.filing_date == "2024-12-17"
    assert metadata.subject_cik == "0001009759"
    assert metadata.subject_name == "Example Target Corp"
    assert metadata.acceptance_datetime == "2024-12-17T16:35:10-05:00"
    assert metadata.cusip_marker is True
    assert metadata.event_date_marker is True
    assert metadata.item4_marker is True
    assert metadata.structured_primary_xml_marker is False


def test_structured_submission_detects_primary_xml_and_target_not_filer() -> None:
    text = """<SEC-DOCUMENT>0001213900-26-057989.txt : 20260515
<SEC-HEADER>
<ACCEPTANCE-DATETIME>20260515173727
ACCESSION NUMBER:        0001213900-26-057989
CONFORMED SUBMISSION TYPE: SCHEDULE 13D
FILED AS OF DATE:        20260515
SUBJECT COMPANY:
    COMPANY DATA:
        COMPANY CONFORMED NAME: XTI Aerospace, Inc.
        CENTRAL INDEX KEY: 0001529113
FILED BY:
    COMPANY DATA:
        COMPANY CONFORMED NAME: Pomeroy Scott
        CENTRAL INDEX KEY: 0001297880
</SEC-HEADER>
<DOCUMENT>
<TYPE>SCHEDULE 13D
<SEQUENCE>1
<FILENAME>primary_doc.xml
<TEXT>
CUSIP No. 98423K108
</TEXT>
</DOCUMENT>
"""
    metadata = parse_submission_metadata(text)
    assert metadata.subject_cik == "0001529113"
    assert metadata.form == "SCHEDULE 13D"
    assert metadata.structured_primary_xml_marker is True


def test_decision_session_is_strictly_after_acceptance() -> None:
    assert _decision_session("2025-05-02T08:00:00-04:00") == date(2025, 5, 2)
    assert _decision_session("2025-05-02T09:30:00-04:00") == date(2025, 5, 5)
    assert _decision_session("2025-05-02T12:00:00-04:00") == date(2025, 5, 5)


def test_multiple_common_share_classes_fail_closed() -> None:
    rows = [
        {
            "ticker": "ABC",
            "cik": "0000000001",
            "composite_figi": "BBG000000001",
            "primary_exchange": "XNYS",
            "type": "CS",
        },
        {
            "ticker": "ABC.B",
            "cik": "0000000001",
            "composite_figi": "BBG000000002",
            "primary_exchange": "XNYS",
            "type": "CS",
        },
    ]
    result = _resolve_identity(rows, subject_cik="0000000001", as_of_date=date(2025, 5, 5))
    assert result["status"] == "AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS"
    assert result["unique_instrument_count"] == 2


def test_single_common_stock_resolves_and_fallback_does_not() -> None:
    resolved = _resolve_identity(
        [
            {
                "ticker": "ABC",
                "cik": "0000000001",
                "composite_figi": "BBG000000001",
                "primary_exchange": "XNYS",
                "type": "CS",
            }
        ],
        subject_cik="0000000001",
        as_of_date=date(2025, 5, 5),
    )
    assert resolved["status"] == "UNAMBIGUOUS_PIT_INSTRUMENT"

    fallback = _resolve_identity(
        [{"ticker": "ABC", "cik": "0000000001"}],
        subject_cik="0000000001",
        as_of_date=date(2025, 5, 5),
    )
    assert fallback["status"] == "NO_ELIGIBLE_PIT_INSTRUMENT"


def test_archive_urls_are_narrowly_scoped() -> None:
    assert sec_quarter_master_index_url(year=2026, quarter=3).endswith(
        "/Archives/edgar/full-index/2026/QTR3/master.idx"
    )
    assert sec_archive_submission_url(
        "edgar/data/1529113/0001213900-26-057989.txt"
    ).endswith("/Archives/edgar/data/1529113/0001213900-26-057989.txt")
    with pytest.raises(ProviderError):
        sec_archive_submission_url("../../etc/passwd")
    with pytest.raises(ProviderError):
        SECEDGARArchiveClient._validate_url(
            "https://example.com/Archives/edgar/full-index/2026/QTR3/master.idx"
        )
    with pytest.raises(ProviderError):
        SECEDGARArchiveClient._validate_url("https://www.sec.gov/Archives/other/file.txt")
