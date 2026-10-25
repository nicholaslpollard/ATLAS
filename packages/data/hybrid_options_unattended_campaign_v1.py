from __future__ import annotations

"""V12 unattended, resumable exact frozen at-time source ACQUISITION.

User granted ongoing provider-call permission; the CLI has no interactive
authorization tokens or approval phrases. Preview is the default; --run
streams the remaining frozen requests in priority order, single-threaded,
with an optional --max-calls per execution (omission means all remaining).

Only the exact 9,866-request frozen V9 demand is eligible. Existing V11 AAL
and retained V10 SPY probes are skipped, never repeated. Each attempted
query writes a collision-safe, immutable pre-dispatch marker. Any attempt
with an uncertain result is never automatically retried, but the campaign
can skip that one identity and continue on next execution.

All nonempty SDK-normalized bodies are archived, whole and lossless, on
external D: BEFORE semantic diagnosis. Out-of-DTE/invalid schemas remain
diagnostic and cannot become executable quotes. Cumulative storage budget
and minimum free disk are evaluated again BEFORE EACH provider request.
An SDK exception ends the current run; future invocations can resume.
"""

from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Callable
import zlib

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_acquisition_reservations_v1 import (
    _outstanding_reservations, _storage_capacity,
)
from packages.data.hybrid_options_at_time_one_call_v1 import (
    _load_full_manifest, _validate_attempt_state,
)
from packages.data.hybrid_options_at_time_source_gate_v1 import (
    MAX_RESPONSE_BYTES, diagnose_at_time_response, validate_exact_request,
)
from packages.data.hybrid_options_lossless_archive_v1 import _write_immutable
from packages.data.hybrid_options_frozen_research_demand_v1 import (
    MAX_MANIFEST_BYTES,
)
from packages.data.hybrid_options_saved_aal_audit_v1 import (
    AAL_QUERY_ID, audit_saved_aal,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.research_storage import inspect_research_storage
from packages.providers.thetadata.client import (
    ThetaDataResponse, _canonical_bytes, option_at_time_quote_surface,
)

CONTRACT = "atlas-hybrid-options-at-time-autonomous-source-campaign-v12"
ROOT_REL = "data/options/hybrid/at_time_source_campaign_v12"
LEGACY_SPY_DATE = "2025-06-09"
MAX_RECEIPT_BYTES = 16 * 1024
MAX_ARCHIVE_BYTES = MAX_RESPONSE_BYTES + 4096
MIN_CAPACITY_PER_REQUEST = 2 * MAX_RESPONSE_BYTES + 2 * MAX_RECEIPT_BYTES
TERMINAL_STATES = frozenset({
    "RAW_ARCHIVED_SCOPE_DIAGNOSTIC",
    "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC",
    "RAW_ARCHIVED_INVALID_SCHEMA",
    "EXPLICIT_NO_DATA_SOURCE_ONLY",
    "EMPTY_RESPONSE_SOURCE_ONLY",
    "PROVIDER_OR_STORAGE_ERROR_NO_RETRY",
})


class HybridCampaignError(ValueError):
    pass


def _record_path(settings: AtlasSettings, qid: str, kind: str) -> Path:
    root = settings.resolved_path(ROOT_REL)
    return root / "attempts" / qid[:2] / (qid + "." + kind + ".json")


def _archive_path(settings: AtlasSettings, qid: str) -> Path:
    return (
        settings.resolved_path(ROOT_REL)
        / "sources" / qid[:2] / (qid + ".json.gz")
    )


def _evidence(body: dict[str, Any]) -> dict[str, Any]:
    result = dict(body)
    result["fingerprint"] = _fingerprint(result)
    return result


def _read_receipt(path: Path, qid: str, kind: str) -> dict[str, Any] | None:
    if path.is_symlink():
        raise HybridCampaignError("CAMPAIGN_RECEIPT_SYMLINK")
    if not path.exists():
        return None
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_RECEIPT_BYTES:
        raise HybridCampaignError("CAMPAIGN_RECEIPT_SIZE_OR_TYPE")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeError, ValueError) as exc:
        raise HybridCampaignError("CAMPAIGN_RECEIPT_NOT_JSON") from exc
    if (not isinstance(value, dict)
            or value.get("contract") != CONTRACT
            or value.get("query_id") != qid
            or value.get("kind") != kind
            or value.get("manifest_fingerprint") !=
                "138234eb2276409ae641f6e40d7f6eb3c779502ffb5459b612e0dbc439cb4b63"
            or value.get("simulator_ready") is not False
            or value.get("source_coverage_proven") is not False
            or value.get("fingerprint") != _fingerprint({
                k: v for k, v in value.items() if k != "fingerprint"
            })):
        raise HybridCampaignError("CAMPAIGN_RECEIPT_TAMPER_OR_SCOPE_DRIFT")
    if kind == "started" and value.get("state") != "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY":
        raise HybridCampaignError("CAMPAIGN_STARTED_STATE_DRIFT")
    if kind == "terminal" and value.get("state") not in TERMINAL_STATES:
        raise HybridCampaignError("CAMPAIGN_TERMINAL_STATE_DRIFT")
    return value


