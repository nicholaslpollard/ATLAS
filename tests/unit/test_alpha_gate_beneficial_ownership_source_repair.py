from __future__ import annotations

import pytest

from packages.backtesting.alpha_gate_beneficial_ownership_feasibility import (
    BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT,
    BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED,
    BeneficialOwnershipFeasibilityError,
    BeneficialOwnershipIndexRow,
    parse_submission_metadata,
)
from packages.backtesting.alpha_gate_beneficial_ownership_source_repair import (
    BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_EXTRACTED,
    BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT,
    BENEFICIAL_OWNERSHIP_V1_FAILED_HEAD,
    authoritative_subject_cik,
    beneficial_ownership_source_repair_fingerprint,
    dedupe_discovery_v2,
)
from packages.providers.sec_edgar_archive import (
    SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES,
    SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND,
    SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS,
    SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
    SECEDGARArchiveClient,
    sec_archive_submission_url,
    sec_quarter_master_index_url,
)


def _row(
    *,
    cik: str,
    company: str,
    filename: str,
    form: str = "SC 13G",
    filing_date: str = "2016-08-15",
    form_class: str = "13G_INITIAL",
    stratum: str = "legacy:13G_INITIAL",
) -> BeneficialOwnershipIndexRow:
    return BeneficialOwnershipIndexRow(
        index_cik=cik,
        company_name=company,
        form=form,
        filing_date=filing_date,
        filename=filename,
        accession_number="0001193125-16-687002",
        era="legacy",
        form_class=form_class,
        stratum=stratum,
    )


def test_source_repair_fingerprint_is_frozen_and_parent_v1_is_preserved() -> None:
    assert BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT == (
        "f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb"
    )
    assert BENEFICIAL_OWNERSHIP_V1_FAILED_HEAD == "37194556012bc6df3f5e5579f2dacdcb5bed738b"
    assert beneficial_ownership_source_repair_fingerprint() == BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT
    assert BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT == (
        "78bf3f18368114a5a6073e8a4d66a0c13ee29a5da78b8adeb1d71b1f10c6f78c"
    )
    assert BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_EXTRACTED == BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED == 185


def test_transport_repair_is_bounded_and_distinguishes_index_from_submission() -> None:
    index_url = sec_quarter_master_index_url(year=2026, quarter=1)
    submission_url = sec_archive_submission_url(
        "edgar/data/1859310/0001193125-16-687002.txt"
    )
    assert SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES == 64_000_000
    assert SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES == 20_000_000
    assert SECEDGARArchiveClient._response_limit(index_url) == 64_000_000
    assert SECEDGARArchiveClient._response_limit(submission_url) == 20_000_000
    assert SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES > 32_282 * 1024


def test_archive_transport_uses_conservative_five_request_per_second_cadence() -> None:
    assert SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND == 5
    assert SEC_ARCHIVE_MIN_REQUEST_INTERVAL_SECONDS == pytest.approx(0.2)
    assert SEC_ARCHIVE_MAX_REQUESTS_PER_SECOND < 10


def test_duplicate_accession_entity_associations_collapse_when_filing_semantics_match() -> None:
    first = _row(
        cik="0001859310",
        company="Subject Company",
        filename="edgar/data/1859310/0001193125-16-687002.txt",
    )
    second = _row(
        cik="0001326389",
        company="Filed By Entity",
        filename="edgar/data/1326389/0001193125-16-687002.txt",
    )
    rows, duplicate_count = dedupe_discovery_v2([first, second])
    reversed_rows, reversed_duplicate_count = dedupe_discovery_v2([second, first])

    assert duplicate_count == reversed_duplicate_count == 1
    assert rows == reversed_rows
    assert len(rows) == 1
    assert rows[0].filename == "edgar/data/1326389/0001193125-16-687002.txt"
    assert rows[0].form == "SC 13G"
    assert rows[0].filing_date == "2016-08-15"


def test_duplicate_accession_filing_semantic_conflict_still_fails_closed() -> None:
    first = _row(
        cik="0001859310",
        company="Subject Company",
        filename="edgar/data/1859310/0001193125-16-687002.txt",
    )
    conflicting = _row(
        cik="0001326389",
        company="Filed By Entity",
        filename="edgar/data/1326389/0001193125-16-687002.txt",
        form="SC 13G/A",
        form_class="13G_AMENDMENT",
        stratum="legacy:13G_AMENDMENT",
    )
    with pytest.raises(BeneficialOwnershipFeasibilityError, match="filing semantics"):
        dedupe_discovery_v2([first, conflicting])


def test_authoritative_security_identity_uses_submission_subject_cik_not_index_cik() -> None:
    text = """<SEC-DOCUMENT>0001062993-22-003438.txt : 20220210
<SEC-HEADER>
<ACCEPTANCE-DATETIME>20220210112132
ACCESSION NUMBER:        0001062993-22-003438
CONFORMED SUBMISSION TYPE: SC 13G
FILED AS OF DATE:        20220210
SUBJECT COMPANY:
    COMPANY DATA:
        COMPANY CONFORMED NAME: Minority Equality Opportunities Acquisition Inc.
        CENTRAL INDEX KEY: 0001859310
FILED BY:
    COMPANY DATA:
        COMPANY CONFORMED NAME: Polar Asset Management Partners Inc.
        CENTRAL INDEX KEY: 0001326389
</SEC-HEADER>
<DOCUMENT>
<TYPE>SC 13G
<TEXT>CUSIP No. 123456789</TEXT>
</DOCUMENT>
"""
    metadata = parse_submission_metadata(text)
    assert authoritative_subject_cik(metadata) == "0001859310"
    assert authoritative_subject_cik(metadata) != "0001326389"
