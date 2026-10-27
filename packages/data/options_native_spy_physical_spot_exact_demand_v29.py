from __future__ import annotations

"""V29 one provisional SPY ATM identity per week and exact-contract EXIT demand.

The spot comes solely from the accepted native 09:59 regular-minute raw bar.
That bar's historical availability is UNKNOWN: selection is research-only,
NOT eligible for original SPY 10:01 pilot execution or fill/performance.

Fix identity in entry-time order: earliest expiration in 30..45 DTE,
same-expiry common strike nearest that day's physically observed spot,
lower strike tie breaker. ONLY AFTER identity is frozen validate its quotes;
never choose a different contract because the selected quote is poor, or
because it happens to be observable on subsequent exit review days.

The exact-contract requests preview only MISSING original quote rights at five
originally frozen review sessions. No provider requests, no writes to source,
no fabricated fills, no dynamic-exit optimization or protected 2026 reads.
"""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_original_pair_diagnostic_v26 import (
    _decimal, _key, _pair_observations, PairDiagnosticError,
)
from packages.data.options_native_exit_coverage_attribution_v28 import (
    _categorize, _review_index,
)
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_at_time_query, _exit_review_sessions,
)
from packages.strategies.options_native_pilot_v1_contract import (
    SPECIFICATION_FINGERPRINT, MIN_DTE, MAX_DTE,
)
from packages.data.options_native_spy_development_clock_coverage_v1 import (
    CONTRACT as SPOT_COVERAGE_CONTRACT, frozen_clock_demand,
)

CONTRACT = "atlas-spy-physical-spot-selected-exact-contract-demand-v29"
MAX_CASES = 411
MAX_MISSING_RIGHT_QUERIES = MAX_CASES * 5 * 2
SOURCE_PREVIEW = "EXACT_CONTRACT_EXIT_REQUEST_PREVIEW_NO_PROVIDER_AUTHORITY"


def _eligible_identity_pair(
    original: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    decision: date,
    spot: Decimal,
) -> tuple[tuple[str, str] | None, str]:
    """Identity first, quality second, matching the frozen selection order."""
    by_expiry: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"call": set(), "put": set()}
    )
    seen: set[tuple[str, str, str]] = set()
    for quote in original:
        key = _key(quote)
        if key in seen:
            raise PairDiagnosticError("V29_DUPLICATE_ENTRY_CONTRACT")
        seen.add(key)
        dte = (date.fromisoformat(key[0]) - decision).days
        if MIN_DTE <= dte <= MAX_DTE:
            by_expiry[key[0]][key[2]].add(key[1])
    if not by_expiry:
        return None, "NO_EXPIRATION_IN_BAND"
    expiry = min(by_expiry)
    common = by_expiry[expiry]["call"] & by_expiry[expiry]["put"]
    if not common:
        return None, "EARLIEST_EXPIRATION_NO_COMMON_STRIKE"
    strike = min(common, key=lambda raw: (abs(Decimal(raw) - spot), Decimal(raw)))
    return (expiry, strike), "IDENTITY_SELECTED_FROM_ORIGINAL_ENTRY_ROSTER"


