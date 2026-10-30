from __future__ import annotations

"""V49 immutable OFFLINE options opportunity trace and clock/price diagnostics.

No changed entry, exit, original quote gate, executable order, provider call,
broker call, performance claim or parameter optimization is authorized.
"""

from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

CONTRACT = "atlas-options-simulator-opportunity-trace-and-clock-sensitivity-v49"
PINNED = {
    "v45": ("atlas-spy-unified-two-clock-original-plus-alternate-v45",
            "450da4ee779aad96b6656e1d7a03435bf3521875c72ebca6f69b845a7205bd5e"),
    "v46": ("atlas-spy-provisional-variance-economics-v46",
            "966a6155d57423cd680a26a84bc5bf85e6d02b1f0f06015037612659ef0cc2f7"),
    "v47": ("atlas-spy-v47-exploratory-fixed-hold-quote-economics",
            "9eea1abc12eca482d967cad172a9a2851b7c8cfc0879a7f97104d4bed01e855d"),
}
CLOCKS = ("pretrade_0959", "execution_1001")
RIGHTS = ("call", "put")
SKEW_SECONDS = (1, 3)
PRICE_DRIFT_PCT = (Decimal("0.5"), Decimal("1"), Decimal("2"))
LONG = "ROBUST_HYPOTHETICAL_LONG"
PASS = "TWO_CLOCK_SOURCE_QUALITY_PASSES"
MAX_AGE_SECONDS = Decimal("30")


class TraceError(ValueError):
    pass


def fingerprint(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str) + "\n"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _verified(report: dict, version: str) -> None:
    contract, expected = PINNED[version]
    if (not isinstance(report, dict) or report.get("contract") != contract
            or report.get("fingerprint") != expected
            or fingerprint({k: v for k, v in report.items() if k != "fingerprint"}) != expected):
        raise TraceError(f"V49_{version.upper()}_INPUT_FINGERPRINT_OR_CONTRACT_DRIFT")


