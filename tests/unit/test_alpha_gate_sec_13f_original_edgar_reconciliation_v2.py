from __future__ import annotations

import pytest

from packages.backtesting.alpha_gate_sec_13f_feasibility import SEC13FFeasibilityError
from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation_v2 import (
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT,
    _archive_cik_from_filename,
    _submission_identity_matches,
    parse_13f_hr_master_index,
    sec_13f_original_edgar_reconciliation_v2_fingerprint,
)


def test_v2_fingerprint_is_frozen() -> None:
    assert (
        sec_13f_original_edgar_reconciliation_v2_fingerprint()
        == SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT
    )
    assert SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT == (
        "88402d747d52c4631f12661aa5d8d35738f114775795243c82ab123d6c22cf61"
    )


def test_master_index_resolves_exact_filename_and_archive_cik() -> None:
    text = (
        "Description: Master Index of EDGAR Dissemination Feed\n"
        "CIK|Company Name|Form Type|Date Filed|Filename\n"
        "913414|BLACKROCK INSTITUTIONAL TRUST|13F-HR|2016-02-12|"
        "edgar/data/913414/0001034551-16-000001.txt\n"
        "1112520|AKRE CAPITAL MANAGEMENT LLC|13F-HR|2016-02-12|"
        "edgar/data/1112520/0001112520-16-000001.txt\n"
    )
    resolved = parse_13f_hr_master_index(text)
    assert resolved["0001034551-16-000001"] == (
        "edgar/data/913414/0001034551-16-000001.txt"
    )
    assert _archive_cik_from_filename(resolved["0001034551-16-000001"]) == "913414"


def test_master_index_rejects_conflicting_duplicate_accession() -> None:
    text = (
        "CIK|Company Name|Form Type|Date Filed|Filename\n"
        "1|A|13F-HR|2016-02-12|edgar/data/1/0000000001-16-000001.txt\n"
        "2|B|13F-HR|2016-02-12|edgar/data/2/0000000001-16-000001.txt\n"
    )
    with pytest.raises(SEC13FFeasibilityError):
        parse_13f_hr_master_index(text)


def test_cached_submission_identity_requires_accession_in_header_region() -> None:
    accession = "0001034551-16-000001"
    assert _submission_identity_matches(
        f"<SEC-DOCUMENT>{accession}.txt : 20160212\n<SEC-HEADER>...", accession
    )
    assert not _submission_identity_matches("<SEC-DOCUMENT>other.txt\n", accession)


def test_runner_v2_imports_current_settings_and_archive_api() -> None:
    from scripts.run_alpha_gate_sec_13f_original_edgar_reconciliation_v2 import main

    assert callable(main)
