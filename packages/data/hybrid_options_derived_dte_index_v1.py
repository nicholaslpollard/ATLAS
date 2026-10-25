from __future__ import annotations

"""V14 immutable, source-linked DTE observation indices: never fake provider quotes.

The V12 original at-time quote response is ALWAYS retained, fully hashed
and never replaced or filtered. V14 creates only an independently identified
index of original positional row IDs whose expiration is within the original
V9 requested DTE. It does not write selected quote data, certify full chain
coverage, validate strategy performance, run a simulator or use a provider.

Read-only preview is default; explicit local --write-indexes persists an
immutable content-addressed sidecar on the external options research volume.
Repeat writes are idempotent iff the exact original receipt/bytes and index
still match. Corruption, invalid rows, stale lineage or conflicting indices
fail closed; no automatic index repairs or source promotions.
"""

from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    _load_full_manifest, PINNED_MANIFEST_FINGERPRINT,
)
from packages.data.hybrid_options_at_time_source_gate_v1 import (
    validate_exact_request,
)
from packages.data.hybrid_options_lossless_archive_v1 import _write_immutable
from packages.data.hybrid_options_saved_scope_quality_v1 import (
    _one_source_quality, _original_rows,
)
from packages.data.hybrid_options_unattended_campaign_v1 import (
    ROOT_REL as V12_ROOT, _inspect_attempt, _read_receipt, _safe_storage,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.research_storage import inspect_research_storage

CONTRACT = "atlas-hybrid-exact-at-time-derived-dte-reference-index-v14"
OUTPUT_REL = "data/options/hybrid/derived_dte_scope_index_v14"
MAX_INDEX_BYTES_PER_SOURCE = 1024 * 1024
MAX_ROWS = 50_000
ELIGIBLE_STATES = frozenset({
    "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC",
    "RAW_ARCHIVED_SCOPE_DIAGNOSTIC",
})


class HybridDteIndexError(ValueError):
    pass


def _expected_index(
    row: dict[str, Any], terminal: dict[str, Any],
    quotes: list[dict[str, Any]],
) -> dict[str, Any]:
    sdk = validate_exact_request(row)
    source = terminal.get("archive")
    if (terminal.get("query_id") != row["query_id"]
            or terminal.get("state") not in ELIGIBLE_STATES
            or not isinstance(source, dict)
            or not isinstance(source.get("original_sha256"), str)
            or len(source["original_sha256"]) != 64
            or not isinstance(terminal.get("fingerprint"), str)
            or len(terminal["fingerprint"]) != 64
            or not isinstance(quotes, list)
            or not 0 < len(quotes) <= MAX_ROWS):
        raise HybridDteIndexError("V12_ORIGINAL_SOURCE_RECEIPT_UNQUALIFIED")

    quality = _one_source_quality(row, quotes)
    if (quality["other_invalid_rows"] != 0
            or quality["original_quote_rows"] != source["observed_rows"]):
        raise HybridDteIndexError("ORIGINAL_SOURCE_ROW_SEMANTICS_UNQUALIFIED")

    request_day = date.fromisoformat(sdk["date_et"])
    maximum_dte = sdk["max_dte"]
    selected: list[int] = []
    for i, item in enumerate(quotes):
        expiry = date.fromisoformat(str(item["expiration"])[:10])
        dte = (expiry - request_day).days
        if 0 <= dte <= maximum_dte:
            selected.append(i)

    if (len(selected) != quality["in_requested_dte"]
            or len(quotes) - len(selected) != quality["outside_requested_dte"]):
        raise HybridDteIndexError("IN_SCOPE_INDEX_CENSUS_DIVERGENCE")

    body: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "LOCAL_DTE_SELECTION_REFERENCES_ONLY_NOT_PROVIDER_SCOPED",
        "original_frozen_manifest_fingerprint": PINNED_MANIFEST_FINGERPRINT,
        "v9_original_query_id": row["query_id"],
        "v9_original_query_fingerprint": row["origin_query_fingerprint"],
        "original_v12_terminal_fingerprint": terminal["fingerprint"],
        "original_v12_archive_sha256": source["original_sha256"],
        "original_v12_compressed_sha256": source["compressed_sha256"],
        "request_origin": row["origin"],
        "symbol": sdk["symbol"],
        "session_et": sdk["date_et"],
        "decision_clock_et": sdk["time_of_day_et"],
        "requested_right": sdk["right"],
        "requested_max_dte": maximum_dte,
        "all_original_rows": len(quotes),
        "locally_selected_rows": len(selected),
        "locally_excluded_over_dte_rows": len(quotes) - len(selected),
        "original_row_indices": selected,
        "original_chain_completeness_proven": False,
        "provider_max_dte_forwarding_proven": False,
        "source_replaced_or_modified": False,
        "option_execution_admissible": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "simulations_run": 0,
    }
    body["index_fingerprint"] = _fingerprint(body)
    return body


