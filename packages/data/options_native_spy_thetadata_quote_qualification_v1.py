from __future__ import annotations

"""Bounded, outcome-blind 10:00 SPY CALL+PUT ThetaData source qualification.

This is NOT an IV estimate, contract selector, option quote-to-fill bridge,
OI/Greeks source acceptance, historical performance run or trading authority.
Exactly the existing frozen 24 year-stratified anchors plus one repeat may be
read, with explicit CLI authorization and immutable raw receipts.
"""

from collections import Counter
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_plan_v1 import (
    build_options_native_pilot_plan, verify_options_native_pilot_plan,
)
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    REQUIRED_FIELDS, _nonnegative_int, _finite_number,
    _symbol_matches_underlying, _persist_raw, _validate_provider_provenance,
)
from packages.providers.thetadata.client import (
    ThetaDataError, ThetaDataResponse, _canonical_bytes,
    option_at_time_quote_surface,
)

CONTRACT = "atlas-options-native-spy-1000-thetadata-quote-source-gate-v1"
OUTPUT_REL = "data/options/provider_qualification/options_native_spy_1000_v1"
EASTERN = ZoneInfo("America/New_York")
QUOTE_REQUEST_CAP = 25
RAW_RESPONSE_CAP = 4 * 1024 * 1024
SUMMARY_CAP = 512 * 1024
MAX_DTE = 45
MAX_STALE_SECONDS = 30
MAX_PAIR_SKEW_SECONDS = 1
MIN_OI_NOT_YET_QUALIFIED = 100


class PilotQuoteSourceError(ValueError):
    pass


