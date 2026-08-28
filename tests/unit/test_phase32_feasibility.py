from __future__ import annotations

import gzip
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.backtesting.phase32_feasibility import (
    PHASE32_PROBE_WINDOWS,
    Phase32EightKFeasibility,
    Phase32FeasibilityError,
    phase32_feasibility_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.providers.massive.phase32 import Phase32SECIndexWindowResult
from packages.providers.sec_edgar import (
    SECEDGARClient,
    SECSubmissionRecord,
    SEC_EDGAR_CONTACT_EMAIL_ENV,
    sec_company_submissions_url,
    sec_submission_shard_url,
)


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(
            paths=SimpleNamespace(provider="data/provider", derived="data/derived")
        )

    def resolved_path(self, value: str) -> Path:
        return self.root / value


class FakeIndexClient:
    def __init__(self, *, drift: bool = False) -> None:
        self.drift = drift

    def eight_k_window(self, *, start_date, end_date) -> Phase32SECIndexWindowResult:
        suffix = "drift" if self.drift else "stable"
        accession = f"0000000001-{str(start_date.year)[2:]}-000001"
        row = {
            "accession_number": accession,
            "cik": "0000000001",
            "filing_date": start_date.isoformat(),
            "filing_url": f"https://www.sec.gov/Archives/edgar/data/1/{suffix}.txt",
            "form_type": "8-K",
            "issuer_name": "Example Corp",
            "ticker": "BrK.B",
        }
        return Phase32SECIndexWindowResult(
            rows=(row,), page_count=1, request_ids=(f"req-{start_date}",)
        )


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
                "items": "8.01,9.01",
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
            item_codes=("8.01", "9.01"),
            primary_document="example.htm",
            source_url=sec_company_submissions_url(cik=cik),
            source_record_json=source_record,
            source_record_sha256="0" * 64,
        )


class FakeResponse:
    def __init__(self, body: bytes, *, content_encoding: str | None = None) -> None:
        self._body = body
        self.headers = {}
        if content_encoding is not None:
            self.headers["Content-Encoding"] = content_encoding

    def read(self, _size: int = -1) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _recent_payload(
    *,
    accession: str = "0000000001-21-000001",
    filing_date: str = "2021-08-16",
    form: str = "8-K",
    items: str = "8.01,9.01",
) -> dict:
    return {
        "filings": {
            "recent": {
                "accessionNumber": [accession],
                "filingDate": [filing_date],
                "acceptanceDateTime": ["2021-08-16T22:30:45.000Z"],
                "form": [form],
                "items": [items],
                "primaryDocument": ["example.htm"],
            },
            "files": [],
        }
    }


def test_phase32_feasibility_v2_is_source_only_and_case_preserving(tmp_path: Path) -> None:
    report = Phase32EightKFeasibility(
        FakeSettings(tmp_path), FakeIndexClient(), FakeSECClient()
    ).run()  # type: ignore[arg-type]
    assert report["pass"] is True
    assert report["contract_version"].startswith("phase32-feasibility-v2-")
    assert report["sec_source"] == "data.sec.gov/submissions"
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["phase33_signal_to_trade_entry_satisfied"] is False
    assert report["total_index_rows"] == len(PHASE32_PROBE_WINDOWS)
    index_text = (
        tmp_path
        / "data/provider/phase32_sec_8k_feasibility/v2/massive_index/research_boundary.jsonl"
    ).read_text(encoding="utf-8")
    assert "BrK.B" in index_text


def test_phase32_v2_reuses_immutable_evidence_and_fails_drift(tmp_path: Path) -> None:
    settings = FakeSettings(tmp_path)
    first = Phase32EightKFeasibility(settings, FakeIndexClient(), FakeSECClient()).run()  # type: ignore[arg-type]
    second = Phase32EightKFeasibility(settings, FakeIndexClient(), FakeSECClient()).run()  # type: ignore[arg-type]
    assert first["windows"][0]["massive_index_sha256"] == second["windows"][0]["massive_index_sha256"]
    with pytest.raises(Phase32FeasibilityError, match="evidence drifted"):
        Phase32EightKFeasibility(settings, FakeIndexClient(drift=True), FakeSECClient()).run()  # type: ignore[arg-type]


def test_sec_company_submissions_url_requires_zero_padded_cik() -> None:
    assert sec_company_submissions_url(cik="4904") == (
        "https://data.sec.gov/submissions/CIK0000004904.json"
    )
    assert sec_submission_shard_url("CIK0000004904-submissions-001.json") == (
        "https://data.sec.gov/submissions/CIK0000004904-submissions-001.json"
    )


