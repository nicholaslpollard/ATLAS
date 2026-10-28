from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from copy import deepcopy

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_recovered_quote_tape_v32 import (
    CONTRACT as V32_CONTRACT, REVIEW_STATES,
)
from packages.simulation.options_native_spy_quote_account_diagnostic_v34 import (
    _account, QuoteScenarioError, run_quote_account_diagnostic, validate_v32_tape,
)


def tape(*, missing_first_fifth: bool = True) -> dict:
    """361 frozen weekly selections, five reviews each, no providers."""
    rows = []
    by_hold = {}
    for hold in (1, 2, 3, 4, 5):
        counter = Counter()
        for i in range(361):
            entry = date(2018, 1, 1) + timedelta(days=i * 7)
            review = entry + timedelta(days=hold)
            state = ("BOTH_OPTION_RIGHTS_NOT_AVAILABLE"
                     if missing_first_fifth and i == 0 and hold == 5
                     else "EXACT_SOURCE_RECOVERED_PAIR_QUOTE_MATCH")
            counter[state] += 1
            rows.append({
                "entry_date_et": entry.isoformat(),
                "review_date_et": review.isoformat(),
                "hold_xnys_sessions": hold,
                "expiration": (entry + timedelta(days=35)).isoformat(),
                "strike": "100.5",
                "entry_source_query_id": "entry-" + entry.isoformat(),
                "original_review_source_query_id": "review-" + review.isoformat(),
                "quote_match_state": state,
                "original_100share_two_leg_entry_ask": "400.00",
                "observed_100share_two_leg_exit_bid": (
                    "440.00" if state == "EXACT_SOURCE_RECOVERED_PAIR_QUOTE_MATCH"
                    else None
                ),
                "quote_price_observation_only": True,
                "historical_execution_fill": None,
                "historical_strategy_profit": None,
            })
        matches = counter["EXACT_SOURCE_RECOVERED_PAIR_QUOTE_MATCH"]
        by_hold[str(hold)] = {
            "selected_entry_pair_denominator": 361,
            "total_qualified_quote_matches": matches,
            "missing_or_unqualified_after_recovery": 361 - matches,
            "states": {s: counter[s] for s in sorted(REVIEW_STATES)},
        }
    doc = {
        "contract": V32_CONTRACT,
        "status": "ORIGINAL_AND_EXACT_QUOTE_EVIDENCE_TAPE_NO_HISTORICAL_FILL",
        "original_frozen_weekly_entries": 411,
        "provisionally_selected_original_weekly_pairs": 361,
        "original_weekly_abstentions": 50,
        "hold_sessions": [1, 2, 3, 4, 5],
        "quote_review_observations": 1805,
        "by_exit_horizon": by_hold,
        "observations": rows,
        "provider_requests": 0,
        "broker_requests": 0,
        "simulator_ready": False,
        "historical_stock_spot_pit_availability_proven": False,
        "historical_101_order_fills": None,
        "historical_account_profitability": None,
        "protected_2026_outcomes_read": 0,
    }
    doc["fingerprint"] = _fingerprint(doc)
    return doc


