from __future__ import annotations

"""Inspect existing multi-underlying option CALL source demand; zero market IO.

The accepted historical 09:35 candidate demand is DIFFERENT from the
single-SPY 10:00 both-rights straddle pilot. Neither is a list of historical
trade opportunities, source-qualified option prices, or complete option symbols.
"""

from collections import Counter
from datetime import date
import re
from typing import Any

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as SOURCE_CONTRACT,
    EXPECTED_UNIQUE_SURFACES, EXPECTED_DECISION_READY,
    EXPECTED_CLOCK_READY, EXPECTED_DECISION_MISSING,
    EXPECTED_MAX_DTE, PROVIDER_CANDIDATE,
)

CONTRACT = "atlas-options-multi-underlying-source-demand-inventory-v1"
MAX_PLAN_QUERIES = 10000
DATE_YYYYMMDD = re.compile(r"20(?:21|22|23|24|25)[01][0-9][0-3][0-9]")
HASH_64 = re.compile(r"[0-9a-f]{64}")


class MultiUnderlyingSourceDemandError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MultiUnderlyingSourceDemandError(message)


def _check_plan_signature(plan: dict[str, Any]) -> None:
    _require(isinstance(plan, dict), "candidate-source plan must be object")
    unsigned = dict(plan)
    fp = unsigned.pop("plan_fingerprint", None)
    _require(isinstance(fp, str) and bool(HASH_64.fullmatch(fp)) and
             _fingerprint(unsigned) == fp, "original source plan hash changed")


