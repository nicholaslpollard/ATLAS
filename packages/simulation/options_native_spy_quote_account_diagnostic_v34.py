from __future__ import annotations

"""V34 historical SPY *quote-based* cash scenario replay, never historical fills.

Uses the immutable V32 10:00 quote observation tape, not synthetic price fixtures.
The frozen one-pair-per-week universe is an ALL-ENTER diagnostic, not the pilot's
unimplemented volatility entry signal. No 10:01 order, execution, mark, or alpha
qualification is inferred from a 10:00 quote.
"""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_recovered_quote_tape_v32 import (
    CONTRACT as V32_CONTRACT, REVIEW_STATES,
)

CONTRACT = "atlas-spy-v34-source-linked-quote-account-diagnostic-v1"
MATCHED = frozenset({
    "ORIGINAL_PAIR_QUOTE_MATCH", "EXACT_SOURCE_RECOVERED_PAIR_QUOTE_MATCH",
})
HOLDS = (1, 2, 3, 4, 5)
FEES = ("0.65", "1.30")
SLIPPAGES = ("0.00", "0.05")  # dollars per share per leg, applied adversely
INITIAL_CASH = Decimal("100000.00")
CASH_FRACTION = Decimal("0.10")
MAX_OPEN_PAIRS = 2
MAX_CONTRACT_PAIRS = 10
CENTS = Decimal("0.01")


class QuoteScenarioError(ValueError):
    pass


# V32's evaluator builds and fingerprints the inner quote tape. Its V26
# source-audit wrapper then spreads that entire inner tape (including its
# "fingerprint") into the audited result, and REPLACES "fingerprint" with
# the wrapper digest. Saved V32 reports therefore need BOTH hash layers
# reconstructed: hash(inner without fingerprint), then hash(outer with
# fingerprint temporarily replaced by that inner digest).
V32_INNER_FIELDS = frozenset({
    "contract", "status", "source_plan_fingerprint",
    "original_frozen_weekly_entries", "provisionally_selected_original_weekly_pairs",
    "original_weekly_abstentions", "hold_sessions", "by_exit_horizon",
    "exact_requested_right_terminal_states_encountered",
    "quote_review_observations", "observations",
    "original_source_archives_unmodified",
    "historical_stock_spot_pit_availability_proven",
    "original_option_contract_roster_completeness_proven",
    "historical_101_order_fills", "historical_account_profitability",
    "simulator_ready", "provider_requests", "broker_requests",
    "protected_2026_outcomes_read",
})
V26_AUDIT_ONLY_FIELDS = frozenset({
    "original_411_entry_plan", "distinct_new_exit_request_plan",
    "observed_source_identities_loaded", "note", "pricing",
    "fee_grid_is_model_assumption", "simulations_run",
    "account_pnl_reported", "historical_execution_qualified",
    "protected_outcomes_read", "strategy_promotion",
})


def _verify_v32_fingerprint(tape: dict, expected: str) -> None:
    """Accept the direct V32 evaluator or actual V26-wrapped V32 SHA preimage.

    The caller still supplies the original independently pinned final digest.
    Neither path changes the file or accepts a digest recalculated from an
    untrusted report as a replacement for that independently pinned digest.
    """
    if tape.get("fingerprint") != expected:
        raise QuoteScenarioError("V34_SOURCE_TAPE_FINGERPRINT_MISMATCH")
    without_digest = {key: val for key, val in tape.items() if key != "fingerprint"}
    if _fingerprint(without_digest) == expected:
        return  # Direct source evaluator result, common in isolated fixtures.
    if (not V32_INNER_FIELDS.issubset(tape)
            or not V26_AUDIT_ONLY_FIELDS.issubset(tape)
            or set(tape) != V32_INNER_FIELDS | V26_AUDIT_ONLY_FIELDS | {"fingerprint"}):
        raise QuoteScenarioError("V34_SOURCE_TAPE_FINGERPRINT_MISMATCH")
    inner = {key: tape[key] for key in V32_INNER_FIELDS}
    nested_preimage = dict(tape)
    nested_preimage["fingerprint"] = _fingerprint(inner)
    if _fingerprint(nested_preimage) != expected:
        raise QuoteScenarioError("V34_SOURCE_TAPE_FINGERPRINT_MISMATCH")


