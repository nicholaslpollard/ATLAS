from __future__ import annotations

"""V36 2018-25 source-linked SPY quote cash replay with explicit expiry-zero stress.

Every entry identity is the frozen V29 selection from the verified V32 report.
This is *not* the pilot's economic entry signal and no quote is a historical
execution receipt. An unobserved exit is NEVER invented at review time: capital
remains reserved until the original contractual expiration; only then may a
separately labeled ZERO-PROCEEDS stress write off the entire entry debit.
"""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, ROUND_DOWN
from typing import Any

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.options_native_spy_quote_account_diagnostic_v34 import (
    _num, _money, _quote_mean, QuoteScenarioError, INITIAL_CASH,
    MATCHED, HOLDS, FEES, SLIPPAGES, validate_v32_tape,
)

CONTRACT = "atlas-spy-v36-quote-account-expiry-zero-stress-v1"
POLICIES: tuple[tuple[str, Decimal, int, int], ...] = (
    # The original V34 account configuration, now with an explicit terminal
    # assumption instead of holding missing-price positions forever.
    ("v34_two_slots_ten_pairs_10pct", Decimal("0.10"), 2, 10),
    # Mirrors frozen SPY pilot capacity/quantity; ONLY the risk geometry,
    # not the required volatility decision signal or 10:01 execution proofs.
    ("pilot_capacity_only_one_slot_one_pair_5pct", Decimal("0.05"), 1, 1),
)


def _record_pnl(
    amount: Decimal, at: date,
    weeks: dict[str, Decimal], months: dict[str, Decimal],
    years: dict[str, Decimal],
) -> None:
    week = at.isocalendar()
    weeks[f"{week.year}-W{week.week:02d}"] += amount
    months[at.isoformat()[:7]] += amount
    years[str(at.year)] += amount


def replay_expiry_zero_stress(
    rows: list[dict[str, Any]], *, fee: Decimal, slip: Decimal,
    fraction: Decimal, max_slots: int, max_pairs: int,
) -> dict[str, Any]:
    """Deterministic 10:00 review, 10:01 entry, EOD expiry-zero accounting.

    At a same-date expiry, capital is NOT available for the 10:01 entry.
    An expiry event only closes an unpriced/uncertain position after the
    contractual expiry date; a genuine bid observation already closed at the
    originally frozen review session never reaches this artificial terminal.
    """
    if (not Decimal(0) < fraction <= 1 or not 1 <= max_slots <= 10
            or not 1 <= max_pairs <= 100 or fee < 0 or slip < 0):
        raise QuoteScenarioError("V36_POLICY_OUT_OF_BOUNDS")
    events: list[tuple[str, int, str, dict]] = []
    seen: set[str] = set()
    for r in rows:
        entry = date.fromisoformat(r["entry_date_et"])
        review = date.fromisoformat(r["review_date_et"])
        expiry = date.fromisoformat(r["expiration"])
        key = entry.isoformat()
        if key in seen or not entry < review <= expiry:
            raise QuoteScenarioError("V36_DUPLICATE_OR_UNORDERED_QUOTE_CASE")
        seen.add(key)
        # Review 10:00 < entry 10:01 < expiry after regular close.
        events.extend((
            (entry.isoformat(), 1, key, r),
            (review.isoformat(), 0, key, r),
            (expiry.isoformat(), 2, key, r),
        ))
    events.sort(key=lambda event: (event[0], event[1], event[2]))
    cash, realized = INITIAL_CASH, Decimal(0)
    positions: dict[str, tuple[int, Decimal]] = {}
    counts = Counter()
    by_week: dict[str, Decimal] = defaultdict(Decimal)
    by_month: dict[str, Decimal] = defaultdict(Decimal)
    by_year: dict[str, Decimal] = defaultdict(Decimal)
    by_entry_year: dict[str, Counter] = defaultdict(Counter)
    zero_examples: list[dict[str, Any]] = []
    for when, phase, key, r in events:
        entry_year = key[:4]
        if phase == 1:
            if len(positions) >= max_slots:
                counts["skipped_open_slot_limit"] += 1
                by_entry_year[entry_year]["skipped_open_slot_limit"] += 1
                continue
            ask = _num(r["original_100share_two_leg_entry_ask"], "ENTRY", positive=True)
            debit = ask + 2 * fee + 200 * slip
            budget = min(cash * fraction, cash)
            units = min(max_pairs, int((budget / debit).to_integral_value(
                rounding=ROUND_DOWN)))
            if units == 0 or debit * units > cash:
                counts["skipped_insufficient_budget"] += 1
                by_entry_year[entry_year]["skipped_insufficient_budget"] += 1
                continue
            cash -= units * debit
            positions[key] = (units, debit)
            counts["hypothetical_entries"] += 1
            by_entry_year[entry_year]["hypothetical_entries"] += 1
        elif phase == 0:
            if key not in positions:
                continue
            if r["quote_match_state"] not in MATCHED:
                counts["observed_review_exit_missing_or_unqualified"] += 1
                by_entry_year[entry_year]["observed_review_exit_missing_or_unqualified"] += 1
                continue  # Remains open until contract expiration.
            units, debit = positions.pop(key)
            bid = _num(r["observed_100share_two_leg_exit_bid"], "EXIT")
            credit = max(Decimal(0), bid - 200 * slip) - 2 * fee
            cash += units * credit
            pnl = units * (credit - debit)
            realized += pnl
            _record_pnl(pnl, date.fromisoformat(when), by_week, by_month, by_year)
            counts["hypothetical_quote_closures"] += 1
            by_entry_year[entry_year]["hypothetical_quote_closures"] += 1
        else:
            if key not in positions:
                continue
            units, debit = positions.pop(key)
            # Zero credit is a deliberate pessimistic assumption, not an
            # observed exercise, worthless expiry, or liquidation fill.
            writeoff = -(units * debit)
            realized += writeoff
            _record_pnl(writeoff, date.fromisoformat(when), by_week, by_month, by_year)
            counts["unobserved_expiry_assumed_zero_credit"] += 1
            by_entry_year[entry_year]["unobserved_expiry_assumed_zero_credit"] += 1
            if len(zero_examples) < 12:
                zero_examples.append({
                    "original_entry_date_et": key,
                    "frozen_expiration_date_et": when,
                    "source_entry_query_id": r["entry_source_query_id"],
                    "original_quote_review_state": r["quote_match_state"],
                    "hypothetical_entry_debit_written_off": _money(units * debit),
                    "observed_contract_settlement": None,
                    "payout_assumption": "ZERO_CREDIT_ON_CONTRACT_EXPIRY_ONLY",
                })
    counts["original_provisional_entry_denominator"] = len(rows)
    counts["hypothetical_skipped"] = (
        counts["skipped_open_slot_limit"] + counts["skipped_insufficient_budget"]
    )
    if (positions or counts["hypothetical_entries"] !=
            counts["hypothetical_quote_closures"]
            + counts["unobserved_expiry_assumed_zero_credit"]
            or counts["hypothetical_entries"] + counts["hypothetical_skipped"] != len(rows)):
        raise QuoteScenarioError("V36_CASH_OR_CONTRACT_LIFECYCLE_DID_NOT_RECONCILE")
    if abs(cash - INITIAL_CASH - realized) > Decimal("0.000001"):
        raise QuoteScenarioError("V36_CASH_REALIZED_RECONCILIATION_FAILURE")
    assert counts["hypothetical_entries"] == (
        sum(y["hypothetical_entries"] for y in by_entry_year.values())
    )
    return {
        "initial_hypothetical_cash": _money(INITIAL_CASH),
        "terminal_hypothetical_cash_after_zero_expiry_assumptions": _money(cash),
        "net_hypothetical_pnl_including_expiry_zero_writeoffs": _money(realized),
        "assumption_dependent_net_return_pct": str(
            ((cash / INITIAL_CASH - 1) * 100).quantize(Decimal("0.0001"))
        ),
        "position_slots_still_open_after_assumed_expiry": len(positions),
        "counts": dict(sorted(counts.items())),
        "by_original_entry_year_counts": {
            year: dict(sorted(c.items())) for year, c in sorted(by_entry_year.items())
        },
        "hypothetical_pnl_by_exit_or_assumed_expiry_iso_week": {
            week: _money(value) for week, value in sorted(by_week.items())
        },
        "hypothetical_pnl_by_exit_or_assumed_expiry_calendar_month": {
            month: _money(value) for month, value in sorted(by_month.items())
        },
        "hypothetical_pnl_by_exit_or_assumed_expiry_calendar_year": {
            year: _money(value) for year, value in sorted(by_year.items())
        },
        "sample_assumed_zero_expiry_cases": zero_examples,
        "unobserved_valuation_days_and_drawdown": None,
        "actual_fill_evidence": None,
        "actual_contract_settlement_evidence": None,
        "true_historical_account_return": None,
        "historical_profitability_qualified": False,
    }


