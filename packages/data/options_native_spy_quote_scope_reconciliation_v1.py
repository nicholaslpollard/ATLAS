from __future__ import annotations

"""Explicit, outcome-blind 45-DTE projection of a retained SPY quote response.

This is a DATA-QUALITY DIAGNOSTIC, not a substitute for a provider response
that obeys requested max_dte. Every original row is validated first; the
144 out-of-scope rows remain in immutable archival evidence. Projected prices
are NEVER accepted as tradable, strategy-admissible, or proof of quote service
semantics. No provider method can be called by this module.
"""

from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timedelta
import hashlib
from typing import Any

from packages.data.thetadata_candidate_surface_qualification_v1 import (
    REQUIRED_FIELDS, _finite_number, _nonnegative_int,
    _symbol_matches_underlying, _validate_provider_provenance,
)
from packages.data.options_native_spy_thetadata_quote_qualification_v1 import (
    RAW_RESPONSE_CAP, PilotQuoteSourceError, _et,
    analyze_pilot_quote_surface,
)
from packages.providers.thetadata.client import ThetaDataResponse, _canonical_bytes


class SourceProjectionError(ValueError):
    pass


def inspect_explicit_dte_projection(
    source: ThetaDataResponse, request: dict[str, Any],
) -> dict[str, Any]:
    """Validate *all* source rows before an explicit, nonpromotable projection.

    Fails on every non-DTE defect including excess-DTE rows: type, clock,
    crossed markets, wrong root, duplicate contract/right, or invalid exchange.
    Eligibility is evaluated on the 0..45 day projection only, and results
    are labelled diagnostic regardless of the underlying validator status.
    """
    params = request.get("params")
    if (not isinstance(params, dict)
            or params.get("symbol") != "SPY"
            or params.get("right") != "both"
            or params.get("time_of_day") != "10:00:00.000"
            or params.get("max_dte") != 45
            or params.get("strike_range") != 2
            or params.get("start_date") != params.get("end_date")):
        raise SourceProjectionError("ORIGINAL_QUOTE_QUERY_SCOPE_CHANGED")
    try:
        day = date.fromisoformat(str(params["start_date"])[:4] + "-"
                                + str(params["start_date"])[4:6] + "-"
                                + str(params["start_date"])[6:8])
    except (ValueError, TypeError, KeyError) as exc:
        raise SourceProjectionError("ORIGINAL_QUOTE_DATE_INVALID") from exc
    # Always use the NY timezone database for historical DST transitions.
    from zoneinfo import ZoneInfo
    decision = datetime.combine(
        day, datetime.strptime("10:00:00.000", "%H:%M:%S.%f").time(),
        ZoneInfo("America/New_York"),
    )
    _validate_provider_provenance(source)
    if (source.http_status != 200
            or source.explicit_no_data
            or not source.rows
            or source.response_bytes != len(source.raw_body)
            or not 0 < len(source.raw_body) <= RAW_RESPONSE_CAP
            or source.raw_body != _canonical_bytes(source.rows)):
        raise SourceProjectionError("ORIGINAL_SDK_SOURCE_RECEIPT_UNQUALIFIED")
    selected: list[dict[str, Any]] = []
    excluded = Counter()
    identities: set[tuple[str, float, str]] = set()
    rights_included = Counter()
    rights_excluded = Counter()
    for record in source.rows:
        if any(key not in record for key in REQUIRED_FIELDS):
            raise SourceProjectionError("ORIGINAL_ROW_FIELDS_MISSING")
        if not _symbol_matches_underlying(str(record["symbol"]), "SPY"):
            raise SourceProjectionError("ORIGINAL_OPTION_ROOT_CHANGED")
        right = str(record["right"]).lower()
        if right not in ("call", "put"):
            raise SourceProjectionError("ORIGINAL_OPTION_RIGHT_UNEXPECTED")
        try:
            expiry = date.fromisoformat(str(record["expiration"]))
        except ValueError as exc:
            raise SourceProjectionError("ORIGINAL_EXPIRATION_INVALID") from exc
        dte = (expiry - day).days
        if dte < 0:
            raise SourceProjectionError("ORIGINAL_CONTAINS_ALREADY_EXPIRED_OPTION")
        strike = _finite_number(record["strike"], "strike")
        if strike <= 0:
            raise SourceProjectionError("ORIGINAL_STRIKE_INVALID")
        identity = (expiry.isoformat(), strike, right)
        if identity in identities:
            raise SourceProjectionError("ORIGINAL_DUPLICATE_OPTION_IDENTITY")
        identities.add(identity)
        quote_time = _et(record["timestamp"])
        if quote_time.date() != day or quote_time > decision:
            raise SourceProjectionError("ORIGINAL_FUTURE_OR_WRONG_DATE_QUOTE")
        bid = _finite_number(record["bid"], "bid")
        ask = _finite_number(record["ask"], "ask")
        for field in ("bid_size", "ask_size", "bid_exchange",
                      "ask_exchange", "bid_condition", "ask_condition"):
            _nonnegative_int(record[field], field)
        if bid > 0 and ask > 0 and ask < bid:
            raise SourceProjectionError("ORIGINAL_CROSSED_QUOTE")
        if dte <= 45:
            selected.append(dict(record))
            rights_included[right] += 1
        else:
            excluded[dte] += 1
            rights_excluded[right] += 1
    if not selected or not excluded:
        raise SourceProjectionError("EXPECTED_PROVIDER_DTE_OVERRUN_NOT_OBSERVED")
    projection_bytes = _canonical_bytes(selected)
    projected = replace(
        source, rows=tuple(selected), raw_body=projection_bytes,
        response_bytes=len(projection_bytes),
    )
    # This is the original unchanged quote validator with the ORIGINAL request,
    # operating on an explicitly declared projection, not an actual provider
    # response that complied with its source query.
    validated = analyze_pilot_quote_surface(projected, request)
    if (validated["row_count"] != len(selected)
            or validated["call_rows"] != rights_included["call"]
            or validated["put_rows"] != rights_included["put"]):
        raise SourceProjectionError("PROJECTED_ROW_RECONCILIATION_CHANGED")
    return {
        "status": "DECLARED_DTE_PROJECTION_RESEARCH_DIAGNOSTIC",
        "full_original_rows": len(source.rows),
        "within_requested_dte_rows": len(selected),
        "beyond_requested_dte_rows": sum(excluded.values()),
        "over_max_dte_by_calendar_days": dict(sorted(excluded.items())),
        "within_requested_dte_calls": rights_included["call"],
        "within_requested_dte_puts": rights_included["put"],
        "out_of_scope_calls": rights_excluded["call"],
        "out_of_scope_puts": rights_excluded["put"],
        "full_original_sdk_sha256": hashlib.sha256(source.raw_body).hexdigest(),
        "explicit_projection_sha256": hashlib.sha256(projection_bytes).hexdigest(),
        "original_query_fingerprint": request["query_fingerprint"],
        "projected_validator_diagnostic": {
            "status": validated["status"],
            "row_count": validated["row_count"],
            "common_30_45_dte_pairs": validated["common_30_45_dte_pairs"],
            "clock_qualified_common_pairs": validated["clock_qualified_common_pairs"],
            "normalized_surface_sha256": validated["normalized_surface_sha256"],
        },
        "projection_was_provider_requested": False,
        "original_response_satisfies_max_dte": False,
        "provider_sdk_or_server_max_dte_cause_proved": False,
        "provider_requests": 0,
        "protected_outcomes_read": 0,
        "source_accepted": False,
        "pair_input_admissible": False,
        "historical_replay_authority": False,
        "trading_authority": False,
        "further_paid_reads_authorized": False,
    }
