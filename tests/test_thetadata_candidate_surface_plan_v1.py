from __future__ import annotations

import copy

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
import packages.data.thetadata_candidate_surface_plan_v1 as module
from packages.simulation.multiyear_option_decision_spot_v1 import (
    CONTRACT as DECISION_SPOT_CONTRACT,
)


def _surface(case_id: str, year: int, symbol: str = "ABC") -> dict:
    payload = {
        "request_type": "OPTION_CALL_CANDIDATE_SURFACE_AT_DECISION_CLOCK",
        "symbol": symbol,
        "date_et": f"{year}-01-06",
        "time_of_day_et": "09:35:00.000",
        "right": "call",
        "max_dte_calendar_days": 75,
        "expiration_policy": "ALL_EXPIRATIONS_WITHIN_PROVIDER_MAX_DTE",
        "strike_policy": "CANDIDATE_SURFACE_NOT_PRESELECTED_STRIKE",
    }
    return {
        **payload,
        "query_fingerprint": _fingerprint(payload),
        "member_case_ids": [case_id],
        "member_case_count": 1,
    }


def _report() -> dict:
    surfaces = [_surface(f"case-{year}", year) for year in range(2021, 2026)]
    rows = [
        {
            "case_id": f"case-{year}",
            "year": str(year),
            "status": "CAUSAL_0935_DECISION_SPOT_READY",
        }
        for year in range(2021, 2026)
    ]
    body = {
        "contract": DECISION_SPOT_CONTRACT,
        "clock_ready_case_denominator": 5,
        "decision_spot_ready_cases": 5,
        "decision_spot_missing_cases": 0,
        "candidate_entry_surface_demand": {
            "case_members": 5,
            "unique_underlying_date_clock_queries": 5,
            "right": "call",
            "max_dte_calendar_days": 75,
            "single_strike_preselection": False,
            "provider_specific_request_shape_authorized": False,
            "demands": surfaces,
        },
        "provider_requests": 0,
        "option_prices_read": 0,
        "option_outcomes_read": 0,
        "historical_fill_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "rows": rows,
    }
    body["decision_spot_fingerprint"] = _fingerprint(body)
    return body


def _small(monkeypatch) -> None:
    monkeypatch.setattr(module, "EXPECTED_CLOCK_READY", 5)
    monkeypatch.setattr(module, "EXPECTED_DECISION_READY", 5)
    monkeypatch.setattr(module, "EXPECTED_DECISION_MISSING", 0)
    monkeypatch.setattr(module, "EXPECTED_UNIQUE_SURFACES", 5)


def _resign(report: dict) -> dict:
    value = copy.deepcopy(report)
    value.pop("decision_spot_fingerprint", None)
    value["decision_spot_fingerprint"] = _fingerprint(value)
    return value


def test_plan_maps_each_surface_to_one_wildcard_provider_request(monkeypatch):
    _small(monkeypatch)
    result = module.build_thetadata_candidate_surface_source_plan(_report())

    assert result["provider_requests"] == 0
    assert result["target_scope"]["unique_surface_requests"] == 5
    assert result["provider_request_contract"]["requests_if_fully_acquired"] == 5
    assert result["provider_request_contract"]["expiration"] == "*"
    assert result["provider_request_contract"]["strike"] == "*"
    assert result["provider_request_contract"]["strike_range"] is None
    assert result["target_scope"]["by_year"] == {
        "2021": 1,
        "2022": 1,
        "2023": 1,
        "2024": 1,
        "2025": 1,
    }
    assert result["qualification"]["anchor_query_count"] == 5
    assert all(
        anchor["query"]["params"]["max_dte"] == 75
        for anchor in result["qualification"]["anchors"]
    )


def test_plan_keeps_contract_selection_downstream(monkeypatch):
    _small(monkeypatch)
    result = module.build_thetadata_candidate_surface_source_plan(_report())

    downstream = result["downstream_contract_selection"]
    assert downstream["single_contract_selected_here"] is False
    assert downstream["phase13_eligible_dte_window_days"] == [14, 45]
    assert downstream["phase13_abs_delta_window"] == [0.35, 0.65]
    assert downstream["open_interest_source_required_separately"] is True
    assert downstream["exact_exit_quote_deferred_until_entry_contract_selected"] is True


def test_non_0935_surface_fails_closed(monkeypatch):
    _small(monkeypatch)
    report = _report()
    item = report["candidate_entry_surface_demand"]["demands"][0]
    item["time_of_day_et"] = "09:36:00.000"
    payload = {
        key: item[key]
        for key in (
            "request_type",
            "symbol",
            "date_et",
            "time_of_day_et",
            "right",
            "max_dte_calendar_days",
            "expiration_policy",
            "strike_policy",
        )
    }
    item["query_fingerprint"] = _fingerprint(payload)
    report = _resign(report)

    with pytest.raises(
        module.ThetaDataCandidateSurfacePlanError,
        match="no longer 09:35",
    ):
        module.build_thetadata_candidate_surface_source_plan(report)


def test_surface_query_fingerprint_drift_fails_closed(monkeypatch):
    _small(monkeypatch)
    report = _report()
    report["candidate_entry_surface_demand"]["demands"][0][
        "query_fingerprint"
    ] = "0" * 64
    report = _resign(report)

    with pytest.raises(
        module.ThetaDataCandidateSurfacePlanError,
        match="query fingerprint changed",
    ):
        module.build_thetadata_candidate_surface_source_plan(report)
