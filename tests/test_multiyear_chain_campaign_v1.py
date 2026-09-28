from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data import multiyear_chain_campaign_v1 as campaign
from packages.data.marketdata_candidate_chain_cache_v1 import _paths, _valid_receipt
from packages.providers.marketdata_app.client import MarketDataResponse


def _fixture() -> tuple[dict, dict]:
    # Complete accepted population, synthetic identities; no workstation corpus.
    annual = [
        ("2021", 1342, 0, 0),
        ("2022", 3, 0, 0),
        ("2023", 1473, 36, 0),
        ("2024", 1322, 34, 1),
        ("2025", 3434, 1, 0),
    ]
    tickets, overlap = [], []
    n = 0
    for year, missing, reused, no_data in annual:
        for status, count in (
            (campaign.MISSING, missing), (campaign.REUSED, reused),
            (campaign.NO_DATA, no_data),
        ):
            for i in range(count):
                n += 1
                identity = hashlib.sha256(f"{year}:{n}".encode()).hexdigest()
                ticker = f"TEST{n}"
                snap = f"{year}-10-01"
                expiry = f"{year}-11-19"
                members = [hashlib.sha256(f"case{n}".encode()).hexdigest()]
                params = {
                    "date": snap, "expiration": expiry, "strike": "10.00-12.00",
                }
                tickets.append({
                    "physical_request_identity": identity, "ticker": ticker,
                    "snapshot_date": snap, "expiration": expiry,
                    "endpoint": f"options/chain/{ticker}/", "params": params,
                    "member_case_ids": members, "request_sides": ["call", "put"],
                })
                overlap.append({
                    "physical_request_identity": identity,
                    "key": [ticker, snap, expiry], "case_ids": members,
                    "requested_strike_window": ["10.00", "12.00"],
                    "source_status": status,
                    "intersecting_orphan_attempt_ids": [],
                    "verified_existing_overlaps": [],
                })
    assert len(tickets) == 7646
    return {"requests": tickets}, {"rows": overlap}


def test_complete_frozen_population_balanced_years() -> None:
    demand, overlap = _fixture()
    result = campaign.freeze_execution_order(demand, overlap)
    assert result["missing_physical_sources"] == 7574
    assert result["preexisting_complete_physical_sources"] == 71
    assert result["preexisting_exact_no_data_physical_queries"] == 1
    assert result["original_case_denominator"] == 14902
    assert result["original_2022_exact_quote_histories_pointer_reused"] == 6398
    assert result["by_year_missing"] == {
        "2021": 1342, "2022": 3, "2023": 1473, "2024": 1322, "2025": 3434,
    }
    years = [r["params"]["date"][:4] for r in result["requests"]]
    assert years[:10] == ["2021", "2022", "2023", "2024", "2025"] * 2
    assert Counter(years) == Counter(result["by_year_missing"])


def test_drift_or_prior_unresolved_source_stops() -> None:
    demand, overlap = _fixture()
    overlap["rows"][0]["intersecting_orphan_attempt_ids"] = ["unknown"]
    with pytest.raises(campaign.MultiYearChainCampaignError, match="unresolved"):
        campaign.freeze_execution_order(demand, overlap)
    overlap["rows"][0]["intersecting_orphan_attempt_ids"] = []
    demand["requests"][0]["params"]["strike"] = "10.00-13.00"
    with pytest.raises(campaign.MultiYearChainCampaignError, match="identity"):
        campaign.freeze_execution_order(demand, overlap)


class _Settings:
    def __init__(self, root: Path):
        self.root = root

    def resolved_path(self, rel: str) -> Path:
        return self.root / rel


def _request(ticker: str = "OLMA") -> dict:
    return {
        "request_identity": hashlib.sha256(ticker.encode()).hexdigest(),
        "ticker": ticker, "endpoint": f"options/chain/{ticker}/",
        "params": {"date": "2021-09-27", "expiration": "2021-11-19",
                   "strike": "27.26-32.02"},
        "bounded_query": True,
    }


