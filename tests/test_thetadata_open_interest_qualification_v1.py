from __future__ import annotations

import json
from pathlib import Path

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_enrichment_plan_v1 import (
    CONTRACT as ENRICHMENT_PLAN_CONTRACT,
    PROVIDER_CANDIDATE,
)
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    CONTRACT as QUOTE_QUALIFICATION_CONTRACT,
)
import packages.data.thetadata_open_interest_qualification_v1 as module
from packages.providers.thetadata.client import ThetaDataResponse


class _Settings:
    def __init__(self, root: Path) -> None:
        self.root = root

    def assert_external_storage_binding(self, category: str) -> None:
        assert category == "options"

    def resolved_path(self, relative: str) -> Path:
        return self.root / relative


def _anchor(index: int, year: int) -> dict:
    date_text = f"{year}0106"
    source_fp = f"{index:064x}"
    query = {
        "endpoint": "/v3/option/history/open_interest",
        "params": {
            "symbol": "ABC",
            "expiration": "*",
            "strike": "*",
            "right": "call",
            "date": date_text,
            "max_dte": 75,
            "strike_range": None,
            "format": "json",
        },
        "source_quote_query_fingerprint": source_fp,
        "query_fingerprint": f"{index + 100:064x}",
        "member_case_ids": [f"case-{year}"],
        "member_case_count": 1,
    }
    return {
        "anchor_index": index,
        "qualification_reasons": [f"YEAR_{year}_FIRST"],
        "symbol": "ABC",
        "date_et": f"{year}-01-06",
        "source_quote_query_fingerprint": source_fp,
        "query": query,
    }


def _enrichment_plan() -> dict:
    anchors = [_anchor(index, year) for index, year in enumerate(range(2021, 2026), 1)]
    body = {
        "contract": ENRICHMENT_PLAN_CONTRACT,
        "status": "PLANNED_ZERO_PROVIDER_READS",
        "source_plan_fingerprint": "2" * 64,
        "decision_spot_fingerprint": "1" * 64,
        "provider_candidate": PROVIDER_CANDIDATE,
        "open_interest_stage": {
            "qualification_anchor_count": len(anchors),
            "qualification_anchors": anchors,
        },
        "provider_requests": 0,
        "historical_fill_authority": False,
        "strategy_evidence_authority": False,
    }
    body["enrichment_plan_fingerprint"] = _fingerprint(body)
    return body


def _quote_qualification(plan: dict) -> dict:
    body = {
        "contract": QUOTE_QUALIFICATION_CONTRACT,
        "plan_fingerprint": plan["source_plan_fingerprint"],
        "decision_spot_fingerprint": plan["decision_spot_fingerprint"],
        "provider_candidate": PROVIDER_CANDIDATE,
        "full_acquisition_source_qualified": True,
        "hard_validation_or_transport_errors": 0,
        "repeatability_probe": {
            "deterministic_normalized_surface": True,
        },
    }
    body["qualification_fingerprint"] = _fingerprint(body)
    return body


def _response(
    *,
    symbol: str,
    date_et: str,
    right: str,
    max_dte: int,
    strike_range=None,
    empty: bool = False,
) -> ThetaDataResponse:
    if empty:
        rows = ()
        raw = b"NO_DATA"
        status = 472
    else:
        day = (
            f"{date_et[:4]}-{date_et[4:6]}-{date_et[6:8]}"
            if len(date_et) == 8
            else date_et
        )
        year = int(day[:4])
        rows_list = [
            {
                "symbol": symbol,
                "expiration": f"{year}-02-21",
                "strike": 100.0,
                "right": right,
                "timestamp": f"{day}T06:30:00.000",
                "open_interest": 250,
            },
            {
                "symbol": symbol,
                "expiration": f"{year}-03-07",
                "strike": 105.0,
                "right": right,
                "timestamp": f"{day}T06:31:00.000",
                "open_interest": 25,
            },
        ]
        rows = tuple(rows_list)
        raw = json.dumps(rows_list, sort_keys=True).encode("utf-8")
        status = 200
    return ThetaDataResponse(
        http_status=status,
        rows=rows,
        headers={},
        response_bytes=len(raw),
        elapsed_seconds=0.01,
        raw_body=raw,
        library_version="1.0.12",
    )


def _small(monkeypatch) -> None:
    monkeypatch.setattr(module, "EXPECTED_QUALIFICATION_ANCHORS", 5)


def test_open_interest_qualification_proves_all_years_and_repeatability(
    tmp_path, monkeypatch
):
    _small(monkeypatch)
    calls = []

    def reader(**kwargs):
        calls.append(dict(kwargs))
        return _response(**kwargs)

    plan = _enrichment_plan()
    report = module.run_thetadata_open_interest_qualification_v1(
        _Settings(tmp_path),
        plan,
        _quote_qualification(plan),
        workers=2,
        reader=reader,
    )

    assert report["status"] == "QUALIFIED_FOR_BOUNDED_OPEN_INTEREST_SURFACE_ACQUISITION"
    assert report["full_open_interest_acquisition_source_qualified"] is True
    assert report["oldest_2021_surface_proven"] is True
    assert report["full_2021_2025_surface_coverage_proven"] is True
    assert report["repeatability_probe"]["deterministic_normalized_surface"] is True
    assert report["provider_requests"] == 6
    assert len(calls) == 6
    assert report["valid_surface_coverage_by_year"] == {
        "2021": 1,
        "2022": 1,
        "2023": 1,
        "2024": 1,
        "2025": 1,
    }
    assert all(value == 1 for value in report["phase13_oi_rows_by_year"].values())
    assert Path(report["report_path"]).is_file()


def test_explicit_no_data_2021_blocks_oi_acquisition_without_hard_error(
    tmp_path, monkeypatch
):
    _small(monkeypatch)

    def reader(**kwargs):
        return _response(
            **kwargs,
            empty=str(kwargs["date_et"]).startswith("2021"),
        )

    plan = _enrichment_plan()
    report = module.run_thetadata_open_interest_qualification_v1(
        _Settings(tmp_path),
        plan,
        _quote_qualification(plan),
        workers=2,
        reader=reader,
    )

    assert report["status"] == "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
    assert report["full_open_interest_acquisition_source_qualified"] is False
    assert report["oldest_2021_surface_proven"] is False
    assert report["status_counts"]["EXPLICIT_NO_DATA"] == 1
    assert report["hard_validation_or_transport_errors"] == 0


def test_oi_after_decision_clock_fails_validation(tmp_path, monkeypatch):
    _small(monkeypatch)

    def reader(**kwargs):
        response = _response(**kwargs)
        rows = [dict(row) for row in response.rows]
        date_et = str(kwargs["date_et"])
        day = (
            f"{date_et[:4]}-{date_et[4:6]}-{date_et[6:8]}"
            if len(date_et) == 8
            else date_et
        )
        rows[0]["timestamp"] = f"{day}T10:00:00.000"
        raw = json.dumps(rows, sort_keys=True).encode("utf-8")
        return ThetaDataResponse(
            http_status=200,
            rows=tuple(rows),
            headers={},
            response_bytes=len(raw),
            elapsed_seconds=0.01,
            raw_body=raw,
            library_version="1.0.12",
        )

    plan = _enrichment_plan()
    report = module.run_thetadata_open_interest_qualification_v1(
        _Settings(tmp_path),
        plan,
        _quote_qualification(plan),
        workers=2,
        reader=reader,
    )

    assert report["full_open_interest_acquisition_source_qualified"] is False
    assert report["hard_validation_or_transport_errors"] == 5
    assert report["status_counts"]["SURFACE_VALIDATION_ERROR"] == 5