def _num(value: Any, label: str, *, positive: bool = False) -> Decimal:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise QuoteScenarioError("V34_INVALID_DECIMAL_" + label)
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise QuoteScenarioError("V34_INVALID_DECIMAL_" + label) from exc
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise QuoteScenarioError("V34_INVALID_DECIMAL_" + label)
    return number


def _money(value: Decimal) -> str:
    return str(value.quantize(CENTS))


def validate_v32_tape(tape: Any, expected_fingerprint: str) -> dict[int, list[dict]]:
    """Verify the persisted outcome tape and entire frozen entry denominator."""
    if not isinstance(tape, dict) or not isinstance(expected_fingerprint, str):
        raise QuoteScenarioError("V34_TAPE_NOT_VERIFIABLE")
    _verify_v32_fingerprint(tape, expected_fingerprint)
    if (tape.get("contract") != V32_CONTRACT
            or tape.get("status") != "ORIGINAL_AND_EXACT_QUOTE_EVIDENCE_TAPE_NO_HISTORICAL_FILL"
            or tape.get("original_frozen_weekly_entries") != 411
            or tape.get("provisionally_selected_original_weekly_pairs") != 361
            or tape.get("original_weekly_abstentions") != 50
            or tape.get("hold_sessions") != list(HOLDS)
            or tape.get("quote_review_observations") != 1805
            or tape.get("provider_requests") != 0 or tape.get("broker_requests") != 0
            or tape.get("simulator_ready") is not False
            or tape.get("historical_stock_spot_pit_availability_proven") is not False
            or tape.get("historical_101_order_fills") is not None
            or tape.get("historical_account_profitability") is not None
            or tape.get("protected_2026_outcomes_read") != 0):
        raise QuoteScenarioError("V34_INCORRECT_V32_RESEARCH_AUTHORITY")
    rows = tape.get("observations")
    summaries = tape.get("by_exit_horizon")
    if not isinstance(rows, list) or len(rows) != 1805 or not isinstance(summaries, dict):
        raise QuoteScenarioError("V34_INCOMPLETE_FROZEN_OBSERVATIONS")
    grouped: dict[int, list[dict]] = {h: [] for h in HOLDS}
    identities: dict[str, tuple] = {}
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise QuoteScenarioError("V34_MALFORMED_OBSERVATION")
        try:
            entry = date.fromisoformat(row["entry_date_et"])
            review = date.fromisoformat(row["review_date_et"])
            expiry = date.fromisoformat(row["expiration"])
            hold = row["hold_xnys_sessions"]
            state = row["quote_match_state"]
            strike = _num(row["strike"], "STRIKE", positive=True)
            entry_ask = _num(row["original_100share_two_leg_entry_ask"],
                             "ENTRY_ASK", positive=True)
            out = row["observed_100share_two_leg_exit_bid"]
            exit_bid = _num(out, "EXIT_BID") if out is not None else None
        except (ValueError, KeyError, TypeError) as exc:
            raise QuoteScenarioError("V34_MALFORMED_OBSERVATION") from exc
        if (type(hold) is not int or hold not in HOLDS
                or state not in REVIEW_STATES or not entry < review <= expiry
                or not 2018 <= entry.year <= 2025
                or (state in MATCHED) != (exit_bid is not None)
                or row.get("quote_price_observation_only") is not True
                or row.get("historical_execution_fill") is not None
                or row.get("historical_strategy_profit") is not None):
            raise QuoteScenarioError("V34_OBSERVATION_AUTHORITY_OR_CLOCK_DRIFT")
        ident = (row["expiration"], str(strike), str(entry_ask),
                 row["entry_source_query_id"])
        key = (entry.isoformat(), hold)
        if key in seen:
            raise QuoteScenarioError("V34_DUPLICATE_ENTRY_HOLD")
        seen.add(key)
        if entry.isoformat() in identities and identities[entry.isoformat()] != ident:
            raise QuoteScenarioError("V34_FUTURE_DRIVEN_ENTRY_IDENTITY")
        identities[entry.isoformat()] = ident
        grouped[hold].append(row)
    if len(identities) != 361 or any(len(grouped[h]) != 361 for h in HOLDS):
        raise QuoteScenarioError("V34_ORIGINAL_COHORT_DENOMINATOR_DRIFT")
    for hold in HOLDS:
        summary = summaries.get(str(hold))
        if not isinstance(summary, dict):
            raise QuoteScenarioError("V34_MISSING_SOURCE_HORIZON")
        counts = Counter(r["quote_match_state"] for r in grouped[hold])
        matches = sum(counts[s] for s in MATCHED)
        if (summary.get("selected_entry_pair_denominator") != 361
                or summary.get("total_qualified_quote_matches") != matches
                or summary.get("missing_or_unqualified_after_recovery") != 361 - matches
                or any(summary.get("states", {}).get(s) != counts[s] for s in REVIEW_STATES)):
            raise QuoteScenarioError("V34_SOURCE_HORIZON_MISMATCH")
        grouped[hold].sort(key=lambda r: r["entry_date_et"])
    return grouped


