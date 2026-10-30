from __future__ import annotations

"""V44 causal alternate-contract source discovery for an independent SPY variant.

Select a *different* contract from decision-morning OI plus the previously
observed 09:59 SPY spot only. Never use 10:01 prices, later exits or P&L to
choose a candidate. V38/V39 acquires any missing quote source and retains it.
This does not mutate the frozen original 361 selected contracts.
"""

from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
import math
from typing import Any

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_source_admission_v43 import (
    CONTRACT as V43_CONTRACT, MAX_RELATIVE_SPREAD, _aware_venue_timestamp,
    _clock, _exact_quote, _match, _number,
)

CONTRACT = "atlas-spy-oi-alternate-candidate-recovery-v44"
PINNED_V43_FINGERPRINT = "d974e1510717b20a69fe4cb26121bf03be55f7ea4016dcdd49c166b8c59feecc"
MIN_OI = 100
MIN_DTE = 30
MAX_DTE = 45
PRETRADE_TIME = "09:59:00"
ORDER_TIME = "10:01:00"
MAX_QUOTE_AGE_SECONDS = 30
MAX_LEG_SKEW_SECONDS = 1


class AlternateSourceError(ValueError):
    pass


def verified_original_cases(v43: dict) -> list[dict]:
    if (not isinstance(v43, dict)
            or v43.get("contract") != V43_CONTRACT
            or v43.get("fingerprint") != PINNED_V43_FINGERPRINT
            or _fingerprint({k: v for k, v in v43.items() if k != "fingerprint"})
               != PINNED_V43_FINGERPRINT
            or v43.get("source_v40_fingerprint")
               != "7e5b088af272ec8f32af038480d28204156f5e16246985ff6bedded69dacf05e"
            or v43.get("case_counts", {}).get("SOURCE_MICROSTRUCTURE_OI_CHECKS_PASS") != 178
            or v43.get("case_counts", {}).get("SOURCE_QUALITY_UNQUALIFIED") != 183
            or v43.get("source_uses") != 1083
            or v43.get("actual_strategy_entry_count") is not None):
        raise AlternateSourceError("V44_ORIGINAL_V43_SOURCE_REPORT_FINGERPRINT_DRIFT")
    cases = v43.get("original_cases")
    if (not isinstance(cases, list) or len(cases) != 361
            or [x.get("date_et") for x in cases] != sorted(x.get("date_et") for x in cases)
            or len({x.get("date_et") for x in cases}) != 361):
        raise AlternateSourceError("V44_ORIGINAL_361_DATE_COHORT_DRIFT")
    return cases


def oi_recovery_targets(cases: list[dict]) -> list[dict]:
    return [
        x for x in cases if
        "ORIGINAL_CALL_PUT_OI_UNQUALIFIED" in x.get("reason_codes", ())
    ]


def oi_surface_demand(case: dict) -> dict:
    day = case["date_et"]
    return {
        "candidate_id": f"SPY.{day}.{case['expiration']}.{case['strike']}",
        "purpose": "decision_date_prior_state_oi_surface",
        "method": "option_history_open_interest_surface",
        "kwargs": {
            "symbol": "SPY", "date_et": day, "right": "both",
            "max_dte": 75, "strike_range": None,
        },
    }


def _valid_spy_underlying(raw: Any) -> bool:
    token = str(raw).strip().replace(" ", "").upper()
    return (
        token in ("SPY", "SPY.US")
        or (len(token) == 18 and token.startswith("SPY")
            and token[3:9].isdigit() and token[9] in "CP"
            and token[10:].isdigit())
    )


