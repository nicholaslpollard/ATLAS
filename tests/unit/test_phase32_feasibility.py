from __future__ import annotations

import gzip
import io
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
    SEC_EDGAR_CONTACT_EMAIL_ENV,
    SECFilingHeader,
    parse_sec_filing_header,
    sec_index_headers_url,
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
    def filing_header(self, *, cik, accession_number: str) -> SECFilingHeader:
        raw = (
            f"ACCESSION NUMBER: {accession_number}\n"
            "CENTRAL INDEX KEY: 0000000001\n"
            "<ACCEPTANCE-DATETIME>20210816183045\n"
            "ITEM INFORMATION: Results of Operations and Financial Condition\n"
        )
        return SECFilingHeader(
            accession_number=accession_number,
            first_cik="0000000001",
            acceptance_datetime="2021-08-16T18:30:45-04:00",
            item_information=("Results of Operations and Financial Condition",),
            raw_header=raw,
            raw_header_sha256="0" * 64,
            source_url=sec_index_headers_url(cik=cik, accession_number=accession_number),
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


def test_phase32_feasibility_is_source_only_and_case_preserving(tmp_path: Path) -> None:
    report = Phase32EightKFeasibility(
        FakeSettings(tmp_path), FakeIndexClient(), FakeSECClient()
    ).run()  # type: ignore[arg-type]
    assert report["pass"] is True
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["phase33_signal_to_trade_entry_satisfied"] is False
    assert report["total_index_rows"] == len(PHASE32_PROBE_WINDOWS)
    assert report["public_availability_rule"] == "FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME"
    index_text = (
        tmp_path
        / "data/provider/phase32_sec_8k_feasibility/v1/massive_index/research_boundary.jsonl"
    ).read_text(encoding="utf-8")
    assert "BrK.B" in index_text


def test_phase32_feasibility_reuses_immutable_evidence_and_fails_drift(tmp_path: Path) -> None:
    settings = FakeSettings(tmp_path)
    first = Phase32EightKFeasibility(settings, FakeIndexClient(), FakeSECClient()).run()  # type: ignore[arg-type]
    second = Phase32EightKFeasibility(settings, FakeIndexClient(), FakeSECClient()).run()  # type: ignore[arg-type]
    assert first["windows"][0]["massive_index_sha256"] == second["windows"][0]["massive_index_sha256"]
    with pytest.raises(Phase32FeasibilityError, match="evidence drifted"):
        Phase32EightKFeasibility(settings, FakeIndexClient(drift=True), FakeSECClient()).run()  # type: ignore[arg-type]


def test_sec_index_headers_url_and_header_parser() -> None:
    accession = "0000000001-21-000001"
    url = sec_index_headers_url(cik="0000000001", accession_number=accession)
    assert url.endswith(
        "/1/000000000121000001/0000000001-21-000001-index-headers.html"
    )
    raw = """<SEC-DOCUMENT>
<SEC-HEADER>
ACCESSION NUMBER: 0000000001-21-000001
CENTRAL INDEX KEY: 0000000001
<ACCEPTANCE-DATETIME>20210816183045
ITEM INFORMATION: Results of Operations and Financial Condition
ITEM INFORMATION: Regulation FD Disclosure
</SEC-HEADER>
</SEC-DOCUMENT>
"""
    parsed = parse_sec_filing_header(raw, source_url=url)
    assert parsed.accession_number == accession
    assert parsed.acceptance_datetime == "2021-08-16T18:30:45-04:00"
    assert parsed.item_information == (
        "Results of Operations and Financial Condition",
        "Regulation FD Disclosure",
    )


def test_sec_client_requires_declared_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SEC_EDGAR_CONTACT_EMAIL_ENV, raising=False)
    with pytest.raises(ProviderError, match="fair-access identity is missing"):
        SECEDGARClient(opener=lambda *args, **kwargs: io.BytesIO(b""), sleeper=lambda _: None)


def test_sec_client_declared_user_agent_matches_sec_sample_shape() -> None:
    client = SECEDGARClient(
        contact_email="research@example.com",
        opener=lambda *args, **kwargs: io.BytesIO(b""),
        sleeper=lambda _: None,
    )
    assert client.declared_user_agent == "ATLAS Research research@example.com"
    assert "github.com" not in client.declared_user_agent


def test_sec_client_sends_fair_access_headers_and_decodes_gzip() -> None:
    accession = "0000000001-21-000001"
    raw = b"""<SEC-DOCUMENT>
<SEC-HEADER>
ACCESSION NUMBER: 0000000001-21-000001
CENTRAL INDEX KEY: 0000000001
<ACCEPTANCE-DATETIME>20210816183045
ITEM INFORMATION: Regulation FD Disclosure
</SEC-HEADER>
</SEC-DOCUMENT>
"""
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(gzip.compress(raw), content_encoding="gzip")

    client = SECEDGARClient(
        contact_email="research@example.com",
        opener=opener,
        sleeper=lambda _: None,
    )
    header = client.filing_header(cik="1", accession_number=accession)
    sent = {key.lower(): value for key, value in captured["request"].header_items()}
    assert sent["user-agent"] == "ATLAS Research research@example.com"
    assert sent["accept-encoding"] == "gzip, deflate"
    assert sent["host"] == "www.sec.gov"
    assert header.accession_number == accession
    assert header.item_information == ("Regulation FD Disclosure",)


def test_sec_client_rejects_non_sec_host() -> None:
    client = SECEDGARClient(
        contact_email="research@example.com",
        opener=lambda *args, **kwargs: io.BytesIO(b""),
        sleeper=lambda _: None,
    )
    with pytest.raises(Exception, match="changed host"):
        client.get_text(
            "https://example.com/Archives/edgar/data/1/"
            "000000000121000001/0000000001-21-000001-index-headers.html"
        )


def test_sec_client_rejects_complete_submission_text_target() -> None:
    client = SECEDGARClient(
        contact_email="research@example.com",
        opener=lambda *args, **kwargs: io.BytesIO(b""),
        sleeper=lambda _: None,
    )
    with pytest.raises(Exception, match="index-headers"):
        client.get_text(
            "https://www.sec.gov/Archives/edgar/data/1/"
            "000000000121000001/0000000001-21-000001.txt"
        )


def test_phase32_feasibility_fingerprint_is_sha256_shape() -> None:
    value = phase32_feasibility_fingerprint()
    assert len(value) == 64
    int(value, 16)