def _quote_mean(rows: list[dict], fee: Decimal, slip: Decimal) -> dict:
    """Conditional ask-to-bid premium return; never unconditional strategy P&L."""
    returns: list[Decimal] = []
    for r in rows:
        if r["quote_match_state"] not in MATCHED:
            continue
        ask = _num(r["original_100share_two_leg_entry_ask"], "ENTRY_ASK", positive=True)
        bid = _num(r["observed_100share_two_leg_exit_bid"], "EXIT_BID")
        debit = ask + 2 * fee + 200 * slip
        credit = max(Decimal(0), bid - 200 * slip) - 2 * fee
        returns.append((credit - debit) / debit * 100)
    mean = sum(returns) / len(returns) if returns else None
    return {
        "matched_conditional_count": len(returns),
        "selected_denominator": 361,
        "conditional_mean_quote_return_pct": (
            str(mean.quantize(Decimal("0.0001"))) if mean is not None else None
        ),
        "missing_observations_not_imputed": 361 - len(returns),
    }


def _account(rows: list[dict], fee: Decimal, slip: Decimal) -> dict:
    """Chronological cash scenario: exits before same-date entries.

    Once an exit quote is missing, no sale or valuation is invented.
    Subsequent new entries must share the actual remaining hypothetical cash.
    """
    events = []
    for r in rows:
        events.append((r["entry_date_et"], 1, r))
        events.append((r["review_date_et"], 0, r))
    events.sort(key=lambda event: (event[0], event[1], event[2]["entry_date_et"]))
    cash = INITIAL_CASH
    realized = Decimal(0)
    opened: dict[str, tuple[int, Decimal]] = {}
    counts = Counter()
    realized_by_week = defaultdict(Decimal)
    realized_by_month = defaultdict(Decimal)
    realized_by_year = defaultdict(Decimal)
    for day, kind, r in events:
        key = r["entry_date_et"]
        if kind == 0:
            if key not in opened:
                continue
            units, debit = opened[key]
            if r["quote_match_state"] not in MATCHED:
                counts["open_unresolved_missing_exit_quote"] += 1
                continue
            bid = _num(r["observed_100share_two_leg_exit_bid"], "EXIT_BID")
            credit = max(Decimal(0), bid - 200 * slip) - 2 * fee
            cash += units * credit
            pnl = units * (credit - debit)
            realized += pnl
            counts["hypothetical_closed_pairs"] += 1
            ending = date.fromisoformat(day)
            iso = ending.isocalendar()
            realized_by_week[f"{iso.year}-W{iso.week:02d}"] += pnl
            realized_by_month[day[:7]] += pnl
            realized_by_year[day[:4]] += pnl
            del opened[key]
        else:
            if len(opened) >= MAX_OPEN_PAIRS:
                counts["rejected_shared_position_limit"] += 1
                continue
            ask = _num(r["original_100share_two_leg_entry_ask"], "ENTRY_ASK", positive=True)
            debit = ask + 2 * fee + 200 * slip
            cap = min(cash * CASH_FRACTION, cash)
            units = min(MAX_CONTRACT_PAIRS, int((cap / debit).to_integral_value(
                rounding=ROUND_DOWN)))
            if units < 1 or debit * units > cash:
                counts["rejected_insufficient_cash"] += 1
                continue
            cash -= debit * units
            opened[key] = (units, debit)
            counts["hypothetical_opened_pairs"] += 1
    counts["original_selected_pairs"] = len(rows)
    counts["not_executed_or_unadmitted"] = (
        counts["rejected_shared_position_limit"] + counts["rejected_insufficient_cash"]
    )
    if counts["hypothetical_opened_pairs"] != (
        counts["hypothetical_closed_pairs"] + len(opened)
    ):
        raise QuoteScenarioError("V34_POSITION_ACCOUNT_RECONCILIATION_FAILURE")
    return {
        "starting_cash": _money(INITIAL_CASH),
        "ending_cash_not_equity": _money(cash),
        "hypothetical_known_closed_realized_pnl": _money(realized),
        "ending_equity": _money(cash) if not opened else None,
        "hypothetical_account_return_pct": (
            str(((cash / INITIAL_CASH - 1) * 100).quantize(Decimal("0.0001")))
            if not opened else None
        ),
        "ending_open_pairs_without_trusted_terminal_mark": len(opened),
        "opening_reserved_cost_of_unresolved_pairs": _money(
            sum((units * cost for units, cost in opened.values()), Decimal(0))
        ),
        "counts": dict(sorted(counts.items())),
        "realized_pnl_by_exit_iso_week_incomplete_if_unresolved": {
            k: _money(v) for k, v in sorted(realized_by_week.items())
        },
        "realized_pnl_by_exit_month_incomplete_if_unresolved": {
            k: _money(v) for k, v in sorted(realized_by_month.items())
        },
        "realized_pnl_by_exit_year_incomplete_if_unresolved": {
            k: _money(v) for k, v in sorted(realized_by_year.items())
        },
        "drawdown_without_independent_marks": None,
        "real_historical_execution_fills": None,
        "historical_profitability_qualified": False,
    }