def _index_path(settings: AtlasSettings, body: dict[str, Any]) -> Path:
    query_id = body["v9_original_query_id"]
    fingerprint = body["index_fingerprint"]
    return (settings.resolved_path(OUTPUT_REL) / query_id[:2]
            / (query_id + "_" + fingerprint[:16] + ".json"))


def _index_bytes(body: dict[str, Any]) -> bytes:
    encoded = (json.dumps(
        body, sort_keys=True, indent=2, allow_nan=False,
    ) + "\n").encode("utf-8")
    if not 0 < len(encoded) <= MAX_INDEX_BYTES_PER_SOURCE:
        raise HybridDteIndexError("DTE_SIDECAR_INDEX_BYTE_LIMIT")
    return encoded


def _match_existing(settings: AtlasSettings, body: dict[str, Any]) -> bool:
    path = _index_path(settings, body)
    root = settings.resolved_path(OUTPUT_REL)
    if root.is_symlink() or path.parent.is_symlink() or path.is_symlink():
        raise HybridDteIndexError("DERIVED_INDEX_SYMLINK_FORBIDDEN")
    if not path.parent.exists():
        return False
    # A distinct index for one source ID would conceal changed originals.
    # Never leave mutually contradictory derived identities unnoticed.
    query = body["v9_original_query_id"]
    matching = list(path.parent.glob(query + "_*.json"))
    if len(matching) > 1 or (
        matching and (len(matching) != 1 or matching[0] != path)
    ):
        raise HybridDteIndexError("CONFLICTING_DERIVED_INDEX_FOR_SOURCE_ID")
    if not path.exists():
        return False
    if not path.is_file() or path.stat().st_size != len(_index_bytes(body)):
        raise HybridDteIndexError("EXISTING_DERIVED_INDEX_CONTENT_DRIFT")
    if path.read_bytes() != _index_bytes(body):
        raise HybridDteIndexError("EXISTING_DERIVED_INDEX_CONTENT_DRIFT")
    return True


