from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from packages.simulation.options_native_spy_expiry_zero_stress_v36 import (
    POLICIES, replay_expiry_zero_stress, run_expiry_zero_stress,
)
from packages.simulation.options_native_spy_quote_account_diagnostic_v34 import (
    QuoteScenarioError,
)
from packages.simulation import options_native_spy_expiry_zero_stress_v36 as v36


def row(entry: str, review: str, expiry: str, *, exit_bid: str | None):
    return {
        "entry_date_et": entry,
        "review_date_et": review,
        "expiration": expiry,
        "entry_source_query_id": "frozen-" + entry,
        "quote_match_state": (
            "ORIGINAL_PAIR_QUOTE_MATCH" if exit_bid is not None
            else "BOTH_OPTION_RIGHTS_NOT_AVAILABLE"
        ),
        "original_100share_two_leg_entry_ask": "400.00",
        "observed_100share_two_leg_exit_bid": exit_bid,
    }


def replay(rows, *, slots=1, max_pairs=1, frac="0.05", fee="0.65", slip="0.00"):
    return replay_expiry_zero_stress(
        rows, fee=Decimal(fee), slip=Decimal(slip),
        fraction=Decimal(frac), max_slots=slots, max_pairs=max_pairs,
    )


def test_expiry_zero_assumption_releases_capacity_without_hindsight_exit():
    # A original review exit missing, cannot silently liquidate on Jan 3.
    # B before Jan 19 expiry has to abstain, C after expiry can participate.
    cases = [
        row("2018-01-02", "2018-01-03", "2018-01-19", exit_bid=None),
        row("2018-01-09", "2018-01-10", "2018-02-09", exit_bid="600.00"),
        row("2018-01-22", "2018-01-23", "2018-02-16", exit_bid="500.00"),
    ]
    result = replay(cases)
    counts = result["counts"]
    assert counts["original_provisional_entry_denominator"] == 3
    assert counts["hypothetical_entries"] == 2
    assert counts["skipped_open_slot_limit"] == 1
    assert counts["hypothetical_quote_closures"] == 1
    assert counts["observed_review_exit_missing_or_unqualified"] == 1
    assert counts["unobserved_expiry_assumed_zero_credit"] == 1
    assert result["position_slots_still_open_after_assumed_expiry"] == 0
    # Loss of entry debit 401.30, later matched +97.40.
    assert result["net_hypothetical_pnl_including_expiry_zero_writeoffs"] == "-303.90"
    assert result["terminal_hypothetical_cash_after_zero_expiry_assumptions"] == "99696.10"
    missing = result["sample_assumed_zero_expiry_cases"]
    assert len(missing) == 1
    assert missing[0]["original_entry_date_et"] == "2018-01-02"
    assert missing[0]["frozen_expiration_date_et"] == "2018-01-19"
    assert missing[0]["observed_contract_settlement"] is None
    assert result["real_historical_execution_fills"] is None if "real_historical_execution_fills" in result else True
    assert result["true_historical_account_return"] is None
    assert not result["historical_profitability_qualified"]


def test_same_day_expiration_does_not_release_10am_entry_slot():
    cases = [
        row("2018-01-02", "2018-01-03", "2018-01-19", exit_bid=None),
        row("2018-01-19", "2018-01-22", "2018-02-16", exit_bid="500.00"),
        row("2018-01-26", "2018-01-29", "2018-02-23", exit_bid="510.00"),
    ]
    result = replay(cases)
    assert result["counts"]["skipped_open_slot_limit"] == 1
    assert result["counts"]["hypothetical_entries"] == 2
    assert result["counts"]["unobserved_expiry_assumed_zero_credit"] == 1


def test_raises_if_unordered_or_duplicate_case_or_invalid_capacity():
    cases = [row("2018-01-02", "2018-01-03", "2018-01-19", exit_bid="500.00")]
    with pytest.raises(QuoteScenarioError, match="DUPLICATE"):
        replay(cases * 2)
    with pytest.raises(QuoteScenarioError, match="UNORDERED"):
        replay([row("2018-01-02", "2018-01-02", "2018-01-19", exit_bid="500.00")])
    with pytest.raises(QuoteScenarioError, match="POLICY_OUT_OF_BOUNDS"):
        replay(cases, slots=0)
    with pytest.raises(QuoteScenarioError, match="POLICY_OUT_OF_BOUNDS"):
        replay(cases, frac="1.10")


def test_source_unresolved_quote_never_becomes_observed_real_fill():
    cases = [row("2018-01-02", "2018-01-03", "2018-01-19", exit_bid=None)]
    r = replay(cases)
    assert r["sample_assumed_zero_expiry_cases"][0]["payout_assumption"] == (
        "ZERO_CREDIT_ON_CONTRACT_EXPIRY_ONLY"
    )
    assert r["actual_fill_evidence"] is None
    assert r["actual_contract_settlement_evidence"] is None
    assert r["unobserved_valuation_days_and_drawdown"] is None


def test_cost_sensitivity_and_pilot_capacity_limits_are_explicit():
    cases = [row("2018-01-02", "2018-01-03", "2018-01-19", exit_bid="500.00")]
    cheap = replay(cases, slots=1, max_pairs=1, fee="0.65", slip="0.00")
    dear = replay(cases, slots=1, max_pairs=1, fee="1.30", slip="0.05")
    assert Decimal(cheap["net_hypothetical_pnl_including_expiry_zero_writeoffs"]) > (
        Decimal(dear["net_hypothetical_pnl_including_expiry_zero_writeoffs"])
    )
    assert len(POLICIES) == 2
    assert POLICIES[1] == (
        "pilot_capacity_only_one_slot_one_pair_5pct", Decimal("0.05"), 1, 1
    )


def test_40_scenarios_consume_frozen_cohort_and_do_not_upgrade_to_real_pnl(monkeypatch):
    groups = {}
    for hold in (1, 2, 3, 4, 5):
        rows = []
        for i in range(361):
            day = date(2018, 1, 1) + timedelta(days=7 * i)
            rows.append(row(
                day.isoformat(), (day + timedelta(days=hold)).isoformat(),
                (day + timedelta(days=35)).isoformat(),
                exit_bid=None if i in (1, 2) else "440.00",
            ))
        groups[hold] = rows
    seen = []
    def validated(_tape, fingerprint):
        seen.append(fingerprint)
        return groups

    monkeypatch.setattr(v36, "validate_v32_tape", validated)
    out = run_expiry_zero_stress({}, "c" * 64)
    assert seen == ["c" * 64]
    assert out["scenario_count"] == 40
    assert len(out["scenarios"]) == 40
    assert out["pilot_volatility_signal_evaluated"] is False
    assert out["historical_strategy_account_returns_qualified"] is False
    assert out["provider_requests"] == out["broker_requests"] == 0
    assert out["zero_credit_at_expiry_modeled_not_observed"] is True
    assert {x["capacity_policy"] for x in out["scenarios"]} == {
        "v34_two_slots_ten_pairs_10pct",
        "pilot_capacity_only_one_slot_one_pair_5pct",
    }
    for case in out["scenarios"]:
        account = case["hypothetical_expiry_zero_account"]
        c = account["counts"]
        assert c["original_provisional_entry_denominator"] == 361
        assert c["hypothetical_entries"] + c["hypothetical_skipped"] == 361
        assert c["hypothetical_entries"] == (
            c["hypothetical_quote_closures"] + c["unobserved_expiry_assumed_zero_credit"]
        )
        assert account["position_slots_still_open_after_assumed_expiry"] == 0
        assert account["true_historical_account_return"] is None
        assert account["historical_profitability_qualified"] is False