def _number(value: Any) -> Decimal | None:
    try:
        n = Decimal(str(value))
        return n if n.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _timestamp(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.utcoffset() is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


def clock_gate(pair: dict | None, clock: str, *, max_skew_seconds: int) -> dict:
    """Compare SAME-clock call/put timestamp alignment, not put-vs-call prices."""
    if max_skew_seconds not in SKEW_SECONDS or clock not in CLOCKS:
        raise TraceError("V49_UNREGISTERED_CLOCK_POLICY")
    reasons = []
    if not isinstance(pair, dict):
        return {"status": "UNKNOWN_NO_OBSERVED_PAIR", "pass": None,
                "reasons": ["NO_QUALIFIED_PAIR"], "measured_skew_seconds": None}
    expected = "PRETRADE_QUOTE_0959_PASSES" if clock == "pretrade_0959" else "QUOTE_MICROSTRUCTURE_PASSES"
    for right in RIGHTS:
        leg = pair.get(right, {})
        if not isinstance(leg, dict) or leg.get("status") != expected:
            reasons.append(f"{right.upper()}_BASE_QUOTE_QUALITY_NOT_PASSED")
        for needed in ("timestamp_et", "bid", "ask", "bid_size", "ask_size", "source_query_id", "source_sha256"):
            if not isinstance(leg, dict) or leg.get(needed) is None:
                reasons.append(f"{right.upper()}_MISSING_{needed.upper()}")
    stamps = [_timestamp(pair.get(r, {}).get("timestamp_et")) if isinstance(pair.get(r), dict) else None
              for r in RIGHTS]
    measured = abs((stamps[0]-stamps[1]).total_seconds()) if all(stamps) else None
    if measured is None:
        reasons.append("PAIR_TIMESTAMP_UNKNOWN")
    elif measured > max_skew_seconds:
        reasons.append("CALL_PUT_PAIR_SKEW_OVER_POLICY")
    # Same original quote age and spread requirements are never relaxed.
    for right in RIGHTS:
        q = pair.get(right, {}) if isinstance(pair.get(right), dict) else {}
        age = _number(q.get("age_seconds" if clock == "pretrade_0959" else "seconds_before_1001"))
        spread = _number(q.get("spread_fraction"))
        if age is None or not 0 <= age <= MAX_AGE_SECONDS:
            reasons.append(f"{right.upper()}_QUOTE_AGE_OVER_30S_OR_UNKNOWN")
        if spread is None or not 0 <= spread <= Decimal("0.15"):
            reasons.append(f"{right.upper()}_SPREAD_OVER_15PCT_OR_UNKNOWN")
    reasons = sorted(set(reasons))
    return {
        "status": "CLOCK_QUOTE_DIAGNOSTIC_PASSES" if not reasons else "CLOCK_QUOTE_DIAGNOSTIC_REJECTED",
        "pass": not reasons, "reasons": reasons,
        "measured_skew_seconds": measured,
        "max_allowed_skew_seconds": max_skew_seconds,
        "original_strategy_gate_changed": False,
    }


def same_contract_two_clock_drift(pretrade: dict | None, execution: dict | None) -> dict:
    """Two MINUTES between observation clocks; NOT a 1-3s execution-latency measurement."""
    result: dict[str, Any] = {
        "clock_interval": "09:59_PREDECISION_TO_10:01_ORDER_REFERENCE",
        "is_execution_latency_measurement": False,
        "historical_broker_fill": False,
        "status": "UNKNOWN_NOT_ENOUGH_INDEPENDENT_QUOTE_EVIDENCE",
        "call": None, "put": None, "pair_ask": None,
    }
    if not isinstance(pretrade, dict) or not isinstance(execution, dict):
        return result
    costs: dict[str, tuple[Decimal, Decimal]] = {}
    for right in RIGHTS:
        pre, post = pretrade.get(right), execution.get(right)
        if not isinstance(pre, dict) or not isinstance(post, dict):
            return result
        if (pre.get("status") != "PRETRADE_QUOTE_0959_PASSES"
                or post.get("status") != "QUOTE_MICROSTRUCTURE_PASSES"):
            return result
        p, a = _number(pre.get("ask")), _number(post.get("ask"))
        if p is None or a is None or p <= 0 or a <= 0:
            return result
        costs[right] = p, a
        result[right] = {
            "pretrade_ask_per_share": str(p),
            "order_reference_ask_per_share": str(a),
            "ask_price_change_pct": round(float((a / p - 1) * 100), 5),
            "ask_price_change_dollars_per_contract": str((a-p)*100),
            "pretrade_timestamp_et": pre["timestamp_et"],
            "order_timestamp_et": post["timestamp_et"],
        }
    before = sum((costs[r][0] for r in RIGHTS), Decimal(0))
    after = sum((costs[r][1] for r in RIGHTS), Decimal(0))
    drift = (after/before-1)*100
    result["pair_ask"] = {
        "pretrade_total_dollars_one_call_one_put": str(before*100),
        "order_total_dollars_one_call_one_put": str(after*100),
        "absolute_cost_change_dollars": str((after-before)*100),
        "cost_change_pct": round(float(drift), 5),
        "adverse_cost_increase_pct": round(float(max(0, drift)), 5),
        "diagnostic_only_price_band_pass": {
            str(cap): drift <= cap for cap in PRICE_DRIFT_PCT
        },
        "no_spread_or_fee_based_fill_claim": True,
    }
    result["status"] = "OBSERVED_TWO_CLOCK_PRICE_CHANGE_NOT_LATENCY"
    return result


def execution_action_diagnostic(
    reference: dict, action: dict, *, order_at: str, action_at: str,
    max_skew_seconds: int, max_adverse_pair_cost_change_pct: str,
) -> dict:
    """Future integration seam: require actual quote AT delayed action clock.

    Caller supplies original 10:01 reference and independently saved delayed
    CALL/PUT quotes (same contract identities externally). No interpolation.
    """
    order_time, action_time = _timestamp(order_at), _timestamp(action_at)
    cap = _number(max_adverse_pair_cost_change_pct)
    if (max_skew_seconds not in SKEW_SECONDS or cap not in PRICE_DRIFT_PCT
            or order_time is None or action_time is None):
        raise TraceError("V49_EXECUTION_DIAGNOSTIC_POLICY_OR_TIMESTAMP_INVALID")
    lag = Decimal(str((action_time-order_time).total_seconds()))
    if not 0 <= lag <= 3:
        raise TraceError("V49_EXECUTION_LAG_OUTSIDE_REGISTERED_ZERO_TO_THREE_SECONDS")
    reasons = []
    measures = {}
    for right in RIGHTS:
        before, after = reference.get(right, {}), action.get(right, {})
        if not isinstance(before, dict) or not isinstance(after, dict):
            reasons.append(f"{right.upper()}_MISSING_ACTION_QUOTE")
            continue
        before_at = _timestamp(before.get("timestamp_et"))
        after_at = _timestamp(after.get("timestamp_et"))
        pre_ask, post_ask = _number(before.get("ask")), _number(after.get("ask"))
        pre_bid, post_bid = _number(before.get("bid")), _number(after.get("bid"))
        if (None in (before_at, after_at, pre_ask, post_ask, pre_bid, post_bid)
                or pre_ask <= 0 or post_ask <= 0 or pre_bid <= 0 or post_bid <= 0):
            reasons.append(f"{right.upper()}_ACTION_QUOTE_INCOMPLETE")
            continue
        if not before_at <= order_time or not before_at <= after_at <= action_time:
            reasons.append(f"{right.upper()}_ACTION_PRICE_FUTURE_OR_OUT_OF_ORDER")
        age = Decimal(str((action_time-after_at).total_seconds()))
        if not 0 <= age <= MAX_AGE_SECONDS:
            reasons.append(f"{right.upper()}_ACTION_QUOTE_STALE_OR_FUTURE")
        if (after.get("bid_size", 0) <= 0 or after.get("ask_size", 0) <= 0
                or post_ask < post_bid
                or (post_ask-post_bid)/((post_ask+post_bid)/2) > Decimal("0.15")):
            reasons.append(f"{right.upper()}_ACTION_PRICE_OR_SIZE_UNQUALIFIED")
        measures[right] = {
            "reference_ask": str(pre_ask), "action_ask": str(post_ask),
            "reference_bid": str(pre_bid), "action_bid": str(post_bid),
            "action_quote_age_seconds": float(age),
            "adverse_buy_price_increase_pct": round(float((post_ask/pre_ask-1)*100), 5),
            "action_source_query_id": after.get("source_query_id"),
            "action_source_sha256": after.get("source_sha256"),
        }
    skew = None
    if all(isinstance(action.get(right), dict) and _timestamp(action[right].get("timestamp_et"))
           for right in RIGHTS):
        skew = abs((_timestamp(action["call"]["timestamp_et"])
                    -_timestamp(action["put"]["timestamp_et"])).total_seconds())
        if skew > max_skew_seconds:
            reasons.append("ACTION_CALL_PUT_SKEW_OVER_POLICY")
    else:
        reasons.append("ACTION_PAIR_SKEW_UNAVAILABLE")
    if set(measures) == set(RIGHTS):
        b = sum((_number(measures[r]["reference_ask"]) for r in RIGHTS), Decimal(0))
        a = sum((_number(measures[r]["action_ask"]) for r in RIGHTS), Decimal(0))
        drift = (a/b-1)*100
        if drift > cap:
            reasons.append("ACTION_PAIR_ADVERSE_PRICE_DRIFT_OVER_POLICY")
    else:
        drift = None
        reasons.append("ACTION_PAIR_PRICE_DRIFT_UNAVAILABLE")
    return {
        "status": "COUNTERFACTUAL_QUOTE_GATES_PASS_NO_FILL" if not reasons
                  else "COUNTERFACTUAL_QUOTE_GATES_REJECT",
        "observed_action_lag_seconds": float(lag),
        "observed_pair_skew_seconds": skew,
        "observed_pair_buy_ask_cost_change_pct": round(float(drift), 5) if drift is not None else None,
        "max_pair_skew_seconds": max_skew_seconds,
        "max_adverse_pair_cost_change_pct": str(cap),
        "reason_codes": sorted(set(reasons)),
        "per_leg": measures,
        "actual_order_fill_proven": False,
        "cannot_replace_original_one_second_strategy_policy": True,
    }


def _by_day(report: dict, key: str, count: int) -> dict:
    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) != count:
        raise TraceError("V49_CASE_DENOMINATOR_DRIFT")
    by_day = {row[key]: row for row in cases}
    if len(by_day) != count:
        raise TraceError("V49_DUPLICATE_CASE_DATE")
    return by_day


