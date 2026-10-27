from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from packages.data.options_native_spy_development_clock_coverage_v1 import (
    CONTRACT as STOCK_CONTRACT, frozen_clock_demand,
)
from packages.data.options_native_spy_physical_spot_exact_demand_v29 import (
    CONTRACT, MAX_CASES, _eligible_identity_pair, _spot_lookup,
    evaluate_spot_selected_exact_contract_demand,
)
from packages.data.options_native_original_pair_diagnostic_v26 import PairDiagnosticError
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_at_time_query, _exit_review_sessions,
)
from packages.strategies.options_native_pilot_v1_contract import SPECIFICATION_FINGERPRINT

ET = ZoneInfo("America/New_York")


def quote(day: date, right: str, expiry: date, strike: str = "100",
          bid="1.0", ask="1.1"):
    stamp = datetime.combine(
        day, datetime.strptime("10:00", "%H:%M").time(), ET
    ) - timedelta(seconds=10)
    return {
        "expiration": expiry.isoformat(), "strike": strike, "right": right,
        "timestamp": stamp.isoformat(), "bid": bid, "ask": ask,
        "bid_size": 1, "ask_size": 1,
    }


def native_spot_report():
    frozen, _ = frozen_clock_demand()
    original_cases, observations = [], {}
    for case in frozen["cases"]:
        original_cases.append({
            "decision_date": case["decision_date"],
            "spot_key": case["spot"],
            "decision_utc": case["decision_utc"],
            "quote_query_fingerprint": case["quote_query_fingerprint"],
            "historical_input_accepted": False,
        })
        observations[case["spot"]] = {
            "raw_close": "101.00", "status": "RAW_MINUTE_PRESENT",
            "source_unit_id": "unit-fixture",
            "canonical_sha256": "f" * 64,
            "historical_available_at_utc": None,
        }
    return {
        "contract": STOCK_CONTRACT,
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "frozen_plan_fingerprint": frozen["plan_fingerprint"],
        "target_weekly_cases": MAX_CASES,
        "historical_publication_and_adjustment_qualified": False,
        "pilot_input_acceptance": False,
        "protected_return_rows_read": 0, "option_outcomes_read": 0,
        "cases": original_cases, "observations": observations,
    }


def test_native_raw_spot_mapping_obeys_original_frozen_411_clock_identity():
    report = native_spot_report()
    selected = _spot_lookup(report)
    assert len(selected) == MAX_CASES
    assert all(row["raw_spot"] == "101.00" for row in selected.values())
    report["cases"][0]["spot_key"] = "2025-06-09T01:00:00+00:00"
    with pytest.raises(PairDiagnosticError, match="FROZEN_CLOCK_DRIFT"):
        _spot_lookup(report)


def test_frozen_identity_precedes_liquidity_and_prefers_lower_strike_tie():
    session = date(2025, 1, 6)
    expiry = session + timedelta(days=35)
    original = [
        quote(session, "call", expiry, "100"),
        quote(session, "put", expiry, "100"),
        quote(session, "call", expiry, "102", bid="0", ask="1.1"),
        quote(session, "put", expiry, "102"),
    ]
    selected, reason = _eligible_identity_pair(original, session, __import__("decimal").Decimal("101"))
    assert selected == (expiry.isoformat(), "1E+2")
    assert reason == "IDENTITY_SELECTED_FROM_ORIGINAL_ENTRY_ROSTER"
    earlier = session + timedelta(days=31)
    original.append(quote(session, "call", earlier, "200"))
    # Earliest expiry lacking a common CALL+PUT strike means abstain;
    # no fall-through to the next expiry just because that might fill.
    selected, reason = _eligible_identity_pair(original, session, __import__("decimal").Decimal("101"))
    assert selected is None
    assert reason == "EARLIEST_EXPIRATION_NO_COMMON_STRIKE"


def test_one_provisional_pair_each_original_week_without_future_contract_selection():
    stock = native_spot_report()
    frozen, _ = frozen_clock_demand()
    cases = []
    for n, item in enumerate(frozen["cases"]):
        cases.append({"date_et": item["decision_date"], "query_id": f"e{n}"})

    def source(qid, request):
        if "date_et" in request:
            day = date.fromisoformat(request["date_et"])
            expiry = day + timedelta(days=35)
            return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", [
                quote(day, "call", expiry), quote(day, "put", expiry),
            ]
        return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", []

    result = evaluate_spot_selected_exact_contract_demand(
        cases, source, stock_report=stock,
    )
    assert result["contract"] == CONTRACT
    assert result["original_entry_clocks"] == MAX_CASES
    assert result["provisional_entry_pairs"] == MAX_CASES
    assert result["abstained_weekly_clocks"] == 0
    assert result["selected_pair_five_session_review_uses"] == 5 * MAX_CASES
    assert result["selected_pair_review_source_states"]["BOTH_RIGHTS_ABSENT"] == 5 * MAX_CASES
    assert result["missing_exact_contract_right_request_count"] <= 2 * 5 * MAX_CASES
    assert result["missing_exact_contract_right_request_count"] >= MAX_CASES
    assert result["provider_requests"] == 0
    assert result["option_account_equity"] is None
    assert result["pilot_variance_signal_computed"] is False
    assert result["entry_physical_spot_historical_availability_qualified"] is False
    assert all(x["source_quote_selection_used_future_prices"] is False
               for x in [result])
    assert all(
        x["sdk_kwargs"]["right"] in {"call", "put"}
        and x["sdk_kwargs"]["time_of_day_et"] == "10:00:00.000"
        and x["request_state"] == "EXACT_CONTRACT_EXIT_REQUEST_PREVIEW_NO_PROVIDER_AUTHORITY"
        for x in result["missing_exact_contract_right_requests"]
    )
    reread = evaluate_spot_selected_exact_contract_demand(
        cases, source, stock_report=stock,
    )
    assert result["fingerprint"] == reread["fingerprint"]


def test_bad_selected_entry_quotes_do_not_trigger_lucky_next_strike_fallback(monkeypatch):
    stock = native_spot_report()
    frozen, _ = frozen_clock_demand()
    dates = [i["decision_date"] for i in frozen["cases"]]
    cases = [{"date_et": d, "query_id": f"e{i}"} for i, d in enumerate(dates)]
    called_exit = []

    def source(qid, request):
        if "date_et" in request:
            day = date.fromisoformat(request["date_et"])
            expiry = day + timedelta(days=35)
            return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", [
                quote(day, "call", expiry, "100", bid="0", ask="1.10"),
                quote(day, "put", expiry, "100"),
                quote(day, "call", expiry, "102"),
                quote(day, "put", expiry, "102"),
            ]
        called_exit.append(qid)
        return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", []

    result = evaluate_spot_selected_exact_contract_demand(
        cases, source, stock_report=stock,
    )
    assert result["abstained_weekly_clocks"] == MAX_CASES
    assert result["provisional_entry_pairs"] == 0
    assert not called_exit
    assert result["missing_exact_contract_right_request_count"] == 0
    assert all(r["selected_strike"] == "1E+2" for r in result["cases"])
    assert all(r["reason"] == "SELECTED_ENTRY_PAIR_FAILED_QUOTE_QUALITY" for r in result["cases"])
