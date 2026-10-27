from __future__ import annotations

"""V28 source-only attribution for missing exact SPY option exit quotes.

All five holding periods retain the same V27 entry-eligible pair denominator.
No provider/broker calls, outcome optimization, invented fills, or strategy
promotion. Absent rights are *only* proved absent from the retained response:
the underlying reason (SDK strike_range, historical chain incompleteness,
actual quote absence, etc.) cannot be inferred from this original archive.
"""

from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_original_pair_diagnostic_v26 import (
    _key, _decimal, _pair_observations, _validated_quote,
    EASTERN, MAX_AGE_SECONDS, MAX_LEG_SKEW_SECONDS, MAX_SPREAD_TO_MID,
    PairDiagnosticError,
)
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_at_time_query, _exit_review_sessions,
)
from packages.simulation.options_native_fixed_hold_quote_sweep_v27 import (
    HOLD_SESSIONS,
)

CONTRACT = "atlas-spy-exact-contract-exit-coverage-attribution-v28-source-only"
REASONS = (
    "NO_REVIEW_SOURCE", "EXPIRED_AT_REVIEW", "BOTH_RIGHTS_ABSENT",
    "CALL_ABSENT", "PUT_ABSENT", "BOTH_QUOTES_REJECTED",
    "CALL_QUOTE_REJECTED", "PUT_QUOTE_REJECTED", "PAIR_CLOCK_SKEW", "MATCHED",
)
QUALITY = ("STALE", "NO_TWO_SIDED_PRICE", "NO_DISPLAY_SIZE", "WIDE_SPREAD", "PASS")


