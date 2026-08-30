from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.backtesting.alpha_gate_xbrl_feasibility import XBRL_REPORT_RELATIVE
from packages.backtesting.alpha_gate_xbrl_pit_audit import (
    XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT,
    XBRL_PIT_AUDIT_FINGERPRINT,
    XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE,
    XBRL_PIT_MAX_ACCESSIONS_PER_ISSUER,
    XBRLPITSourceAudit,
    _same_accession_context_conflicts,
    _select_accessions,
    _version_summary,
    accepted_feasibility_evidence_fingerprint,
    xbrl_pit_audit_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.providers.massive.xbrl_pit import MassiveCIKPITReferenceProvider
from packages.providers.sec_xbrl import SECCompanyFactsDocument, sec_companyfacts_url
from packages.providers.sec_xbrl_pit import SECOriginalFilingMetadata, SECXBRLPITMetadataClient


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(paths=SimpleNamespace(derived="data/derived", provider="data/provider"))
        self.massive = SimpleNamespace(reference=SimpleNamespace(page_limit=1000))

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


def _group_summary(ready: bool) -> dict[str, object]:
    return {"period_end_count": 8 if ready else 0}


def _accepted_feasibility_report() -> dict[str, object]:
    issuer_reports: list[dict[str, object]] = []
    for index in range(200):
        cik = str(index + 1).zfill(10)
        assets = index < 174
        net_income = index < 170 or 174 <= index < 184
        ocf = index < 170 or 184 <= index < 194
        revenue = index < 136
        gross = index < 78
        cost = index < 92 or 136 <= index < 141
        issuer_reports.append(
            {
                "issuer_cik": cik,
                "accrual_history_ready": assets and net_income and ocf,
                "profitability_history_ready": assets and revenue and (gross or cost),
                "concept_groups": {
                    "assets": _group_summary(assets),
                    "net_income": _group_summary(net_income),
                    "operating_cash_flow": _group_summary(ocf),
                    "revenue": _group_summary(revenue),
                    "gross_profit": _group_summary(gross),
                    "cost_of_revenue": _group_summary(cost),
                },
            }
        )
    report: dict[str, object] = {
        "feasibility_fingerprint": "6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152",
        "status": "FEASIBILITY_PASS",
        "source_inventory_unique_ciks": 4400,
        "sample_size": 200,
        "sample_ciks": [str(index + 1).zfill(10) for index in range(200)],
        "successful_documents": 200,
        "failed_documents": 0,
        "accrual_history_ready": 170,
        "profitability_history_ready": 92,
        "group_history_ready_counts": {
            "assets": 174,
            "cost_of_revenue": 97,
            "gross_profit": 78,
            "net_income": 180,
            "operating_cash_flow": 180,
            "revenue": 136,
        },
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "provider_reads_performed": 200,
        "provider_writes_performed": 0,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "automation_writes_performed": 0,
        "issuer_reports": issuer_reports,
    }
    return report


def _write_feasibility_report(root: Path) -> Path:
    path = root / "data/derived" / XBRL_REPORT_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_accepted_feasibility_report(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _companyfacts_document(cik: str) -> SECCompanyFactsDocument:
    rows: list[dict[str, object]] = []
    for index, year in enumerate((2017, 2019, 2021, 2023, 2025), start=1):
        rows.append(
            {
                "end": f"{year}-03-31",
                "filed": f"{year}-05-01",
                "form": "10-Q",
                "accn": f"{int(cik):010d}-{year % 100:02d}-{index:06d}",
                "fy": year,
                "fp": "Q1",
                "frame": f"CY{year}Q1I",
                "val": 1000 + index,
            }
        )
    return SECCompanyFactsDocument(
        issuer_cik=cik,
        entity_name=f"Issuer {cik}",
        facts={"us-gaap": {"Assets": {"units": {"USD": rows}}}},
        source_url=sec_companyfacts_url(cik=cik),
        source_sha256="a" * 64,
    )


class FakeCompanyFactsClient:
    def company_facts(self, *, cik: object) -> SECCompanyFactsDocument:
        return _companyfacts_document(str(cik).zfill(10))


class FakeSubmissionClient:
    def filing_metadata(
        self,
        *,
        cik: object,
        accession_number: str,
        filing_date: str,
        allowed_forms: tuple[str, ...],
    ) -> SECOriginalFilingMetadata:
        form = allowed_forms[0]
        return SECOriginalFilingMetadata(
            accession_number=accession_number,
            issuer_cik=str(cik).zfill(10),
            filing_date=filing_date,
            acceptance_datetime=f"{filing_date}T16:30:00-04:00",
            form=form,
            primary_document="report.htm",
            source_url="https://data.sec.gov/submissions/example.json",
            source_record_json="{}\n",
            source_record_sha256="b" * 64,
        )


class FakeReferenceProvider:
    def cik_snapshot(self, *, cik: object, as_of_date: date, include_inactive: bool = True):
        text = str(cik).zfill(10)
        return [
            {
                "ticker": f"T{int(text)}",
                "cik": text,
                "composite_figi": f"BBG{int(text):09d}",
                "share_class_figi": None,
                "primary_exchange": "XNYS",
                "type": "CS",
                "active": True,
            }
        ]


def test_accepted_feasibility_evidence_fingerprint_is_exact() -> None:
    report = _accepted_feasibility_report()
    assert accepted_feasibility_evidence_fingerprint(report) == (
        XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT
    )


def test_pit_audit_fingerprint_is_frozen() -> None:
    assert xbrl_pit_audit_fingerprint() == XBRL_PIT_AUDIT_FINGERPRINT


def test_evenly_spaced_accession_selection_includes_history_endpoints() -> None:
    groups = [
        {
            "accession_number": f"0000000001-2{index}-{index:06d}",
            "filing_date": f"202{index}-05-01",
            "form": "10-Q",
            "clean": True,
            "rows": [],
        }
        for index in range(7)
    ]
    selected = _select_accessions(groups)
    assert len(selected) == XBRL_PIT_MAX_ACCESSIONS_PER_ISSUER
    assert selected[0]["accession_number"] == groups[0]["accession_number"]
    assert selected[-1]["accession_number"] == groups[-1]["accession_number"]


def test_same_accession_conflict_fails_but_exact_duplicate_does_not() -> None:
    base = {
        "tag": "Assets",
        "unit": "USD",
        "start": None,
        "end": "2025-03-31",
        "fy": 2025,
        "fp": "Q1",
        "frame": "CY2025Q1I",
        "val": 100,
    }
    conflicts, duplicates = _same_accession_context_conflicts([base, dict(base)])
    assert conflicts == 0
    assert duplicates == 1
    changed = dict(base)
    changed["val"] = 101
    conflicts, _ = _same_accession_context_conflicts([base, changed])
    assert conflicts == 1


def test_cross_accession_revision_is_versioned_not_overwritten() -> None:
    first = {
        "tag": "Assets",
        "unit": "USD",
        "start": None,
        "end": "2024-12-31",
        "fy": 2024,
        "fp": "FY",
        "frame": "CY2024I",
        "val": 100,
        "accn": "0000000001-25-000001",
        "filed": "2025-02-01",
    }
    second = {**first, "val": 110, "accn": "0000000001-26-000001", "filed": "2026-02-01"}
    summary = _version_summary([first, second])
    assert summary["repeated_cross_accession_contexts"] == 1
    assert summary["revised_cross_accession_contexts"] == 1
    assert summary["cross_accession_version_rows"] == 2


def test_sec_pit_metadata_client_accepts_original_10q_and_rejects_amendment() -> None:
    accession = "0000000001-25-000001"
    payload = {
        "filings": {
            "recent": {
                "accessionNumber": [accession],
                "filingDate": ["2025-05-01"],
                "acceptanceDateTime": ["2025-05-01T16:30:00-04:00"],
                "form": ["10-Q"],
                "items": [""],
                "primaryDocument": ["report.htm"],
            },
            "files": [],
        }
    }

    def opener(request, timeout):
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    client = SECXBRLPITMetadataClient(
        contact_email="research@example.com", opener=opener, sleeper=lambda _: None
    )
    record = client.filing_metadata(
        cik="1", accession_number=accession, filing_date="2025-05-01", allowed_forms=("10-Q",)
    )
    assert record.form == "10-Q"
    with pytest.raises(ProviderError, match="allowed original forms"):
        client.filing_metadata(
            cik="1", accession_number=accession, filing_date="2025-05-01", allowed_forms=("10-Q/A",)
        )


def test_massive_cik_pit_provider_uses_exact_cik_and_date_filters(tmp_path: Path) -> None:
    captured: list[dict[str, object]] = []

    class FakeMassiveClient:
        def iter_pages(self, path, params):
            captured.append({"path": path, "params": dict(params)})
            yield {
                "results": [
                    {
                        "ticker": "ABC",
                        "cik": "0000000001",
                        "composite_figi": "BBG000000001",
                        "primary_exchange": "XNYS",
                        "type": "CS",
                        "active": params["active"],
                    }
                ]
            }

    provider = MassiveCIKPITReferenceProvider(
        FakeSettings(tmp_path), client=FakeMassiveClient()  # type: ignore[arg-type]
    )
    rows = provider.cik_snapshot(cik="1", as_of_date=date(2025, 5, 2), include_inactive=True)
    assert rows
    assert len(captured) == 2
    assert all(item["path"] == "/v3/reference/tickers" for item in captured)
    assert all(item["params"]["cik"] == "0000000001" for item in captured)
    assert all(item["params"]["date"] == "2025-05-02" for item in captured)


def test_source_only_pit_audit_passes_without_market_outcomes(tmp_path: Path) -> None:
    _write_feasibility_report(tmp_path)
    report = XBRLPITSourceAudit(
        FakeSettings(tmp_path),
        FakeCompanyFactsClient(),  # type: ignore[arg-type]
        FakeSubmissionClient(),  # type: ignore[arg-type]
        FakeReferenceProvider(),  # type: ignore[arg-type]
    ).run()
    assert report["pass"] is True
    assert report["status"] == "AUDIT_PASS"
    assert report["audit_issuer_sample_size"] == XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE
    assert report["companyfacts_success"] == XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE
    assert report["selected_original_filings"] == 200
    assert report["sec_metadata_reconciled"] == 200
    assert report["acceptance_decisions"] == 200
    assert report["unambiguous_identity_mappings"] == 200
    assert report["issuers_with_3_unambiguous_mappings"] == XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE
    assert report["same_accession_context_conflicts"] == 0
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