def quote_design(plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reconstruct the plan instead of trusting a self-reported hash."""
    verified = verify_options_native_pilot_plan(
        build_options_native_pilot_plan() if plan is None else plan
    )
    lookups = {
        request["query_fingerprint"]: request
        for request in verified["entry_quote_surface_requests"]
    }
    anchors = verified["qualification_design"]["anchors"]
    if len(anchors) != 24 or len(lookups) != 411:
        raise PilotQuoteSourceError("FROZEN_PILOT_ANCHOR_POPULATION_CHANGED")
    calls = []
    for index, anchor in enumerate(anchors):
        query = lookups.get(anchor["query_fingerprint"])
        if query is None:
            raise PilotQuoteSourceError("FROZEN_PILOT_ANCHOR_SOURCE_MISSING")
        params = query["params"]
        if (params != {
            "symbol": "SPY", "expiration": "*", "strike": "*", "right": "both",
            "start_date": params["start_date"], "end_date": params["start_date"],
            "time_of_day": "10:00:00.000", "max_dte": 45,
            "strike_range": 2, "format": "json",
        }):
            raise PilotQuoteSourceError("FROZEN_PILOT_QUOTE_PARAMETERS_CHANGED")
        calls.append({
            "ordinal": index, "reason": anchor["reason"],
            "query_fingerprint": query["query_fingerprint"],
            "params": dict(params), "repeat": False,
        })
    if (verified["qualification_design"]["repeat_query_fingerprint"]
            != calls[0]["query_fingerprint"]):
        raise PilotQuoteSourceError("FROZEN_PILOT_REPEAT_SOURCE_CHANGED")
    calls.append({**calls[0], "ordinal": 24, "reason": "REPEAT_FIRST_ANCHOR", "repeat": True})
    if (len(calls) != QUOTE_REQUEST_CAP
            or verified["qualification_design"]["quote_requests_including_repeat"] != QUOTE_REQUEST_CAP
            or verified["qualification_design"]["total_initial_provider_request_design_cap"] != 64
            or verified["qualification_design"]["run_authorized"] is not False
            or verified["authority"]["provider_requests"] != 0
            or verified["authority"]["historical_replay_authority"] is not False):
        raise PilotQuoteSourceError("FROZEN_PILOT_QUOTE_REQUEST_AUTHORITY_CHANGED")
    output = {
        "contract": CONTRACT, "status": "DESIGN_ONLY_ZERO_PROVIDER_REQUESTS",
        "plan_fingerprint": verified["plan_fingerprint"],
        "specification_fingerprint": verified["specification_fingerprint"],
        "data_contract_fingerprint": verified["data_contract_fingerprint"],
        "quote_method_call_cap": QUOTE_REQUEST_CAP,
        "quote_source_calls": calls,
        "years": sorted({str(c["params"]["start_date"])[:4] for c in calls}),
        "provider_requests": 0, "broker_requests": 0,
        "outcomes_read": 0, "protected_outcomes_read": 0,
        "run_authorized": False, "source_accepted": False,
        "strategy_evidence": False, "trading_authority": False,
        "new_acquisition_campaign_authorized": False,
        "note": "Separate from legacy 09:35 CALL-only source plan. Even complete "
                "quotes cannot establish OI/IV/PIT issuers/fills/performance.",
    }
    output["design_fingerprint"] = _fingerprint(output)
    return output


def _et(value: Any) -> datetime:
    if not isinstance(value, str):
        raise PilotQuoteSourceError("INVALID_QUOTE_TIMESTAMP_TYPE")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PilotQuoteSourceError("INVALID_QUOTE_TIMESTAMP") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise PilotQuoteSourceError("UNQUALIFIED_NAIVE_QUOTE_CLOCK")
    return stamp.astimezone(EASTERN)


def analyze_pilot_quote_surface(
    response: ThetaDataResponse, request: dict[str, Any],
) -> dict[str, Any]:
    """Synthetic-testable, outcome-blind source-shape and clock diagnostics."""
    if request.get("params", {}).get("right") != "both":
        raise PilotQuoteSourceError("CALL_PUT_SOURCE_SCOPE_CHANGED")
    params = request["params"]
    try:
        day = date(int(params["start_date"][:4]),
                   int(params["start_date"][4:6]),
                   int(params["start_date"][6:]))
        clock = datetime.combine(day, datetime.strptime(
            params["time_of_day"], "%H:%M:%S.%f").time(), EASTERN)
    except (KeyError, ValueError, TypeError) as exc:
        raise PilotQuoteSourceError("PILOT_QUOTE_REQUEST_CLOCK_CHANGED") from exc
    _validate_provider_provenance(response)
    if (response.response_bytes != len(response.raw_body)
            or not 0 < len(response.raw_body) <= RAW_RESPONSE_CAP
            or response.raw_body != _canonical_bytes(response.rows)):
        raise PilotQuoteSourceError("QUOTE_RAW_RECEIPT_OR_SIZE_CHANGED")
    if response.http_status != 200:
        raise PilotQuoteSourceError("UNQUALIFIED_PROVIDER_STATUS")
    if response.explicit_no_data:
        if response.rows:
            raise PilotQuoteSourceError("NO_DATA_WITH_ROWS")
        return {
            "status": "PROVIDER_EXPLICIT_NO_DATA",
            "row_count": 0, "call_rows": 0, "put_rows": 0,
            "common_30_45_dte_pairs": 0, "clock_qualified_common_pairs": 0,
            "pair_input_admissible": False,
            "normalized_surface_sha256": hashlib.sha256(b"[]").hexdigest(),
        }
    if not response.rows:
        return {
            "status": "EMPTY_RESPONSE_WITHOUT_EXPLICIT_NO_DATA",
            "row_count": 0, "call_rows": 0, "put_rows": 0,
            "common_30_45_dte_pairs": 0, "clock_qualified_common_pairs": 0,
            "pair_input_admissible": False,
            "normalized_surface_sha256": hashlib.sha256(b"[]").hexdigest(),
        }
    observations = {}
    rights = Counter()
    for row in response.rows:
        if not all(k in row for k in REQUIRED_FIELDS):
            raise PilotQuoteSourceError("QUOTE_REQUIRED_FIELDS_MISSING")
        response_symbol = str(row["symbol"])
        if not _symbol_matches_underlying(response_symbol, "SPY"):
            raise PilotQuoteSourceError("UNEXPECTED_OPTION_ROOT")
        right = str(row["right"]).lower()
        if right not in ("call", "put"):
            raise PilotQuoteSourceError("UNEXPECTED_OPTION_RIGHT")
        try:
            exp = date.fromisoformat(str(row["expiration"])[:10])
        except ValueError as exc:
            raise PilotQuoteSourceError("INVALID_OPTION_EXPIRATION") from exc
        if not day <= exp <= day + timedelta(days=int(params["max_dte"])):
            raise PilotQuoteSourceError("OUT_OF_SCOPE_OPTION_EXPIRATION")
        strike = _finite_number(row["strike"], "strike")
        if strike <= 0:
            raise PilotQuoteSourceError("INVALID_STRIKE")
        stamp = _et(row["timestamp"])
        if stamp.date() != day or stamp > clock:
            raise PilotQuoteSourceError("FUTURE_OR_WRONG_SESSION_QUOTE")
        bid = _finite_number(row["bid"], "bid")
        ask = _finite_number(row["ask"], "ask")
        bidsz = _nonnegative_int(row["bid_size"], "bid_size")
        asksz = _nonnegative_int(row["ask_size"], "ask_size")
        for field in ("bid_exchange", "ask_exchange", "bid_condition", "ask_condition"):
            _nonnegative_int(row[field], field)
        if bid > 0 and ask > 0 and ask < bid:
            raise PilotQuoteSourceError("CROSSED_QUOTE")
        key = (exp.isoformat(), strike, right)
        if key in observations:
            raise PilotQuoteSourceError("DUPLICATE_EXACT_CONTRACT_RIGHT")
        stale = (clock - stamp).total_seconds()
        mid = (bid + ask) / 2
        spread = (ask - bid) / mid if mid > 0 else None
        observations[key] = {
            "stamp": stamp, "stale": stale,
            "symbol": response_symbol,
            "bid": bid, "ask": ask, "bid_size": bidsz, "ask_size": asksz,
            "bid_exchange": _nonnegative_int(row["bid_exchange"], "bid_exchange"),
            "ask_exchange": _nonnegative_int(row["ask_exchange"], "ask_exchange"),
            "bid_condition": _nonnegative_int(row["bid_condition"], "bid_condition"),
            "ask_condition": _nonnegative_int(row["ask_condition"], "ask_condition"),
            "valid_quote": (
                bid > 0 and ask >= bid and bidsz > 0 and asksz > 0
                and spread is not None and math.isfinite(spread) and spread <= 0.15
                and stale <= MAX_STALE_SECONDS
            ),
        }
        rights[right] += 1
    common = 0
    clock_qualified = 0
    for (exp, strike, right), call in observations.items():
        if right != "call":
            continue
        expiration = date.fromisoformat(exp)
        if not 30 <= (expiration - day).days <= MAX_DTE:
            continue
        put = observations.get((exp, strike, "put"))
        if put is None:
            continue
        common += 1
        if (call["valid_quote"] and put["valid_quote"]
                and abs((call["stamp"] - put["stamp"]).total_seconds())
                    <= MAX_PAIR_SKEW_SECONDS):
            clock_qualified += 1
    # Verify actual bid/ask, sizes, exchange/condition, right and timestamp.
    # A repeated eligibility boolean cannot prove provider price consistency.
    shape = [
        (
            key[0], key[1], key[2], value["symbol"],
            value["stamp"].isoformat(), value["bid"], value["ask"],
            value["bid_size"], value["ask_size"], value["bid_exchange"],
            value["ask_exchange"], value["bid_condition"], value["ask_condition"],
            value["valid_quote"],
        )
        for key, value in sorted(observations.items())
    ]
    return {
        "status": ("OBSERVED_BOTH_RIGHTS_CLOCK_DIAGNOSTIC"
                   if clock_qualified else "NO_CLOCK_QUALIFIED_COMMON_PAIR"),
        "row_count": len(observations), "call_rows": rights["call"],
        "put_rows": rights["put"],
        "common_30_45_dte_pairs": common,
        "clock_qualified_common_pairs": clock_qualified,
        "pair_input_admissible": False,
        "normalized_surface_sha256": _fingerprint(shape),
    }


def run_pilot_quote_source_gate(
    settings: AtlasSettings,
    *,
    reader: Callable[..., ThetaDataResponse] = option_at_time_quote_surface,
    authorize_provider_reads: bool = False,
    confirm_thetadata_standard: bool = False,
    acknowledge_25_quote_method_call_cap: bool = False,
) -> dict[str, Any]:
    """Require three affirmative authorizations for CLI AND direct Python calls.

    Supplying an injected test reader does not bypass the source-read gate.
    """
    if not (
        authorize_provider_reads is True
        and confirm_thetadata_standard is True
        and acknowledge_25_quote_method_call_cap is True
    ):
        raise PilotQuoteSourceError("PAID_QUOTE_READS_NOT_EXPLICITLY_AUTHORIZED")
    design = quote_design()
    settings.assert_external_storage_binding("options")
    root = settings.resolved_path(f"{OUTPUT_REL}/{design['design_fingerprint'][:16]}/{uuid4().hex}")
    root.mkdir(parents=True, exist_ok=False)
    reports = []
    original_repeat_fingerprint = None
    repeat_raw_bytes_equal = False
    requests_attempted = 0
    for call in design["quote_source_calls"]:
        params = call["params"]
        requests_attempted += 1
        try:
            response = reader(
                symbol="SPY",
                date_et=params["start_date"],
                time_of_day_et="10:00:00.000",
                right="both",
                max_dte=45,
                strike_range=2,
            )
        except ThetaDataError as exc:
            reports.append({
                "ordinal": call["ordinal"], "reason": call["reason"],
                "status": "TRANSPORT_OR_ENTITLEMENT_ERROR",
                "error_type": type(exc).__name__,
                "http_status": exc.http_status,
            })
            # No blind retries, no reclassification of transport as no-data.
            break
        label = f"quote_{call['ordinal']:02d}"
        if not isinstance(response, ThetaDataResponse):
            raise PilotQuoteSourceError("UNEXPECTED_PROVIDER_RESPONSE_TYPE")
        if (response.response_bytes != len(response.raw_body)
                or not 0 < len(response.raw_body) <= RAW_RESPONSE_CAP):
            raise PilotQuoteSourceError("QUOTE_RAW_RECEIPT_OR_SIZE_CHANGED")
        receipt = _persist_raw(
            root, label=label, response=response,
            query=call, plan_fingerprint=design["plan_fingerprint"],
        )
        try:
            summary = analyze_pilot_quote_surface(response, call)
        except (PilotQuoteSourceError, ValueError, TypeError) as exc:
            summary = {
                "status": "SOURCE_SCHEMA_OR_CLOCK_UNQUALIFIED",
                "failure_class": type(exc).__name__,
            }
        if call["repeat"]:
            # An empty or invalid first/repeated result is not a successful
            # quote repeatability observation, even if hashes match.
            qualified = (
                summary.get("status") == "OBSERVED_BOTH_RIGHTS_CLOCK_DIAGNOSTIC"
                and reports[0].get("status") == "OBSERVED_BOTH_RIGHTS_CLOCK_DIAGNOSTIC"
            )
            original_repeat_fingerprint = (
                summary.get("normalized_surface_sha256")
                if qualified and summary.get("normalized_surface_sha256")
                == reports[0].get("normalized_surface_sha256") else None
            )
            repeat_raw_bytes_equal = (
                qualified
                and receipt["body_sha256"] == reports[0].get("raw_body_sha256")
            )
        reports.append({
            "ordinal": call["ordinal"], "reason": call["reason"],
            "date_et": params["start_date"],
            "query_fingerprint": call["query_fingerprint"],
            "raw_body_sha256": receipt["body_sha256"],
            "raw_receipt_path": receipt["receipt_path"],
            **summary,
        })
    status_counts = dict(sorted(Counter(row["status"] for row in reports).items()))
    summary = {
        "contract": CONTRACT, "status": "BOUNDED_SOURCE_DIAGNOSTIC_NO_TRADING_AUTHORITY",
        "design_fingerprint": design["design_fingerprint"],
        "plan_fingerprint": design["plan_fingerprint"],
        "pilot_specification_fingerprint": design["specification_fingerprint"],
        "requested_quote_cap": QUOTE_REQUEST_CAP,
        "requests_attempted": requests_attempted,
        "requests_not_attempted": QUOTE_REQUEST_CAP - requests_attempted,
        "status_counts": status_counts, "anchors": reports,
        "repeat_surface_equal": original_repeat_fingerprint is not None,
        "repeat_sdk_normalized_raw_bytes_equal": repeat_raw_bytes_equal,
        "all_24_anchor_surfaces_observed": (
            len(reports) == QUOTE_REQUEST_CAP
            and all(r.get("status") == "OBSERVED_BOTH_RIGHTS_CLOCK_DIAGNOSTIC"
                    for r in reports[:24])
        ),
        "raw_network_response_body_retained": False,
        "sdk_normalized_canonical_response_retained": True,
        "all_years_observed": (
            set(design["years"]) ==
            {r["date_et"][:4] for r in reports
             if r["status"] == "OBSERVED_BOTH_RIGHTS_CLOCK_DIAGNOSTIC"}
        ),
        "source_accepted": False, "pair_input_admissible": False,
        "OI_state_and_publication_qualified": False,
        "IV_rate_dividends_qualified": False,
        "historical_contract_adjustments_qualified": False,
        "historical_fill_authority": False, "historical_replay_authority": False,
        "strategy_promotion": False, "paper": False, "live": False,
        "broker_requests": 0, "option_outcomes_read": 0,
        "protected_outcomes_read": 0, "new_acquisition_authorized": False,
    }
    summary["report_fingerprint"] = _fingerprint(summary)
    payload = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if len(payload.encode("utf-8")) > SUMMARY_CAP:
        raise PilotQuoteSourceError("QUALIFICATION_SUMMARY_SIZE_CAP_EXCEEDED")
    atomic_write_text(root / "summary.json", payload, fsync=True)
    summary["report_path"] = str(root / "summary.json")
    return summary
