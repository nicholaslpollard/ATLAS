from __future__ import annotations

import hashlib
import io
import zipfile

from packages.backtesting.alpha_gate_sec_13f_feasibility import (
    SEC_13F_ANCHORS,
    SEC_13F_FEASIBILITY_FINGERPRINT,
    SEC_13F_PROTECTED_SOURCE_CUTOFF,
    _analyze_archive,
    _gate_results,
    sec_13f_feasibility_fingerprint,
)
from packages.providers.sec_13f_datasets import SEC13FDatasetArchive


def _fixture_archive() -> SEC13FDatasetArchive:
    submission = (
        "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT\n"
        "0000000001-25-000001\t15-MAY-2025\t13F-HR\t1\t31-MAR-2025\n"
    )
    cover = (
        "ACCESSION_NUMBER\tREPORTCALENDARORQUARTER\tFILINGMANAGER_NAME\tREPORTTYPE\n"
        "0000000001-25-000001\t31-MAR-2025\tExample Manager\t13F HOLDINGS REPORT\n"
    )
    info = (
        "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tVALUE\t"
        "SSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL\tINVESTMENTDISCRETION\t"
        "VOTING_AUTH_SOLE\tVOTING_AUTH_SHARED\tVOTING_AUTH_NONE\tFIGI\n"
        "0000000001-25-000001\t1\tExample Corp\tCOM\t123456789\t1000\t10\tSH\t\t"
        "SOLE\t10\t0\t0\t\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("SUBMISSION.tsv", submission)
        handle.writestr("COVERPAGE.tsv", cover)
        handle.writestr("INFOTABLE.tsv", info)
    raw = buffer.getvalue()
    return SEC13FDatasetArchive(
        source_url=SEC_13F_ANCHORS[-1][1],
        source_sha256=hashlib.sha256(raw).hexdigest(),
        raw_bytes=raw,
    )


def test_feasibility_fingerprint_is_frozen() -> None:
    assert sec_13f_feasibility_fingerprint() == SEC_13F_FEASIBILITY_FINGERPRINT
    assert SEC_13F_FEASIBILITY_FINGERPRINT == (
        "8959769669d4c2e51b86627b8c03a67509a339698025683108cbda4e287fb310"
    )


def test_all_source_anchors_precede_master_protected_window() -> None:
    assert SEC_13F_PROTECTED_SOURCE_CUTOFF.isoformat() == "2025-05-31"
    assert all("2026" not in url for _, url in SEC_13F_ANCHORS)


def test_archive_analysis_is_source_only_and_preserves_cusip() -> None:
    report = _analyze_archive("fixture", _fixture_archive())
    assert report["initial_hr_submissions"] == 1
    assert report["initial_hr_infotable_rows"] == 1
    assert report["initial_hr_unique_ciks"] == 1
    assert report["initial_hr_valid_cusip_fraction"] == 1.0
    assert report["initial_hr_unique_cusips"] == 1
    assert report["infotable_orphan_rows"] == 0
    assert report["infotable_primary_key_duplicates"] == 0
    assert report["initial_hr_filing_before_period_violations"] == 0


def test_gate_results_fail_closed_below_capacity() -> None:
    tiny = _analyze_archive("fixture", _fixture_archive())
    gates = _gate_results([tiny] * 4)
    assert gates["anchor_count_exact"]
    assert not gates["initial_hr_submissions_min_all_anchors"]
    assert not gates["initial_hr_infotable_rows_min_all_anchors"]
    assert not gates["initial_hr_managers_min_all_anchors"]


def test_static_contract_validator_runs_inside_full_pytest() -> None:
    from scripts.validate_alpha_gate_sec_13f_feasibility import main

    assert main() == 0