def build_trace(v45: dict, v46: dict, v47: dict) -> dict:
    """Source-verified audit: all 361 reviewed candidates, including abstentions."""
    for label, report in (("v45", v45), ("v46", v46), ("v47", v47)):
        _verified(report, label)
    if (v46.get("source_v45_fingerprint") != PINNED["v45"][1]
            or v47.get("source_v45_fingerprint") != PINNED["v45"][1]
            or v47.get("source_v46_fingerprint") != PINNED["v46"][1]
            or v45.get("total_original_weekly_clocks") != 411
            or v45.get("original_abstentions_unchanged") != 50
            or v47.get("hypothetical_long_candidates") != 106
            or v47.get("historical_strategy_profitability") is not None):
        raise TraceError("V49_PROVENANCE_OR_AUTHORITY_DRIFT")
    admission = _by_day(v45, "date_et", 361)
    signals = _by_day(v46, "date_et", 361)
    exits = _by_day(v47, "entry_date_et", 106)
    if set(admission) != set(signals):
        raise TraceError("V49_V45_V46_DATE_OR_COHORT_DRIFT")
    expected = {d for d, c in signals.items() if c["scenario_screen_status"] == LONG}
    if set(exits) != expected:
        raise TraceError("V49_MISSING_OR_EXTRA_HYPOTHETICAL_EXIT_CASES")
    account_events = defaultdict(list)
    for account in v47["chronological_one_slot_quote_reference_accounts"]:
        meta = {k: account.get(k) for k in ("research_variant", "hold_sessions", "cost_scenario")}
        for event in account.get("events", []):
            account_events[event["entry_date_et"]].append({**meta, **event})
    traces = []
    stats = Counter()
    skew_observations = []
    for day in sorted(admission):
        source, screen = admission[day], signals[day]
        if (screen.get("source_quality_status") != source["status"]
                or screen.get("cohort_origin") != source["cohort_origin"]):
            raise TraceError("V49_SIGNAL_SOURCE_IDENTITY_CHANGED")
        quotes = source.get("quote_quality", {})
        gates = {
            clock: {str(max_s): clock_gate(quotes.get(clock), clock, max_skew_seconds=max_s)
                    for max_s in SKEW_SECONDS}
            for clock in CLOCKS
        }
        drift = same_contract_two_clock_drift(quotes.get("pretrade_0959"),
                                              quotes.get("execution_1001"))
        if day in exits:
            e = exits[day]
            if (e["cohort_origin"] != source["cohort_origin"]
                    or e["expiration"] != source["expiration"]
                    or Decimal(e["strike"]) != Decimal(source["strike"])):
                raise TraceError("V49_EXIT_SOURCE_CONTRACT_CHANGED")
            holds = e["holds"]
            for h, result in holds.items():
                if result["status"] == "CENSORED_EXIT_LEG_SKEW":
                    skew_observations.append({"entry_date_et": day, "hold_sessions":int(h),
                        "exit_date_et": result["exit_date_et"],
                        "observed_skew_seconds": result["reason"]["skew_seconds"],
                        "original_one_second_pass": False,
                        "three_second_skew_only_pass": result["reason"]["skew_seconds"] <= 3,
                        "independent_quote_and_execution_qualification": False})
        else:
            holds = None
        event = {
            "opportunity_id": f"SPY:{day}:{source['cohort_origin']}",
            "date_et": day,
            "original_strategy_version": "options-native-spy-long-straddle-v1",
            "research_cohort_origin": source["cohort_origin"],
            "original_source_status": source["status"],
            "original_source_reasons": source.get("reason_codes", []),
            "original_v43_reasons": source.get("original_v43_reasons"),
            "alternate_v44_status": source.get("alternate_v44_status"),
            "alternate_v44_reasons": source.get("alternate_v44_reasons"),
            "expiration": source.get("expiration"),
            "strike": source.get("strike"),
            "spot_0959": source.get("spot_0959"),
            "morning_open_interest_and_provenance": source.get("oi_quality"),
            "saved_full_quote_source_evidence": quotes or None,
            "quoted_clock_comparisons": gates,
            "two_minute_same_contract_ask_drift_not_latency": drift,
            "all_hypothetical_model_scenarios": screen.get("scenario_results", []),
            "hypothetical_screen_status": screen["scenario_screen_status"],
            "decision_reason_codes": [screen["scenario_screen_status"]],
            "original_trade_decision_is_validated": False,
            "simulator_disposition": ("NO_HISTORICAL_TRADE_AUTHORIZED_HYPOTHETICAL_LONG"
                   if day in exits else "NO_ENTRY_HYPOTHETICAL_ABSTAIN_OR_SOURCE_BLOCK"),
            "five_independent_fixed_hold_exit_observations": holds,
            "v47_separate_account_reference_events": account_events.get(day, []),
            "live_or_paper_order_id": None,
            "broker_fills": None,
            "realized_strategy_pnl": None,
            "causal_feature_publication_verified": False,
            "unobserved_scenario_is_not_assumed_eligible": True,
        }
        stats[screen["scenario_screen_status"]] += 1
        traces.append(event)
    if len(traces) != 361 or len(skew_observations) != 18:
        raise TraceError("V49_SOURCE_OR_SKEW_RECONCILIATION_DRIFT")
    candidate_three = sum(e["three_second_skew_only_pass"] for e in skew_observations)
    if candidate_three != 14:
        raise TraceError("V49_THREE_SECOND_SKETCH_DRIFT")
    drift_counts = Counter()
    for r in traces:
        drift = r["two_minute_same_contract_ask_drift_not_latency"]
        if drift["status"] == "OBSERVED_TWO_CLOCK_PRICE_CHANGE_NOT_LATENCY":
            for cap, accepted in drift["pair_ask"]["diagnostic_only_price_band_pass"].items():
                drift_counts[f"{cap}%_band_pass"] += bool(accepted)
            drift_counts["measured"] += 1
    out = {
        "contract": CONTRACT,
        "status": "DEVELOPMENT_OFFLINE_FULL_OPPORTUNITY_TRACE_NO_EXECUTION",
        "input_report_fingerprints": {k: v[1] for k, v in PINNED.items()},
        "original_weekly_decision_clocks": 411,
        "original_not_selected_weekly_abstentions_no_case_ids_in_sources": 50,
        "traceable_original_selected_clocks": len(traces),
        "hypothetical_long_exit_case_count": len(exits),
        "hypothetical_screen_counts": dict(sorted(stats.items())),
        "quote_policy_comparison_seconds": list(SKEW_SECONDS),
        "unchanged_original_quote_skew_cutoff_seconds": 1,
        "two_minute_observed_price_change_band_descriptive_counts": dict(sorted(drift_counts.items())),
        "censored_future_exit_skew_observations": skew_observations,
        "censored_future_exit_skew_within_3s_only": candidate_three,
        "censored_future_exit_skew_over_3s": 18-candidate_three,
        "reclassified_as_actual_fills_or_historical_profitability": 0,
        "independent_one_to_three_second_action_quote_tapes_present": False,
        "simulated_latency_prices_without_observed_source": False,
        "provider_requests": 0, "broker_requests": 0,
        "opportunities": traces,
        "source_coverage_and_censored_exit_summary": v47["source_request_counts"],
        "no_strategy_filter_selected_using_retrospective_profits": True,
    }
    out["fingerprint"] = fingerprint(out)
    return out