def _write_receipt(settings: AtlasSettings, qid: str, kind: str,
                   body: dict[str, Any]) -> None:
    path = _record_path(settings, qid, kind)
    if path.parent.is_symlink() or path.is_symlink() or path.exists():
        raise HybridCampaignError("CAMPAIGN_IMMUTABLE_RECEIPT_COLLISION")
    payload = (json.dumps(body, sort_keys=True, indent=2, allow_nan=False)
               + "\n").encode("utf-8")
    if len(payload) > MAX_RECEIPT_BYTES:
        raise HybridCampaignError("CAMPAIGN_RECEIPT_OVERSIZE")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_immutable(path, payload)
    if _read_receipt(path, qid, kind) != body:
        raise HybridCampaignError("CAMPAIGN_RECEIPT_POSTWRITE_MISMATCH")


def _check_archive(settings: AtlasSettings,
                   qid: str, source: dict[str, Any]) -> None:
    path = _archive_path(settings, qid)
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= MAX_ARCHIVE_BYTES
            or source["original_bytes"] > MAX_RESPONSE_BYTES
            or path.stat().st_size != source["compressed_bytes"]):
        raise HybridCampaignError("CAMPAIGN_ARCHIVE_INVALID")
    packed = path.read_bytes()
    if hashlib.sha256(packed).hexdigest() != source["compressed_sha256"]:
        raise HybridCampaignError("CAMPAIGN_ARCHIVE_SHA_DRIFT")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        raw = decoder.decompress(packed, MAX_RESPONSE_BYTES + 1)
    except zlib.error as exc:
        raise HybridCampaignError("CAMPAIGN_ARCHIVE_GZIP_CORRUPT") from exc
    if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
            or len(raw) != source["original_bytes"]
            or hashlib.sha256(raw).hexdigest() != source["original_sha256"]):
        raise HybridCampaignError("CAMPAIGN_ARCHIVE_LOSSLESS_MISMATCH")


def _inspect_attempt(settings: AtlasSettings, qid: str) -> str:
    start = _read_receipt(_record_path(settings, qid, "started"), qid, "started")
    finish = _read_receipt(_record_path(settings, qid, "terminal"), qid, "terminal")
    if finish is not None and (
        start is None or finish.get("started_fingerprint") != start["fingerprint"]
    ):
        raise HybridCampaignError("CAMPAIGN_TERMINAL_WITHOUT_MATCHING_START")
    if start is None:
        return "UNATTEMPTED"
    if finish is None:
        return "UNCERTAIN_PRIOR_ATTEMPT_NO_RETRY"
    archive = finish.get("archive")
    if finish["state"].startswith("RAW_ARCHIVED"):
        if not isinstance(archive, dict):
            raise HybridCampaignError("CAMPAIGN_TERMINAL_MISSING_ARCHIVE")
        _check_archive(settings, qid, archive)
    elif archive is not None:
        raise HybridCampaignError("CAMPAIGN_UNEXPECTED_ARCHIVE_ON_NON_SOURCE")
    return finish["state"]


def _store_entire_source(settings: AtlasSettings, qid: str,
                         response: ThetaDataResponse) -> dict[str, Any]:
    if (not isinstance(response, ThetaDataResponse)
            or response.response_bytes != len(response.raw_body)
            or not 0 < len(response.raw_body) <= MAX_RESPONSE_BYTES
            or _canonical_bytes(response.rows) != response.raw_body):
        raise HybridCampaignError("CANONICAL_SOURCE_RECEIPT_INVALID")
    packed = gzip.compress(response.raw_body, compresslevel=9, mtime=0)
    if not 0 < len(packed) <= MAX_ARCHIVE_BYTES:
        raise HybridCampaignError("COMPRESSED_SOURCE_EXCEEDS_PER_QUERY_LIMIT")
    path = _archive_path(settings, qid)
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise HybridCampaignError("SOURCE_ID_ALREADY_ARCHIVED")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_immutable(path, packed)
    source = {
        "original_sha256": hashlib.sha256(response.raw_body).hexdigest(),
        "compressed_sha256": hashlib.sha256(packed).hexdigest(),
        "original_bytes": len(response.raw_body),
        "compressed_bytes": len(packed),
        "observed_rows": len(response.rows),
        "source_coverage_proven": False,
        "simulator_ready": False,
    }
    _check_archive(settings, qid, source)
    return source