def _spot_lookup(stock_report: dict[str, Any]) -> dict[str, dict[str, str | None]]:
    demand, _ = frozen_clock_demand()
    if (stock_report.get("contract") != SPOT_COVERAGE_CONTRACT
            or stock_report.get("specification_fingerprint") != SPECIFICATION_FINGERPRINT
            or stock_report.get("frozen_plan_fingerprint") != demand["plan_fingerprint"]
            or stock_report.get("target_weekly_cases") != MAX_CASES
            or stock_report.get("historical_publication_and_adjustment_qualified") is not False
            or stock_report.get("pilot_input_acceptance") is not False
            or stock_report.get("protected_return_rows_read") != 0
            or stock_report.get("option_outcomes_read") != 0):
        raise PairDiagnosticError("V29_PHYSICAL_SPOT_REPORT_SCOPE_UNQUALIFIED")
    cases = stock_report["cases"]
    observations = stock_report["observations"]
    if (not isinstance(cases, list) or len(cases) != MAX_CASES
            or not isinstance(observations, dict)):
        raise PairDiagnosticError("V29_SPOT_CASE_SCHEMA_OR_COUNT_DRIFT")
    expected = {r["decision_date"]: r for r in demand["cases"]}
    resolved: dict[str, dict[str, str | None]] = {}
    for case in cases:
        day = case["decision_date"]
        pinned = expected.get(day)
        if (pinned is None or day in resolved
                or case["spot_key"] != pinned["spot"]
                or case["decision_utc"] != pinned["decision_utc"]
                or case["quote_query_fingerprint"] != pinned["quote_query_fingerprint"]
                or case.get("historical_input_accepted") is not False):
            raise PairDiagnosticError("V29_SPOT_CASE_FROZEN_CLOCK_DRIFT")
        observation = observations.get(case["spot_key"])
        if observation is None or not isinstance(observation, dict):
            raise PairDiagnosticError("V29_SPOT_MINUTE_SOURCE_ENTRY_OMITTED")
        spot = observation.get("raw_close")
        if spot is not None:
            _decimal(spot)
            if _decimal(spot) <= 0:
                raise PairDiagnosticError("V29_SPOT_PRICE_NONPOSITIVE")
            if observation.get("status") != "RAW_MINUTE_PRESENT":
                raise PairDiagnosticError("V29_SPOT_SOURCE_STATUS_INVALID")
        resolved[day] = {
            "raw_spot": spot,
            "minute_unit_id": observation.get("source_unit_id"),
            "minute_source_sha256": observation.get("canonical_sha256"),
            "historical_available_at_utc": observation.get("historical_available_at_utc"),
        }
        if resolved[day]["historical_available_at_utc"] is not None:
            raise PairDiagnosticError("V29_PHYSICAL_REPORT_MUST_NOT_INVENT_AVAILABILITY")
    if len(resolved) != MAX_CASES or set(resolved) != set(expected):
        raise PairDiagnosticError("V29_SPOT_DEMAND_INCOMPLETE")
    return resolved