def build_dte_reference_indices(
    settings: AtlasSettings,
    manifest: Path,
    candidate_plan: Path,
    *,
    write_indexes: bool = False,
) -> dict[str, Any]:
    """Read every accepted V12 quote archive, optionally write index-only metadata."""
    settings.assert_external_storage_binding("options")
    frozen = _load_full_manifest(settings, manifest, candidate_plan)
    if (frozen["manifest_fingerprint"] != PINNED_MANIFEST_FINGERPRINT
            or frozen["source_request_count"] != 9866):
        raise HybridDteIndexError("FROZEN_EXACT_RESEARCH_SOURCE_DRIFT")

    # Verify all sources and complete index shapes before any writing.
    planned: list[tuple[dict[str, Any], bool]] = []
    scanned = 0
    inside = 0
    outside = 0
    saved_bytes = 0
    for row in frozen["requests"]:
        validate_exact_request(row)
        qid = row["query_id"]
        state = _inspect_attempt(settings, qid)
        if state not in ELIGIBLE_STATES:
            if state.startswith("RAW_ARCHIVED"):
                raise HybridDteIndexError("V12_ARCHIVE_INVALID_SCHEMA_NOT_INDEXABLE")
            continue
        terminal = _read_receipt(
            settings.resolved_path(V12_ROOT) / "attempts" / qid[:2]
            / (qid + ".terminal.json"),
            qid, "terminal",
        )
        if terminal is None or not isinstance(terminal.get("archive"), dict):
            raise HybridDteIndexError("V12_TERMINAL_ARCHIVE_LINEAGE_MISSING")
        rows = _original_rows(settings, qid, terminal["archive"])
        body = _expected_index(row, terminal, rows)
        existed = _match_existing(settings, body)
        planned.append((body, existed))
        scanned += 1
        inside += body["locally_selected_rows"]
        outside += body["locally_excluded_over_dte_rows"]
        saved_bytes += len(_index_bytes(body))
    if scanned > 9866:
        raise HybridDteIndexError("INDEXED_MORE_SOURCES_THAN_FROZEN_MANIFEST")

    already = sum(1 for _, present in planned if present)
    newly_written = 0
    if write_indexes and already < scanned:
        storage = _safe_storage(settings, inspect_research_storage)
        if not storage["safe"]:
            raise HybridDteIndexError("OPTIONS_SAFE_STORAGE_HEADROOM_NOT_MET")
        need = sum(len(_index_bytes(body)) for body, present in planned
                   if not present)
        if storage["available_after_hourly_reservations"] < need:
            raise HybridDteIndexError("OPTIONS_INDEX_HEADROOM_EXCEEDED")
        for body, present in planned:
            if present:
                continue
            target = _index_path(settings, body)
            if target.parent.is_symlink() or target.is_symlink():
                raise HybridDteIndexError("DERIVED_INDEX_TARGET_SYMLINK")
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_immutable(target, _index_bytes(body))
            if not _match_existing(settings, body):
                raise HybridDteIndexError("IMMUTABLE_DTE_INDEX_POSTWRITE_FAILED")
            newly_written += 1

    result = {
        "contract": CONTRACT,
        "status": ("DERIVED_INDEX_REFERENCES_WRITTEN_DIAGNOSTIC_ONLY"
                   if write_indexes else "DERIVED_INDEX_PREVIEW_ONLY"),
        "frozen_manifest_fingerprint": frozen["manifest_fingerprint"],
        "original_archives_scanned": scanned,
        "in_requested_dte_references": inside,
        "outside_requested_dte_rows_not_indexed": outside,
        "already_immutable_indices": already,
        "new_immutable_indices": newly_written,
        "estimated_all_index_bytes": saved_bytes,
        "no_duplicate_quote_payload_written": True,
        "original_sources_untouched": True,
        "provider_max_dte_forwarding_proven": False,
        "source_chain_completeness_proven": False,
        "option_execution_admissible": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_read": 0,
        "simulations_run": 0,
    }
    result["fingerprint"] = _fingerprint(result)
    return result


def verify_scoped_reference(
    settings: AtlasSettings, row: dict[str, Any],
) -> dict[str, Any]:
    """Independently replay an existing sidecar against its original archive.

    Returns reference counts only; intentionally not an executable data feed.
    """
    sdk = validate_exact_request(row)
    qid = row["query_id"]
    if _inspect_attempt(settings, qid) not in ELIGIBLE_STATES:
        raise HybridDteIndexError("NOT_AN_ARCHIVED_DIAGNOSTIC_SOURCE")
    terminal = _read_receipt(
        settings.resolved_path(V12_ROOT) / "attempts" / qid[:2]
        / (qid + ".terminal.json"),
        qid, "terminal",
    )
    rows = _original_rows(settings, qid, terminal["archive"])
    expected = _expected_index(row, terminal, rows)
    if not _match_existing(settings, expected):
        raise HybridDteIndexError("DTE_SOURCE_REFERENCE_INDEX_ABSENT")
    return {
        "status": "VERIFIED_LOCAL_DTE_REFS_ONLY",
        "query_id": qid,
        "expected_date": sdk["date_et"],
        "index_fingerprint": expected["index_fingerprint"],
        "original_source_sha256": expected["original_v12_archive_sha256"],
        "selected": expected["locally_selected_rows"],
        "original": expected["all_original_rows"],
        "option_execution_admissible": False,
        "simulator_ready": False,
        "provider_requests": 0,
    }