def run_expiry_zero_stress(tape: dict[str, Any], expected_fingerprint: str) -> dict:
    groups = validate_v32_tape(tape, expected_fingerprint)
    scenarios = []
    for name, allocation, max_slots, max_pairs in POLICIES:
        for hold in HOLDS:
            for fee_text in FEES:
                for slip_text in SLIPPAGES:
                    fee, slip = Decimal(fee_text), Decimal(slip_text)
                    scenarios.append({
                        "capacity_policy": name,
                        "allocation_fraction": str(allocation),
                        "maximum_open_pair_positions": max_slots,
                        "maximum_pair_contract_sets_per_entry": max_pairs,
                        "hold_xnys_sessions": hold,
                        "fee_per_contract_per_side": fee_text,
                        "adverse_slippage_per_share_per_leg": slip_text,
                        "conditional_quote_economics": _quote_mean(groups[hold], fee, slip),
                        "hypothetical_expiry_zero_account": replay_expiry_zero_stress(
                            groups[hold], fee=fee, slip=slip,
                            fraction=allocation, max_slots=max_slots, max_pairs=max_pairs,
                        ),
                    })
    result = {
        "contract": CONTRACT,
        "status": "RETROSPECTIVE_HISTORICAL_QUOTE_EXPIRY_ZERO_STRESS_ONLY",
        "original_v32_report_fingerprint": expected_fingerprint,
        "source_entry_pairs": 361,
        "original_weekly_clock_abstentions": 50,
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
        "quote_tape_input_verified": True,
        "original_pair_decisions_unmodified": True,
        "all_enter_diagnostic_only": True,
        "pilot_volatility_signal_evaluated": False,
        "execution_clock_10am_quotes_not_10_01_fills": True,
        "exit_at_review_when_qualified_quote_exists": True,
        "missing_review_exit_held_until_expiry": True,
        "zero_credit_at_expiry_modeled_not_observed": True,
        "expiry_observation_or_american_assignment_proved": False,
        "historical_strategy_account_returns_qualified": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_2026_market_outcomes_opened": 0,
    }
    result["fingerprint"] = _fingerprint(result)
    return result
