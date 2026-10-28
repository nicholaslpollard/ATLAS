from __future__ import annotations

"""V32 offline SPY historical quote observation tape, NOT trade/account replay.

Joins one already selected SPY CALL+PUT original entry identity per V29 week
with original V24 broad exit sources and independently archived V30 exact
contract RIGHT responses. All original SHA/receipt gates stay authoritative.
Absence/unqualified price -> NULL observation, never a fabricated fill.
Every selected entry stays in each of five fixed, predetermined denominators.
No historical-provider/broker requests; no outcome-driven pair reselection.
"""

from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
import json
from typing import Any, Callable
import zlib

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_original_pair_diagnostic_v26 import (
    _decimal, _key, _pair_observations, PairDiagnosticError,
)
from packages.data.options_native_exit_coverage_attribution_v28 import _review_index
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_review_sessions, _exit_at_time_query,
)
from packages.data.options_native_spy_physical_spot_exact_demand_v29 import (
    CONTRACT as V29_CONTRACT,
)
from packages.data.options_native_spy_exact_exit_source_campaign_v30 import (
    MAX_RAW, _path, _read_receipt, _state,
)
from packages.simulation.options_native_fixed_hold_quote_sweep_v27 import HOLD_SESSIONS
from packages.strategies.options_native_pilot_v1_contract import SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-spy-original-plus-exact-exit-quote-tape-v32"
REVIEW_STATES = frozenset({
    "ORIGINAL_PAIR_QUOTE_MATCH",
    "EXACT_SOURCE_RECOVERED_PAIR_QUOTE_MATCH",
    "MISSING_ORIGINAL_REVIEW_SOURCE",
    "BOTH_OPTION_RIGHTS_NOT_AVAILABLE",
    "ONE_OPTION_RIGHT_NOT_AVAILABLE",
    "PRESENT_QUOTES_UNQUALIFIED",
})
EXACT_ARCHIVED = "RAW_ARCHIVED_EXACT_CONTRACT_DIAGNOSTIC"


def _canonical_identity(expiry: str, strike: str, right: str) -> tuple[str, str, str]:
    return expiry, str(_decimal(strike).normalize()), right


def _exact_quote(
    settings: Any,
    request: dict[str, Any],
    fingerprint: str,
) -> tuple[str, dict[str, Any] | None]:
    """Only a terminal, SHA-verifiable original V30 source qualifies."""
    state = _state(settings, request, fingerprint)
    if state != EXACT_ARCHIVED:
        return state, None
    receipt = _read_receipt(settings, request, fingerprint, "terminal")
    if receipt is None or not isinstance(receipt.get("archive"), dict):
        raise PairDiagnosticError("V32_ARCHIVED_EXACT_RECEIPT_MISSING")
    archive = receipt["archive"]
    raw_compressed = _path(settings, request["query_id"], "sources").read_bytes()
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        raw = decoder.decompress(raw_compressed, MAX_RAW + 1)
    except zlib.error as exc:
        raise PairDiagnosticError("V32_EXACT_SOURCE_COMPRESSION_UNQUALIFIED") from exc
    if (not decoder.eof or decoder.unconsumed_tail or decoder.unused_data
            or len(raw) != archive["original_bytes"]):
        raise PairDiagnosticError("V32_EXACT_SOURCE_BOUNDS_UNQUALIFIED")
    try:
        rows = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise PairDiagnosticError("V32_EXACT_SOURCE_JSON_UNQUALIFIED") from exc
    if not isinstance(rows, list) or len(rows) != archive["observed_rows"]:
        raise PairDiagnosticError("V32_EXACT_SOURCE_ROW_COUNT_DRIFT")
    query = request["sdk_kwargs"]
    identity = _canonical_identity(
        query["expiration"], query["strike"], query["right"],
    )
    matched = [r for r in rows if _key(r) == identity]
    if len(matched) != 1:
        raise PairDiagnosticError("V32_EXACT_SOURCE_IDENTITY_MISSING_OR_DUPLICATED")
    return state, matched[0]


