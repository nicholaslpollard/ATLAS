from __future__ import annotations

"""V27 historical-source quoted exit-horizon sensitivity, NOT executable fills.

Every 30..45-DTE entry candidate is frozen before any review is inspected.
For five PREDECLARED holding periods, match the exact same CALL/PUT contracts
at the original 10:00 review source, using the existing V26 local DTE,
two-sided spread, timestamp and displayed-size gates. Each holding-period
variant uses the SAME entry denominator; absent future prices remain UNKNOWN.
This is a quote-path diagnostic only, NOT a tradable SPY strategy, a filled
account, or evidence that an optimal holding period will work forward.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from packages.data.options_native_original_pair_diagnostic_v26 import (
    _decimal, _pair_observations, _stats, FEE_GRID,
)
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_review_sessions, _exit_at_time_query,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-spy-fixed-hold-original-quote-sweep-v27-research-only"
HOLD_SESSIONS = (1, 2, 3, 4, 5)
OPTION_MULTIPLIER_ASSUMPTION = Decimal(100)


@dataclass
class _HorizonResult:
    candidates: int = 0
    matched: int = 0
    no_review_source: int = 0
    missing_contract_or_quality: int = 0
    observation_only_returns: dict[str, list[float]] = field(
        default_factory=lambda: {fee: [] for fee in FEE_GRID}
    )
    by_year: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    review_states: Counter = field(default_factory=Counter)


def _summarize_horizon(state: _HorizonResult) -> dict[str, Any]:
    if state.candidates != (
        state.matched + state.no_review_source + state.missing_contract_or_quality
    ):
        raise ValueError("V27_FIXED_HORIZON_DENOMINATOR_DRIFT")
    if any(len(values) != state.matched for values in state.observation_only_returns.values()):
        raise ValueError("V27_FEE_GRID_DENOMINATOR_DRIFT")
    for year, counts in state.by_year.items():
        if counts["entry_pairs"] != (
            counts["matched"] + counts["no_review_source"]
            + counts["missing_contract_or_quality"]
        ):
            raise ValueError("V27_YEAR_DENOMINATOR_DRIFT")
    return {
        "eligible_entry_pair_count": state.candidates,
        "source_observed_same_contract_pair": state.matched,
        "unobserved_due_to_missing_review_source": state.no_review_source,
        "unobserved_due_to_contract_absence_or_quality": state.missing_contract_or_quality,
        "paired_observation_coverage_fraction": (
            round(state.matched / state.candidates, 6) if state.candidates else None
        ),
        "review_source_states_by_entry": dict(sorted(state.review_states.items())),
        "by_entry_year": {
            year: dict(sorted(counts.items()))
            for year, counts in sorted(state.by_year.items())
        },
        "hypothetical_10am_entry_ask_exit_bid_return_by_fee_per_contract_per_side": {
            fee: _stats(state.observation_only_returns[fee]) for fee in FEE_GRID
        },
    }


def evaluate_fixed_hold_quote_scenarios(
    entries: list[dict[str, Any]],
    read_source: Callable[[str, dict[str, Any]], tuple[str, Any]],
) -> dict[str, Any]:
    """Compute independent 1..5-session fixed-hold quote scenarios in one pass.

    No scenario chooses or changes its exit date from observed future return,
    substitutes a different option contract, assumes an unresolved trade was
    profitable, or drops a missing outcome from its original denominator.
    """
    results = {h: _HorizonResult() for h in HOLD_SESSIONS}
    unqualified_entry_states: Counter = Counter()
    no_pair_entries: Counter = Counter()
    source_reads = 0
    for record in entries:
        day = date.fromisoformat(record["date_et"])
        entry_state, raw = read_source(record["query_id"], record)
        source_reads += 1
        if raw is None:
            unqualified_entry_states[entry_state] += 1
            continue
        entry_pairs = _pair_observations(raw, day, entry=True)
        if not entry_pairs:
            no_pair_entries[str(day.year)] += 1
        review_days = _exit_review_sessions(day)
        for hold, review_day in zip(HOLD_SESSIONS, review_days, strict=True):
            horizon = results[hold]
            pair_count = len(entry_pairs)
            year = str(day.year)
            horizon.candidates += pair_count
            horizon.by_year[year]["entry_pairs"] += pair_count
            req = _exit_at_time_query(review_day)
            review_state, later = read_source(req["query_id"], req)
            source_reads += 1
            horizon.review_states[review_state] += 1
            if later is None:
                horizon.no_review_source += pair_count
                horizon.by_year[year]["no_review_source"] += pair_count
                continue
            exit_pairs = _pair_observations(later, review_day, entry=False)
            for key, at_entry in entry_pairs.items():
                at_exit = exit_pairs.get(key)
                if at_exit is None:
                    horizon.missing_contract_or_quality += 1
                    horizon.by_year[year]["missing_contract_or_quality"] += 1
                    continue
                entry_debit = at_entry["entry_ask"] * OPTION_MULTIPLIER_ASSUMPTION
                if entry_debit <= 0:
                    raise ValueError("V27_ENTRY_DEBIT_NONPOSITIVE")
                exit_credit = at_exit["exit_bid"] * OPTION_MULTIPLIER_ASSUMPTION
                horizon.matched += 1
                horizon.by_year[year]["matched"] += 1
                for fee in FEE_GRID:
                    estimated_fees = _decimal(fee) * 4  # 2 legs in + 2 legs out
                    return_fraction = (exit_credit - entry_debit - estimated_fees) / entry_debit
                    horizon.observation_only_returns[fee].append(float(return_fraction))
    payload = {
        "contract": CONTRACT,
        "status": "ORIGINAL_QUOTE_FIXED_HOLD_SCENARIO_DIAGNOSTIC_NOT_SIMULATION",
        "planned_weekly_entry_clocks": len(entries),
        "entry_source_states_unavailable": dict(sorted(unqualified_entry_states.items())),
        "source_qualified_but_no_eligible_pair_by_year": dict(sorted(no_pair_entries.items())),
        "fixed_holding_periods_in_XNYS_sessions": list(HOLD_SESSIONS),
        "scenarios": {str(h): _summarize_horizon(results[h]) for h in HOLD_SESSIONS},
        "source_read_uses": source_reads,
        "fee_per_contract_per_side_assumptions": list(FEE_GRID),
        "returns_conditioned_on_future_quote_observability": True,
        "each_scenario_includes_all_entry_eligible_pairs_in_original_denominator": True,
        "strike_selection": "ALL_ENTRY_ELIGIBLE_PAIRS_NOT_PIT_ATM_STRATEGY",
        "price_assumption": "original 10:00 ASK sum at entry / 10:00 BID sum on fixed review session",
        "no_historical_101_execution_or_fills_proven": True,
        "missing_quote_pnl": None,
        "combined_portfolio_equity": None,
        "historical_alpha_authority": False,
        "provider_requests": 0, "broker_requests": 0,
        "paper": False, "live": False,
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload
