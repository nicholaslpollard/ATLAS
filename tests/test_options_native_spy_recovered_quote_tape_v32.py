from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_original_pair_diagnostic_v26 import PairDiagnosticError
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_review_sessions, _exit_at_time_query,
)
from packages.data.options_native_spy_physical_spot_exact_demand_v29 import (
    CONTRACT as V29_CONTRACT,
)
from packages.data.options_native_spy_development_clock_coverage_v1 import frozen_clock_demand
from packages.data.options_native_spy_recovered_quote_tape_v32 import (
    CONTRACT, evaluate_original_plus_exact_option_quote_tape,
)
from packages.strategies.options_native_pilot_v1_contract import SPECIFICATION_FINGERPRINT
from packages.data import options_native_spy_recovered_quote_tape_v32 as v32

ET = ZoneInfo("America/New_York")
ENTRY = date(2025, 1, 6)
EXPIRY = date(2025, 2, 14)


def quote(day, right, *, bid="2.00", ask="2.10", strike="100"):
    stamp = datetime.combine(
        day, datetime.strptime("10:00", "%H:%M").time(), ET
    ) - timedelta(seconds=10)
    return {
        "symbol": "SPY",
        "expiration": EXPIRY.isoformat(),
        "strike": strike, "right": right,
        "timestamp": stamp.isoformat(),
        "bid": bid, "ask": ask, "bid_size": 1, "ask_size": 1,
    }


def pair(day, *, both=True):
    out = [quote(day, "call")]
    if both:
        out.append(quote(day, "put"))
    return out


def fixture():
    demand, _ = frozen_clock_demand()
    assert ENTRY.isoformat() in {x["decision_date"] for x in demand["cases"]}
    entry_rows = [{
        "date_et": case["decision_date"],
        "query_id": f"entry-{i}",
    } for i, case in enumerate(demand["cases"])]
    selection = next(x for x in entry_rows if x["date_et"] == ENTRY.isoformat())
    chosen = []
    exact_requests = []
    reviews = _exit_review_sessions(ENTRY)
    for hold, day in enumerate(reviews, 1):
        absent = [] if hold == 1 else ["call", "put"]
        chosen.append({
            "hold_sessions": hold,
            "session_et": day.isoformat(),
            "missing_exact_rights": absent,
        })
        for right in absent:
            req = {
                "symbol": "SPY", "date_et": day.isoformat(),
                "time_of_day_et": "10:00:00.000",
                "expiration": EXPIRY.isoformat(),
                "strike": "100", "right": right,
            }
            exact_requests.append({
                "query_id": _fingerprint({
                    "provider": "thetadata", "method": "option_at_time_quote",
                    "kwargs": req,
                }),
                "sdk_kwargs": req,
            })
    by_day = {
        row["date_et"]: {
            "date_et": row["date_et"], "status": "RESEARCH_IDENTITY_NOT_AVAILABLE",
        }
        for row in entry_rows
    }
    by_day[ENTRY.isoformat()] = {
        "date_et": ENTRY.isoformat(),
        "status": "PHYSICAL_SPOT_PROVISIONAL_PAIR_ONLY",
        "selected_expiration": EXPIRY.isoformat(),
        "selected_strike": "100",
        "review_results": chosen,
    }
    plan = {
        "contract": V29_CONTRACT, "original_entry_clocks": 411,
        "pilot_specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "source_quote_selection_used_future_prices": False,
        "entry_physical_spot_historical_availability_qualified": False,
        "provisional_entry_pairs": 1, "abstained_weekly_clocks": 410,
        "missing_exact_contract_right_requests": exact_requests,
        "cases": list(by_day.values()), "fingerprint": "e" * 64,
    }
    original_lookups = []

    def original(qid, row):
        original_lookups.append(qid)
        if qid == selection["query_id"]:
            return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", pair(ENTRY)
        for hold, day in enumerate(reviews, 1):
            if qid == _exit_at_time_query(day)["query_id"]:
                return "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC", (
                    pair(day) if hold == 1 else []
                )
        raise AssertionError(f"unexpected historical fetch {qid}")

    return plan, entry_rows, original, original_lookups, reviews


