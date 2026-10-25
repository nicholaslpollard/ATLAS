from __future__ import annotations

"""V11 one-attempt qualification of ONE frozen 2021 09:35 CALL at-time source.

This is NOT full historical acquisition. The default path is offline preview.
A paid request requires the explicitly frozen 9,866-query D:-bound manifest
AND its independently accepted 9,455-query source plan, one exact pinned
2021 qualification-anchor query ID and THREE affirmative operator approvals.

A global immutable STARTED marker is committed before any ThetaData access.
A crash, timeout, provider fault or archive failure blocks every other V11
provider request. The full original normalized response is losslessly gzipped
on D: even if its DTE/scope checks subsequently fail. No data enters V6,
the simulator, strategy evidence, PAPER or LIVE.
"""

import gzip
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable
import zlib

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_acquisition_reservations_v1 import (
    _outstanding_reservations, _storage_capacity,
)
from packages.data.hybrid_options_at_time_source_gate_v1 import (
    MAX_RESPONSE_BYTES, diagnose_at_time_response, validate_exact_request,
)
from packages.data.hybrid_options_frozen_research_demand_v1 import (
    CONTRACT as V9_CONTRACT,
    MAX_MANIFEST_BYTES,
    build_frozen_research_demand,
    load_candidate_source_plan,
)
from packages.data.hybrid_options_lossless_archive_v1 import _write_immutable
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.research_storage import inspect_research_storage
from packages.providers.thetadata.client import (
    ThetaDataResponse, _canonical_bytes, option_at_time_quote_surface,
)

CONTRACT = "atlas-hybrid-at-time-single-qualification-attempt-v1"
ROOT_REL = "data/options/hybrid/at_time_qualification_v1"
SOURCE_MANIFEST_PREFIX = "hybrid_exact_at_time_research_demand_v1_"
PINNED_MANIFEST_FINGERPRINT = (
    "138234eb2276409ae641f6e40d7f6eb3c779502ffb5459b612e0dbc439cb4b63"
)
MAX_RECEIPT_BYTES = 16 * 1024
MAX_ARCHIVE_BYTES = MAX_RESPONSE_BYTES + 4096
MAX_PAID_ATTEMPTS_FOR_CAMPAIGN = 1
GIB = 1024**3
SHA = re.compile(r"[a-f0-9]{64}")


class HybridAtTimeQualificationError(ValueError):
    pass


def _paths(settings: AtlasSettings) -> tuple[Path, Path]:
    root = settings.resolved_path(ROOT_REL)
    return (
        root / "qualification_once.started.json",
        root / "qualification_once.terminal.json",
    )


def _fp_body(value: dict[str, Any]) -> dict[str, Any]:
    body = dict(value)
    body["fingerprint"] = _fingerprint(body)
    return body


