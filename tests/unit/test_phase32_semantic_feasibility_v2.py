from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.backtesting.phase32_semantic_feasibility_v2 import (
    PHASE32_SEMANTIC_V2_PROBE_WINDOWS,
    Phase32SemanticSourceFeasibilityV2,
    Phase32SemanticV2FeasibilityError,
    phase32_semantic_v2_fingerprint,
)
from packages.providers.massive.phase32 import Phase32SECIndexWindowResult
from packages.providers.massive.phase32_semantic import (
    Phase32DisclosureWindowResult,
    Phase32TaxonomyResult,
)
from packages.providers.sec_edgar import SECSubmissionRecord, sec_company_submissions_url


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(
            paths=SimpleNamespace(provider="data/provider", derived="data/derived")
        )

    def resolved_path(self, value: str) -> Path:
        return self.root / value


def _accession(start_date: date) -> str:
    return f"0000000001-{str(start_date.year)[2:]}-000001"


class FakeIndexClient:
    def __init__(self, *, bad_cik: bool = False) -> None:
        self.bad_cik = bad_cik

    def eight_k_window(self, *, start_date, end_date):
        return Phase32SECIndexWindowResult(
            rows=(
                {
                    "accession_number": _accession(start_date),
                    "cik": "0000000002" if self.bad_cik else "0000000001",
                    "filing_date": start_date.isoformat(),
                    "filing_url": "https://www.sec.gov/Archives/edgar/data/1/example.txt",
                    "form_type": "8-K",
                    "issuer_name": "Example Corp",
                    "ticker": None if start_date.year == 2023 else "NEW",
                },
            ),
            page_count=1,
            request_ids=(f"index-{start_date}",),
        )


class FakeSemanticClient:
    def taxonomy(self):
        return Phase32TaxonomyResult(
            rows=(
                {
                    "taxonomy": "1.0",
                    "primary_category": "corporate_events",
                    "secondary_category": "material_agreements",
                    "tertiary_category": "material_agreement",
                    "description": "Material agreement.",
                },
            ),
            page_count=1,
            request_ids=("taxonomy",),
        )

    def disclosures_window(self, *, start_date, end_date):
        tickers = [] if start_date.year == 2023 else ["OLD"]
        return Phase32DisclosureWindowResult(
            rows=(
                {
                    "accession_number": _accession(start_date),
                    "cik": "0000000001",
                    "filing_date": start_date.isoformat(),
                    "filing_url": "https://www.sec.gov/Archives/edgar/data/1/example.txt",
                    "primary_category": "corporate_events",
                    "secondary_category": "material_agreements",
                    "tertiary_category": "material_agreement",
                    "supporting_text": "The company entered a material agreement from an exhibit.",
                    "tickers": tickers,
                },
            ),
            page_count=1,
            request_ids=(f"disclosure-{start_date}",),
        )

    def eight_k_text(self, *, cik, filing_date):
        return (
            {
                "accession_number": _accession(filing_date),
                "cik": "0000000001",
                "filing_date": filing_date.isoformat(),
                "filing_url": "https://www.sec.gov/Archives/edgar/data/1/example.txt",
                "form_type": "8-K",
                "items_text": "Item 1.01. Core item text does not reproduce the exhibit excerpt verbatim.",
                "ticker": "OLD" if filing_date.year != 2023 else None,
            },
        )


class FakeSECClient:
    def filing_metadata(self, *, cik, accession_number: str, filing_date: str):
        source_record = json.dumps(
            {
                "accessionNumber": accession_number,
                "issuerCIK": "0000000001",
                "filingDate": filing_date,
                "acceptanceDateTime": f"{filing_date}T22:30:45.000Z",
                "form": "8-K",
                "items": "1.01,9.01",
                "primaryDocument": "example.htm",
                "sourceUrl": sec_company_submissions_url(cik=cik),
            },
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
        return SECSubmissionRecord(
            accession_number=accession_number,
            issuer_cik="0000000001",
            filing_date=filing_date,
            acceptance_datetime=f"{filing_date}T18:30:45-04:00",
            form="8-K",
            item_codes=("1.01", "9.01"),
            primary_document="example.htm",
            source_url=sec_company_submissions_url(cik=cik),
            source_record_json=source_record,
            source_record_sha256="0" * 64,
        )


def test_semantic_v2_is_source_scope_aware_and_ticker_is_not_identity(tmp_path: Path) -> None:
    report = Phase32SemanticSourceFeasibilityV2(
        FakeSettings(tmp_path),
        FakeIndexClient(),
        FakeSemanticClient(),
        FakeSECClient(),
    ).run()  # type: ignore[arg-type]
    assert report["pass"] is True
    assert report["research_start"] == "2021-08-16"
    assert report["total_sampled_accessions"] == len(PHASE32_SEMANTIC_V2_PROBE_WINDOWS)
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["items_text_scope_diagnostics"]["is_acceptance_gate"] is False
    relations = report["ticker_relation_counts"]
    assert relations["DISCLOSURE_TEXT_AGREE_INDEX_DIFFERS"] >= 1
    assert relations["ALL_UNMAPPED"] >= 1


def test_semantic_v2_fails_exact_cik_identity_mismatch(tmp_path: Path) -> None:
    with pytest.raises(Phase32SemanticV2FeasibilityError, match="accession_cik_dates"):
        Phase32SemanticSourceFeasibilityV2(
            FakeSettings(tmp_path),
            FakeIndexClient(bad_cik=True),
            FakeSemanticClient(),
            FakeSECClient(),
        ).run()  # type: ignore[arg-type]


def test_semantic_v2_fingerprint_is_frozen_shape() -> None:
    value = phase32_semantic_v2_fingerprint()
    assert value == "eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566"