def evaluate_original_plus_exact_option_quote_tape(
    entries: list[dict[str, Any]],
    read_source: Callable[[str, dict[str, Any]], tuple[str, Any]],
    *,
    settings: Any,
    plan: dict[str, Any],
) -> dict[str, Any]:
    """For 411 weekly entries, join only previously committed quote sources."""
    if (plan.get("contract") != V29_CONTRACT
            or plan.get("pilot_specification_fingerprint") != SPECIFICATION_FINGERPRINT
            or plan.get("original_entry_clocks") != 411
            or plan.get("source_quote_selection_used_future_prices") is not False
            or plan.get("entry_physical_spot_historical_availability_qualified") is not False
            or len(entries) != 411):
        raise PairDiagnosticError("V32_FROZEN_V29_ORIGINAL_SCOPE_DRIFT")
    by_entry_day = {case["date_et"]: case for case in plan["cases"]}
    if len(by_entry_day) != 411:
        raise PairDiagnosticError("V32_V29_WEEKLY_CASE_COUNT_DRIFT")
    by_query = {r["query_id"]: r for r in plan["missing_exact_contract_right_requests"]}
    if len(by_query) != len(plan["missing_exact_contract_right_requests"]):
        raise PairDiagnosticError("V32_V29_EXACT_RIGHT_IDENTITY_DUPLICATED")
    counters = {str(i): Counter() for i in HOLD_SESSIONS}
    terminal_reasons = Counter()
    observations = []
    selected = 0
    entered_absent = 0
    exact_cache: dict[str, tuple[str, dict[str, Any] | None]] = {}
    for entry in sorted(entries, key=lambda e: e["date_et"]):
        day = date.fromisoformat(entry["date_et"])
        case = by_entry_day.get(day.isoformat())
        if case is None:
            raise PairDiagnosticError("V32_NOT_AN_ORIGINAL_WEEKLY_ENTRY")
        if case["status"] != "PHYSICAL_SPOT_PROVISIONAL_PAIR_ONLY":
            entered_absent += 1
            continue
        selected += 1
        identity = (
            case["selected_expiration"],
            str(_decimal(case["selected_strike"]).normalize()),
        )
        state, entry_source = read_source(entry["query_id"], entry)
        if entry_source is None:
            raise PairDiagnosticError("V32_PRESELECTED_ENTRY_SOURCE_NOW_MISSING")
        entry_pair = _pair_observations(entry_source, day, entry=True).get(identity)
        if entry_pair is None:
            raise PairDiagnosticError("V32_ORIGINAL_ENTRY_PAIR_QUALITY_CHANGED")
        reviews = case["review_results"]
        if len(reviews) != 5:
            raise PairDiagnosticError("V32_SELECTED_ENTRY_REVIEW_COUNT_DRIFT")
        for i, later_day in enumerate(_exit_review_sessions(day), 1):
            review = reviews[i - 1]
            if (review["hold_sessions"] != i
                    or review["session_et"] != later_day.isoformat()):
                raise PairDiagnosticError("V32_FROZEN_REVIEW_DAY_DRIFT")
            query = _exit_at_time_query(later_day)
            original_state, original = read_source(query["query_id"], query)
            original_by_key = _review_index(original) if original is not None else {}
            source_qids = []
            recovered = []
            demand_state = {}
            for right in ("call", "put"):
                contract = (*identity, right)
                if contract in original_by_key:
                    continue
                if right not in review["missing_exact_rights"]:
                    continue
                requested = {
                    "symbol": "SPY",
                    "date_et": later_day.isoformat(),
                    "time_of_day_et": "10:00:00.000",
                    "expiration": identity[0],
                    "strike": case["selected_strike"],
                    "right": right,
                }
                qid = _fingerprint({
                    "provider": "thetadata",
                    "method": "option_at_time_quote",
                    "kwargs": requested,
                })
                row = by_query.get(qid)
                if row is None or row["sdk_kwargs"] != requested:
                    raise PairDiagnosticError("V32_EXACT_MISSING_RIGHT_REQUEST_DRIFT")
                if qid not in exact_cache:
                    exact_cache[qid] = _exact_quote(settings, row, plan["fingerprint"])
                exact_state, quote = exact_cache[qid]
                demand_state[right] = exact_state
                if quote is not None:
                    source_qids.append(qid)
                    recovered.append(quote)
            if original is None and recovered:
                raise PairDiagnosticError("V32_RECOVERY_WHEN_ORIGINAL_SOURCE_UNAVAILABLE")
            rows = (list(original) if original is not None else []) + recovered
            complete = _pair_observations(rows, later_day, entry=False).get(identity)
            original_match = (
                _pair_observations(original, later_day, entry=False).get(identity)
                if original is not None else None
            )
            if original is None:
                status = "MISSING_ORIGINAL_REVIEW_SOURCE"
            elif complete is not None:
                status = ("ORIGINAL_PAIR_QUOTE_MATCH" if original_match is not None
                          else "EXACT_SOURCE_RECOVERED_PAIR_QUOTE_MATCH")
            else:
                present = sum(
                    (*identity, side) in original_by_key or any(
                        _key(r) == (*identity, side) for r in recovered
                    )
                    for side in ("call", "put")
                )
                status = (
                    "BOTH_OPTION_RIGHTS_NOT_AVAILABLE" if present == 0
                    else "ONE_OPTION_RIGHT_NOT_AVAILABLE" if present == 1
                    else "PRESENT_QUOTES_UNQUALIFIED"
                )
            if status not in REVIEW_STATES:
                raise PairDiagnosticError("V32_EXIT_STATE_UNKNOWN")
            counters[str(i)][status] += 1
            terminal_reasons.update(demand_state.values())
            observations.append({
                "entry_date_et": day.isoformat(),
                "review_date_et": later_day.isoformat(),
                "hold_xnys_sessions": i,
                "expiration": identity[0],
                "strike": case["selected_strike"],
                "entry_source_query_id": entry["query_id"],
                "original_review_source_query_id": query["query_id"],
                "original_source_state": original_state,
                "exact_source_query_ids": source_qids,
                "requested_right_source_states": demand_state,
                "quote_match_state": status,
                "original_100share_two_leg_entry_ask": str(
                    entry_pair["entry_ask"] * Decimal(100)
                ),
                "observed_100share_two_leg_exit_bid": (
                    str(complete["exit_bid"] * Decimal(100))
                    if complete is not None else None
                ),
                "quote_price_observation_only": True,
                "hypothetical_100share_pair_fee_per_0_65_side": "2.60",
                "historical_execution_fill": None,
                "historical_strategy_profit": None,
            })
    if selected != plan["provisional_entry_pairs"] or entered_absent != plan["abstained_weekly_clocks"]:
        raise PairDiagnosticError("V32_PRESERVED_SELECTED_COHORT_DRIFT")
    if len(observations) != selected * 5:
        raise PairDiagnosticError("V32_FIVE_HORIZON_COHORT_COUNT_DRIFT")
    result_by_hold = {}
    for hold in HOLD_SESSIONS:
        label = str(hold)
        cnt = counters[label]
        if sum(cnt.values()) != selected:
            raise PairDiagnosticError("V32_FIXED_HORIZON_DENOMINATOR_DRIFT")
        original = cnt["ORIGINAL_PAIR_QUOTE_MATCH"]
        gained = cnt["EXACT_SOURCE_RECOVERED_PAIR_QUOTE_MATCH"]
        result_by_hold[label] = {
            "selected_entry_pair_denominator": selected,
            "original_qualified_pair_matches": original,
            "newly_matched_using_exact_source": gained,
            "total_qualified_quote_matches": original + gained,
            "missing_or_unqualified_after_recovery": selected - original - gained,
            "coverage_fraction": (
                round((original + gained) / selected, 6) if selected else None
            ),
            "states": {s: cnt[s] for s in sorted(REVIEW_STATES)},
        }
    result = {
        "contract": CONTRACT,
        "status": "ORIGINAL_AND_EXACT_QUOTE_EVIDENCE_TAPE_NO_HISTORICAL_FILL",
        "source_plan_fingerprint": plan["fingerprint"],
        "original_frozen_weekly_entries": 411,
        "provisionally_selected_original_weekly_pairs": selected,
        "original_weekly_abstentions": entered_absent,
        "hold_sessions": list(HOLD_SESSIONS),
        "by_exit_horizon": result_by_hold,
        "exact_requested_right_terminal_states_encountered": dict(
            sorted(terminal_reasons.items())
        ),
        "quote_review_observations": len(observations),
        "observations": observations,
        "original_source_archives_unmodified": True,
        "historical_stock_spot_pit_availability_proven": False,
        "original_option_contract_roster_completeness_proven": False,
        "historical_101_order_fills": None,
        "historical_account_profitability": None,
        "simulator_ready": False,
        "provider_requests": 0, "broker_requests": 0,
        "protected_2026_outcomes_read": 0,
    }
    result["fingerprint"] = _fingerprint(result)
    return result
