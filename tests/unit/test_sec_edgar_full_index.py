from __future__ import annotations

from datetime import date

import pytest

from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar_full_index import (
    filter_sec_master_index_rows,
    normalize_sec_cik,
    parse_sec_quarter_master_index,
)


MASTER = """
Description: Master Index of EDGAR Dissemination Feed
Last Data Received: July 10, 2026
Comments: webmaster@sec.gov

CIK|Company Name|Form Type|Date Filed|Filename
--------------------------------------------------------------------------------
320017|LISATA THERAPEUTICS, INC.|SC TO-T/A|2026-07-10|edgar/data/320017/0001140361-26-028238.txt
1645666|Kezar Life Sciences, Inc.|SC TO-T/A|2026-05-11|edgar/data/1645666/0001140361-26-020397.txt
2117902|Kuva Labs, Inc.|8-K|2026-07-10|edgar/data/2117902/0002117902-26-000001.txt
"""


def test_parse_master_index_preserves_index_provided_archive_path() -> None:
    rows = parse_sec_quarter_master_index(MASTER)
    assert len(rows) == 3
    assert rows[0].cik == "0000320017"
    assert rows[0].form_type == "SC TO-T/A"
    assert rows[0].filename == "edgar/data/320017/0001140361-26-028238.txt"
    # The archive directory CIK may differ from the accession prefix. The parser
    # must preserve the official index path rather than deriving one.
    assert rows[0].filename.split("/")[-1].startswith("0001140361-")
    assert rows[0].filename.split("/")[2] == "320017"


def test_filter_master_index_uses_target_cik_form_and_date() -> None:
    rows = parse_sec_quarter_master_index(MASTER)
    selected = filter_sec_master_index_rows(
        rows,
        ciks={"320017", "1645666"},
        forms={"SC TO-T/A", "SC 13E3/A"},
        start_date=date(2026, 5, 1),
        end_date=date(2026, 7, 31),
    )
    assert [row.cik for row in selected] == ["0001645666", "0000320017"]
    assert all(row.form_type == "SC TO-T/A" for row in selected)


def test_normalize_cik_is_exact_and_bounded() -> None:
    assert normalize_sec_cik("320017") == "0000320017"
    assert normalize_sec_cik("0000320017") == "0000320017"
    with pytest.raises(ProviderError):
        normalize_sec_cik("ABC")
    with pytest.raises(ProviderError):
        normalize_sec_cik("12345678901")


def test_master_index_rejects_non_archive_filename() -> None:
    bad = MASTER.replace(
        "edgar/data/320017/0001140361-26-028238.txt",
        "https://example.com/file.txt",
    )
    with pytest.raises(ProviderError, match="outside edgar/data"):
        parse_sec_quarter_master_index(bad)


def test_master_index_rejects_missing_header() -> None:
    with pytest.raises(ProviderError, match="column header"):
        parse_sec_quarter_master_index("not an EDGAR master index")