def _prior_external_source_ids(
    settings: AtlasSettings, manifest: dict[str, Any],
    candidate_plan: Path, manifest_path: Path,
) -> set[str]:
    # Independently verify old full-archive AAL evidence and quarantine.
    audit_saved_aal(settings, manifest_path, candidate_plan)
    started, finished = _validate_attempt_state(settings)
    if (started is None or finished is None
            or started.get("source_request_id") != AAL_QUERY_ID):
        raise HybridCampaignError("KNOWN_AAL_V11_EVIDENCE_NOT_ACCEPTED")
    existing = {AAL_QUERY_ID}
    matches = [
        row for row in manifest["requests"]
        if row["origin"] == "FROZEN_SPY_WEEKLY_OPTIONS_NATIVE"
        and row["date_et"] == LEGACY_SPY_DATE
    ]
    if len(matches) != 1:
        raise HybridCampaignError("V10_ORIGINAL_SPY_SOURCE_NOT_IN_MANIFEST")
    existing.add(matches[0]["query_id"])
    return existing


def _safe_storage(settings: AtlasSettings,
                  storage_reader: Callable[..., Any]) -> dict[str, Any]:
    snap = _storage_capacity(settings, storage_reader)
    reservations = _outstanding_reservations(settings)
    safe = snap["safe_available_bytes"] - reservations["bytes"]
    return {
        "available_after_hourly_reservations": max(0, safe),
        "safe": (
            snap["storage_status"] != "BLOCKED_MINIMUM_FREE_SPACE"
            and safe >= MIN_CAPACITY_PER_REQUEST
        ),
        "storage_status": snap["storage_status"],
    }


def preview_campaign(
    settings: AtlasSettings, manifest_path: Path, candidate_plan: Path,
    *,
    storage_reader: Callable[..., Any] = inspect_research_storage,
) -> dict[str, Any]:
    frozen = _load_full_manifest(settings, manifest_path, candidate_plan)
    if frozen["source_request_count"] != 9866:
        raise HybridCampaignError("EXACT_PINNED_CAMPAIGN_SCOPE_DRIFT")
    excluded = _prior_external_source_ids(
        settings, frozen, candidate_plan, manifest_path,
    )
    first = None
    counters = {
        "previously_attempted": 0, "uncertain_attempts": 0,
        "not_attempted": 0, "external_existing": len(excluded),
        "saved_archives": 0, "quarantined_archives": 0,
    }
    for row in frozen["requests"]:
        validate_exact_request(row)
        if row["query_id"] in excluded:
            continue
        state = _inspect_attempt(settings, row["query_id"])
        if state == "UNATTEMPTED":
            counters["not_attempted"] += 1
            if first is None:
                first = row
        else:
            counters["previously_attempted"] += 1
            if state == "UNCERTAIN_PRIOR_ATTEMPT_NO_RETRY":
                counters["uncertain_attempts"] += 1
            if state.startswith("RAW_ARCHIVED"):
                counters["saved_archives"] += 1
            if state == "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC":
                counters["quarantined_archives"] += 1
    budget = _safe_storage(settings, storage_reader)
    return {
        "contract": CONTRACT,
        "mode": "OFFLINE_PREVIEW_NO_PROVIDER",
        "manifest_fingerprint": frozen["manifest_fingerprint"],
        "total_frozen_requests": frozen["source_request_count"],
        "counts": counters,
        "next_request": None if first is None else {
            "query_id": first["query_id"], "date_et": first["date_et"],
            "symbol": first["symbol"], "clock": first["decision_clock_et"],
            "right": first["right"], "priority": first["priority"],
        },
        "storage": budget,
        "provider_requests": 0,
        "simulations_run": 0,
        "source_coverage_proven": False,
        "simulator_ready": False,
    }