def _review_index(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    result = {}
    for row in rows:
        key = _key(row)
        if key in result:
            raise PairDiagnosticError("V28_DUPLICATE_ORIGINAL_REVIEW_CONTRACT")
        result[key] = row
    return result


def _quality_reason(row: dict[str, Any], day: date) -> str:
    # Structural validation stays delegated to V26. Invalid source clocks,
    # crossed markets, malformed identities etc. are NOT tolerated or
    # converted into soft economic filters.
    validated = _validated_quote(row, day)
    if validated is not None:
        return "PASS"
    stamp = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
    cutoff = datetime.combine(day, datetime.strptime("10:00:00", "%H:%M:%S").time(), EASTERN)
    if (cutoff - stamp.astimezone(EASTERN)).total_seconds() > MAX_AGE_SECONDS:
        return "STALE"
    bid, ask = _decimal(row["bid"]), _decimal(row["ask"])
    if bid <= 0 or ask <= 0:
        return "NO_TWO_SIDED_PRICE"
    if (type(row["bid_size"]) is not int or type(row["ask_size"]) is not int
            or row["bid_size"] < 1 or row["ask_size"] < 1):
        return "NO_DISPLAY_SIZE"
    if (ask - bid) / ((ask + bid) / 2) > MAX_SPREAD_TO_MID:
        return "WIDE_SPREAD"
    raise PairDiagnosticError("V28_QUALITY_CLASSIFICATION_DRIFT")


def _categorize(
    key: tuple[str, str],
    day: date,
    raw_index: dict[tuple[str, str, str], dict[str, Any]],
) -> tuple[str, tuple[str, ...]]:
    expiry = date.fromisoformat(key[0])
    if expiry < day:
        return "EXPIRED_AT_REVIEW", ()
    call = raw_index.get((*key, "call"))
    put = raw_index.get((*key, "put"))
    if call is None and put is None:
        return "BOTH_RIGHTS_ABSENT", ()
    if call is None:
        return "CALL_ABSENT", ()
    if put is None:
        return "PUT_ABSENT", ()
    cq, pq = _quality_reason(call, day), _quality_reason(put, day)
    failures = tuple(q for q in (cq, pq) if q != "PASS")
    if cq != "PASS" and pq != "PASS":
        return "BOTH_QUOTES_REJECTED", failures
    if cq != "PASS":
        return "CALL_QUOTE_REJECTED", failures
    if pq != "PASS":
        return "PUT_QUOTE_REJECTED", failures
    call_checked, put_checked = _validated_quote(call, day), _validated_quote(put, day)
    if call_checked is None or put_checked is None:
        raise PairDiagnosticError("V28_V26_QUALITY_GATE_CONTRADICTION")
    if abs((call_checked["clock"] - put_checked["clock"]).total_seconds()) > MAX_LEG_SKEW_SECONDS:
        return "PAIR_CLOCK_SKEW", ()
    return "MATCHED", ()


def _full_reason_counts(
    entry_pairs: dict[tuple[str, str], dict[str, Any]],
    later: Any,
    day: date,
) -> tuple[Counter, Counter]:
    if later is None:
        return Counter({"NO_REVIEW_SOURCE": len(entry_pairs)}), Counter()
    raw_index = _review_index(later)
    # Invariant against V26's actual qualified-pair gate. The root-cause
    # breakdown is EXPLANATORY ONLY, never a second relaxed acceptance path.
    reference = _pair_observations(later, day, entry=False)
    reasons, quality = Counter(), Counter()
    for key in entry_pairs:
        category, failures = _categorize(key, day, raw_index)
        if (category == "MATCHED") != (key in reference):
            raise PairDiagnosticError("V28_MATCH_DISAGREES_WITH_V26_ACCEPTANCE")
        reasons[category] += 1
        quality.update(failures)
    return reasons, quality


def evaluate_exit_coverage_root_causes(
    entries: list[dict[str, Any]],
    read_source: Callable[[str, dict[str, Any]], tuple[str, Any]],
) -> dict[str, Any]:
    """A single source-only read pass, five fixed predetermined exit horizons."""
    by_hold: dict[int, Counter] = {h: Counter() for h in HOLD_SESSIONS}
    quality_by_hold: dict[int, Counter] = {h: Counter() for h in HOLD_SESSIONS}
    by_year: dict[int, dict[str, Counter]] = {
        h: defaultdict(Counter) for h in HOLD_SESSIONS
    }
    review_states: dict[int, Counter] = {h: Counter() for h in HOLD_SESSIONS}
    missing_entry_state: Counter = Counter()
    total_source_read_uses = 0
    total_weekly_entry_pairs = 0
    unique_missing_contracts: set[tuple[str, str, str, str]] = set()
    for record in entries:
        day = date.fromisoformat(record["date_et"])
        entry_state, source = read_source(record["query_id"], record)
        total_source_read_uses += 1
        if source is None:
            missing_entry_state[entry_state] += 1
            continue
        entry_pairs = _pair_observations(source, day, entry=True)
        total_weekly_entry_pairs += len(entry_pairs)
        review_days = _exit_review_sessions(day)
        for hold, later_day in zip(HOLD_SESSIONS, review_days, strict=True):
            request = _exit_at_time_query(later_day)
            state, rows = read_source(request["query_id"], request)
            total_source_read_uses += 1
            review_states[hold][state] += 1
            breakdown, quality = _full_reason_counts(entry_pairs, rows, later_day)
            by_hold[hold].update(breakdown)
            quality_by_hold[hold].update(quality)
            by_year[hold][str(day.year)].update(breakdown)
            # Exact missing contract identities are diagnostic demand leads,
            # not authorized SDK acquisitions or guaranteed provider inventory.
            if rows is not None:
                raw_index = _review_index(rows)
                for key in entry_pairs:
                    if date.fromisoformat(key[0]) < later_day:
                        continue
                    for right in ("call", "put"):
                        if (*key, right) not in raw_index:
                            unique_missing_contracts.add(
                                (later_day.isoformat(), key[0], key[1], right)
                            )
    scenarios = {}
    for hold in HOLD_SESSIONS:
        counter = by_hold[hold]
        for reason in counter:
            if reason not in REASONS:
                raise PairDiagnosticError("V28_UNCLASSIFIED_EXIT_STATUS")
        if sum(counter.values()) != total_weekly_entry_pairs:
            raise PairDiagnosticError("V28_ENTRY_COHORT_DENOMINATOR_DRIFT")
        year_counts = by_year[hold]
        if sum(sum(v.values()) for v in year_counts.values()) != total_weekly_entry_pairs:
            raise PairDiagnosticError("V28_ENTRY_YEAR_DENOMINATOR_DRIFT")
        scenarios[str(hold)] = {
            "eligible_entry_pairs": total_weekly_entry_pairs,
            "exact_contract_pair_match": counter["MATCHED"],
            "reasons": {reason: counter[reason] for reason in REASONS},
            "quote_quality_rejection_reasons_individual_legs": dict(
                sorted(quality_by_hold[hold].items())
            ),
            "by_entry_year": {
                year: {reason: counts[reason] for reason in REASONS}
                for year, counts in sorted(year_counts.items())
            },
            "review_original_source_states": dict(sorted(review_states[hold].items())),
            "original_pair_coverage_fraction": (
                round(counter["MATCHED"] / total_weekly_entry_pairs, 6)
                if total_weekly_entry_pairs else None
            ),
        }
    report = {
        "contract": CONTRACT,
        "status": "SOURCE_ONLY_EXIT_ATTRITION_EXPLANATION_NOT_HISTORICAL_ACCOUNT",
        "original_weekly_entry_requests": len(entries),
        "eligible_entry_pair_denominator_each_horizon": total_weekly_entry_pairs,
        "unavailable_entry_source_states": dict(sorted(missing_entry_state.items())),
        "fixed_holding_periods": list(HOLD_SESSIONS),
        "scenarios": scenarios,
        "distinct_absent_original_contract_rights_across_all_exit_dates": len(unique_missing_contracts),
        "missing_rights_are_absent_from_retained_response_not_proven_absent_from_market": True,
        "source_read_uses": total_source_read_uses,
        "original_source_hashes_verified_by_v26": True,
        "provider_requests": 0, "broker_requests": 0,
        "trading_fills": 0, "historical_pnl": None,
        "strategy_promotion": False, "paper": False, "live": False,
    }
    report["fingerprint"] = _fingerprint(report)
    return report