def test_recovers_exact_contract_pair_without_hindsight_or_fabricated_missing_pnl(monkeypatch):
    plan, entries, original, lookups, dates = fixture()

    def exact(_settings, req, _fingerprint):
        q = req["sdk_kwargs"]
        day = date.fromisoformat(q["date_et"])
        hold = dates.index(day) + 1
        if hold == 2:
            return "RAW_ARCHIVED_EXACT_CONTRACT_DIAGNOSTIC", quote(day, q["right"])
        if hold == 3 and q["right"] == "call":
            return "RAW_ARCHIVED_EXACT_CONTRACT_DIAGNOSTIC", quote(day, q["right"])
        if hold == 4:
            return "RAW_ARCHIVED_EXACT_CONTRACT_DIAGNOSTIC", quote(
                day, q["right"], bid="0", ask="2.10"
            )
        return "UNCERTAIN_PREVIOUS_DISPATCH_NO_RETRY", None

    monkeypatch.setattr(v32, "_exact_quote", exact)
    result = evaluate_original_plus_exact_option_quote_tape(
        entries, original, settings=None, plan=plan,
    )
    assert result["contract"] == CONTRACT
    assert result["provisionally_selected_original_weekly_pairs"] == 1
    assert result["original_weekly_abstentions"] == 410
    assert result["quote_review_observations"] == 5
    assert result["provider_requests"] == result["broker_requests"] == 0
    assert result["historical_account_profitability"] is None
    states = [
        "ORIGINAL_PAIR_QUOTE_MATCH",
        "EXACT_SOURCE_RECOVERED_PAIR_QUOTE_MATCH",
        "ONE_OPTION_RIGHT_NOT_AVAILABLE",
        "PRESENT_QUOTES_UNQUALIFIED",
        "BOTH_OPTION_RIGHTS_NOT_AVAILABLE",
    ]
    for hold, reason in enumerate(states, 1):
        one = result["by_exit_horizon"][str(hold)]
        assert one["selected_entry_pair_denominator"] == 1
        assert one["states"][reason] == 1
        assert one["total_qualified_quote_matches"] == (1 if hold <= 2 else 0)
        assert sum(one["states"].values()) == 1
    quotes = result["observations"]
    assert quotes[0]["observed_100share_two_leg_exit_bid"] is not None
    assert quotes[1]["observed_100share_two_leg_exit_bid"] is not None
    assert len(quotes[1]["exact_source_query_ids"]) == 2
    assert all(x["observed_100share_two_leg_exit_bid"] is None for x in quotes[2:])
    assert all(x["historical_execution_fill"] is None for x in quotes)
    assert all(x["historical_strategy_profit"] is None for x in quotes)
    assert result["exact_requested_right_terminal_states_encountered"]["UNCERTAIN_PREVIOUS_DISPATCH_NO_RETRY"] == 3
    # Only selected entries can read future original source outcomes.
    assert len(lookups) == 6


def test_changed_selected_entry_quality_fails_closed(monkeypatch):
    plan, entries, original, _, _ = fixture()

    def bad_original(qid, row):
        state, data = original(qid, row)
        if qid.startswith("entry-") and data is not None:
            return state, [dict(x, bid="0") for x in data]
        return state, data

    monkeypatch.setattr(v32, "_exact_quote", lambda *a: ("UNATTEMPTED", None))
    with pytest.raises(PairDiagnosticError, match="ORIGINAL_ENTRY_PAIR_QUALITY_CHANGED"):
        evaluate_original_plus_exact_option_quote_tape(
            entries, bad_original, settings=None, plan=plan,
        )


def test_unverified_plan_scope_or_entry_cohort_fails_before_quote_scan():
    plan, entries, original, lookups, _ = fixture()
    plan["entry_physical_spot_historical_availability_qualified"] = True
    with pytest.raises(PairDiagnosticError, match="FROZEN_V29_ORIGINAL_SCOPE_DRIFT"):
        evaluate_original_plus_exact_option_quote_tape(
            entries, original, settings=None, plan=plan,
        )
    assert not lookups
