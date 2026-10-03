from __future__ import annotations

import json
from pathlib import Path

import packages.data.thetadata_candidate_surface_cache_v1 as module
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as PLAN_CONTRACT,
    PROVIDER_CANDIDATE,
)
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    CONTRACT as QUALIFICATION_CONTRACT,
)
from packages.providers.thetadata.client import ThetaDataResponse


class _Settings:
    def __init__(self, root: Path) -> None:
        self.root = root

    def assert_external_storage_binding(self, category: str) -> None:
        assert category == "options"

    def resolved_path(self, relative: str) -> Path:
        return self.root / relative


def _query(index: int, year: int) -> dict:
    return {
        "endpoint": "/v3/option/at_time/quote",
        "params": {
            "symbol": f"A{index}",
            "expiration": "*",
            "strike": "*",
            "right": "call",
            "start_date": f"{year}0106",
            "end_date": f"{year}0106",
            "time_of_day": "09:35:00.000",
            "max_dte": 75,
            "strike_range": None,
            "format": "json",
        },
        "source_query_fingerprint": f"{index:064x}",
        "member_case_ids": [f"case-{index}"],
        "member_case_count": 1,
    }


def _plan() -> dict:
    queries = [_query(i, year) for i, year in enumerate(range(2021, 2026), 1)]
    body = {
        "contract": PLAN_CONTRACT,
        "status": "PLANNED_ZERO_PROVIDER_READS",
        "decision_spot_fingerprint": "1" * 64,
        "provider_candidate": PROVIDER_CANDIDATE,
        "provider_request_contract": {
            "full_surface_queries": queries,
        },
        "provider_requests": 0,
        "historical_fill_authority": False,
        "strategy_evidence_authority": False,
    }
    body["plan_fingerprint"] = _fingerprint(body)
    return body


def _qualification(plan: dict) -> dict:
    body = {
        "contract": QUALIFICATION_CONTRACT,
        "plan_fingerprint": plan["plan_fingerprint"],
        "decision_spot_fingerprint": plan["decision_spot_fingerprint"],
        "provider_candidate": PROVIDER_CANDIDATE,
        "full_acquisition_source_qualified": True,
        "oldest_2021_surface_proven": True,
        "full_2021_2025_surface_coverage_proven": True,
        "hard_validation_or_transport_errors": 0,
        "repeatability_probe": {
            "deterministic_normalized_surface": True,
        },
        "historical_fill_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
    }
    body["qualification_fingerprint"] = _fingerprint(body)
    return body


def _response(**kwargs) -> ThetaDataResponse:
    date_et = str(kwargs["date_et"])
    day = f"{date_et[:4]}-{date_et[4:6]}-{date_et[6:8]}"
    year = int(date_et[:4])
    rows = [
        {
            "symbol": kwargs["symbol"],
            "expiration": f"{year}-02-21",
            "strike": 100.0,
            "right": "call",
            "timestamp": f"{day}T09:34:59.000",
            "bid_size": 10,
            "bid_exchange": 1,
            "bid": 1.0,
            "bid_condition": 0,
            "ask_size": 12,
            "ask_exchange": 2,
            "ask": 1.1,
            "ask_condition": 0,
        }
    ]
    raw = json.dumps(rows, sort_keys=True).encode("utf-8")
    return ThetaDataResponse(
        http_status=200,
        rows=tuple(rows),
        headers={},
        response_bytes=len(raw),
        elapsed_seconds=0.01,
        raw_body=raw,
    )


def _small(monkeypatch) -> None:
    monkeypatch.setattr(module, "EXPECTED_UNIQUE_SURFACES", 5)
    monkeypatch.setattr(
        module,
        "assert_category_acquisition_allowed",
        lambda *args, **kwargs: None,
    )


def test_preview_is_zero_network_and_reports_all_pending(tmp_path, monkeypatch):
    _small(monkeypatch)
    calls = []

    def reader(**kwargs):
        calls.append(kwargs)
        return _response(**kwargs)

    plan = _plan()
    report = module.run_thetadata_candidate_surface_cache_v1(
        _Settings(tmp_path),
        plan,
        _qualification(plan),
        max_new_requests=0,
        workers=4,
        authorize_provider_reads=False,
        reader=reader,
    )

    assert calls == []
    assert report["status"] == "PREVIEW_PENDING_SOURCE_REQUESTS"
    assert report["candidate_surface_requests"] == 5
    assert report["pending_after_run"] == 5
    assert report["new_provider_attempts"] == 0


def test_bounded_live_run_persists_and_resume_reuses_cache(tmp_path, monkeypatch):
    _small(monkeypatch)
    calls = []

    def reader(**kwargs):
        calls.append(kwargs)
        return _response(**kwargs)

    plan = _plan()
    qualification = _qualification(plan)
    settings = _Settings(tmp_path)

    first = module.run_thetadata_candidate_surface_cache_v1(
        settings,
        plan,
        qualification,
        max_new_requests=2,
        workers=2,
        authorize_provider_reads=True,
        reader=reader,
    )
    assert first["status"] == "PARTIAL_REQUEST_CAP"
    assert first["new_provider_attempts"] == 2
    assert first["new_complete"] == 2
    assert first["pending_after_run"] == 3
    assert len(calls) == 2

    second = module.run_thetadata_candidate_surface_cache_v1(
        settings,
        plan,
        qualification,
        max_new_requests=0,
        workers=4,
        authorize_provider_reads=False,
        reader=reader,
    )
    assert second["verified_cached_complete"] == 2
    assert second["pending_after_run"] == 3
    assert len(calls) == 2


def test_positive_request_cap_requires_explicit_authorization(tmp_path, monkeypatch):
    _small(monkeypatch)
    plan = _plan()

    try:
        module.run_thetadata_candidate_surface_cache_v1(
            _Settings(tmp_path),
            plan,
            _qualification(plan),
            max_new_requests=1,
            workers=1,
            authorize_provider_reads=False,
        )
    except module.ThetaDataCandidateSurfaceCacheError as exc:
        assert "explicit authorization" in str(exc)
    else:
        raise AssertionError("positive provider request cap must require authorization")


def test_failed_request_leaves_intent_and_lock_for_manual_review(tmp_path, monkeypatch):
    _small(monkeypatch)
    plan = _plan()
    qualification = _qualification(plan)

    def failing_reader(**kwargs):
        from packages.providers.thetadata.client import ThetaDataError
        raise ThetaDataError("transport uncertain")

    try:
        module.run_thetadata_candidate_surface_cache_v1(
            _Settings(tmp_path),
            plan,
            qualification,
            max_new_requests=1,
            workers=1,
            authorize_provider_reads=True,
            reader=failing_reader,
        )
    except module.ThetaDataCandidateSurfaceCacheError:
        pass
    else:
        raise AssertionError("uncertain provider attempt must stop")

    lock = module._lock_path(_Settings(tmp_path), plan["plan_fingerprint"])
    assert lock.is_file()
    body, receipt, intent = module._cache_paths(
        _Settings(tmp_path),
        plan_fingerprint=plan["plan_fingerprint"],
        source_query_fingerprint=plan["provider_request_contract"][
            "full_surface_queries"
        ][0]["source_query_fingerprint"],
    )
    assert intent.is_file()
    assert not body.exists()
    assert not receipt.exists()
