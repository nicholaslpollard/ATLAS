from __future__ import annotations

import hashlib
import io
import zipfile

from packages.backtesting.alpha_gate_sec_13f_cusip_diagnostic import (
    SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT,
    diagnose_13f_cusips,
)
from packages.backtesting.alpha_gate_sec_13f_feasibility import SEC_13F_ANCHORS
from packages.providers.sec_13f_datasets import SEC13FDatasetArchive


def _fixture_archive() -> SEC13FDatasetArchive:
    submission = (
        "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT\n"
        "0000000001-16-000001\t15-FEB-2016\t13F-HR\t1\t31-DEC-2015\n"
        "0000000002-16-000001\t15-FEB-2016\t13F-HR\t2\t31-DEC-2015\n"
    )
    cover = (
        "ACCESSION_NUMBER\tREPORTCALENDARORQUARTER\tFILINGMANAGER_NAME\tREPORTTYPE\n"
        "0000000001-16-000001\t31-DEC-2015\tManager One\t13F HOLDINGS REPORT\n"
        "0000000002-16-000001\t31-DEC-2015\tManager Two\t13F HOLDINGS REPORT\n"
    )
    info = (
        "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tVALUE\t"
        "SSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL\tINVESTMENTDISCRETION\t"
        "VOTING_AUTH_SOLE\tVOTING_AUTH_SHARED\tVOTING_AUTH_NONE\tFIGI\n"
        "0000000001-16-000001\t1\tExample Corp\tCOM\t012345678\t1000\t10\tSH\t\tSOLE\t10\t0\t0\t\n"
        "0000000001-16-000001\t2\tExample Corp\tCOM\t12345678\t1000\t10\tSH\t\tSOLE\t10\t0\t0\t\n"
        "0000000001-16-000001\t3\tBlank Corp\tCOM\t\t1000\t10\tSH\t\tSOLE\t10\t0\t0\t\n"
        "0000000002-16-000001\t1\tLong Corp\tCOM\t1234567890\t1000\t10\tSH\t\tSOLE\t10\t0\t0\t\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("SUBMISSION.tsv", submission)
        handle.writestr("COVERPAGE.tsv", cover)
        handle.writestr("INFOTABLE.tsv", info)
    raw = buffer.getvalue()
    return SEC13FDatasetArchive(
        source_url=SEC_13F_ANCHORS[0][1],
        source_sha256=hashlib.sha256(raw).hexdigest(),
        raw_bytes=raw,
    )


def test_cusip_diagnostic_is_source_only_and_nonrepairing() -> None:
    report = diagnose_13f_cusips(_fixture_archive())
    assert report["contract_version"] == SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT
    assert report["initial_hr_rows"] == 4
    assert report["nine_char_rows"] == 1
    assert report["malformed_rows"] == 3
    assert report["blank_rows"] == 1
    assert report["short_nonblank_rows"] == 1
    assert report["long_rows"] == 1
    assert report["cusip_length_histogram"] == {"0": 1, "8": 1, "9": 1, "10": 1}
    assert report["left_zero_pad_candidate_seen_as_valid_rows"] == 1
    assert report["same_issuer_class_single_valid_cusip_rows"] == 1
    assert report["both_diagnostic_signals_agree_rows"] == 1
    assert "do not authorize CUSIP repair" in report["interpretation_boundary"]


def test_cusip_diagnostic_runner_imports_current_settings_api() -> None:
    from scripts.run_alpha_gate_sec_13f_cusip_diagnostic import main

    assert callable(main)
