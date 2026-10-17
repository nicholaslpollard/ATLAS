from __future__ import annotations

from copy import deepcopy

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data import options_multi_underlying_source_inventory_v1 as mod


def signed_small_multi_underlying_plan(monkeypatch):
    monkeypatch.setattr(mod, "EXPECTED_UNIQUE_SURFACES", 3)
    monkeypatch.setattr(mod, "EXPECTED_DECISION_READY", 4)
    monkeypatch.setattr(mod, "EXPECTED_CLOCK_READY", 5)
    monkeypatch.setattr(mod, "EXPECTED_DECISION_MISSING", 1)
    entries = [
        ("AAPL", "20210104", ["a1", "a2"]),
        ("AAPL", "20210105", ["a3"]),
        ("MSFT", "20211210", ["a4"]),
    ]
    queries = []
    for i, (symbol, day, members) in enumerate(entries):
        queries.append({
            "endpoint": "/v3/option/at_time/quote",
            "params": {
                "symbol": symbol, "expiration": "*", "strike": "*",
                "right": "call", "start_date": day, "end_date": day,
                "time_of_day": "09:35:00.000", "max_dte": 75,
                "strike_range": None, "format": "json",
            },
            "source_query_fingerprint": f"{i+1:064x}",
            "member_case_ids": members,
            "member_case_count": len(members),
        })
    plan = {
        "contract": mod.SOURCE_CONTRACT,
        "status": "PLANNED_ZERO_PROVIDER_READS",
        "provider_candidate": dict(mod.PROVIDER_CANDIDATE),
        "decision_spot_fingerprint": "a" * 64,
        "target_scope": {
            "clock_ready_case_denominator": 5, "decision_spot_ready_cases": 4,
            "decision_spot_missing_cases": 1, "candidate_surface_case_members": 4,
            "unique_surface_requests": 3, "unique_underlyings": 2,
            "date_min": "2021-01-04", "date_max": "2021-12-10",
            "by_year": {"2021": 3}, "decision_clock_et": "09:35:00.000",
            "right": "call", "max_dte_calendar_days": 75,
        },
        "provider_request_contract": {
            "requests_if_fully_acquired": 3,
            "one_request_per_underlying_date_decision_clock": True,
            "expiration": "*", "strike": "*", "right": "call",
            "max_dte": 75, "strike_range": None, "minute_boundary_clock": True,
            "full_surface_queries": queries,
        },
        "qualification": {"full_acquisition_authorized": False},
        "provider_requests": 0, "provider_writes": 0,
        "option_prices_read": 0, "option_outcomes_read": 0,
        "historical_fill_authority": False,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False, "paper_authority": False,
        "live_authority": False,
    }
    return sign(plan)


def sign(plan):
    plan.pop("plan_fingerprint", None)
    plan["plan_fingerprint"] = _fingerprint(plan)
    return plan


def test_two_symbols_preserved_without_providing_spy_only_source_authority(monkeypatch):
    plan = signed_small_multi_underlying_plan(monkeypatch)
    summary = mod.build_multi_underlying_source_demand_inventory(plan)
    src = summary["source_inventory"]
    assert src["unique_underlyings"] == 2
    assert src["underlyings"] == [
        {"symbol": "AAPL", "planned_call_surface_requests": 2},
        {"symbol": "MSFT", "planned_call_surface_requests": 1},
    ]
    assert src["underlying_case_members"] == 4
    assert src["unique_symbol_day_0935_call_surfaces"] == 3
    assert summary["spy_only_both_rights_1000_pilot_is_a_separate_frozen_trial"] is True
    assert summary["historical_call_quote_surfaces_accepted"] is False
    assert summary["historical_put_quote_surfaces_accepted"] is False
    assert summary["cross_symbol_issuer_actions_qualified"] is False
    assert summary["historical_strategy_replay_authorized"] is False
    assert summary["source_reads"]["provider_gets"] == 0
    assert summary["report_fingerprint"] == _fingerprint({
        k: v for k, v in summary.items() if k != "report_fingerprint"
    })


@pytest.mark.parametrize("change", [
    "bad_signature", "one_symbol", "more_provider_gets", "claim_historical_fills",
    "duplicate_symbol_day", "duplicate_request_hash", "zero_call_right",
    "changed_clock", "future_day", "malformed_day", "missing_member",
    "bad_target_years", "extra_query", "pretend_acquired",
])
def test_signature_source_and_authority_drift_blocks(monkeypatch, change):
    plan = signed_small_multi_underlying_plan(monkeypatch)
    q = plan["provider_request_contract"]["full_surface_queries"]
    if change == "bad_signature":
        plan["target_scope"]["unique_underlyings"] = 3
    elif change == "one_symbol":
        q[2]["params"]["symbol"] = "AAPL"
    elif change == "more_provider_gets":
        plan["provider_requests"] = 1
    elif change == "claim_historical_fills":
        plan["historical_fill_authority"] = True
    elif change == "duplicate_symbol_day":
        q[2]["params"]["symbol"] = "AAPL"
        q[2]["params"]["start_date"] = "20210104"
        q[2]["params"]["end_date"] = "20210104"
    elif change == "duplicate_request_hash":
        q[2]["source_query_fingerprint"] = q[1]["source_query_fingerprint"]
    elif change == "zero_call_right":
        q[0]["params"]["right"] = "put"
    elif change == "changed_clock":
        q[0]["params"]["time_of_day"] = "10:00:00.000"
    elif change == "future_day":
        q[0]["params"]["start_date"] = "20260104"
        q[0]["params"]["end_date"] = "20260104"
    elif change == "malformed_day":
        q[0]["params"]["start_date"] = "20210230"
        q[0]["params"]["end_date"] = "20210230"
    elif change == "missing_member":
        q[0]["member_case_ids"] = ["a1"]
    elif change == "bad_target_years":
        plan["target_scope"]["by_year"]["2025"] = 1
    elif change == "extra_query":
        q.append(deepcopy(q[-1]))
    elif change == "pretend_acquired":
        plan["qualification"]["full_acquisition_authorized"] = True
    if change != "bad_signature":
        sign(plan)
    with pytest.raises(mod.MultiUnderlyingSourceDemandError):
        mod.build_multi_underlying_source_demand_inventory(plan)