def run_campaign(
    settings: AtlasSettings, manifest_path: Path, candidate_plan: Path,
    *,
    max_calls: int | None = None,
    reader: Callable[..., ThetaDataResponse] = option_at_time_quote_surface,
    storage_reader: Callable[..., Any] = inspect_research_storage,
) -> dict[str, Any]:
    """No interactive authorizations. One invocation resumes saved demand."""
    if max_calls is not None and (
        type(max_calls) is not int or max_calls < 1
    ):
        raise HybridCampaignError("MAX_CALLS_MUST_BE_POSITIVE_OR_OMITTED")
    snapshot = preview_campaign(
        settings, manifest_path, candidate_plan, storage_reader=storage_reader,
    )
    frozen = _load_full_manifest(settings, manifest_path, candidate_plan)
    excluded = _prior_external_source_ids(
        settings, frozen, candidate_plan, manifest_path,
    )
    results = {
        "contract": CONTRACT, "mode": "UNATTENDED_RESUMABLE_ACQUISITION",
        "manifest_fingerprint": frozen["manifest_fingerprint"],
        "provider_calls_this_run": 0,
        "archives_written_this_run": 0,
        "out_of_dte_archives_this_run": 0,
        "invalid_schema_archives_this_run": 0,
        "skipped_existing_or_ambiguous": 0,
        "stop_reason": "FULL_FROZEN_MANIFEST_SCANNED",
        "last_query_id": None,
        "simulator_ready": False, "source_coverage_proven": False,
    }
    if not snapshot["storage"]["safe"]:
        results["stop_reason"] = "SAFE_STORAGE_HEADROOM_INSUFFICIENT"
        return results
    for row in frozen["requests"]:
        qid = row["query_id"]
        if qid in excluded:
            results["skipped_existing_or_ambiguous"] += 1
            continue
        if _inspect_attempt(settings, qid) != "UNATTEMPTED":
            results["skipped_existing_or_ambiguous"] += 1
            continue
        if max_calls is not None and results["provider_calls_this_run"] >= max_calls:
            results["stop_reason"] = "OPTIONAL_RUN_REQUEST_LIMIT_REACHED"
            break
        budget = _safe_storage(settings, storage_reader)
        if not budget["safe"]:
            results["stop_reason"] = "SAFE_STORAGE_HEADROOM_INSUFFICIENT"
            break
        sdk = validate_exact_request(row)
        # Immutable pre-dispatch marker prevents duplicate paid calls after
        # killed processes or ambiguous provider worker/network failures.
        start = _evidence({
            "contract": CONTRACT, "kind": "started",
            "state": "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY",
            "manifest_fingerprint": frozen["manifest_fingerprint"],
            "query_id": qid,
            "original_query_fingerprint": row["origin_query_fingerprint"],
            "sdk_kwargs": sdk,
            "simulator_ready": False, "source_coverage_proven": False,
        })
        _write_receipt(settings, qid, "started", start)
        results["provider_calls_this_run"] += 1
        results["last_query_id"] = qid
        diagnostic = None
        archive = None
        error_type = None
        state = "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
        try:
            source = reader(**sdk)
            if not isinstance(source, ThetaDataResponse):
                raise HybridCampaignError("SOURCE_RESPONSE_TYPE_CHANGED")
            if source.rows:
                archive = _store_entire_source(settings, qid, source)
                try:
                    diagnostic = diagnose_at_time_response(row, source)
                    state = (
                        "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC"
                        if diagnostic["outside_requested_dte_rows"] > 0
                        else "RAW_ARCHIVED_SCOPE_DIAGNOSTIC"
                    )
                except Exception as exc:
                    error_type = type(exc).__name__
                    state = "RAW_ARCHIVED_INVALID_SCHEMA"
            else:
                diagnostic = diagnose_at_time_response(row, source)
                state = (
                    "EXPLICIT_NO_DATA_SOURCE_ONLY"
                    if diagnostic["status"] == "EXPLICIT_NO_DATA_NOT_COVERAGE"
                    else "EMPTY_RESPONSE_SOURCE_ONLY"
                )
        except Exception as exc:
            error_type = type(exc).__name__
            if archive is not None:
                state = "RAW_ARCHIVED_INVALID_SCHEMA"
        end = _evidence({
            "contract": CONTRACT, "kind": "terminal",
            "manifest_fingerprint": frozen["manifest_fingerprint"],
            "query_id": qid, "started_fingerprint": start["fingerprint"],
            "state": state, "archive": archive,
            "diagnostic_fingerprint": (
                diagnostic["diagnostic_fingerprint"] if diagnostic else None
            ),
            "error_type": error_type,
            "simulator_ready": False, "source_coverage_proven": False,
        })
        _write_receipt(settings, qid, "terminal", end)
        if archive is not None:
            results["archives_written_this_run"] += 1
        if state == "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC":
            results["out_of_dte_archives_this_run"] += 1
        if state == "RAW_ARCHIVED_INVALID_SCHEMA":
            results["invalid_schema_archives_this_run"] += 1
        if state == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY":
            # Avoid burning the user's plan after an auth or SDK failure.
            results["stop_reason"] = "PROVIDER_OR_STORAGE_FAILURE_STOPPED_RUN"
            break
    return results