def test_20_fixed_fee_slippage_and_holding_scenarios_are_historical_quote_only():
    doc = tape()
    result = run_quote_account_diagnostic(doc, doc["fingerprint"])
    assert result["scenario_count"] == 20
    assert result["original_v32_fingerprint"] == doc["fingerprint"]
    assert result["actual_options_native_volatility_signal_evaluated"] is False
    assert result["historical_1001_execution_fills"] is None
    assert result["historical_account_profitability"] is None
    assert result["provider_requests"] == result["broker_requests"] == 0
    first = next(x for x in result["scenarios"] if
                 x["hold_sessions"] == 1
                 and x["fee_per_contract_per_side"] == "0.65"
                 and x["slippage_per_share_per_leg"] == "0.00")
    assert first["conditional_quote_economics"]["matched_conditional_count"] == 361
    assert Decimal(first["conditional_quote_economics"]["conditional_mean_quote_return_pct"]) > 0
    assert first["chronological_quote_cash_scenario"]["ending_equity"] is not None
    fifth = next(x for x in result["scenarios"] if
                 x["hold_sessions"] == 5
                 and x["fee_per_contract_per_side"] == "0.65"
                 and x["slippage_per_share_per_leg"] == "0.00")
    assert fifth["conditional_quote_economics"]["matched_conditional_count"] == 360
    assert fifth["chronological_quote_cash_scenario"]["ending_equity"] is None
    assert fifth["chronological_quote_cash_scenario"]["ending_open_pairs_without_trusted_terminal_mark"] == 1
    assert fifth["chronological_quote_cash_scenario"]["hypothetical_account_return_pct"] is None
    assert fifth["chronological_quote_cash_scenario"]["counts"]["hypothetical_opened_pairs"] == 361
    assert fifth["chronological_quote_cash_scenario"]["counts"]["hypothetical_closed_pairs"] == 360


def test_all_original_selections_stay_in_denominator_including_missing_exits():
    doc = tape()
    rows = validate_v32_tape(doc, doc["fingerprint"])
    assert list(rows) == [1, 2, 3, 4, 5]
    assert all(len(v) == 361 for v in rows.values())
    assert sum(x["observed_100share_two_leg_exit_bid"] is None for x in rows[5]) == 1


def test_fingerprint_and_absent_fill_guards_reject_fabrication():
    original = tape()
    fake = deepcopy(original)
    fake["observations"][0]["observed_100share_two_leg_exit_bid"] = "999999"
    with pytest.raises(QuoteScenarioError, match="FINGERPRINT"):
        run_quote_account_diagnostic(fake, original["fingerprint"])
    fake = deepcopy(original)
    fake["historical_101_order_fills"] = [{"fabricated": True}]
    fake["fingerprint"] = _fingerprint({k: v for k, v in fake.items() if k != "fingerprint"})
    with pytest.raises(QuoteScenarioError, match="AUTHORITY"):
        run_quote_account_diagnostic(fake, fake["fingerprint"])


def test_future_source_absence_does_not_remove_past_entry():
    rows = [{
        "entry_date_et": "2024-01-01",
        "review_date_et": "2024-01-02",
        "quote_match_state": "ONE_OPTION_RIGHT_NOT_AVAILABLE",
        "original_100share_two_leg_entry_ask": "400.00",
        "observed_100share_two_leg_exit_bid": None,
    }, {
        "entry_date_et": "2024-01-08",
        "review_date_et": "2024-01-09",
        "quote_match_state": "ORIGINAL_PAIR_QUOTE_MATCH",
        "original_100share_two_leg_entry_ask": "400.00",
        "observed_100share_two_leg_exit_bid": "440.00",
    }]
    replay = _account(rows, Decimal("0.65"), Decimal("0.00"))
    assert replay["counts"]["hypothetical_opened_pairs"] == 2
    assert replay["counts"]["hypothetical_closed_pairs"] == 1
    assert replay["ending_open_pairs_without_trusted_terminal_mark"] == 1
    assert replay["ending_equity"] is None
    assert replay["drawdown_without_independent_marks"] is None
    assert replay["realized_pnl_by_exit_month_incomplete_if_unresolved"]["2024-01"] != "0.00"


def test_cost_stresses_cannot_improve_identical_matched_quote_returns():
    doc = tape(missing_first_fifth=False)
    result = run_quote_account_diagnostic(doc, doc["fingerprint"])
    cells = [x for x in result["scenarios"] if x["hold_sessions"] == 1]
    values = {(x["fee_per_contract_per_side"], x["slippage_per_share_per_leg"]):
              Decimal(x["conditional_quote_economics"]["conditional_mean_quote_return_pct"])
              for x in cells}
    assert values[("0.65", "0.00")] > values[("1.30", "0.00")]
    assert values[("0.65", "0.00")] > values[("0.65", "0.05")]
