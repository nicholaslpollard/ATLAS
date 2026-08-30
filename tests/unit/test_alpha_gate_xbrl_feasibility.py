from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.backtesting.alpha_gate_xbrl_feasibility import (
    XBRL_INPUT_RELATIVE,
    XBRL_SAMPLE_SIZE,
    XBRLFundamentalFeasibility,
    _sample_ciks,
    xbrl_feasibility_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.providers.sec_xbrl import (
    SECCompanyFactsDocument,
    SECXBRLCompanyFactsClient,
    sec_companyfacts_url,
)


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(paths=SimpleNamespace(derived="data/derived"))

    def resolved_path(self, value: str) -> Path:
        return self.root / value


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.headers = {}

    def read(self, _size: int = -1) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _fact_entries(count: int = 8) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    base = date(2021, 3, 31)
    for index in range(count):
        end = base + timedelta(days=91 * index)
        filed = end + timedelta(days=35)
        rows.append(
            {
                "end": end.isoformat(),
                "filed": filed.isoformat(),
                "form": "10-Q",
                "accn": f"0000000001-21-{index + 1:06d}",
                "fy": 2021 + index // 4,
                "fp": f"Q{index % 4 + 1}",
                "frame": None,
                "val": 1000 + index,
            }
        )
    return rows


def _facts_document(cik: str) -> SECCompanyFactsDocument:
    entries = _fact_entries()
    facts = {
        "us-gaap": {
            "Assets": {"units": {"USD": list(entries)}},
            "NetIncomeLoss": {"units": {"USD": list(entries)}},
            "NetCashProvidedByUsedInOperatingActivities": {
                "units": {"USD": list(entries)}
            },
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {"USD": list(entries)}
            },
            "GrossProfit": {"units": {"USD": list(entries)}},
        }
    }
    return SECCompanyFactsDocument(
        issuer_cik=cik,
        entity_name=f"Issuer {cik}",
        facts=facts,
        source_url=sec_companyfacts_url(cik=cik),
        source_sha256="0" * 64,
    )


class FakeCompanyFactsClient:
    def company_facts(self, *, cik: object) -> SECCompanyFactsDocument:
        text = str(cik).zfill(10)
        return _facts_document(text)


def _write_source_inventory(root: Path, count: int = 220) -> Path:
    path = root / "data/derived" / XBRL_INPUT_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"issuer_cik": str(index + 1).zfill(10), "phase32_field_unused": "source_only"}
        for index in range(count)
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_sec_companyfacts_url_zero_pads_cik() -> None:
    assert sec_companyfacts_url(cik="4904") == (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000004904.json"
    )


def test_sec_xbrl_client_reuses_edgar_http_seam_and_validates_cik() -> None:
    payload = {
        "cik": 4904,
        "entityName": "Example Corp",
        "facts": {"us-gaap": {}},
    }
    captured = {"calls": 0}

    def opener(request, timeout):
        captured["calls"] += 1
        captured["request"] = request
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    client = SECXBRLCompanyFactsClient(
        contact_email="research@example.com", opener=opener, sleeper=lambda _: None
    )
    document = client.company_facts(cik="4904")
    assert document.issuer_cik == "0000004904"
    assert document.entity_name == "Example Corp"
    assert captured["calls"] == 1
    sent = {key.lower(): value for key, value in captured["request"].header_items()}
    assert sent["user-agent"] == "ATLAS Research research@example.com"
    assert sent["host"] == "data.sec.gov"


def test_sec_xbrl_client_rejects_non_companyfacts_paths_and_hosts() -> None:
    client = SECXBRLCompanyFactsClient(
        contact_email="research@example.com",
        opener=lambda *args, **kwargs: FakeResponse(b"{}"),
        sleeper=lambda _: None,
    )
    with pytest.raises(ProviderError, match="companyfacts"):
        client.get_json("https://data.sec.gov/submissions/CIK0000004904.json")
    with pytest.raises(ProviderError, match="changed host"):
        client.get_json("https://example.com/api/xbrl/companyfacts/CIK0000004904.json")


def test_deterministic_sample_is_order_independent_and_exact() -> None:
    values = tuple(str(index + 1).zfill(10) for index in range(250))
    first = _sample_ciks(values)
    second = _sample_ciks(tuple(reversed(values)))
    assert first == second
    assert len(first) == XBRL_SAMPLE_SIZE
    assert len(set(first)) == XBRL_SAMPLE_SIZE


def test_source_only_feasibility_passes_without_market_outcomes(tmp_path: Path) -> None:
    _write_source_inventory(tmp_path)
    report = XBRLFundamentalFeasibility(
        FakeSettings(tmp_path), FakeCompanyFactsClient()  # type: ignore[arg-type]
    ).run()
    assert report["pass"] is True
    assert report["status"] == "FEASIBILITY_PASS"
    assert report["sample_size"] == XBRL_SAMPLE_SIZE
    assert report["successful_documents"] == XBRL_SAMPLE_SIZE
    assert report["accrual_history_ready"] == XBRL_SAMPLE_SIZE
    assert report["profitability_history_ready"] == XBRL_SAMPLE_SIZE
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["protected_holdout_consumed"] is False
    assert report["provider_writes_performed"] == 0
    assert report["broker_reads_performed"] == 0
    assert report["broker_writes_performed"] == 0
    assert report["order_writes_performed"] == 0
    assert report["paper_submits_performed"] == 0
    assert report["live_writes_performed"] == 0
    assert report["automation_writes_performed"] == 0
    assert "PIT accession/acceptance-time reconstruction" in report["next_scientific_action"]


def test_feasibility_records_source_failures_and_fails_closed(tmp_path: Path) -> None:
    _write_source_inventory(tmp_path)

    class MostlyFailingClient:
        def company_facts(self, *, cik: object) -> SECCompanyFactsDocument:
            text = str(cik).zfill(10)
            if int(text) % 2:
                raise ProviderError("synthetic source failure")
            return _facts_document(text)

    report = XBRLFundamentalFeasibility(
        FakeSettings(tmp_path), MostlyFailingClient()  # type: ignore[arg-type]
    ).run()
    assert report["pass"] is False
    assert report["status"] == "FEASIBILITY_FAIL"
    assert report["failed_documents"] > 0
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0


def test_xbrl_feasibility_fingerprint_is_sha256_shape() -> None:
    value = xbrl_feasibility_fingerprint()
    assert len(value) == 64
    int(value, 16)
