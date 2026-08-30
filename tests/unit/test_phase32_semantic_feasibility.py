from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.backtesting.phase32_semantic_feasibility import (
    PHASE32_SEMANTIC_PROBE_WINDOWS,
    Phase32SemanticFeasibilityError,
    Phase32SemanticSourceFeasibility,
    phase32_semantic_feasibility_fingerprint,
)
from packages.providers.massive.phase32 import Phase32SECIndexWindowResult
from packages.providers.massive.phase32_semantic import (
    MassivePhase32SemanticClient,
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


def _accession_for(start_date: date) -> str:
    return f"0000000001-{str(start_date.year)[2:]}-000001"


class FakeIndexClient:
    def eight_k_window(self, *, start_date, end_date) -> Phase32SECIndexWindowResult:
        row = {
            "accession_number": _accession_for(start_date),
            "cik": "0000000001",
            "filing_date": start_date.isoformat(),
            "filing_url": "https://www.sec.gov/Archives/edgar/data/1/example.txt",
            "form_type": "8-K",
            "issuer_name": "Example Corp",
            "ticker": "BrK.B",
        }
        return Phase32SECIndexWindowResult(
            rows=(row,), page_count=1, request_ids=(f"index-{start_date}",)
        )


class FakeSemanticClient:
    def __init__(self, *, drift: bool = False) -> None:
        self.drift = drift

    def taxonomy(self) -> Phase32TaxonomyResult:
        row = {
            "taxonomy": "1.0",
            "primary_category": "corporate_events",
            "secondary_category": "material_agreements",
            "tertiary_category": "material_agreement",
            "description": "A material agreement was entered into.",
        }
        return Phase32TaxonomyResult(
            rows=(row,), page_count=1, request_ids=("taxonomy-1",)
        )

    def disclosures_window(
        self, *, start_date, end_date
    ) -> Phase32DisclosureWindowResult:
        if start_date.year < 2022:
            return Phase32DisclosureWindowResult(
                rows=(), page_count=1, request_ids=(f"disclosure-{start_date}",)
            )
        support = (
            "Company entered a changed material agreement."
            if self.drift
            else "Company entered a material agreement."
        )
        row = {
            "accession_number": _accession_for(start_date),
            "cik": "0000000001",
            "filing_date": start_date.isoformat(),
            "filing_url": "https://www.sec.gov/Archives/edgar/data/1/example.txt",
            "primary_category": "corporate_events",
            "secondary_category": "material_agreements",
            "tertiary_category": "material_agreement",
            "supporting_text": support,
            "tickers": ["BrK.B"],
        }
        return Phase32DisclosureWindowResult(
            rows=(row,), page_count=1, request_ids=(f"disclosure-{start_date}",)
        )

    def eight_k_text(self, *, cik, filing_date) -> tuple[dict, ...]:
        row = {
            "accession_number": _accession_for(filing_date),
            "cik": "0000000001",
            "filing_date": filing_date.isoformat(),
            "filing_url": "https://www.sec.gov/Archives/edgar/data/1/example.txt",
            "form_type": "8-K",
            "items_text": "Item 1.01. Company entered a material agreement.",
            "ticker": "BrK.B",
        }
        return (row,)


class FakeSECClient:
    def filing_metadata(
        self, *, cik, accession_number: str, filing_date: str
    ) -> SECSubmissionRecord:
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


class FakeREST:
    def __init__(self, pages_by_path):
        self.pages_by_path = pages_by_path
        self.calls = []

    def iter_pages(self, path, params=None):
        self.calls.append((path, dict(params or {})))
        yield from self.pages_by_path[path]


def test_phase32_semantic_source_gate_is_source_only_and_preserves_ticker_case(
    tmp_path: Path,
) -> None:
    report = Phase32SemanticSourceFeasibility(
        FakeSettings(tmp_path),
        FakeIndexClient(),
        FakeSemanticClient(),
        FakeSECClient(),
    ).run()  # type: ignore[arg-type]
    assert report["pass"] is True
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["phase33_signal_to_trade_entry_satisfied"] is False
    assert report["safe_semantic_history_start"] == "2022-01-03"
    assert report["total_sampled_accessions"] == len(PHASE32_SEMANTIC_PROBE_WINDOWS) - 1
    disclosure_text = (
        tmp_path
        / "data/provider/phase32_sec_8k_semantic_feasibility/v1/"
        "massive_disclosures/published_history_boundary.jsonl"
    ).read_text(encoding="utf-8")
    assert "BrK.B" in disclosure_text


def test_phase32_semantic_source_gate_fails_immutable_disclosure_drift(
    tmp_path: Path,
) -> None:
    settings = FakeSettings(tmp_path)
    Phase32SemanticSourceFeasibility(
        settings, FakeIndexClient(), FakeSemanticClient(), FakeSECClient()
    ).run()  # type: ignore[arg-type]
    with pytest.raises(Phase32SemanticFeasibilityError, match="evidence drifted"):
        Phase32SemanticSourceFeasibility(
            settings,
            FakeIndexClient(),
            FakeSemanticClient(drift=True),
            FakeSECClient(),
        ).run()  # type: ignore[arg-type]


def test_phase32_semantic_source_gate_stops_when_supporting_text_is_not_grounded(
    tmp_path: Path,
) -> None:
    with pytest.raises(Phase32SemanticFeasibilityError, match="supporting_text"):
        Phase32SemanticSourceFeasibility(
            FakeSettings(tmp_path),
            FakeIndexClient(),
            FakeSemanticClient(drift=True),
            FakeSECClient(),
        ).run()  # type: ignore[arg-type]


def test_massive_phase32_semantic_adapter_uses_frozen_endpoints_and_queries() -> None:
    disclosure_page = {
        "status": "OK",
        "request_id": "d1",
        "results": [
            {
                "accession_number": "0000000001-22-000001",
                "cik": "0000000001",
                "filing_date": "2022-01-03",
                "filing_url": "https://www.sec.gov/Archives/edgar/data/1/example.txt",
                "primary_category": "corporate_events",
                "secondary_category": "material_agreements",
                "tertiary_category": "material_agreement",
                "supporting_text": "Company entered a material agreement.",
                "tickers": ["BrK.B"],
            }
        ],
    }
    text_page = {
        "status": "OK",
        "request_id": "t1",
        "results": [
            {
                "accession_number": "0000000001-22-000001",
                "cik": "0000000001",
                "filing_date": "2022-01-03",
                "filing_url": "https://www.sec.gov/Archives/edgar/data/1/example.txt",
                "form_type": "8-K",
                "items_text": "Item 1.01. Company entered a material agreement.",
                "ticker": "BrK.B",
            }
        ],
    }
    taxonomy_page = {
        "status": "OK",
        "request_id": "x1",
        "results": [
            {
                "taxonomy": "1.0",
                "primary_category": "corporate_events",
                "secondary_category": "material_agreements",
                "tertiary_category": "material_agreement",
                "description": "A material agreement was entered into.",
            }
        ],
    }
    rest = FakeREST(
        {
            "/stocks/filings/8-K/vX/disclosures": [disclosure_page],
            "/stocks/filings/8-K/vX/text": [text_page],
            "/stocks/taxonomies/vX/disclosures": [taxonomy_page],
        }
    )
    client = MassivePhase32SemanticClient(rest)  # type: ignore[arg-type]

    disclosures = client.disclosures_window(
        start_date=date(2022, 1, 3), end_date=date(2022, 1, 7)
    )
    texts = client.eight_k_text(cik="1", filing_date=date(2022, 1, 3))
    taxonomy = client.taxonomy()

    assert disclosures.rows[0]["tickers"] == ["BrK.B"]
    assert texts[0]["ticker"] == "BrK.B"
    assert taxonomy.rows[0]["taxonomy"] == "1.0"
    assert rest.calls[0][1]["limit"] == 1000
    assert rest.calls[1][1]["cik"] == "0000000001"
    assert rest.calls[1][1]["form_type"] == "8-K"
    assert rest.calls[2][1]["limit"] == 1000


def test_phase32_semantic_fingerprint_is_sha256_shape() -> None:
    value = phase32_semantic_feasibility_fingerprint()
    assert len(value) == 64
    int(value, 16)