def run_quote_account_diagnostic(tape: dict, expected_fingerprint: str) -> dict:
    groups = validate_v32_tape(tape, expected_fingerprint)
    results: list[dict] = []
    for hold in HOLDS:
        for fee_text in FEES:
            for slip_text in SLIPPAGES:
                fee, slip = Decimal(fee_text), Decimal(slip_text)
                results.append({
                    "hold_sessions": hold,
                    "fee_per_contract_per_side": fee_text,
                    "slippage_per_share_per_leg": slip_text,
                    "conditional_quote_economics": _quote_mean(groups[hold], fee, slip),
                    "chronological_quote_cash_scenario": _account(groups[hold], fee, slip),
                })
    report = {
        "contract": CONTRACT,
        "status": "HISTORICAL_SOURCE_QUOTES_HYPOTHETICAL_EXECUTION_ONLY",
        "original_v32_fingerprint": expected_fingerprint,
        "source_selected_pairs": 361,
        "source_original_weekly_abstentions": 50,
        "scenarios": results,
        "scenario_count": len(results),
        "all_selected_pairs_assumed_entered_if_cash_allows": True,
        "actual_options_native_volatility_signal_evaluated": False,
        "observation_clock_et": "10:00",
        "historical_1001_execution_fills": None,
        "historical_account_profitability": None,
        "independent_historical_valuation_marks": None,
        "account_causally_qualified": False,
        "source_outcome_censoring_retained": True,
        "provider_requests": 0,
        "broker_requests": 0,
    }
    report["fingerprint"] = _fingerprint(report)
    return report
