from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from packages.backtesting.alpha_gate_sec_earnings_innovation_feasibility import (
    EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT,
    EARNINGS_INNOVATION_INPUT_RELATIVE,
    EARNINGS_INNOVATION_SAMPLE_SIZE,
    SECEarningsInnovationFeasibility,
    _extract_eps_entries,
    _same_accession_context_conflicts,
    _sample_ciks,
    earnings_innovation_feasibility_fingerprint,
)
from packages.providers.sec_xbrl import SECCompanyFactsDocument, sec_companyfacts_url


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(paths=SimpleNamespace(derived="data/derived"))

    def resolved_path(self, value: str) -> Path:
        return self.root / value


def _eps_entries(count: int = 32) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    base = date(2017, 3, 31)
    for index in range(count):
        end = base + timedelta(days=91 * index)
        start = end - timedelta(days=89)
        filed = end + timedelta(days=35)
        rows.append(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "filed": filed.isoformat(),
                "form": "10-K" if (index + 1) % 4 == 0 else "10-Q",
                "accn": f"0000000001-{str(filed.year)[-2:]}-{index + 1:06d}",
                "fy": filed.year,
                "fp": "FY" if (index + 1) % 4 == 0 else f"Q{(index % 4) + 1}",
                "frame": None,
                "val": 1.0 + index / 100.0,
            }
        )
    return rows


def _facts_document(cik: str, *, include_eps: bool = True) -> SECCompanyFactsDocument:
    facts = {"us-gaap": {}}
    if include_eps:
        facts["us-gaap"]["EarningsPerShareDiluted"] = {
            "units": {"USD/shares": _eps_entries()}
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
        return _facts_document(str(cik).zfill(10))


def _write_source_inventory(root: Path, count: int = 340) -> Path:
    path = root / "data/derived" / EARNINGS_INNOVATION_INPUT_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"issuer_cik": str(index + 1).zfill(10)} for index in range(count)]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_feasibility_fingerprint_is_frozen() -> None:
    assert earnings_innovation_feasibility_fingerprint() == EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT


def test_deterministic_sample_is_order_independent_and_exact() -> None:
    values = tuple(str(index + 1).zfill(10) for index in range(400))
    first = _sample_ciks(values)
    second = _sample_ciks(tuple(reversed(values)))
    assert first == second
    assert len(first) == EARNINGS_INNOVATION_SAMPLE_SIZE
    assert len(set(first)) == EARNINGS_INNOVATION_SAMPLE_SIZE


def test_eps_extraction_requires_exact_diluted_eps_unit_and_direct_source_window() -> None:
    document = _facts_document("0000000001")
    rows = _extract_eps_entries(document)
    assert rows
    assert all(row["unit"] == "USD/shares" for row in rows)
    assert all(row["form"] in {"10-Q", "10-K"} for row in rows)


def test_same_accession_semantic_context_conflict_is_detected() -> None:
    row = {
        "unit": "USD/shares",
        "start": "2024-01-01",
        "end": "2024-03-31",
        "filed": "2024-05-01",
        "form": "10-Q",
        "accn": "0000000001-24-000001",
        "fy": 2024,
        "fp": "Q1",
        "frame": None,
        "val": 1.0,
    }
    conflict = dict(row)
    conflict["val"] = 1.1
    assert _same_accession_context_conflicts((row, conflict)) == 1


def test_source_only_feasibility_passes_without_market_outcomes(tmp_path: Path) -> None:
    _write_source_inventory(tmp_path)
    report = SECEarningsInnovationFeasibility(
        FakeSettings(tmp_path), FakeCompanyFactsClient()  # type: ignore[arg-type]
    ).run()
    assert report["pass"] is True
    assert report["status"] == "FEASIBILITY_PASS"
    assert report["sample_size"] == EARNINGS_INNOVATION_SAMPLE_SIZE
    assert report["successful_documents"] == EARNINGS_INNOVATION_SAMPLE_SIZE
    assert report["eps_documents"] == EARNINGS_INNOVATION_SAMPLE_SIZE
    assert report["history_ready_issuers"] == EARNINGS_INNOVATION_SAMPLE_SIZE
    assert report["sue_baseline_ready_issuers"] == EARNINGS_INNOVATION_SAMPLE_SIZE
    assert report["direct_quarter_observations"] >= 2500
    assert len(report["calendar_years_observed"]) >= 8
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
    assert report["phase33_signal_to_trade_authority"] is False
    assert "PIT original-accession" in report["next_scientific_action"]


def test_source_insufficiency_fails_closed_without_outcomes(tmp_path: Path) -> None:
    _write_source_inventory(tmp_path)

    class SparseClient:
        def company_facts(self, *, cik: object) -> SECCompanyFactsDocument:
            text = str(cik).zfill(10)
            return _facts_document(text, include_eps=(int(text) % 3 == 0))

    report = SECEarningsInnovationFeasibility(
        FakeSettings(tmp_path), SparseClient()  # type: ignore[arg-type]
    ).run()
    assert report["pass"] is False
    assert report["status"] == "FEASIBILITY_FAIL"
    assert report["eps_documents"] < 210
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["protected_holdout_consumed"] is False