def discover_alternate(original: dict, source: dict) -> dict:
    """Rank DTE/strike from morning OI and 09:59 spot, without later quotes."""
    day = original["date_et"]
    base = {
        "date_et": day, "original_expiration": original["expiration"],
        "original_strike": original["strike"],
        "source_oi_query_id": source.get("query_id"),
        "source_oi_sha256": source.get("source_sha256"),
        "historical_signal": None, "historical_fill": None,
        "actual_pnl": None, "independent_oi_publication_confirmed": False,
    }
    if source.get("status") not in ("CACHE_HIT", "FETCHED_AND_ARCHIVED"):
        return {**base, "status": "OI_SOURCE_UNAVAILABLE", "reason": "MORNING_OI_NOT_ARCHIVED"}
    spot = _number(original.get("source_original_spy_spot_0959"))
    if spot is None or spot <= 0:
        return {**base, "status": "NO_ALTERNATE", "reason": "PREVIOUS_0959_SPY_SPOT_UNQUALIFIED"}
    original_identity = (original["expiration"], Decimal(str(original["strike"])))
    observed = {}
    d = date.fromisoformat(day)
    before_decision = _clock(day, "10:00:00")
    for r in source["source_rows"]:
        if not isinstance(r, dict) or not _valid_spy_underlying(r.get("symbol")):
            continue
        exp = str(r.get("expiration", ""))[:10]
        try:
            expiration_date = date.fromisoformat(exp)
            strike = Decimal(str(r.get("strike")))
        except (ValueError, InvalidOperation, TypeError):
            continue
        dte = (expiration_date - d).days
        if not MIN_DTE <= dte <= MAX_DTE or not strike.is_finite() or strike <= 0:
            continue
        if (exp, strike) == original_identity:
            continue
        right = str(r.get("right", "")).lower()
        if right not in ("call", "put"):
            continue
        oi = _number(r.get("open_interest"))
        stamp = _aware_venue_timestamp(r.get("timestamp"))
        if (oi is None or not oi.is_integer() or oi < MIN_OI or stamp is None
                or stamp.date() != d or stamp > before_decision):
            continue
        key = (exp, strike)
        slot = observed.setdefault(key, {"call": [], "put": []})
        slot[right].append((int(oi), stamp.isoformat()))
    possible = []
    for (expiry, strike), legs in observed.items():
        if len(legs["call"]) != 1 or len(legs["put"]) != 1:
            continue
        call_oi, c_time = legs["call"][0]
        put_oi, p_time = legs["put"][0]
        proximity = abs(float(strike) - spot)
        # Same expiration first, then proximity to last valid 09:59 spot.
        # No current/future option price or later trade outcome is inspected.
        order = (
            0 if expiry == original["expiration"] else 1,
            proximity, abs((date.fromisoformat(expiry) - d).days
                           - (date.fromisoformat(original["expiration"]) - d).days),
            -min(call_oi, put_oi), expiry, strike,
        )
        possible.append((order, {
            **base, "status": "ALTERNATE_FROM_PRIOR_STATE_OI",
            "expiration": expiry, "strike": str(strike),
            "spot_0959": spot, "abs_spot_strike_distance": proximity,
            "call_open_interest": call_oi, "put_open_interest": put_oi,
            "call_oi_message_et": c_time, "put_oi_message_et": p_time,
            "dte": (date.fromisoformat(expiry) - d).days,
            "quote_quality": None,
        }))
    if not possible:
        return {**base, "status": "NO_ALTERNATE", "reason": "NO_DUAL_OI_GE_100_WITHIN_30_45DTE"}
    possible.sort(key=lambda x: x[0])
    return possible[0][1]


def quote_demands(selected: dict):
    if selected["status"] != "ALTERNATE_FROM_PRIOR_STATE_OI":
        return
    day, expiry, strike = selected["date_et"], selected["expiration"], selected["strike"]
    candidate = f"SPY.V44.{day}.{expiry}.{strike}"
    for clock_name, observed_time in (("pretrade_0959", PRETRADE_TIME),
                                      ("execution_1001", ORDER_TIME)):
        for right in ("call", "put"):
            yield {
                "candidate_id": candidate,
                "purpose": f"{right}_{clock_name}_quote",
                "method": "option_at_time_quote",
                "kwargs": {
                    "symbol": "SPY", "expiration": expiry, "strike": strike,
                    "right": right, "date_et": day,
                    "time_of_day_et": observed_time + ".000",
                },
            }


def _quality_for_quote(requirement: dict, source: dict, clock: str) -> dict:
    """V43 exact quote quality plus a distinct pre-decision clock check."""
    if clock == ORDER_TIME:
        return _exact_quote(source, requirement)
    req = requirement["kwargs"]
    if source["status"] not in ("CACHE_HIT", "FETCHED_AND_ARCHIVED"):
        return {"status": "MISSING", "source_query_id": source["query_id"],
                "source_sha256": source.get("source_sha256")}
    matches = [row for row in source["source_rows"] if isinstance(row, dict)
               and _match(row, expiry=req["expiration"], strike=req["strike"],
                          right=req["right"])]
    out = {
        "source_query_id": source["query_id"],
        "source_sha256": source["source_sha256"],
        "matched_original_rows": len(matches),
        "status": "PRETRADE_QUOTE_UNQUALIFIED",
    }
    if len(matches) != 1:
        return {**out, "reason_codes": ["NOT_UNIQUE_EXACT_CONTRACT"]}
    row = matches[0]
    stamp = _aware_venue_timestamp(row.get("timestamp"))
    decision = _clock(req["date_et"], PRETRADE_TIME)
    age = (decision - stamp).total_seconds() if stamp else None
    bid, ask = _number(row.get("bid")), _number(row.get("ask"))
    bs, ass = _number(row.get("bid_size")), _number(row.get("ask_size"))
    spread = (ask - bid) / ((ask + bid) / 2) if (
        ask is not None and bid is not None and ask + bid > 0) else None
    reasons = []
    if (stamp is None or stamp.date().isoformat() != req["date_et"]
            or age is None or not 0 <= age <= MAX_QUOTE_AGE_SECONDS):
        reasons.append("PRETRADE_SOURCE_QUOTE_OUTSIDE_0959_TIME")
    if bid is None or ask is None or bid <= 0 or ask < bid:
        reasons.append("NON_POSITIVE_OR_CROSSED")
    if (bs is None or ass is None or bs < 1 or ass < 1
            or not bs.is_integer() or not ass.is_integer()):
        reasons.append("QUOTED_SIZES_INVALID")
    if spread is None or not 0 <= spread <= MAX_RELATIVE_SPREAD:
        reasons.append("QUOTE_SPREAD_UNQUALIFIED")
    return {
        **out, "status": "PRETRADE_QUOTE_0959_PASSES" if not reasons else "PRETRADE_QUOTE_UNQUALIFIED",
        "reason_codes": reasons,
        "timestamp_et": stamp.isoformat() if stamp else None,
        "age_seconds": age, "bid": bid, "ask": ask,
        "bid_size": int(bs) if bs is not None and bs.is_integer() else None,
        "ask_size": int(ass) if ass is not None and ass.is_integer() else None,
        "spread_fraction": spread,
        "option_quote_historical_publication_independently_proven": False,
    }