def build_multi_underlying_source_demand_inventory(plan: dict[str, Any]) -> dict[str, Any]:
    """One bounded signed manifest; every request shape/identity crosschecked.

    This is metadata/provenance review ONLY. In particular, quote coverage and
    CALL+PUT straddle readiness remain UNKNOWN; no provider requests or
    historical fills are authorized.
    """
    _check_plan_signature(plan)
    scope = plan.get("target_scope")
    provider = plan.get("provider_candidate")
    query_contract = plan.get("provider_request_contract")
    qualification = plan.get("qualification")
    _require(
        plan.get("contract") == SOURCE_CONTRACT
        and plan.get("status") == "PLANNED_ZERO_PROVIDER_READS"
        and isinstance(scope, dict) and isinstance(provider, dict)
        and isinstance(query_contract, dict) and isinstance(qualification, dict)
        and plan.get("provider_requests") == 0
        and plan.get("provider_writes") == 0
        and plan.get("option_prices_read") == 0
        and plan.get("option_outcomes_read") == 0
        and plan.get("historical_fill_authority") is False
        and plan.get("historical_account_pnl_authority") is False
        and plan.get("strategy_evidence_authority") is False
        and plan.get("paper_authority") is False
        and plan.get("live_authority") is False
        and provider == PROVIDER_CANDIDATE
        and qualification.get("full_acquisition_authorized") is False,
        "frozen multi-symbol source plan/authority changed",
    )
    _require(
        scope.get("clock_ready_case_denominator") == EXPECTED_CLOCK_READY
        and scope.get("decision_spot_ready_cases") == EXPECTED_DECISION_READY
        and scope.get("decision_spot_missing_cases") == EXPECTED_DECISION_MISSING
        and scope.get("candidate_surface_case_members") == EXPECTED_DECISION_READY
        and scope.get("unique_surface_requests") == EXPECTED_UNIQUE_SURFACES
        and type(scope.get("unique_underlyings")) is int
        and 1 < scope["unique_underlyings"] <= EXPECTED_UNIQUE_SURFACES
        and scope.get("right") == "call"
        and scope.get("decision_clock_et") == "09:35:00.000"
        and scope.get("max_dte_calendar_days") == EXPECTED_MAX_DTE
        and query_contract.get("requests_if_fully_acquired") == EXPECTED_UNIQUE_SURFACES
        and query_contract.get("one_request_per_underlying_date_decision_clock") is True
        and query_contract.get("expiration") == "*"
        and query_contract.get("strike") == "*"
        and query_contract.get("right") == "call"
        and query_contract.get("max_dte") == EXPECTED_MAX_DTE
        and query_contract.get("strike_range") is None
        and query_contract.get("minute_boundary_clock") is True,
        "frozen multi-symbol scope/shape changed",
    )
    requests = query_contract.get("full_surface_queries")
    _require(isinstance(requests, list) and
             len(requests) == EXPECTED_UNIQUE_SURFACES <= MAX_PLAN_QUERIES,
             "source demand not the fixed 9455-query inventory")
    by_symbol: Counter[str] = Counter()
    by_year: Counter[str] = Counter()
    member_total = 0
    unique_requests = set()
    unique_source_ids = set()
    unique_date_symbol = set()
    for item in requests:
        _require(isinstance(item, dict) and
                 item.get("endpoint") == "/v3/option/at_time/quote"
                 and isinstance(item.get("params"), dict)
                 and type(item.get("member_case_count")) is int
                 and 1 <= item["member_case_count"] <= EXPECTED_DECISION_READY
                 and isinstance(item.get("member_case_ids"), list)
                 and len(item["member_case_ids"]) == item["member_case_count"]
                 and isinstance(item.get("source_query_fingerprint"), str)
                 and bool(HASH_64.fullmatch(item["source_query_fingerprint"])),
                 "one candidate query identity/lineage invalid")
        p = item["params"]
        _require(set(p) == {
                    "symbol", "expiration", "strike", "right", "start_date",
                    "end_date", "time_of_day", "max_dte", "strike_range", "format"}
                 and isinstance(p["symbol"], str)
                 and 1 <= len(p["symbol"]) <= 24
                 and p["symbol"] == p["symbol"].strip()
                 and all(ch.isalnum() or ch in ".-/" for ch in p["symbol"])
                 and p["expiration"] == "*" and p["strike"] == "*"
                 and p["right"] == "call" and p["max_dte"] == EXPECTED_MAX_DTE
                 and p["time_of_day"] == "09:35:00.000"
                 and p["start_date"] == p["end_date"]
                 and isinstance(p["start_date"], str)
                 and bool(DATE_YYYYMMDD.fullmatch(p["start_date"]))
                 and p["strike_range"] is None and p["format"] == "json",
                 "one candidate provider request escaped frozen source universe")
        try:
            day = date(int(p["start_date"][:4]), int(p["start_date"][4:6]),
                       int(p["start_date"][6:8]))
        except ValueError as exc:
            raise MultiUnderlyingSourceDemandError("invalid source decision day") from exc
        _require("2021-01-01" <= day.isoformat() <= "2025-12-31",
                 "requested underlying/day outside fixed 2021-2025 scope")
        identity = (p["symbol"], day.isoformat(), p["time_of_day"])
        _require(identity not in unique_date_symbol and
                 item["source_query_fingerprint"] not in unique_source_ids and
                 len(set(item["member_case_ids"])) == item["member_case_count"],
                 "duplicate original candidate identity or member case")
        unique_date_symbol.add(identity)
        unique_source_ids.add(item["source_query_fingerprint"])
        unique_requests.add((identity, item["source_query_fingerprint"]))
        by_symbol[p["symbol"]] += 1
        by_year[day.isoformat()[:4]] += 1
        member_total += item["member_case_count"]
    _require(
        len(by_symbol) == scope["unique_underlyings"]
        and member_total == EXPECTED_DECISION_READY
        and len(unique_requests) == EXPECTED_UNIQUE_SURFACES
        and scope.get("by_year") == dict(sorted(by_year.items()))
        and scope.get("date_min") == min(x[1] for x in unique_date_symbol)
        and scope.get("date_max") == max(x[1] for x in unique_date_symbol),
        "underlying/date count differs from previously frozen planner",
    )
    report = {
        "contract": CONTRACT,
        "status": "HISTORICAL_MULTI_UNDERLYING_OPTION_DEMAND_INVENTORIED_NO_QUOTES",
        "upstream_plan_fingerprint": plan["plan_fingerprint"],
        "upstream_decision_spot_fingerprint": plan.get("decision_spot_fingerprint"),
        "source_inventory": {
            "unique_underlyings": len(by_symbol),
            "underlyings": [
                {"symbol": symbol, "planned_call_surface_requests": count}
                for symbol, count in sorted(by_symbol.items())
            ],
            "unique_symbol_day_0935_call_surfaces": len(unique_requests),
            "underlying_case_members": member_total,
            "date_min": scope["date_min"], "date_max": scope["date_max"],
            "requests_by_year": dict(sorted(by_year.items())),
            "right_planned_here": "CALL_ONLY",
            "request_clock_et": "09:35",
            "expiration_scope": "ALL_WITHIN_75_CALENDAR_DTE",
            "strikes_preselected": False,
        },
        "spy_only_both_rights_1000_pilot_is_a_separate_frozen_trial": True,
        "all_available_equity_or_etf_option_symbols_acquired": False,
        "cross_symbol_issuer_actions_qualified": False,
        "underlying_listing_and_renaming_asof_qualified": False,
        "option_contract_listing_and_deliverable_pit_qualified": False,
        "historical_call_quote_surfaces_accepted": False,
        "historical_put_quote_surfaces_accepted": False,
        "historical_oi_and_model_inputs_accepted": False,
        "historical_option_fills_or_pnl_qualified": False,
        "historical_strategy_replay_authorized": False,
        "source_reads": {"one_signed_plan_json": 1, "provider_gets": 0,
                         "broker_gets": 0, "source_price_scans": 0,
                         "option_source_scans": 0, "outcome_scans": 0},
        "authority": {"paper": False, "live": False, "strategy_promotion": False},
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