def test_sec_recent_metadata_parses_utc_acceptance_to_eastern_and_item_codes() -> None:
    accession = "0000000001-21-000001"
    body = json.dumps(_recent_payload(accession=accession)).encode()
    client = SECEDGARClient(
        contact_email="research@example.com",
        opener=lambda *args, **kwargs: FakeResponse(body),
        sleeper=lambda _: None,
    )
    record = client.filing_metadata(
        cik="1", accession_number=accession, filing_date="2021-08-16"
    )
    assert record.accession_number == accession
    assert record.issuer_cik == "0000000001"
    assert record.acceptance_datetime == "2021-08-16T18:30:45-04:00"
    assert record.form == "8-K"
    assert record.item_codes == ("8.01", "9.01")
    assert record.primary_document == "example.htm"
    assert record.source_url.endswith("CIK0000000001.json")
    assert '"items":"8.01,9.01"' in record.source_record_json


def test_sec_archived_shard_lookup_is_date_bounded() -> None:
    accession = "0000000001-21-000001"
    root = {
        "filings": {
            "recent": {
                "accessionNumber": [],
                "filingDate": [],
                "acceptanceDateTime": [],
                "form": [],
                "items": [],
                "primaryDocument": [],
            },
            "files": [
                {
                    "name": "CIK0000000001-submissions-001.json",
                    "filingCount": 1,
                    "filingFrom": "2021-01-01",
                    "filingTo": "2021-12-31",
                }
            ],
        }
    }
    shard = {
        "accessionNumber": [accession],
        "filingDate": ["2021-08-16"],
        "acceptanceDateTime": ["2021-08-16T22:30:45.000Z"],
        "form": ["8-K"],
        "items": ["2.04"],
        "primaryDocument": ["example.htm"],
    }

    def opener(request, timeout):
        if request.full_url.endswith("CIK0000000001.json"):
            return FakeResponse(json.dumps(root).encode())
        if request.full_url.endswith("CIK0000000001-submissions-001.json"):
            return FakeResponse(json.dumps(shard).encode())
        raise AssertionError(request.full_url)

    client = SECEDGARClient(
        contact_email="research@example.com",
        opener=opener,
        sleeper=lambda _: None,
    )
    record = client.filing_metadata(
        cik="1", accession_number=accession, filing_date="2021-08-16"
    )
    assert record.item_codes == ("2.04",)
    assert record.source_url.endswith("submissions-001.json")


def test_sec_client_requires_declared_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SEC_EDGAR_CONTACT_EMAIL_ENV, raising=False)
    with pytest.raises(ProviderError, match="fair-access identity is missing"):
        SECEDGARClient(opener=lambda *args, **kwargs: io.BytesIO(b""), sleeper=lambda _: None)


def test_sec_client_sends_fair_access_headers_decodes_gzip_and_caches() -> None:
    accession = "0000000001-21-000001"
    raw = json.dumps(_recent_payload(accession=accession)).encode()
    captured = {"calls": 0}

    def opener(request, timeout):
        captured["calls"] += 1
        captured["request"] = request
        return FakeResponse(gzip.compress(raw), content_encoding="gzip")

    client = SECEDGARClient(
        contact_email="research@example.com",
        opener=opener,
        sleeper=lambda _: None,
    )
    first = client.filing_metadata(
        cik="1", accession_number=accession, filing_date="2021-08-16"
    )
    second = client.filing_metadata(
        cik="1", accession_number=accession, filing_date="2021-08-16"
    )
    sent = {key.lower(): value for key, value in captured["request"].header_items()}
    assert captured["calls"] == 1
    assert sent["user-agent"] == "ATLAS Research research@example.com"
    assert sent["accept"] == "application/json"
    assert sent["accept-encoding"] == "gzip, deflate"
    assert sent["host"] == "data.sec.gov"
    assert first == second


def test_sec_client_rejects_non_original_8k() -> None:
    accession = "0000000001-21-000001"
    body = json.dumps(_recent_payload(accession=accession, form="8-K/A")).encode()
    client = SECEDGARClient(
        contact_email="research@example.com",
        opener=lambda *args, **kwargs: FakeResponse(body),
        sleeper=lambda _: None,
    )
    with pytest.raises(ProviderError, match="not original 8-K"):
        client.filing_metadata(
            cik="1", accession_number=accession, filing_date="2021-08-16"
        )


def test_sec_client_rejects_non_sec_submissions_host() -> None:
    client = SECEDGARClient(
        contact_email="research@example.com",
        opener=lambda *args, **kwargs: io.BytesIO(b""),
        sleeper=lambda _: None,
    )
    with pytest.raises(ProviderError, match="changed host"):
        client.get_json("https://example.com/submissions/CIK0000000001.json")
    with pytest.raises(ProviderError, match="stay under /submissions/"):
        client.get_json("https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json")


def test_phase32_feasibility_fingerprint_is_sha256_shape() -> None:
    value = phase32_feasibility_fingerprint()
    assert len(value) == 64
    int(value, 16)
