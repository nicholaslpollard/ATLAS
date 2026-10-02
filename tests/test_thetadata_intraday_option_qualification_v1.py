from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_intraday_option_plan_v1 import (
    CONTRACT as PLAN_CONTRACT,
    PROVIDER_CANDIDATE,
)
from packages.data.thetadata_intraday_option_qualification_v1 import (
    run_thetadata_intraday_option_qualification_v1,
)
from packages.providers.thetadata.client import ThetaDataResponse


class _Settings:
    def __init__(self, root: Path) -> None:
        self.root = root

    def assert_external_storage_binding(self, category: str) -> None:
        assert category == "options"

    def resolved_path(self, relative: str) -> Path:
        return self.root / relative


def _anchor(index: int, year: int, role: str, time_et: str) -> dict:
    day = f"{year}0106"
    expiration = f"{year}0221"
    return {
        "anchor_index": index,
        "qualification_reasons": [f"YEAR_{year}_{role}_FIRST"],
        "date_et": f"{year}-01-06",
        "time_of_day_et": time_et,
        "option_symbol": f"ABC{str(year)[2:]}0221C00100000",
        "query": {
            "endpoint": "/v3/option/at_time/quote",
            "params": {
                "symbol": "ABC",
                "expiration": expiration,
                "strike": "100",
                "right": "call",
                "start_date": day,
                "end_date": day,
                "time_of_day": time_et,
            },
            "expected_role": [role],
            "source_query_fingerprint": f"{index:064x}",
            "member_case_ids": [f"case-{year}-{role}"],
        },
    }


def _plan() -> dict:
    anchors = []
    index = 1
    for year in range(2021, 2026):
        anchors.append(_anchor(index, year, "ENTRY", "09:35:00.000"))
        index += 1
        anchors.append(_anchor(index, year, "EXIT", "10:00:00.000"))
        index += 1
    body = {
        "contract": PLAN_CONTRACT,
        "status": "PLANNED_ZERO_PROVIDER_READS",
        "intraday_clock_fingerprint": "1" * 64,
        "provider_candidate": PROVIDER_CANDIDATE,
        "target_scope": {
            "date_min": "2021-01-06",
            "date_max": "2025-01-06",
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
    expiration: str,
    strike: str,
    right: str,
    date_et: str,
    time_of_day_et: str,
    empty: bool = False,
) -> ThetaDataResponse:
    if empty:
        rows = ()
        raw = b"[]"
    else:
        day = (
            f"{date_et[:4]}-{date_et[4:6]}-{date_et[6:8]}"
            if len(date_et) == 8 and date_et.isdigit()
            else date_et
        )
        exp = (
            f"{expiration[:4]}-{expiration[4:6]}-{expiration[6:8]}"
            if len(expiration) == 8 and expiration.isdigit()
            else expiration
        )
        row = {
            "symbol": symbol,
            "expiration": exp,
            "strike": float(strike),
            "right": right,
            "timestamp": f"{day}T{time_of_day_et}",
            "bid_size": 10,
            "bid_exchange": 1,
            "bid": 1.0,
            "bid_condition": 0,
            "ask_size": 12,
            "ask_exchange": 2,
            "ask": 1.1,
            "ask_condition": 0,
        }
        rows = (row,)
        raw = json.dumps([row], sort_keys=True).encode("utf-8")
    return ThetaDataResponse(
        http_status=200,
        rows=rows,
        headers={},
        response_bytes=len(raw),
        elapsed_seconds=0.01,
        raw_body=raw,
    )


def test_qualification_proves_all_year_roles_and_repeatability(tmp_path):
    calls = []

    def reader(**kwargs):
        calls.append(dict(kwargs))
        return _response(**kwargs)

    report = run_thetadata_intraday_option_qualification_v1(
        _Settings(tmp_path),
        _plan(),
        workers=2,
        reader=reader,
    )

    assert report["status"] == "QUALIFIED_FOR_BOUNDED_INTRADAY_OPTION_ACQUISITION"
    assert report["full_acquisition_source_qualified"] is True
    assert report["oldest_2021_entry_and_exit_proven"] is True
    assert report["full_2021_2025_entry_exit_coverage_proven"] is True
    assert report["repeatability_probe"]["deterministic_normalized_row"] is True
    assert report["provider_requests"] == 11
    assert len(calls) == 11
    assert Path(report["report_path"]).is_file()
    assert all(
        values["ENTRY"] == 1 and values["EXIT"] == 1
        for values in report["usable_year_role_coverage"].values()
    )


def test_empty_2021_exit_blocks_full_acquisition_without_inventing_error(tmp_path):
    def reader(**kwargs):
        empty = str(kwargs["date_et"]).startswith("2021") and kwargs["time_of_day_et"] == "10:00:00.000"
        return _response(**kwargs, empty=empty)

    report = run_thetadata_intraday_option_qualification_v1(
        _Settings(tmp_path),
        _plan(),
        workers=2,
        reader=reader,
    )

    assert report["status"] == "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
    assert report["full_acquisition_source_qualified"] is False
    assert report["oldest_2021_entry_and_exit_proven"] is False
    assert report["usable_year_role_coverage"]["2021"]["ENTRY"] == 1
    assert report["usable_year_role_coverage"]["2021"]["EXIT"] == 0
    assert report["status_counts"]["EXPLICIT_NO_QUOTE_AT_TIME"] == 1
    assert report["hard_validation_or_transport_errors"] == 0
