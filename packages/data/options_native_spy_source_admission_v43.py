from __future__ import annotations

"""V43 source-linked 10:01 SPY quote liquidity and morning OI admission.

Exact V37 source-selected pairs only; this is not proof of a tradable signal,
causal dividend/rate inputs, OCC deliverables or brokerage executions. V39/V38
may request missing source data automatically. No later returns are opened.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
import math
from typing import Any
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_dynamic_source_acquisition_v40 import (
    CONTRACT as V40_CONTRACT, validate_v37_source_packet,
)

CONTRACT = "atlas-spy-v43-quote-oi-contract-admission"
EASTERN = ZoneInfo("America/New_York")
MAX_QUOTE_AGE_SECONDS = 30
MAX_PAIR_SKEW_SECONDS = 1
MAX_RELATIVE_SPREAD = 0.15
MIN_OPEN_INTEREST = 100
INPUT_CLOCK = "10:01:00"
SIGNAL_CLOCK = "10:00:00"
EXPECTED_SOURCE_USE_COUNT = 1083
PINNED_V40_REPORT_SHA = "7e5b088af272ec8f32af038480d28204156f5e16246985ff6bedded69dacf05e"
SOURCES = ("decision_date_prior_state_oi_surface", "call_1001_quote", "put_1001_quote")


class SourceAdmissionError(ValueError):
    pass


def _number(raw: Any) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        n = float(raw)
    except (ValueError, TypeError):
        return None
    return n if math.isfinite(n) else None


def _date(row: dict) -> str:
    return row["original_entry_date_et"]


def _aware_venue_timestamp(raw: Any) -> datetime | None:
    """No guessed timezone; a naive provider timestamp cannot pass PIT checks."""
    if not isinstance(raw, str):
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(EASTERN)


def _clock(day: str, clock: str) -> datetime:
    return datetime.combine(
        date.fromisoformat(day), time.fromisoformat(clock), tzinfo=EASTERN,
    )


def _match(row: dict, *, expiry: str, strike: str, right: str) -> bool:
    try:
        symbol = str(row["symbol"])
        # ThetaData's original underlying may also be an OCC OSI compact
        # symbol; check both exact underlying and standard OCC token form.
        compact = symbol.replace(" ", "").upper()
        root_ok = compact == "SPY" or (
            compact.startswith("SPY")
            and len(compact) == 18
            and compact[3:9].isdigit()
            and compact[9] in ("C", "P")
            and compact[10:].isdigit()
        )
        return (
            root_ok
            and str(row["expiration"])[:10] == expiry
            and Decimal(str(row["strike"])) == Decimal(strike)
            and str(row["right"]).lower() == right
        )
    except (TypeError, KeyError, InvalidOperation, ValueError):
        return False


def validate_source_pair_reports(v37: dict, v40: dict) -> list[dict]:
    entries = validate_v37_source_packet(v37)
    if (not isinstance(v40, dict)
            or v40.get("contract") != V40_CONTRACT
            or v40.get("fingerprint") != PINNED_V40_REPORT_SHA
            or _fingerprint({k: v for k, v in v40.items() if k != "fingerprint"})
                != PINNED_V40_REPORT_SHA
            or v40.get("source_v37_fingerprint") != v37["fingerprint"]
            or v40.get("original_candidate_pairs") != 361
            or v40.get("original_decision_clocks") != 411
            or v40.get("original_weekly_abstentions") != 50
            or v40.get("source_demand_status") != "ALL_REQUESTED_SOURCES_PRESENT"
            or v40.get("actual_strategy_entries") is not None
            or v40.get("historical_option_fill_evidence") is not None):
        raise SourceAdmissionError("V43_V40_ORIGINAL_COHORT_SOURCE_FINGERPRINT_DRIFT")
    counts = v40.get("source_demand_counts", {})
    if (counts.get("source_uses_requested") != EXPECTED_SOURCE_USE_COUNT
            or counts.get("source_uses_resolved") != EXPECTED_SOURCE_USE_COUNT
            or counts.get("source_uses_failed_or_unresolved") != 0):
        raise SourceAdmissionError("V43_ORIGINAL_SOURCE_RECEIPTS_INCOMPLETE")
    return entries


def _exact_quote(source: dict, requirement: dict) -> dict:
    kw = requirement["kwargs"]
    if source["status"] not in ("CACHE_HIT", "FETCHED_AND_ARCHIVED"):
        return {"status": "SOURCE_MISSING", "source_query_id": source["query_id"]}
    hits = [
        r for r in source["source_rows"] if isinstance(r, dict) and _match(
            r, expiry=kw["expiration"], strike=kw["strike"], right=kw["right"]
        )
    ]
    result = {
        "source_query_id": source["query_id"],
        "source_sha256": source["source_sha256"],
        "matched_original_rows": len(hits),
        "status": "EXACT_UNAVAILABLE_OR_DUPLICATE",
        "historically_executable_order_fill": False,
    }
    if len(hits) != 1:
        return result
    row = hits[0]
    timestamp = _aware_venue_timestamp(row.get("timestamp"))
    clock = _clock(kw["date_et"], INPUT_CLOCK)
    bid, ask = _number(row.get("bid")), _number(row.get("ask"))
    bid_size, ask_size = _number(row.get("bid_size")), _number(row.get("ask_size"))
    quote_age = (clock - timestamp).total_seconds() if timestamp is not None else None
    spread = (
        (ask - bid) / ((bid + ask) / 2)
        if bid is not None and ask is not None and bid + ask > 0
        else None
    )
    reasons = []
    if (timestamp is None or timestamp.date().isoformat() != kw["date_et"]
            or quote_age is None or not 0 <= quote_age <= MAX_QUOTE_AGE_SECONDS):
        reasons.append("QUOTATION_AGE_OR_TIMEZONE_UNQUALIFIED")
    if (bid is None or ask is None or bid <= 0 or ask < bid):
        reasons.append("NON_POSITIVE_OR_CROSSED_TWO_SIDED_MARKET")
    if (bid_size is None or ask_size is None
            or bid_size <= 0 or ask_size <= 0
            or not bid_size.is_integer() or not ask_size.is_integer()):
        reasons.append("MISSING_QUOTED_SIZE")
    if spread is None or not 0 <= spread <= MAX_RELATIVE_SPREAD:
        reasons.append("SPREAD_ABOVE_15_PERCENT_OR_UNKNOWN")
    result.update({
        "status": "QUOTE_MICROSTRUCTURE_PASSES" if not reasons else "QUOTE_REJECTED",
        "timestamp_et": timestamp.isoformat() if timestamp else None,
        "seconds_before_1001": quote_age,
        "bid": bid, "ask": ask,
        "bid_size": int(bid_size) if bid_size is not None and bid_size.is_integer() else None,
        "ask_size": int(ask_size) if ask_size is not None and ask_size.is_integer() else None,
        "spread_fraction": spread,
        "reason_codes": reasons,
        "option_bid_ask_source_pit_publication_independently_proven": False,
    })
    return result


def _exact_oi(source: dict, row: dict) -> dict:
    result = {
        "source_query_id": source["query_id"],
        "source_sha256": source.get("source_sha256"),
        "status": "SOURCE_MISSING",
        "decision_morning_oi_publication_independently_proven": False,
    }
    if source["status"] not in ("CACHE_HIT", "FETCHED_AND_ARCHIVED"):
        return result
    expiry, strike, day = (
        row["frozen_expiration_et"], row["frozen_strike"], _date(row),
    )
    both = {"call": [], "put": []}
    for item in source["source_rows"]:
        if not isinstance(item, dict):
            continue
        for right in both:
            if _match(item, expiry=expiry, strike=strike, right=right):
                both[right].append(item)
    legs = {}
    reasons = []
    for right in ("call", "put"):
        matched = both[right]
        record = {"matched_original_rows": len(matched)}
        if len(matched) != 1:
            reasons.append(f"{right.upper()}_OI_NOT_UNIQUE")
        else:
            candidate = matched[0]
            oi = _number(candidate.get("open_interest"))
            stamp = _aware_venue_timestamp(candidate.get("timestamp"))
            if (oi is None or oi < 0 or not oi.is_integer()):
                reasons.append(f"{right.upper()}_OI_INVALID")
            elif oi < MIN_OPEN_INTEREST:
                reasons.append(f"{right.upper()}_OI_BELOW_100")
            if (stamp is None or stamp.date().isoformat() != day or
                    stamp > _clock(day, SIGNAL_CLOCK)):
                reasons.append(f"{right.upper()}_OI_PUBLICATION_TIME_UNQUALIFIED")
            record.update({
                "open_interest": int(oi) if oi is not None and oi >= 0 and oi.is_integer() else None,
                "observed_publication_timestamp_et": stamp.isoformat() if stamp else None,
            })
        legs[right] = record
    result.update({
        "call": legs["call"], "put": legs["put"],
        "status": "OI_SOURCE_FILTER_PASSES" if not reasons else "OI_REJECTED",
        "reason_codes": reasons,
    })
    return result


def assess_case(row: dict, sources: dict) -> dict:
    """Assess one original selected pair; absence is unresolved, never a loss."""
    missing = sorted(set(SOURCES) - set(sources))
    day = _date(row)
    if missing:
        return {
            "date_et": day, "expiration": row["frozen_expiration_et"],
            "strike": row["frozen_strike"], "status": "SOURCE_INCOMPLETE",
            "missing_source_purposes": missing,
            "entry_signal": None, "execution_fill": None,
        }
    call = _exact_quote(*sources["call_1001_quote"])
    put = _exact_quote(*sources["put_1001_quote"])
    oi = _exact_oi(sources["decision_date_prior_state_oi_surface"][1], row)
    reasons = []
    if call["status"] != "QUOTE_MICROSTRUCTURE_PASSES":
        reasons.append("CALL_QUOTE_UNQUALIFIED")
    if put["status"] != "QUOTE_MICROSTRUCTURE_PASSES":
        reasons.append("PUT_QUOTE_UNQUALIFIED")
    if oi["status"] != "OI_SOURCE_FILTER_PASSES":
        reasons.append("ORIGINAL_CALL_PUT_OI_UNQUALIFIED")
    skew = None
    if call.get("timestamp_et") and put.get("timestamp_et"):
        skew = abs((
            datetime.fromisoformat(call["timestamp_et"]) -
            datetime.fromisoformat(put["timestamp_et"])
        ).total_seconds())
        if skew > MAX_PAIR_SKEW_SECONDS:
            reasons.append("CALL_PUT_QUOTE_SKEW_ABOVE_1_SECOND")
    else:
        reasons.append("PAIR_QUOTE_CLOCK_UNQUALIFIED")
    passed = not reasons
    return {
        "date_et": day, "expiration": row["frozen_expiration_et"],
        "strike": row["frozen_strike"],
        "source_original_spy_spot_0959": row["source_spy_0959_spot"],
        "retrospective_volatility": row["conditional_retrospective_dividend_volatility"],
        "source_10_01_call": call, "source_10_01_put": put,
        "source_decision_morning_oi": oi,
        "call_put_quote_time_skew_seconds": skew,
        "status": "SOURCE_MICROSTRUCTURE_OI_CHECKS_PASS" if passed else "SOURCE_QUALITY_UNQUALIFIED",
        "reason_codes": reasons,
        "point_in_time_input_acceptance": False,
        "rate_dividend_source_pit_qualified": False,
        "discrete_dividend_american_iv_qualified": False,
        "historical_entry_signal": None,
        "hypothetical_order_fill": None,
        "historical_account_pnl": None,
    }


def build_report(v37: dict, v40: dict, cases: list[dict], acquisition: dict) -> dict:
    if len(cases) != 361 or len({c["date_et"] for c in cases}) != 361:
        raise SourceAdmissionError("V43_CASE_COVERAGE_DRIFT")
    counts = Counter(c["status"] for c in cases)
    reason_counts = Counter(reason for case in cases for reason in case.get("reason_codes", ()))
    year = defaultdict(Counter)
    for c in cases:
        year[c["date_et"][:4]][c["status"]] += 1
    result = {
        "contract": CONTRACT,
        "status": "ORIGINAL_SOURCE_QUOTE_OI_QUALITY_AUDIT_NO_TRADING_AUTHORITY",
        "source_v37_fingerprint": v37["fingerprint"],
        "source_v40_fingerprint": v40["fingerprint"],
        "source_uses": acquisition["source_uses_requested"],
        "provider_attempts_this_run": acquisition["provider_dispatch_attempts"],
        "cache_hits_this_run": acquisition["persisted_cache_hits"],
        "newly_acquired_sources_this_run": acquisition["provider_fetch_successes"],
        "explicit_no_data_this_run": acquisition["source_uses_explicit_no_data"],
        "source_failures_this_run": acquisition["source_uses_failed_or_unresolved"],
        "case_counts": dict(sorted(counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "by_year": {key: dict(sorted(value.items())) for key, value in sorted(year.items())},
        "original_cases": sorted(cases, key=lambda x: x["date_et"]),
        "source_only_quote_not_a_broker_fill": True,
        "quote_1001_is_not_1000_entry_signal_input": True,
        "pit_corporate_action_rate_dividend_iv_qualification_not_complete": True,
        "actual_strategy_entry_count": None,
        "actual_historical_profitability": None,
        "next": "SOURCE_ADMISSION_REPAIR_AND_PIT_SOFR_DIVIDEND_AMERICAN_IV_BRIDGE",
    }
    result["fingerprint"] = _fingerprint(result)
    return result