def evaluate_spot_selected_exact_contract_demand(
    entries: list[dict[str, Any]],
    read_source: Callable[[str, dict[str, Any]], tuple[str, Any]],
    *,
    stock_report: dict[str, Any],
) -> dict[str, Any]:
    spots = _spot_lookup(stock_report)
    if len(entries) != MAX_CASES or len({r["date_et"] for r in entries}) != MAX_CASES:
        raise PairDiagnosticError("V29_ENTRIES_NOT_FROZEN_411")
    counts = Counter()
    review_outcomes = Counter()
    by_entry_year: dict[str, Counter] = defaultdict(Counter)
    selected_by_year: dict[str, int] = defaultdict(int)
    missing_requests: dict[str, dict[str, Any]] = {}
    cases = []
    for record in sorted(entries, key=lambda row: row["date_et"]):
        day = date.fromisoformat(record["date_et"])
        label = day.isoformat()
        year = str(day.year)
        if label not in spots:
            raise PairDiagnosticError("V29_ENTRY_DATE_NOT_IN_STOCK_PLAN")
        entry_state, original = read_source(record["query_id"], record)
        reason = None
        selection = None
        if original is None:
            reason = "ORIGINAL_ENTRY_SOURCE_UNAVAILABLE:" + entry_state
        elif spots[label]["raw_spot"] is None:
            reason = "PHYSICAL_0959_SPOT_MISSING"
        else:
            selection, reason = _eligible_identity_pair(
                original, day, _decimal(spots[label]["raw_spot"])
            )
            if selection is not None:
                observed_qualified = _pair_observations(original, day, entry=True)
                if selection not in observed_qualified:
                    reason = "SELECTED_ENTRY_PAIR_FAILED_QUOTE_QUALITY"
        if selection is None or reason != "IDENTITY_SELECTED_FROM_ORIGINAL_ENTRY_ROSTER":
            counts["ABSTAIN"] += 1
            by_entry_year[year][reason] += 1
            cases.append({
                "date_et": label, "status": "RESEARCH_IDENTITY_NOT_AVAILABLE",
                "reason": reason, "selected_expiration": (
                    selection[0] if selection else None
                ), "selected_strike": selection[1] if selection else None,
                "raw_0959_spot": spots[label]["raw_spot"],
                "review_results": [],
            })
            continue
        counts["PROVISIONAL_SELECTED_PAIR"] += 1
        selected_by_year[year] += 1
        review_results = []
        for hold, exit_day in enumerate(_exit_review_sessions(day), 1):
            req = _exit_at_time_query(exit_day)
            state, later = read_source(req["query_id"], req)
            index = _review_index(later) if later is not None else {}
            reason, individual_quality = (
                _categorize(selection, exit_day, index)
                if later is not None else ("NO_REVIEW_SOURCE", ())
            )
            review_outcomes[reason] += 1
            demand_rights = []
            if later is not None and reason not in {"EXPIRED_AT_REVIEW"}:
                for right in ("call", "put"):
                    if (*selection, right) in index:
                        continue
                    params = {
                        "symbol": "SPY", "date_et": exit_day.isoformat(),
                        "time_of_day_et": "10:00:00.000",
                        "expiration": selection[0],
                        "strike": selection[1],
                        "right": right,
                    }
                    # This key is LOCAL original demand identity, not a provider
                    # promise or retrospective price/quote acceptance.
                    query_id = _fingerprint({
                        "provider": "thetadata", "method": "option_at_time_quote",
                        "kwargs": params,
                    })
                    existing = missing_requests.get(query_id)
                    candidate = {
                        "query_id": query_id, "sdk_method": "option_at_time_quote",
                        "sdk_kwargs": params, "request_state": SOURCE_PREVIEW,
                        "case_date": label, "hold_sessions": hold,
                        "source_original_exit_query_id": req["query_id"],
                        "entry_spot_unqualified": True,
                        "source_response_absence_not_market_absence": True,
                    }
                    if existing is None:
                        missing_requests[query_id] = candidate
                    demand_rights.append(right)
            review_results.append({
                "hold_sessions": hold, "session_et": exit_day.isoformat(),
                "original_exit_source_state": state,
                "reason": reason, "individual_quote_quality_reasons": list(individual_quality),
                "missing_exact_rights": demand_rights,
                "historical_fill_event": None,
            })
        cases.append({
            "date_et": label, "status": "PHYSICAL_SPOT_PROVISIONAL_PAIR_ONLY",
            "reason": "PIT_SPOT_AVAILABILITY_OI_IV_RATE_DIVIDEND_NOT_QUALIFIED",
            "raw_0959_spot": spots[label]["raw_spot"],
            "spot_native_unit_id": spots[label]["minute_unit_id"],
            "spot_native_unit_sha256": spots[label]["minute_source_sha256"],
            "selected_expiration": selection[0], "selected_strike": selection[1],
            "entry_original_query_id": record["query_id"],
            "selection_used_future_prices": False,
            "review_results": review_results,
        })
    if sum(counts.values()) != MAX_CASES:
        raise PairDiagnosticError("V29_ENTRY_DECISION_COUNT_DRIFT")
    ordered_requests = sorted(
        missing_requests.values(),
        key=lambda x: (x["sdk_kwargs"]["date_et"], x["sdk_kwargs"]["expiration"],
                       Decimal(x["sdk_kwargs"]["strike"]), x["sdk_kwargs"]["right"]),
    )
    if len(ordered_requests) > MAX_MISSING_RIGHT_QUERIES:
        raise PairDiagnosticError("V29_EXACT_RIGHT_DEMAND_EXCEEDS_FROZEN_LIMIT")
    if sum(review_outcomes.values()) != 5 * counts["PROVISIONAL_SELECTED_PAIR"]:
        raise PairDiagnosticError("V29_FIVE_SESSION_REVIEW_DENOMINATOR_DRIFT")
    result = {
        "contract": CONTRACT,
        "status": "ORIGINAL_PRICE_SPOT_PROVISIONAL_IDENTITY_AND_EXACT_SOURCE_NEEDS_ONLY",
        "pilot_specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "original_entry_clocks": MAX_CASES,
        "provisional_entry_pairs": counts["PROVISIONAL_SELECTED_PAIR"],
        "abstained_weekly_clocks": counts["ABSTAIN"],
        "by_entry_year": {y: dict(sorted(v.items())) for y, v in sorted(by_entry_year.items())},
        "provisional_selections_by_year": dict(sorted(selected_by_year.items())),
        "selected_pair_review_source_states": dict(sorted(review_outcomes.items())),
        "selected_pair_five_session_review_uses": sum(review_outcomes.values()),
        "missing_exact_contract_right_requests": ordered_requests,
        "missing_exact_contract_right_request_count": len(ordered_requests),
        "source_quote_selection_used_future_prices": False,
        "entry_physical_spot_historical_availability_qualified": False,
        "entry_option_identity_roster_completeness_proven": False,
        "pilot_variance_signal_computed": False,
        "historical_options_fill_authority": False,
        "option_account_equity": None,
        "original_quotes_replaced": False,
        "provider_requests": 0, "broker_requests": 0,
        "protected_2026_outcomes_read": 0, "historical_profitability_proven": False,
        "cases": cases,
    }
    result["fingerprint"] = _fingerprint(result)
    return result