def assess_alternate_quotes(selected: dict, sources: dict) -> dict:
    if selected["status"] != "ALTERNATE_FROM_PRIOR_STATE_OI":
        return selected
    result = dict(selected)
    slots = {}
    problems = []
    for clock_name, clock in (("pretrade_0959", PRETRADE_TIME),
                              ("execution_1001", ORDER_TIME)):
        pair = {}
        for right in ("call", "put"):
            purpose = f"{right}_{clock_name}_quote"
            if purpose not in sources:
                problems.append(f"MISSING_{purpose.upper()}")
                pair[right] = {"status": "MISSING"}
                continue
            item, src = sources[purpose]
            pair[right] = _quality_for_quote(item, src, clock)
            expected = ("PRETRADE_QUOTE_0959_PASSES" if clock_name == "pretrade_0959"
                        else "QUOTE_MICROSTRUCTURE_PASSES")
            if pair[right]["status"] != expected:
                problems.append(f"UNQUALIFIED_{purpose.upper()}")
        stamps = [pair[r].get("timestamp_et") for r in ("call", "put")]
        if all(stamps):
            skew = abs((datetime.fromisoformat(stamps[0]) -
                        datetime.fromisoformat(stamps[1])).total_seconds())
            if skew > MAX_LEG_SKEW_SECONDS:
                problems.append(f"PAIR_SKEW_{clock_name.upper()}")
        else:
            skew = None
        slots[clock_name] = {**pair, "skew_seconds": skew}
    result["quote_quality"] = slots
    result["status"] = ("ALTERNATE_SOURCE_QUALITY_PASSES" if not problems
                        else "ALTERNATE_SOURCE_QUALITY_UNQUALIFIED")
    result["reason_codes"] = sorted(set(problems))
    result["real_historical_entry_signal"] = None
    result["broker_fill_asserted"] = False
    result["historical_profitability"] = None
    return result


def build_report(v43: dict, cases: list[dict], source_summaries: list[dict]) -> dict:
    originals = verified_original_cases(v43)
    expected = {c["date_et"] for c in oi_recovery_targets(originals)}
    if (len(cases) != len(expected)
            or {c["date_et"] for c in cases} != expected):
        raise AlternateSourceError("V44_RECOVERY_TARGET_COVERAGE_INCOMPLETE")
    counts = Counter(c["status"] for c in cases)
    out = {
        "contract": CONTRACT,
        "status": "CHANGED_STRATEGY_OI_PRETRADE_0959_AND_EXECUTION_1001_SOURCE_EVIDENCE",
        "parent_v43_fingerprint": v43["fingerprint"],
        "original_361_pairs_unchanged": True,
        "original_pass_pairs": 178,
        "oi_recovery_targets": len(expected),
        "recovery_status_counts": dict(sorted(counts.items())),
        "recovery_by_year": {
            year: dict(sorted(Counter(c["status"] for c in cases
                       if c["date_et"].startswith(year)).items()))
            for year in sorted({c["date_et"][:4] for c in cases})
        },
        "source_acquisition": source_summaries,
        "recovery_cases": sorted(cases, key=lambda x: x["date_et"]),
        "selection_uses_post_1000_price_or_outcome": False,
        "quote_1001_cannot_inform_1000_decision": True,
        "dividend_rate_occ_publication_and_american_iv_not_yet_qualified": True,
        "true_historical_signals": None,
        "actual_historical_profitability": None,
    }
    out["fingerprint"] = _fingerprint(out)
    return out
