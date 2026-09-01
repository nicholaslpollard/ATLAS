from __future__ import annotations

import io
import zipfile

import pytest

from packages.core.exceptions import ProviderError
from packages.providers.sec_13f_datasets import (
    SEC13FDatasetArchive,
    SEC13FDatasetClient,
    validate_13f_zip_structure,
)


def _zip_bytes(extra_name: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("SUBMISSION.tsv", "ACCESSION_NUMBER\n")
        handle.writestr("COVERPAGE.tsv", "ACCESSION_NUMBER\n")
        handle.writestr("INFOTABLE.tsv", "ACCESSION_NUMBER\n")
        if extra_name:
            handle.writestr(extra_name, "x")
    return buffer.getvalue()


def test_official_url_validation_accepts_frozen_shapes() -> None:
    SEC13FDatasetClient.validate_url(
        "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/2016q1_form13f.zip"
    )
    SEC13FDatasetClient.validate_url(
        "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/01mar2025-31may2025_form13f.zip"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://www.sec.gov/files/structureddata/data/form-13f-data-sets/2016q1_form13f.zip",
        "https://data.sec.gov/files/structureddata/data/form-13f-data-sets/2016q1_form13f.zip",
        "https://www.sec.gov/Archives/edgar/data/1/example.zip",
        "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/other.zip",
    ],
)
def test_official_url_validation_rejects_scope_drift(url: str) -> None:
    with pytest.raises(ProviderError):
        SEC13FDatasetClient.validate_url(url)


def test_zip_structure_requires_three_source_tables() -> None:
    raw = _zip_bytes()
    report = validate_13f_zip_structure(
        SEC13FDatasetArchive(
            source_url="https://www.sec.gov/files/structureddata/data/form-13f-data-sets/2016q1_form13f.zip",
            source_sha256="0" * 64,
            raw_bytes=raw,
        )
    )
    assert set(report["table_members"]) == {"SUBMISSION.tsv", "COVERPAGE.tsv", "INFOTABLE.tsv"}


def test_zip_structure_rejects_path_traversal() -> None:
    raw = _zip_bytes("../escape.txt")
    with pytest.raises(ProviderError, match="unsafe member"):
        validate_13f_zip_structure(
            SEC13FDatasetArchive(
                source_url="https://www.sec.gov/files/structureddata/data/form-13f-data-sets/2016q1_form13f.zip",
                source_sha256="0" * 64,
                raw_bytes=raw,
            )
        )
