from __future__ import annotations

"""V10 offline-only, exact 09:35/10:00 ThetaData at-time source boundary.

Maps a V9 *original* provider-request identity to the pinned Python SDK
surface method without changing strike, expiration, decision clock, option
right or max_dte. This module never calls the method or constructs a client.
Independent row-by-row provenance/schema/causality/DTE diagnostics use the
entire original SDK-normalized response, WITHOUT filtering over-DTE rows.
All results are diagnostic: no source acceptance, acquisition authorization,
reservation, strategy/market-data promotion or simulator admission.
"""

from collections import Counter
from datetime import date, datetime, timedelta
import hashlib
from typing import Any
from zoneinfo import ZoneInfo

from packages.data.hybrid_options_frozen_research_demand_v1 import (
    EXPECTED_CANDIDATE_PARAMS, EXPECTED_PROVIDER_ENDPOINT,
    ROW_KEY_FIELDS,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    REQUIRED_FIELDS, _symbol_matches_underlying, _validate_provider_provenance,
    _finite_number, _nonnegative_int, _aware_et,
)
from packages.providers.thetadata.client import (
    TARGET_LIBRARY_VERSION, ThetaDataResponse, _canonical_bytes,
)

CONTRACT = "atlas-hybrid-at-time-exact-request-source-admission-v1"
EASTERN = ZoneInfo("America/New_York")
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_ROWS = 50_000
SDK_METHOD = "option_at_time_quote_surface"
BLOCKED_SDK_DTE_STATUS = "MAX_DTE_PROVIDER_FORWARDING_AND_COMPLETENESS_UNPROVEN"


class HybridAtTimeSourceGateError(ValueError):
    pass


def validate_exact_request(row: dict[str, Any]) -> dict[str, Any]:
    """Original V9 at-time identity -> exact SDK keyword arguments, no call."""
    if not isinstance(row, dict) or set(row) != ROW_KEY_FIELDS | {"priority"}:
        raise HybridAtTimeSourceGateError("V9_EXACT_ROW_SCHEMA_REQUIRED")
    params = row["params"]
    if not isinstance(params, dict) or set(params) != EXPECTED_CANDIDATE_PARAMS:
        raise HybridAtTimeSourceGateError("V9_AT_TIME_PARAMETER_SCOPE_CHANGED")
    if not isinstance(row["priority"], int) or row["priority"] < 1:
        raise HybridAtTimeSourceGateError("V9_PRIORITY_INVALID")
    if (row["endpoint"] != EXPECTED_PROVIDER_ENDPOINT
            or row["query_id"] != _fingerprint({
                "provider": "thetadata",
                "endpoint": row["endpoint"], "params": params,
            })
            or row["symbol"] != params["symbol"]
            or row["right"] != params["right"]
            or row["decision_clock_et"] != params["time_of_day"]
            or row["origin"] not in {
                "FROZEN_SPY_WEEKLY_OPTIONS_NATIVE",
                "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES",
            }
            or row["original_source_fingerprint"] is None
            or not isinstance(row["origin_query_fingerprint"], str)
            or len(row["origin_query_fingerprint"]) != 64
            or row["exact_adapter"] !=
                "AT_TIME_ADAPTER_NOT_IMPLEMENTED_NO_PROVIDER_AUTHORITY"
            or row["provider_requests"] != 0
            or row["simulator_ready"] is not False
            or params["expiration"] != "*"
            or params["strike"] != "*"
            or params["start_date"] != params["end_date"]
            or params["format"] != "json"):
        raise HybridAtTimeSourceGateError("V9_ORIGINAL_SOURCE_IDENTITY_DRIFT")

    try:
        day = date.fromisoformat(row["date_et"])
        if day.strftime("%Y%m%d") != params["start_date"]:
            raise ValueError("date mismatch")
        datetime.strptime(params["time_of_day"], "%H:%M:%S.%f")
    except (ValueError, TypeError, KeyError) as exc:
        raise HybridAtTimeSourceGateError("V9_REQUEST_DATE_CLOCK_INVALID") from exc

    if row["origin"] == "FROZEN_SPY_WEEKLY_OPTIONS_NATIVE":
        if (params["symbol"] != "SPY" or params["right"] != "both"
                or params["time_of_day"] != "10:00:00.000"
                or params["strike_range"] != 2
                or params["max_dte"] != 45
                or row["source_role"] != "WEEKLY_ENTRY_DECISION"):
            raise HybridAtTimeSourceGateError("SPY_WEEKLY_EXACT_SCOPE_DRIFT")
    else:
        if (params["right"] != "call"
                or params["time_of_day"] != "09:35:00.000"
                or params["strike_range"] is not None
                or params["max_dte"] != 75
                or row["source_role"] != "0935_CALL_ENTRY_DISCOVERY"):
            raise HybridAtTimeSourceGateError("MULTIYEAR_CALL_EXACT_SCOPE_DRIFT")

    # SDK wrapper correctly accepts strike_range=None by *omitting* the
    # keyword at the worker boundary. V10 passes None only to the wrapper.
    return {
        "symbol": params["symbol"],
        "date_et": row["date_et"],
        "time_of_day_et": params["time_of_day"],
        "right": params["right"],
        "max_dte": params["max_dte"],
        "strike_range": params["strike_range"],
    }


