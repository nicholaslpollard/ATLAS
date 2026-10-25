from __future__ import annotations

"""V8: explicitly authorized, single-attempt historical hourly quote acquisition.

Only an immutable, existing V7 NO_CALL reservation can authorize an attempt.
An attempt marker is promoted *before* invoking the provider. Any later crash,
timeout, invalid response, persist failure or interrupted provider connection
therefore blocks implicit retry. The initial V8 command is PREVIEW-ONLY.

Provider responses are written through the V6 lossless gzip-at-ingestion store.
Neither a successful source, nor an explicit no-data result, establishes
historical completeness, execution prices or simulator admission.
"""

from pathlib import Path
import hashlib
import json
import re
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_acquisition_reservations_v1 import (
    HOURLY_METHOD, MIB, _adapter_status, _existing_reservation,
    _outstanding_reservations, _reservation_path,
    plan_acquisition_reservations,
)
from packages.data.hybrid_options_gap_planner_v1 import normalize_batch
from packages.data.hybrid_options_lossless_archive_v1 import _write_immutable
from packages.data.hybrid_options_source_store_v2 import (
    MAX_SOURCE_BYTES, store_historical_quote_source,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.providers.thetadata.client import (
    ThetaDataResponse, option_history_hourly_quote_surface,
)

CONTRACT = "atlas-hybrid-options-one-attempt-provider-acquisition-v1"
ATTEMPT_REL = "data/options/hybrid/provider_attempts_v1"
SHA = re.compile(r"[a-f0-9]{64}")
MAX_ATTEMPT_BYTES = 16 * 1024
MAX_QUERY_SCOPE_BYTES = 8 * 1024


class HybridSingleAttemptError(ValueError):
    pass


def _paths(settings: AtlasSettings, query_id: str) -> tuple[Path, Path]:
    root = settings.resolved_path(ATTEMPT_REL) / query_id[:2]
    return (root / (query_id + ".attempt.json"),
            root / (query_id + ".result.json"))


def _checked_receipt(path: Path, *, query_id: str,
                     expected_contract: str) -> dict[str, Any] | None:
    """Read one immutable receipt, rejecting unsafe paths and drift."""
    if path.is_symlink():
        raise HybridSingleAttemptError("ATTEMPT_RECEIPT_SYMLINK_FORBIDDEN")
    if not path.exists():
        return None
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_ATTEMPT_BYTES:
        raise HybridSingleAttemptError("ATTEMPT_RECEIPT_FILE_UNSAFE")
    try:
        body = json.loads(path.read_bytes())
    except (UnicodeError, ValueError) as exc:
        raise HybridSingleAttemptError("ATTEMPT_RECEIPT_JSON_INVALID") from exc
    if (not isinstance(body, dict)
            or body.get("contract") != expected_contract
            or body.get("query_id") != query_id
            or not isinstance(body.get("fingerprint"), str)
            or body["fingerprint"] != _fingerprint({
                k: v for k, v in body.items() if k != "fingerprint"
            })):
        raise HybridSingleAttemptError("ATTEMPT_RECEIPT_IDENTITY_OR_HASH_DRIFT")
    return body


def _evidence(body: dict[str, Any]) -> dict[str, Any]:
    exact = dict(body)
    exact["fingerprint"] = _fingerprint(exact)
    return exact


def _write_receipt(path: Path, body: dict[str, Any]) -> None:
    raw = (json.dumps(body, indent=2, sort_keys=True, allow_nan=False)
           + "\n").encode("utf-8")
    if not 0 < len(raw) <= MAX_ATTEMPT_BYTES:
        raise HybridSingleAttemptError("ATTEMPT_RECEIPT_SIZE_EXCEEDED")
    if path.exists() or path.is_symlink():
        raise HybridSingleAttemptError("ATTEMPT_ALREADY_RECORDED_NO_RETRY")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_immutable(path, raw)
    if _checked_receipt(
        path, query_id=body["query_id"], expected_contract=CONTRACT,
    ) != body:
        raise HybridSingleAttemptError("ATTEMPT_RECEIPT_POSTWRITE_DRIFT")


def _validate_existing(
    settings: AtlasSettings, query_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    marker, result = _paths(settings, query_id)
    root = settings.resolved_path("data/options").resolve()
    for path in (marker, result):
        if not path.parent.resolve().is_relative_to(root):
            raise HybridSingleAttemptError("ATTEMPT_PATH_OUTSIDE_OPTIONS")
    started = _checked_receipt(
        marker, query_id=query_id, expected_contract=CONTRACT,
    )
    ended = _checked_receipt(
        result, query_id=query_id, expected_contract=CONTRACT,
    )
    if ended is not None and started is None:
        raise HybridSingleAttemptError("ORPHAN_PROVIDER_RESULT_RECEIPT")
    if started is not None:
        if (started.get("kind") != "ATTEMPT_STARTED"
                or started.get("state") != "POSSIBLY_DISPATCHED_NO_RETRY"
                or started.get("provider") != "thetadata"
                or started.get("provider_method") != HOURLY_METHOD
                or started.get("attempt_limit") != 1
                or started.get("simulator_ready") is not False
                or started.get("automatic_retry_authorized") is not False
                or started.get("provider_response_received") is not False
                or not isinstance(started.get("reservation_fingerprint"), str)):
            raise HybridSingleAttemptError("ATTEMPT_MARKER_AUTHORITY_DRIFT")
    if ended is not None:
        if (ended.get("kind") != "ATTEMPT_TERMINAL"
                or ended.get("state") not in {
                    "SOURCE_ARCHIVED_DIAGNOSTIC",
                    "EXPLICIT_NO_DATA_NOT_COVERAGE",
                    "EMPTY_RESPONSE_UNQUALIFIED",
                    "REQUEST_OR_STORAGE_FAILED_NO_RETRY",
                }
                or ended.get("started_fingerprint") != started["fingerprint"]
                or ended.get("simulator_ready") is not False
                or ended.get("automatic_retry_authorized") is not False
                or ended.get("provider_requests_maximum") != 1):
            raise HybridSingleAttemptError("ATTEMPT_RESULT_AUTHORITY_DRIFT")
    return started, ended


def _single_item(
    batch: dict[str, Any], query_id: str,
) -> dict[str, Any]:
    if not isinstance(query_id, str) or not SHA.fullmatch(query_id):
        raise HybridSingleAttemptError("EXACT_QUERY_ID_REQUIRED")
    # Strict duplicate validation delegated to the accepted V2 interface.
    normalized = normalize_batch(batch)
    matched = []
    for item in normalized:
        qid = _fingerprint({
            "source_type": "option_history_quote", "query": item["query"],
        })
        if qid == query_id:
            matched.append(item)
    if not matched:
        raise HybridSingleAttemptError("QUERY_NOT_IN_FROZEN_REQUIREMENTS")
    identity = matched[0]["query"]
    if any(it["query"] != identity for it in matched):
        raise HybridSingleAttemptError("QUERY_ID_SCOPE_CONFLICT")
    if _adapter_status(identity) != "HOURLY_SDK_ADAPTER_MATCH":
        raise HybridSingleAttemptError("EXACT_HOURLY_ADAPTER_UNAVAILABLE")
    return identity


def inspect_single_attempt(
    settings: AtlasSettings,
    batch: dict[str, Any],
    query_id: str,
    *,
    plan_reader: Callable[..., dict[str, Any]] = plan_acquisition_reservations,
) -> dict[str, Any]:
    """Provider-free exact-query verification; NEVER creates a marker."""
    query = _single_item(batch, query_id)
    settings.assert_external_storage_binding("options")
    plan = plan_reader(settings, batch)
    result = next(
        (r for r in plan["queries"] if r["query_id"] == query_id),
        None,
    )
    if result is None or result["query"] != query:
        raise HybridSingleAttemptError("PLANNER_QUERY_IDENTITY_CHANGED")
    if (plan.get("paid_provider_authority") is not False
            or plan.get("provider_requests") != 0
            or plan.get("simulator_ready") is not False
            or result["simulator_ready"] is not False):
        raise HybridSingleAttemptError("PLANNER_AUTHORITY_DRIFT")
    reservation = _existing_reservation(settings, query_id, query)
    started, finished = _validate_existing(settings, query_id)
    if result["verified_sources"]:
        state = "LOCAL_SOURCE_ALREADY_PRESENT_NO_API"
    elif started is not None:
        state = ("ATTEMPT_COMPLETED_NO_RETRY" if finished is not None
                 else "ATTEMPT_STATUS_UNKNOWN_NO_RETRY")
    elif reservation is None:
        state = "NO_RESERVATION_NO_API"
    elif result["adapter"] != "HOURLY_SDK_ADAPTER_MATCH":
        state = "ADAPTER_UNAVAILABLE_NO_API"
    elif plan["storage"]["storage_status"] != "SAFE":
        state = "STORAGE_WARNING_OR_BLOCKED_NO_API"
    elif plan["storage"]["safe_available_bytes"] < reservation["reserved_worst_case_bytes"]:
        state = "STORAGE_HEADROOM_INSUFFICIENT_NO_API"
    elif reservation["reserved_worst_case_bytes"] < MAX_SOURCE_BYTES:
        state = "RESERVATION_SMALLER_THAN_SOURCE_LIMIT_NO_API"
    else:
        state = "RESERVED_READY_FOR_EXPLICIT_SINGLE_ATTEMPT"

    return {
        "contract": CONTRACT,
        "query_id": query_id,
        "query": query,
        "state": state,
        "reservation_fingerprint": (
            reservation["fingerprint"] if reservation else None
        ),
        "previous_attempt_marker": started is not None,
        "previous_attempt_result": finished is not None,
        "existing_verified_sources": len(result["verified_sources"]),
        "reservation_bytes": (
            reservation["reserved_worst_case_bytes"] if reservation else 0
        ),
        "source_preflight": "VERIFIED_LOCAL_ONLY",
        "paid_provider_authority": False,
        "automatic_retry_authorized": False,
        "simulator_ready": False,
        "provider_requests": 0,
    }


def acquire_one_hourly_source(
    settings: AtlasSettings,
    batch: dict[str, Any],
    query_id: str,
    *,
    authorize_paid_single_request: bool = False,
    acknowledge_ambiguous_request_no_retry: bool = False,
    reader: Callable[..., ThetaDataResponse] = option_history_hourly_quote_surface,
    plan_reader: Callable[..., dict[str, Any]] = plan_acquisition_reservations,
) -> dict[str, Any]:
    """Make <=one paid quote method call, only with two explicit opt-ins.

    Once the start marker has been committed to storage, even a process crash
    before SDK dispatch makes the query ineligible for automatic resumption.
    """
    if (authorize_paid_single_request is not True
            or acknowledge_ambiguous_request_no_retry is not True):
        raise HybridSingleAttemptError("EXPLICIT_PAID_ONE_REQUEST_AUTH_REQUIRED")
    preflight = inspect_single_attempt(
        settings, batch, query_id, plan_reader=plan_reader,
    )
    if preflight["state"] != "RESERVED_READY_FOR_EXPLICIT_SINGLE_ATTEMPT":
        raise HybridSingleAttemptError(
            "ONE_ATTEMPT_NOT_ELIGIBLE_" + preflight["state"]
        )
    query = preflight["query"]
    # Re-read all reservations and planning headroom immediately before writing.
    ledger = _outstanding_reservations(settings)
    if ledger["count"] < 1 or ledger["bytes"] < preflight["reservation_bytes"]:
        raise HybridSingleAttemptError("OUTSTANDING_RESERVATION_LEDGER_CHANGED")
    reserved = _existing_reservation(settings, query_id, query)
    if (reserved is None or
            reserved["fingerprint"] != preflight["reservation_fingerprint"]):
        raise HybridSingleAttemptError("RESERVATION_CHANGED_BEFORE_DISPATCH")
    started, finished = _validate_existing(settings, query_id)
    if started is not None or finished is not None:
        raise HybridSingleAttemptError("ATTEMPT_ALREADY_RECORDED_NO_RETRY")

    marker, terminal = _paths(settings, query_id)
    intent = _evidence({
        "contract": CONTRACT,
        "kind": "ATTEMPT_STARTED",
        "state": "POSSIBLY_DISPATCHED_NO_RETRY",
        "query_id": query_id,
        "query": query,
        "provider": "thetadata",
        "provider_method": HOURLY_METHOD,
        "reservation_fingerprint": reserved["fingerprint"],
        "reserved_bytes": reserved["reserved_worst_case_bytes"],
        "attempt_limit": 1,
        "automatic_retry_authorized": False,
        "provider_response_received": False,
        "simulator_ready": False,
    })
    # Write BEFORE network access. If this fails, the SDK is never invoked.
    _write_receipt(marker, intent)

    status = "REQUEST_OR_STORAGE_FAILED_NO_RETRY"
    archived: dict[str, Any] | None = None
    error_type: str | None = None
    response_rows: int | None = None
    try:
        response = reader(
            symbol=query["symbol"], date_et=query["date_et"],
            right=query["right"], max_dte=query["max_dte"],
            strike_range=query["strike_range"],
        )
        if not isinstance(response, ThetaDataResponse):
            raise HybridSingleAttemptError("PROVIDER_RESPONSE_ENVELOPE_INVALID")
        response_rows = len(response.rows)
        if response.explicit_no_data:
            if response.rows:
                raise HybridSingleAttemptError("CONTRADICTORY_EXPLICIT_NO_DATA")
            status = "EXPLICIT_NO_DATA_NOT_COVERAGE"
        elif not response.rows:
            status = "EMPTY_RESPONSE_UNQUALIFIED"
        else:
            saved = store_historical_quote_source(
                settings, query, response=response, write=True,
            )
            if (not saved["archived"] or not saved["indexed"]
                    or saved["simulator_ready"] is not False
                    or saved["source_bytes"] > reserved["reserved_worst_case_bytes"]):
                raise HybridSingleAttemptError("STORED_SOURCE_OUTSIDE_RESERVATION")
            archived = {
                "source_id": saved["source_id"],
                "source_sha256": saved["body_sha256"],
                "quote_rows": saved["diagnostics"]["observed_rows"],
                "compressed_bytes": saved["compressed_bytes"],
                "original_bytes": saved["source_bytes"],
            }
            status = "SOURCE_ARCHIVED_DIAGNOSTIC"
    except Exception as exc:
        # Never auto retry, even if delivery timed out or local index failed.
        error_type = type(exc).__name__
    terminal_data = _evidence({
        "contract": CONTRACT,
        "kind": "ATTEMPT_TERMINAL",
        "query_id": query_id,
        "started_fingerprint": intent["fingerprint"],
        "state": status,
        "error_type": error_type,
        "provider_rows_received": response_rows,
        "stored_source": archived,
        "provider_requests_maximum": 1,
        "automatic_retry_authorized": False,
        "simulator_ready": False,
        "source_coverage_proven": False,
    })
    _write_receipt(terminal, terminal_data)
    return {
        "contract": CONTRACT, "query_id": query_id,
        "result_state": status, "stored_source": archived,
        "error_type": error_type,
        "provider_requests_maximum": 1,
        "automatic_retry_authorized": False,
        "simulator_ready": False,
    }
