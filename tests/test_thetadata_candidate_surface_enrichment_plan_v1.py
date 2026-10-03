from __future__ import annotations

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
import packages.data.thetadata_candidate_surface_enrichment_plan_v1 as module
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as SOURCE_PLAN_CONTRACT,
    PROVIDER_CANDIDATE,
)


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


def _source_plan() -> dict:
    queries = [_query(i, year) for i, year in enumerate(range(2021, 2026), 1)]
    body = {
        "contract": SOURCE_PLAN_CONTRACT,
        "status": "PLANNED_ZERO_PROVIDER_READS",
        "decision_spot_fingerprint": "1" * 64,
        "provider_candidate": PROVIDER_CANDIDATE,
        "provider_request_contract": {
            "expiration": "*",
            "strike": "*",
            "right": "call",
            "max_dte": 75,
            "strike_range": None,
            "full_surface_queries": queries,
        },
        "provider_requests": 0,
        "historical_fill_authority": False,
        "strategy_evidence_authority": False,
    }
    body["plan_fingerprint"] = _fingerprint(body)
    return body


def _small(monkeypatch) -> None:
    monkeypatch.setattr(module, "EXPECTED_UNIQUE_SURFACES", 5)


def test_enrichment_plan_adds_one_open_interest_surface_per_quote_surface(monkeypatch):
    _small(monkeypatch)
    result = module.build_thetadata_surface_enrichment_plan(_source_plan())

    oi = result["open_interest_stage"]
    assert result["provider_requests"] == 0
    assert oi["request_count"] == 5
    assert oi["by_year"] == {
        "2021": 1,
        "2022": 1,
        "2023": 1,
        "2024": 1,
        "2025": 1,
    }
    assert all(item["params"]["expiration"] == "*" for item in oi["requests"])
    assert all(item["params"]["strike"] == "*" for item in oi["requests"])
    assert all(item["params"]["right"] == "call" for item in oi["requests"])
    assert all(item["params"]["max_dte"] == 75 for item in oi["requests"])
    assert all(item["params"]["strike_range"] is None for item in oi["requests"])

    greeks = result["greeks_stage"]
    assert greeks["request_creation"] == "DYNAMIC_AFTER_QUOTE_AND_OPEN_INTEREST_JOIN"
    assert greeks["annual_dividend"] == "REQUIRED_PIT_INPUT_NO_SILENT_ZERO_DEFAULT"
    assert greeks["version"] == "1"
    assert greeks["binomial_steps"] == 101


def _quote(expiration: str, strike: float, bid: float, ask: float) -> dict:
    return {
        "symbol": "ABC",
        "expiration": expiration,
        "strike": strike,
        "right": "call",
        "bid": bid,
        "ask": ask,
    }


def _oi(expiration: str, strike: float, value: int) -> dict:
    return {
        "symbol": "ABC",
        "expiration": expiration,
        "strike": strike,
        "right": "call",
        "open_interest": value,
    }


def test_pre_greeks_filter_creates_only_surviving_expiration_requests():
    quotes = [
        _quote("2025-01-24", 100.0, 1.00, 1.10),
        _quote("2025-01-24", 105.0, 0.50, 0.80),
        _quote("2025-02-14", 100.0, 2.00, 2.10),
        _quote("2025-02-21", 100.0, 2.00, 2.10),
    ]
    oi = [
        _oi("2025-01-24", 100.0, 150),
        _oi("2025-01-24", 105.0, 200),
        _oi("2025-02-14", 100.0, 50),
        _oi("2025-02-21", 100.0, 500),
    ]

    result = module.build_binomial_greeks_demand(
        symbol="ABC",
        date_et="2025-01-06",
        quote_rows=quotes,
        open_interest_rows=oi,
        annual_dividend=1.25,
    )

    assert result["status"] == "GREEKS_DEMAND_READY"
    assert result["surviving_expirations"] == ["2025-01-24"]
    assert len(result["greeks_requests"]) == 1
    params = result["greeks_requests"][0]["params"]
    assert params["expiration"] == "20250124"
    assert params["start_time"] == "09:35:00.000"
    assert params["end_time"] == "09:35:00.000"
    assert params["annual_dividend"] == 1.25
    assert params["version"] == "1"
    assert params["binomial_steps"] == 101


def test_greeks_demand_blocks_if_dividend_context_unknown():
    quotes = [_quote("2025-01-24", 100.0, 1.00, 1.10)]
    oi = [_oi("2025-01-24", 100.0, 150)]

    result = module.build_binomial_greeks_demand(
        symbol="ABC",
        date_et="2025-01-06",
        quote_rows=quotes,
        open_interest_rows=oi,
        annual_dividend=None,
    )

    assert result["status"] == "BLOCKED_HISTORICAL_DIVIDEND_CONTEXT_REQUIRED"
    assert result["surviving_expirations"] == ["2025-01-24"]
    assert result["greeks_requests"] == []


def test_no_survivor_needs_no_dividend_context():
    quotes = [_quote("2025-01-24", 100.0, 1.00, 1.50)]
    oi = [_oi("2025-01-24", 100.0, 10)]

    result = module.build_binomial_greeks_demand(
        symbol="ABC",
        date_et="2025-01-06",
        quote_rows=quotes,
        open_interest_rows=oi,
        annual_dividend=None,
    )

    assert result["status"] == "NO_PRE_GREEKS_SURVIVORS"
    assert result["surviving_expirations"] == []
    assert result["greeks_requests"] == []


def test_open_interest_row_from_other_underlying_fails_closed():
    quotes = [_quote("2025-01-24", 100.0, 1.00, 1.10)]
    oi = [_oi("2025-01-24", 100.0, 150)]
    oi[0]["symbol"] = "XYZ"

    with pytest.raises(
        module.ThetaDataSurfaceEnrichmentPlanError,
        match="underlying changed",
    ):
        module.build_binomial_greeks_demand(
            symbol="ABC",
            date_et="2025-01-06",
            quote_rows=quotes,
            open_interest_rows=oi,
            annual_dividend=0.0,
        )