def _checked_receipt(path: Path, kind: str) -> dict[str, Any] | None:
    if path.is_symlink():
        raise HybridAtTimeQualificationError("ATTEMPT_RECEIPT_SYMLINK")
    if not path.exists():
        return None
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_RECEIPT_BYTES:
        raise HybridAtTimeQualificationError("ATTEMPT_RECEIPT_INVALID_SIZE")
    try:
        content = json.loads(path.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise HybridAtTimeQualificationError("ATTEMPT_RECEIPT_JSON_INVALID") from exc
    if (not isinstance(content, dict)
            or content.get("contract") != CONTRACT
            or content.get("kind") != kind
            or content.get("manifest_fingerprint") != PINNED_MANIFEST_FINGERPRINT
            or content.get("max_provider_attempts") != MAX_PAID_ATTEMPTS_FOR_CAMPAIGN
            or content.get("automatic_retry_allowed") is not False
            or content.get("simulator_ready") is not False
            or content.get("fingerprint") != _fingerprint({
                k: v for k, v in content.items() if k != "fingerprint"
            })):
        raise HybridAtTimeQualificationError("ATTEMPT_RECEIPT_IDENTITY_DRIFT")
    if kind == "STARTED" and (
        content.get("state") != "POSSIBLY_DISPATCHED_NO_RETRY"
        or not isinstance(content.get("source_request_id"), str)
        or not SHA.fullmatch(content["source_request_id"])
        or content.get("provider_method") != "option_at_time_quote_surface"
    ):
        raise HybridAtTimeQualificationError("ATTEMPT_START_AUTHORITY_DRIFT")
    if kind == "TERMINAL" and content.get("state") not in (
        "SOURCE_ARCHIVED_DIAGNOSTIC_ONLY",
        "SOURCE_ARCHIVED_QUARANTINED_DTE",
        "SOURCE_ARCHIVED_INVALID_SCHEMA",
        "EMPTY_RESPONSE_NO_COVERAGE",
        "EXPLICIT_NO_DATA_NO_COVERAGE",
        "ATTEMPT_FAILED_UNCERTAIN_NO_RETRY",
    ):
        raise HybridAtTimeQualificationError("ATTEMPT_RESULT_AUTHORITY_DRIFT")
    return content


def _validate_attempt_state(settings: AtlasSettings) -> tuple[
    dict[str, Any] | None, dict[str, Any] | None
]:
    marker, terminal = _paths(settings)
    root = settings.resolved_path("data/options").resolve()
    for path in (marker, terminal):
        if not path.parent.resolve().is_relative_to(root):
            raise HybridAtTimeQualificationError("ATTEMPT_PATH_ESCAPES_OPTIONS")
    started = _checked_receipt(marker, "STARTED")
    finished = _checked_receipt(terminal, "TERMINAL")
    if finished is not None and (
        started is None or
        finished.get("started_fingerprint") != started["fingerprint"] or
        finished.get("source_request_id") != started["source_request_id"]
    ):
        raise HybridAtTimeQualificationError("ORPHAN_OR_DRIFTED_TERMINAL_RECEIPT")
    return started, finished


def _record_once(path: Path, body: dict[str, Any], kind: str) -> None:
    raw = (json.dumps(
        body, indent=2, sort_keys=True, allow_nan=False,
    ) + "\n").encode("utf-8")
    if not 0 < len(raw) <= MAX_RECEIPT_BYTES:
        raise HybridAtTimeQualificationError("ATTEMPT_RECEIPT_TOO_LARGE")
    if path.exists() or path.is_symlink():
        raise HybridAtTimeQualificationError("ATTEMPT_ALREADY_RECORDED")
    if path.parent.is_symlink():
        raise HybridAtTimeQualificationError("ATTEMPT_DIRECTORY_SYMLINK")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_immutable(path, raw)
    if _checked_receipt(path, kind) != body:
        raise HybridAtTimeQualificationError("ATTEMPT_POSTWRITE_VERIFICATION_FAILED")


def _load_full_manifest(settings: AtlasSettings,
                        manifest: Path, candidate_plan: Path) -> dict[str, Any]:
    settings.assert_external_storage_binding("options")
    root = settings.resolved_path("data/options/manifests")
    actual = manifest if manifest.is_absolute() else settings.resolved_path(manifest)
    if (actual.is_symlink() or not actual.is_file()
            or not actual.resolve().is_relative_to(root.resolve())
            or actual.name !=
                SOURCE_MANIFEST_PREFIX + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
            or not 0 < actual.stat().st_size <= MAX_MANIFEST_BYTES):
        raise HybridAtTimeQualificationError("PINNED_FULL_MANIFEST_NOT_FOUND")
    try:
        saved = json.loads(actual.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise HybridAtTimeQualificationError("PINNED_MANIFEST_JSON_INVALID") from exc
    if (not isinstance(saved, dict)
            or saved.get("contract") != V9_CONTRACT
            or saved.get("manifest_fingerprint") != PINNED_MANIFEST_FINGERPRINT):
        raise HybridAtTimeQualificationError("PINNED_MANIFEST_IDENTITY_DRIFT")
    original = load_candidate_source_plan(settings, candidate_plan)
    reconstructed = build_frozen_research_demand(original)
    if saved != reconstructed or reconstructed["source_request_count"] != 9866:
        raise HybridAtTimeQualificationError("FULL_MANIFEST_SOURCE_LINEAGE_DRIFT")
    return reconstructed


def _qualifier_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    # Only one 2021 multiyear CALL anchor may be selected for the V11
    # scientific probe; failed 2025 SPY quote is never re-requested.
    anchors = [
        row for row in manifest["requests"]
        if row["origin"] == "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES"
        and row["date_et"].startswith("2021-")
        and row["qualification_anchor"] is True
    ]
    anchors.sort(key=lambda x: (
        x["date_et"], x["symbol"], x["query_id"],
    ))
    if len(anchors) != 3 or any(
        row["params"]["max_dte"] != 75
        or row["params"]["strike_range"] is not None
        or row["right"] != "call"
        or row["decision_clock_et"] != "09:35:00.000"
        for row in anchors
    ):
        raise HybridAtTimeQualificationError("2021_FROZEN_QUALIFICATION_ANCHORS_DRIFT")
    for row in anchors:
        validate_exact_request(row)
    return anchors


def inspect_one_qualification(
    settings: AtlasSettings, manifest: Path, candidate_plan: Path,
    *, query_id: str | None = None,
    storage_reader: Callable[[AtlasSettings], Any] = inspect_research_storage,
) -> dict[str, Any]:
    """No-call, no-write preview; returns a single pinned anchor's identity."""
    frozen = _load_full_manifest(settings, manifest, candidate_plan)
    anchors = _qualifier_rows(frozen)
    selected_id = query_id or anchors[0]["query_id"]
    if not isinstance(selected_id, str) or not SHA.fullmatch(selected_id):
        raise HybridAtTimeQualificationError("EXACT_64_HEX_QUERY_ID_REQUIRED")
    selected = next(
        (x for x in anchors if x["query_id"] == selected_id), None,
    )
    if selected is None:
        raise HybridAtTimeQualificationError("QUERY_NOT_A_FROZEN_2021_ANCHOR")
    started, finished = _validate_attempt_state(settings)
    capacity = _storage_capacity(settings, storage_reader)
    outstanding = _outstanding_reservations(settings)
    required = MAX_RESPONSE_BYTES + MAX_ARCHIVE_BYTES + (2 * MAX_RECEIPT_BYTES)
    if started is not None:
        status = ("PRIOR_ATTEMPT_COMPLETE_NO_RETRY"
                  if finished is not None
                  else "PRIOR_ATTEMPT_UNCERTAIN_NO_RETRY")
    elif (capacity["storage_status"] == "BLOCKED_MINIMUM_FREE_SPACE"
          or capacity["safe_available_bytes"] - outstanding["bytes"] < required):
        status = "STORAGE_HEADROOM_BLOCKS_ONE_CALL"
    else:
        status = "ELIGIBLE_FOR_SEPARATE_EXPLICIT_ONE_CALL_ONLY"
    return {
        "contract": CONTRACT,
        "manifest_fingerprint": frozen["manifest_fingerprint"],
        "source_request_id": selected_id,
        "qualifying_anchor": {
            "priority": selected["priority"],
            "symbol": selected["symbol"],
            "date_et": selected["date_et"],
            "clock": selected["decision_clock_et"],
            "right": selected["right"],
            "max_dte": selected["params"]["max_dte"],
            "strike_range": selected["params"]["strike_range"],
        },
        "eligible_2021_anchors": [
            {"query_id": row["query_id"], "date_et": row["date_et"],
             "symbol": row["symbol"]}
            for row in anchors
        ],
        "status": status,
        "prior_attempt_marker": started is not None,
        "prior_terminal_result": finished is not None,
        "outstanding_hourly_reservation_bytes": outstanding["bytes"],
        "safe_additional_budget_bytes": capacity["safe_available_bytes"],
        "one_response_cap_bytes": MAX_RESPONSE_BYTES,
        "sdk_max_dte_forwarding_proven": False,
        "paid_provider_authority": False,
        "automatic_retry_allowed": False,
        "simulator_ready": False,
        "provider_requests": 0,
    }


def _archive_response(settings: AtlasSettings,
                      request_id: str,
                      source: ThetaDataResponse) -> dict[str, Any]:
    """Write exactly one full original, bounded, lossless gzip source to D:."""
    if (not isinstance(source, ThetaDataResponse)
            or not 0 < len(source.raw_body) <= MAX_RESPONSE_BYTES
            or source.response_bytes != len(source.raw_body)
            or source.raw_body != _canonical_bytes(source.rows)):
        raise HybridAtTimeQualificationError("RAW_SOURCE_ENVELOPE_INVALID")
    packed = gzip.compress(source.raw_body, compresslevel=9, mtime=0)
    if not 0 < len(packed) <= MAX_ARCHIVE_BYTES:
        raise HybridAtTimeQualificationError("COMPRESSED_SOURCE_SIZE_INVALID")
    source_sha = hashlib.sha256(source.raw_body).hexdigest()
    stored_sha = hashlib.sha256(packed).hexdigest()
    root = settings.resolved_path(ROOT_REL) / "source" / source_sha[:2]
    path = root / (source_sha + ".json.gz")
    if path.exists() or path.is_symlink() or root.is_symlink():
        raise HybridAtTimeQualificationError("SOURCE_ARCHIVE_COLLISION_NO_OVERWRITE")
    root.mkdir(parents=True, exist_ok=True)
    _write_immutable(path, packed)
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size != len(packed)):
        raise HybridAtTimeQualificationError("SOURCE_ARCHIVE_POSTWRITE_MISMATCH")
    on_disk = path.read_bytes()
    if hashlib.sha256(on_disk).hexdigest() != stored_sha:
        raise HybridAtTimeQualificationError("COMPRESSED_SOURCE_SHA_CHANGED")
    # Bounds decompression to the original byte count plus one.
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    restored = decoder.decompress(on_disk, len(source.raw_body) + 1)
    if (not decoder.eof or decoder.unconsumed_tail or decoder.unused_data
            or restored != source.raw_body):
        raise HybridAtTimeQualificationError("LOSSLESS_SOURCE_REPLAY_FAILED")
    return {
        "relative_archive": str(path.relative_to(
            settings.resolved_path("data/options")
        )).replace("\\", "/"),
        "original_sha256": source_sha,
        "compressed_sha256": stored_sha,
        "original_bytes": len(source.raw_body),
        "compressed_bytes": len(packed),
        "observed_rows": len(source.rows),
        "full_original_retained": True,
        "source_coverage_proven": False,
        "simulator_ready": False,
    }


def run_one_qualification(
    settings: AtlasSettings,
    manifest: Path,
    candidate_plan: Path,
    *,
    query_id: str,
    authorize_one_paid_diagnostic_call: bool = False,
    acknowledge_max_dte_unproven: bool = False,
    acknowledge_no_retry_after_ambiguity: bool = False,
    reader: Callable[..., ThetaDataResponse] = option_at_time_quote_surface,
    storage_reader: Callable[[AtlasSettings], Any] = inspect_research_storage,
) -> dict[str, Any]:
    if not (
        authorize_one_paid_diagnostic_call is True
        and acknowledge_max_dte_unproven is True
        and acknowledge_no_retry_after_ambiguity is True
    ):
        raise HybridAtTimeQualificationError(
            "THREE_EXPLICIT_PAID_DIAGNOSTIC_APPROVALS_REQUIRED"
        )
    preliminary = inspect_one_qualification(
        settings, manifest, candidate_plan,
        query_id=query_id, storage_reader=storage_reader,
    )
    if preliminary["status"] != "ELIGIBLE_FOR_SEPARATE_EXPLICIT_ONE_CALL_ONLY":
        raise HybridAtTimeQualificationError(
            "ONE_CALL_SOURCE_PREFLIGHT_BLOCKED_" + preliminary["status"]
        )
    frozen = _load_full_manifest(settings, manifest, candidate_plan)
    row = next(x for x in _qualifier_rows(frozen)
               if x["query_id"] == query_id)
    kwargs = validate_exact_request(row)
    if _validate_attempt_state(settings)[0] is not None:
        raise HybridAtTimeQualificationError("GLOBAL_CAMPAIGN_ATTEMPT_ALREADY_EXISTS")
    marker, result = _paths(settings)
    started = _fp_body({
        "contract": CONTRACT,
        "kind": "STARTED",
        "state": "POSSIBLY_DISPATCHED_NO_RETRY",
        "manifest_fingerprint": PINNED_MANIFEST_FINGERPRINT,
        "source_request_id": query_id,
        "original_source_fingerprint": row["original_source_fingerprint"],
        "original_query_fingerprint": row["origin_query_fingerprint"],
        "query": kwargs,
        "provider_method": "option_at_time_quote_surface",
        "max_provider_attempts": 1,
        "automatic_retry_allowed": False,
        "simulator_ready": False,
    })
    # Commit BEFORE constructing the actual provider worker/request.
    _record_once(marker, started, "STARTED")

    archive = None
    diagnostic = None
    error_type = None
    status = "ATTEMPT_FAILED_UNCERTAIN_NO_RETRY"
    try:
        response = reader(**kwargs)
        if not isinstance(response, ThetaDataResponse):
            raise HybridAtTimeQualificationError("SDK_RESPONSE_TYPE_CHANGED")
        if not response.rows:
            # Even an empty/no-data response must prove its canonical SDK
            # envelope, pinned provenance and explicit no-data semantics.
            diagnostic = diagnose_at_time_response(row, response)
            status = (
                "EXPLICIT_NO_DATA_NO_COVERAGE"
                if diagnostic["status"] == "EXPLICIT_NO_DATA_NOT_COVERAGE"
                else "EMPTY_RESPONSE_NO_COVERAGE"
            )
        else:
            # Preserve the complete raw response BEFORE semantic diagnostics.
            archive = _archive_response(settings, query_id, response)
            diagnostic = diagnose_at_time_response(row, response)
            status = (
                "SOURCE_ARCHIVED_QUARANTINED_DTE"
                if diagnostic["outside_requested_dte_rows"]
                else "SOURCE_ARCHIVED_DIAGNOSTIC_ONLY"
            )
    except Exception as exc:
        error_type = type(exc).__name__
        if archive is not None:
            status = "SOURCE_ARCHIVED_INVALID_SCHEMA"

    terminal = _fp_body({
        "contract": CONTRACT,
        "kind": "TERMINAL",
        "state": status,
        "manifest_fingerprint": PINNED_MANIFEST_FINGERPRINT,
        "source_request_id": query_id,
        "started_fingerprint": started["fingerprint"],
        "archive": archive,
        "diagnostic_fingerprint": (
            diagnostic["diagnostic_fingerprint"] if diagnostic else None
        ),
        "diagnostic_state": diagnostic["status"] if diagnostic else None,
        "error_type": error_type,
        "max_provider_attempts": 1,
        "automatic_retry_allowed": False,
        "at_time_sdk_max_dte_forwarding_proven": False,
        "source_coverage_proven": False,
        "simulator_ready": False,
    })
    _record_once(result, terminal, "TERMINAL")
    return {
        "contract": CONTRACT,
        "status": status,
        "source_request_id": query_id,
        "original_archive": archive,
        "diagnostic_state": terminal["diagnostic_state"],
        "error_type": error_type,
        "maximum_provider_calls": 1,
        "retry_authorized": False,
        "simulator_ready": False,
    }
