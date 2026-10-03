from __future__ import annotations

import json
from pathlib import Path

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as PLAN_CONTRACT,
    PROVIDER_CANDIDATE,
)
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    _symbol_matches_underlying,
    run_thetadata_candidate_surface_qualification_v1,
)
from packages.providers.thetadata.client import ThetaDataResponse


class _Settings:
    def __init__(self, root: Path) -> None:
        self.root = root

    def assert_external_storage_binding(self, category: str) -> None:
        assert category == "options"

    def resolved_path(self, relative: str) -> Path:
        return self.root / relative


def _anchor(index: int, year: int) -> dict:
    day = f"{year}0106"
    return {
        "anchor_index": index,
        "qualification_reasons": [f"YEAR_{year}_FIRST"],
        "date_et": f"{year}-01-06",
        "time_of_day_et": "09:35:00.000",
        "symbol": "ABC",
        "decision_spot_query_fingerprint": f"{index:064x}",
        "query": {
            "endpoint": "/v3/option/at_time/quote",
            "params": {
                "symbol": "ABC",
                "expiration": "*",
                "strike": "*",
                "right": "call",
                "start_date": day,
                "end_date": day,
                "time_of_day": "09:35:00.000",
                "max_dte": 75,
                "strike_range": None,
                "format": "json",
            },
            "source_query_fingerprint": f"{index:064x}",
            "member_case_ids": [f"case-{year}"],
            "member_case_count": 1,
        },
    }


def _plan() -> dict:
    anchors = [_anchor(index, year) for index, year in enumerate(range(2021, 2026), 1)]
    body = {
        "contract": PLAN_CONTRACT,
        "status": "PLANNED_ZERO_PROVIDER_READS",
        "decision_spot_fingerprint": "1" * 64,
        "provider_candidate": PROVIDER_CANDIDATE,
        "target_scope": {
            "date_min": "2021-01-06",
            "date_max": "2025-01-06",
            "decision_clock_et": "09:35:00.000",
            "max_dte_calendar_days": 75,
        },
        "provider_request_contract": {
            "expiration": "*",
            "strike": "*",
            "right": "call",
            "strike_range": None,
        },
        "qualification": {
            "outcome_blind": True,
            "full_acquisition_authorized": False,
            "anchor_query_count": len(anchors),
            "anchors": anchors,
        },
        "provider_requests": 0,
        "historical_fill_authority": False,
        "strategy_evidence_authority": False,
    }
    body["plan_fingerprint"] = _fingerprint(body)
    return body


def _response(
    *,
    symbol: str,
    date_et: str,
    time_of_day_et: str,
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
            if len(date_et) == 8 and date_et.isdigit()
            else date_et
        )
        year = int(day[:4])
        rows_list = [
            {
                "symbol": symbol,
                "expiration": f"{year}-02-21",
                "strike": 100.0,
                "right": right,
                "timestamp": f"{day}T09:34:59.500",
                "bid_size": 10,
                "bid_exchange": 1,
                "bid": 1.0,
                "bid_condition": 0,
                "ask_size": 12,
                "ask_exchange": 2,
                "ask": 1.1,
                "ask_condition": 0,
            },
            {
                "symbol": symbol,
                "expiration": f"{year}-03-07",
                "strike": 105.0,
                "right": right,
                "timestamp": f"{day}T09:34:58.000",
                "bid_size": 5,
                "bid_exchange": 1,
                "bid": 0.5,
                "bid_condition": 0,
                "ask_size": 6,
                "ask_exchange": 2,
                "ask": 0.6,
                "ask_condition": 0,
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


def test_qualification_proves_all_years_and_repeatability(tmp_path):
    calls = []

    def reader(**kwargs):
        calls.append(dict(kwargs))
        return _response(**kwargs)

    report = run_thetadata_candidate_surface_qualification_v1(
        _Settings(tmp_path),
        _plan(),
        workers=2,
        reader=reader,
    )

    assert report["status"] == "QUALIFIED_FOR_BOUNDED_CANDIDATE_SURFACE_ACQUISITION"
    assert report["full_acquisition_source_qualified"] is True
    assert report["oldest_2021_surface_proven"] is True
    assert report["full_2021_2025_surface_coverage_proven"] is True
    assert report["repeatability_probe"]["deterministic_normalized_surface"] is True
    assert report["provider_requests"] == 6
    assert len(calls) == 6
    assert Path(report["report_path"]).is_file()
    assert report["valid_surface_coverage_by_year"] == {
        "2021": 1,
        "2022": 1,
        "2023": 1,
        "2024": 1,
        "2025": 1,
    }
    assert all(value == 2 for value in report["two_sided_rows_by_year"].values())


def test_explicit_no_data_2021_blocks_full_acquisition_without_transport_error(tmp_path):
    def reader(**kwargs):
        empty = str(kwargs["date_et"]).startswith("2021")
        return _response(**kwargs, empty=empty)

    report = run_thetadata_candidate_surface_qualification_v1(
        _Settings(tmp_path),
        _plan(),
        workers=2,
        reader=reader,
    )

    assert report["status"] == "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
    assert report["full_acquisition_source_qualified"] is False
    assert report["oldest_2021_surface_proven"] is False
    assert report["status_counts"]["EXPLICIT_NO_DATA"] == 1
    assert report["hard_validation_or_transport_errors"] == 0


def test_future_quote_in_surface_fails_validation(tmp_path):
    def reader(**kwargs):
        response = _response(**kwargs)
        rows = [dict(row) for row in response.rows]
        rows[0]["timestamp"] = (
            f"{str(kwargs['date_et'])[:4]}-01-06T09:35:00.500"
        )
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

    report = run_thetadata_candidate_surface_qualification_v1(
        _Settings(tmp_path),
        _plan(),
        workers=2,
        reader=reader,
    )

    assert report["full_acquisition_source_qualified"] is False
    assert report["hard_validation_or_transport_errors"] == 5
    assert report["status_counts"]["SURFACE_VALIDATION_ERROR"] == 5


def test_response_symbol_accepts_same_root_occ_but_not_neighbor_root():
    assert _symbol_matches_underlying("AAPL", "AAPL") is True
    assert _symbol_matches_underlying("AAPL250221C00100000", "AAPL") is True
    assert _symbol_matches_underlying("AAPL  250221C00100000", "AAPL") is True
    assert _symbol_matches_underlying("AAPLX250221C00100000", "AAPL") is False
