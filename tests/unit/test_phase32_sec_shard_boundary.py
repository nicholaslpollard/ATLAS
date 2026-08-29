from __future__ import annotations

import json

import pytest

from packages.core.exceptions import ProviderError
from packages.providers.sec_edgar import (
    SEC_EDGAR_DECLARED_SHARD_BOUNDARY_TOLERANCE_DAYS,
    SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP,
    SECEDGARClient,
    _select_declared_shard_candidates,
    sec_company_submissions_url,
    sec_submission_shard_url,
)


CIK = "0001564708"
ACCESSION = "0001564708-23-000471"
TARGET_DATE = "2023-10-05"
SHARD_NAME = "CIK0001564708-submissions-001.json"
ROOT_URL = sec_company_submissions_url(cik=CIK)
SHARD_URL = sec_submission_shard_url(SHARD_NAME)


def _empty_recent() -> dict[str, list[str]]:
    return {
        "accessionNumber": [],
        "filingDate": [],
        "acceptanceDateTime": [],
        "form": [],
        "items": [],
        "primaryDocument": [],
    }


def _filing_block(*, filing_date: str = TARGET_DATE, form: str = "8-K") -> dict[str, list[str]]:
    return {
        "accessionNumber": [ACCESSION],
        "filingDate": [filing_date],
        "acceptanceDateTime": ["2023-10-04T22:16:27.000Z"],
        "form": [form],
        "items": ["8.01,9.01"],
        "primaryDocument": ["nws-20231004.htm"],
    }


def _root(files: list[dict[str, str]]) -> dict[str, object]:
    return {"filings": {"recent": _empty_recent(), "files": files}}


class StubSECEDGARClient(SECEDGARClient):
    def __init__(self, payloads: dict[str, dict[str, object]]) -> None:
        super().__init__(contact_email="atlas-tests@example.com", sleeper=lambda _: None)
        self.payloads = payloads
        self.requested_urls: list[str] = []

    def get_json(self, url: str) -> tuple[dict[str, object], str]:  # type: ignore[override]
        self.requested_urls.append(url)
        if url not in self.payloads:
            raise AssertionError(f"unexpected SEC URL: {url}")
        payload = self.payloads[url]
        return payload, json.dumps(payload, sort_keys=True)


def test_one_day_declared_boundary_gap_uses_only_sec_declared_shard() -> None:
    files = [
        {
            "name": SHARD_NAME,
            "filingFrom": "2012-12-21",
            "filingTo": "2023-10-04",
        }
    ]
    client = StubSECEDGARClient(
        {
            ROOT_URL: _root(files),
            SHARD_URL: _filing_block(),
        }
    )

    record = client.filing_metadata(
        cik=CIK,
        accession_number=ACCESSION,
        filing_date=TARGET_DATE,
    )

    assert SEC_EDGAR_DECLARED_SHARD_BOUNDARY_TOLERANCE_DAYS == 1
    assert record.accession_number == ACCESSION
    assert record.issuer_cik == CIK
    assert record.filing_date == TARGET_DATE
    assert record.form == "8-K"
    assert record.item_codes == ("8.01", "9.01")
    assert record.source_url == SHARD_URL
    assert client.requested_urls == [ROOT_URL, SHARD_URL]


def test_more_than_one_day_gap_remains_fail_closed() -> None:
    files = [
        {
            "name": SHARD_NAME,
            "filingFrom": "2012-12-21",
            "filingTo": "2023-10-03",
        }
    ]
    client = StubSECEDGARClient({ROOT_URL: _root(files)})

    with pytest.raises(ProviderError, match="bounded declared-shard rollover rule"):
        client.filing_metadata(
            cik=CIK,
            accession_number=ACCESSION,
            filing_date=TARGET_DATE,
        )

    assert client.requested_urls == [ROOT_URL]


def test_adjacent_shard_exact_accession_must_match_requested_filing_date() -> None:
    files = [
        {
            "name": SHARD_NAME,
            "filingFrom": "2012-12-21",
            "filingTo": "2023-10-04",
        }
    ]
    client = StubSECEDGARClient(
        {
            ROOT_URL: _root(files),
            SHARD_URL: _filing_block(filing_date="2023-10-04"),
        }
    )

    with pytest.raises(ProviderError, match="filingDate does not match requested date"):
        client.filing_metadata(
            cik=CIK,
            accession_number=ACCESSION,
            filing_date=TARGET_DATE,
        )


def test_covering_shard_prevents_adjacent_fallback() -> None:
    covering_name = "CIK0001564708-submissions-002.json"
    covering_url = sec_submission_shard_url(covering_name)
    files = [
        {
            "name": covering_name,
            "filingFrom": "2023-10-05",
            "filingTo": "2023-10-05",
        },
        {
            "name": SHARD_NAME,
            "filingFrom": "2012-12-21",
            "filingTo": "2023-10-04",
        },
    ]
    client = StubSECEDGARClient(
        {
            ROOT_URL: _root(files),
            covering_url: _empty_recent(),
        }
    )

    with pytest.raises(ProviderError, match="did not contain requested accession"):
        client.filing_metadata(
            cik=CIK,
            accession_number=ACCESSION,
            filing_date=TARGET_DATE,
        )

    assert client.requested_urls == [ROOT_URL, covering_url]


def test_candidate_selector_preserves_two_shard_hard_bound() -> None:
    files = [
        {
            "name": f"CIK0001564708-submissions-{index:03d}.json",
            "filingFrom": "2012-12-21",
            "filingTo": "2023-10-04",
        }
        for index in range(1, SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP + 2)
    ]

    with pytest.raises(ProviderError, match="exceeded bounded shard count"):
        _select_declared_shard_candidates(files, filing_date=TARGET_DATE)


def test_adjacent_shard_still_requires_original_8k() -> None:
    files = [
        {
            "name": SHARD_NAME,
            "filingFrom": "2012-12-21",
            "filingTo": "2023-10-04",
        }
    ]
    client = StubSECEDGARClient(
        {
            ROOT_URL: _root(files),
            SHARD_URL: _filing_block(form="8-K/A"),
        }
    )

    with pytest.raises(ProviderError, match="is not original 8-K metadata"):
        client.filing_metadata(
            cik=CIK,
            accession_number=ACCESSION,
            filing_date=TARGET_DATE,
        )