def _response(request: dict, status: int) -> MarketDataResponse:
    if status == 200:
        payload = {
            "s": "ok",
            "optionSymbol": [request["ticker"] + "211119C00030000"],
            "underlying": [request["ticker"]],
            "expiration": ["2021-11-19"], "side": ["call"], "strike": [30.0],
        }
    else:
        payload = {"s": "no_data"}
    raw = json.dumps(payload).encode()
    return MarketDataResponse(
        http_status=status, payload=payload, raw_body=raw,
        response_bytes=len(raw), elapsed_seconds=0.01,
        headers={"X-Api-Ratelimit-Remaining": "999",
                 "X-Api-Ratelimit-Consumed": "1" if status == 200 else "0"},
    )


def test_exact_body_is_reused_without_second_get(tmp_path: Path) -> None:
    settings = _Settings(tmp_path)
    request = _request()
    calls = []
    def read(endpoint, params):
        calls.append((endpoint, params))
        return _response(request, 200)
    first = campaign._capture(settings, request, "a" * 64, "run1", read)
    assert first["status"] == "NEW_COMPLETE"
    assert first["credits"] == 1
    assert _valid_receipt(_paths(settings, request["request_identity"]), request)
    second = campaign._capture(settings, request, "a" * 64, "run2", read)
    assert second["status"] == "REUSED_EXISTING_EXACT_SOURCE"
    assert len(calls) == 1


def test_exact_404_is_signed_not_retried(tmp_path: Path) -> None:
    settings = _Settings(tmp_path)
    request = _request("PLAB")
    calls = []
    def read(endpoint, params):
        calls.append((endpoint, params))
        return _response(request, 404)
    first = campaign._capture(settings, request, "a" * 64, "run1", read)
    assert first["status"] == "EXACT_QUERY_NO_DATA_PROVEN"
    assert first["credits"] == 0
    receipt = _valid_receipt(_paths(settings, request["request_identity"]), request)
    assert receipt["status"] == "VERIFIED_NO_DATA"
    assert campaign._capture(settings, request, "a" * 64, "run2", read)["status"] == "REUSED_EXISTING_EXACT_SOURCE"
    assert len(calls) == 1


def test_rolling_window_date_boundary() -> None:
    assert campaign._floor(date(2026, 9, 27)) == date(2021, 9, 27)
    assert campaign._floor(date(2026, 9, 28)) == date(2021, 9, 28)
    assert campaign._floor(date(2028, 2, 29)) == date(2023, 2, 28)


def test_explicit_486_floor_uses_smaller_waves_near_1500_credit_cap() -> None:
    wave = campaign._next_wave_size
    assert wave(
        outstanding=7574, workers=24, observed_credits=0,
        max_observed_credits=1500, remaining=None,
        min_remaining_credits=486,
    ) == (1, None)
    assert wave(
        outstanding=7573, workers=24, observed_credits=1,
        max_observed_credits=1500, remaining=1985,
        min_remaining_credits=486,
    ) == (24, None)
    assert wave(
        outstanding=6000, workers=24, observed_credits=1477,
        max_observed_credits=1500, remaining=509,
        min_remaining_credits=486,
    ) == (11, None)
    assert wave(
        outstanding=6000, workers=24, observed_credits=1497,
        max_observed_credits=1500, remaining=489,
        min_remaining_credits=486,
    ) == (1, None)
    assert wave(
        outstanding=6000, workers=24, observed_credits=1499,
        max_observed_credits=1500, remaining=487,
        min_remaining_credits=486,
    ) == (0, "PARTIAL_OBSERVED_CREDIT_BUDGET")
    assert wave(
        outstanding=6000, workers=24, observed_credits=1498,
        max_observed_credits=1500, remaining=486,
        min_remaining_credits=486,
    ) == (0, "PARTIAL_PROVIDER_CREDIT_FLOOR")


def test_credit_floor_not_permitted_to_exceed_provider_balance() -> None:
    assert campaign._next_wave_size(
        outstanding=20, workers=24, observed_credits=1,
        max_observed_credits=1500, remaining=480,
        min_remaining_credits=486,
    ) == (0, "PARTIAL_PROVIDER_CREDIT_FLOOR")