def diagnose_at_time_response(
    row: dict[str, Any],
    response: ThetaDataResponse,
) -> dict[str, Any]:
    """Offline inspect ALL original quote rows and strictly quarantine excess DTE.

    Invalid non-DTE source characteristics fail closed. DTE overrun becomes
    reported nonpromotable diagnostic, not locally projected accepted quotes.
    """
    kwargs = validate_exact_request(row)
    if not isinstance(response, ThetaDataResponse):
        raise HybridAtTimeSourceGateError("SDK_RESPONSE_TYPE_INVALID")
    _validate_provider_provenance(response)
    if (response.http_status != 200
            or response.response_bytes != len(response.raw_body)
            or not 0 < len(response.raw_body) <= MAX_RESPONSE_BYTES
            or response.raw_body != _canonical_bytes(response.rows)
            or len(response.rows) > MAX_ROWS):
        raise HybridAtTimeSourceGateError("SDK_SOURCE_CANONICAL_RECEIPT_INVALID")
    if response.explicit_no_data and response.rows:
        raise HybridAtTimeSourceGateError("CONTRADICTORY_EXPLICIT_NO_DATA")
    request_day = date.fromisoformat(row["date_et"])
    clock = datetime.combine(
        request_day,
        datetime.strptime(kwargs["time_of_day_et"], "%H:%M:%S.%f").time(),
        EASTERN,
    )
    observed = Counter()
    outside = Counter()
    dte_max = int(kwargs["max_dte"])
    identities = set()
    staleness = []
    positive_two_sided = 0
    for item in response.rows:
        if not isinstance(item, dict) or any(
            key not in item for key in REQUIRED_FIELDS
        ):
            raise HybridAtTimeSourceGateError("QUOTE_REQUIRED_FIELDS_MISSING")
        if not _symbol_matches_underlying(
            str(item["symbol"]), kwargs["symbol"],
        ):
            raise HybridAtTimeSourceGateError("OPTION_ROOT_CHANGED")
        right = str(item["right"]).lower()
        if right not in ("call", "put") or (
            kwargs["right"] != "both" and right != kwargs["right"]
        ):
            raise HybridAtTimeSourceGateError("OPTION_RIGHT_OUTSIDE_SOURCE_SCOPE")
        try:
            exp = date.fromisoformat(str(item["expiration"])[:10])
        except ValueError as exc:
            raise HybridAtTimeSourceGateError("OPTION_EXPIRATION_INVALID") from exc
        days = (exp - request_day).days
        if days < 0:
            raise HybridAtTimeSourceGateError("EXPIRED_CONTRACT_IN_SOURCE")
        strike = _finite_number(item["strike"], "strike", nonnegative=False)
        if strike <= 0:
            raise HybridAtTimeSourceGateError("OPTION_STRIKE_INVALID")
        identity = (exp.isoformat(), strike, right)
        if identity in identities:
            raise HybridAtTimeSourceGateError("DUPLICATE_AT_TIME_CONTRACT_ID")
        identities.add(identity)
        # The legacy qualifier's timezone converter may accept a naive
        # ISO timestamp by assigning an ET interpretation. V10 deliberately
        # rejects that uncertainty: source timestamps must carry a real
        # UTC offset before any historical-causality comparison.
        timestamp = item["timestamp"]
        if not isinstance(timestamp, str):
            raise HybridAtTimeSourceGateError("SOURCE_TIMESTAMP_NOT_TEXT")
        try:
            stamped = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HybridAtTimeSourceGateError("SOURCE_TIMESTAMP_INVALID") from exc
        if stamped.tzinfo is None or stamped.utcoffset() is None:
            raise HybridAtTimeSourceGateError("SOURCE_TIMESTAMP_NAIVE_UNQUALIFIED")
        quote_clock = _aware_et(timestamp)
        if quote_clock.date() != request_day or quote_clock > clock:
            raise HybridAtTimeSourceGateError("FUTURE_OR_OTHER_DAY_AT_TIME_QUOTE")
        staleness.append((clock - quote_clock).total_seconds())
        bid = _finite_number(item["bid"], "bid")
        ask = _finite_number(item["ask"], "ask")
        bid_size = _nonnegative_int(item["bid_size"], "bid_size")
        ask_size = _nonnegative_int(item["ask_size"], "ask_size")
        for field in ("bid_exchange", "ask_exchange", "bid_condition", "ask_condition"):
            _nonnegative_int(item[field], field)
        if bid > 0 and ask > 0 and ask < bid:
            raise HybridAtTimeSourceGateError("CROSSED_AT_TIME_QUOTE")
        if bid > 0 and ask > 0 and bid_size > 0 and ask_size > 0:
            positive_two_sided += 1
        observed[right] += 1
        if days > dte_max:
            outside[days] += 1

    if response.explicit_no_data:
        status = "EXPLICIT_NO_DATA_NOT_COVERAGE"
    elif not response.rows:
        status = "EMPTY_RESPONSE_NOT_COVERAGE"
    elif outside:
        status = "QUARANTINED_OUT_OF_SCOPE_DTE_NO_PROJECTION"
    else:
        status = "IN_SCOPE_OBSERVED_NOT_EXECUTABLE"

    body = {
        "contract": CONTRACT,
        "status": status,
        "source_request_id": row["query_id"],
        "original_source_fingerprint": row["original_source_fingerprint"],
        "original_query_fingerprint": row["origin_query_fingerprint"],
        "requested_symbol": kwargs["symbol"],
        "requested_date_et": kwargs["date_et"],
        "requested_clock_et": kwargs["time_of_day_et"],
        "requested_right": kwargs["right"],
        "requested_max_dte": kwargs["max_dte"],
        "sdk_method": SDK_METHOD,
        "sdk_target_version": TARGET_LIBRARY_VERSION,
        "sdk_max_dte_semantics": BLOCKED_SDK_DTE_STATUS,
        "full_original_row_count": len(response.rows),
        "original_source_sha256": hashlib.sha256(response.raw_body).hexdigest(),
        "original_source_bytes": len(response.raw_body),
        "observed_rights": dict(sorted(observed.items())),
        "outside_requested_dte_rows": sum(outside.values()),
        "outside_requested_dte_by_days": dict(sorted(outside.items())),
        "within_requested_dte_rows": len(response.rows) - sum(outside.values()),
        "positive_two_sided_displayed_size_rows": positive_two_sided,
        "observed_max_staleness_seconds": max(staleness) if staleness else None,
        "original_response_replaced_or_filtered": False,
        "original_response_is_complete_chain_proven": False,
        "paid_at_time_provider_calls_authorized": False,
        "source_promoted": False,
        "option_execution_admissible": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_read": 0,
        "simulations_run": 0,
    }
    body["diagnostic_fingerprint"] = _fingerprint(body)
    return body


def match_retained_spy_canary_to_v9(row: dict[str, Any],
                                   *, original_query_fp: str) -> dict[str, Any]:
    """Bind the *existing* 2025 10:00 failed canary to its frozen V9 query."""
    kwargs = validate_exact_request(row)
    if (row["origin"] != "FROZEN_SPY_WEEKLY_OPTIONS_NATIVE"
            or kwargs["date_et"] != "2025-06-09"
            or row["origin_query_fingerprint"] != original_query_fp):
        raise HybridAtTimeSourceGateError("RETAINED_CANARY_V9_LINEAGE_MISMATCH")
    return {
        "contract": CONTRACT,
        "status": "EXACT_RETAINED_SPY_CANARY_SOURCE_REPLAY_ONLY",
        "v9_source_request_id": row["query_id"],
        "frozen_spy_source_query_fingerprint": original_query_fp,
        "provider_requests": 0,
        "simulator_ready": False,
    }
