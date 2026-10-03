from __future__ import annotations

import copy

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
import packages.data.thetadata_intraday_option_plan_v1 as module
from packages.simulation.multiyear_intraday_stock_exit_clock_v1 import (
    CONTRACT as INTRADAY_CLOCK_CONTRACT,
)


def _demand(
    *,
    case_id: str,
    year: int,
    role: str,
    time_et: str,
    strike: str = "100",
) -> dict:
    day = f"{year}-01-06"
    expiration = f"{year}-02-21"
    symbol = "ABC"
    option_symbol = f"ABC{str(year)[2:]}0221C00100000"
    payload = {
        "request_type": "AT_TIME_NBBO_OPTION_QUOTE",
        "option_symbol": option_symbol,
        "symbol": symbol,
        "expiration": expiration,
        "strike": strike,
        "right": "call",
        "date_et": day,
        "time_of_day_et": time_et,
    }
    return {
        **payload,
        "query_fingerprint": _fingerprint(payload),
        "roles": [role],
        "member_case_ids": [case_id],
        "member_case_count": 1,
    }


def _report() -> dict:
    demands = []
    rows = []
    for year in range(2021, 2026):
        case_id = f"case-{year}"
        demands.append(
            _demand(
                case_id=case_id,
                year=year,
                role="ENTRY",
                time_et="09:35:00.000",
            )
        )
        demands.append(
            _demand(
                case_id=case_id,
                year=year,
                role="EXIT",
                time_et="13:00:00.000" if year == 2025 else "10:00:00.000",
            )
        )
        rows.append({"case_id": case_id})
    body = {
        "contract": INTRADAY_CLOCK_CONTRACT,
        "status": "COMPLETE_INTRADAY_STOCK_EXIT_CLOCK_AND_OPTION_QUOTE_DEMAND_PLAN",
        "pre2026_call_policy_stock_exit_cases": 5,
        "clock_ready_cases": 5,
        "option_quote_demand": {
            "entry_case_members": 5,
            "exit_case_members": 5,
            "unique_at_time_nbbo_queries": len(demands),
            "selection_uses_option_price_or_future_liquidity": False,
            "provider_requests_performed": 0,
            "demands": demands,
        },
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "rows": rows,
    }
    body["intraday_clock_fingerprint"] = _fingerprint(body)
    return body


def _small_expected(monkeypatch) -> None:
    monkeypatch.setattr(module, "EXPECTED_CASES", 5)
    monkeypatch.setattr(module, "EXPECTED_CLOCK_READY", 5)
    monkeypatch.setattr(module, "EXPECTED_EXACT_DEMANDS", 10)


def _resign(report: dict) -> dict:
    report = copy.deepcopy(report)
    report.pop("intraday_clock_fingerprint", None)
    report["intraday_clock_fingerprint"] = _fingerprint(report)
    return report


def test_source_plan_is_zero_provider_and_spans_all_years(monkeypatch):
    _small_expected(monkeypatch)
    result = module.build_thetadata_intraday_option_source_plan(_report())

    assert result["provider_requests"] == 0
    assert result["provider_writes"] == 0
    assert result["qualification"]["full_acquisition_authorized"] is False
    assert result["target_scope"]["date_min"] == "2021-01-06"
    assert result["target_scope"]["date_max"] == "2025-01-06"
    assert result["target_scope"]["by_year"] == {
        "2021": 2,
        "2022": 2,
        "2023": 2,
        "2024": 2,
        "2025": 2,
    }
    assert result["target_scope"]["role_memberships"] == {
        "ENTRY": 5,
        "EXIT": 5,
    }
    assert result["provider_candidate"]["target_subscription"] == "Options Standard"
    assert result["provider_candidate"]["documented_concurrent_requests_observed"] == 4

    reasons = {
        reason
        for anchor in result["qualification"]["anchors"]
        for reason in anchor["qualification_reasons"]
    }
    assert "YEAR_2021_ENTRY_FIRST" in reasons
    assert "YEAR_2025_EXIT_LAST" in reasons
    assert "EARLY_CLOSE_1300_ET" in reasons


def test_same_contract_day_is_counted_once_for_history_shape(monkeypatch):
    _small_expected(monkeypatch)
    result = module.build_thetadata_intraday_option_source_plan(_report())

    shape = result["request_shape_analysis"]
    assert shape["exact_at_time_request_count"] == 10
    assert shape["unique_contract_day_groups"] == 5
    assert shape["contract_day_group_size"]["groups_with_multiple_exact_clocks"] == 5
    assert shape["contract_day_group_size"]["min"] == 2
    assert shape["contract_day_group_size"]["max"] == 2
    assert shape["one_minute_history_min_to_max_row_upper_bound"] > 10


def test_subminute_demand_fails_closed(monkeypatch):
    _small_expected(monkeypatch)
    report = _report()
    item = report["option_quote_demand"]["demands"][0]
    item["time_of_day_et"] = "09:35:10.000"
    payload = {
        key: item[key]
        for key in (
            "request_type",
            "option_symbol",
            "symbol",
            "expiration",
            "strike",
            "right",
            "date_et",
            "time_of_day_et",
        )
    }
    item["query_fingerprint"] = _fingerprint(payload)
    report = _resign(report)

    with pytest.raises(module.ThetaDataIntradayOptionPlanError, match="whole minute"):
        module.build_thetadata_intraday_option_source_plan(report)


def test_query_fingerprint_drift_fails_closed(monkeypatch):
    _small_expected(monkeypatch)
    report = _report()
    report["option_quote_demand"]["demands"][0]["query_fingerprint"] = "0" * 64
    report = _resign(report)

    with pytest.raises(
        module.ThetaDataIntradayOptionPlanError,
        match="query fingerprint changed",
    ):
        module.build_thetadata_intraday_option_source_plan(report)
