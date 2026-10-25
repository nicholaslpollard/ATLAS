from __future__ import annotations

"""V12 independently replay archived AAL 2021-11-30 at-time CALL source.

Uses only the already accepted V11 immutable STARTED/TERMINAL receipts and
the archived original SDK-normalized gzip. Never invokes provider/broker.
Confirms the exact V9 request/query identity, full SHA and byte counts,
and reports counts by DTE without projecting them into executable quotes.
"""

from collections import Counter
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Any
import zlib

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    ROOT_REL, _load_full_manifest, _validate_attempt_state,
)
from packages.data.hybrid_options_at_time_source_gate_v1 import (
    MAX_RESPONSE_BYTES, REQUIRED_FIELDS, validate_exact_request,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    _symbol_matches_underlying,
)
from packages.providers.thetadata.client import _canonical_bytes

CONTRACT = "atlas-hybrid-v11-saved-aal-full-source-audit-v12"
AAL_QUERY_ID = "15ac1c4ac389a5b4893530b954f40bc6ed4ee7d4614e1c606aa53a8a920eafe4"
AAL_DAY = "2021-11-30"
MAX_GZIP = MAX_RESPONSE_BYTES + 4096


class HybridAalAuditError(ValueError):
    pass


def _read_bounded_gzip(source_path: Path, max_source: int,
                       max_gzip: int) -> bytes:
    if (source_path.is_symlink() or not source_path.is_file()
            or not 0 < source_path.stat().st_size <= max_gzip):
        raise HybridAalAuditError("AAL_ARCHIVE_FILE_NOT_SAFE")
    packed = source_path.read_bytes()
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        restored = decoder.decompress(packed, max_source + 1)
    except zlib.error as exc:
        raise HybridAalAuditError("AAL_ARCHIVE_GZIP_INVALID") from exc
    if (not decoder.eof or decoder.unconsumed_tail or decoder.unused_data
            or not 0 < len(restored) <= max_source):
        raise HybridAalAuditError("AAL_ARCHIVE_BOUNDARY_OR_TRAILING_BYTES")
    return restored


def audit_saved_aal(
    settings: AtlasSettings,
    manifest: Path,
    candidate_plan: Path,
) -> dict[str, Any]:
    settings.assert_external_storage_binding("options")
    frozen = _load_full_manifest(settings, manifest, candidate_plan)
    matches = [r for r in frozen["requests"] if r["query_id"] == AAL_QUERY_ID]
    if len(matches) != 1:
        raise HybridAalAuditError("AAL_NOT_EXACT_FROZEN_QUERY")
    row = matches[0]
    sdk = validate_exact_request(row)
    if (row["origin"] != "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES"
            or sdk["date_et"] != AAL_DAY
            or sdk["symbol"] != "AAL"
            or sdk["time_of_day_et"] != "09:35:00.000"
            or sdk["right"] != "call"
            or sdk["max_dte"] != 75
            or sdk["strike_range"] is not None):
        raise HybridAalAuditError("AAL_FROZEN_REQUEST_SHAPE_DRIFT")
    start, end = _validate_attempt_state(settings)
    if (start is None or end is None
            or start.get("source_request_id") != AAL_QUERY_ID
            or start.get("query") != sdk
            or end.get("source_request_id") != AAL_QUERY_ID
            or end.get("state") != "SOURCE_ARCHIVED_QUARANTINED_DTE"
            or end.get("diagnostic_state") !=
                "QUARANTINED_OUT_OF_SCOPE_DTE_NO_PROJECTION"
            or end.get("at_time_sdk_max_dte_forwarding_proven") is not False
            or end.get("source_coverage_proven") is not False
            or end.get("simulator_ready") is not False):
        raise HybridAalAuditError("AAL_V11_TERMINAL_SCOPE_CHANGED")
    evidence = end.get("archive")
    required = {
        "relative_archive", "original_sha256", "compressed_sha256",
        "original_bytes", "compressed_bytes", "observed_rows",
        "full_original_retained", "source_coverage_proven",
        "simulator_ready",
    }
    if (not isinstance(evidence, dict)
            or set(evidence) != required
            or evidence["full_original_retained"] is not True
            or evidence["source_coverage_proven"] is not False
            or evidence["simulator_ready"] is not False
            or not isinstance(evidence["observed_rows"], int)
            or not 0 < evidence["observed_rows"] <= 50_000):
        raise HybridAalAuditError("AAL_V11_ARCHIVE_RECEIPT_DRIFT")
    options_root = settings.resolved_path("data/options").resolve()
    archive = options_root / evidence["relative_archive"]
    parent = settings.resolved_path(ROOT_REL).resolve() / "source"
    if (not archive.resolve().is_relative_to(parent)
            or archive.is_symlink()
            or not archive.is_file()
            or archive.stat().st_size != evidence["compressed_bytes"]
            or archive.name != evidence["original_sha256"] + ".json.gz"):
        raise HybridAalAuditError("AAL_ARCHIVE_PATH_IDENTITY_DRIFT")
    packed = archive.read_bytes()
    if hashlib.sha256(packed).hexdigest() != evidence["compressed_sha256"]:
        raise HybridAalAuditError("AAL_COMPRESSED_HASH_MISMATCH")
    raw = _read_bounded_gzip(
        archive, MAX_RESPONSE_BYTES, MAX_GZIP,
    )
    if (len(raw) != evidence["original_bytes"]
            or hashlib.sha256(raw).hexdigest() != evidence["original_sha256"]):
        raise HybridAalAuditError("AAL_ORIGINAL_SHA_OR_SIZE_CHANGED")
    try:
        quotes = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise HybridAalAuditError("AAL_CANONICAL_JSON_INVALID") from exc
    if (not isinstance(quotes, list)
            or len(quotes) != evidence["observed_rows"]
            or any(not isinstance(q, dict) for q in quotes)
            or _canonical_bytes(quotes) != raw):
        raise HybridAalAuditError("AAL_ORIGINAL_CANONICAL_ROWS_CHANGED")
    within, outside = 0, 0
    invalid_rows = 0
    dte_groups = Counter()
    rights = Counter()
    dates = Counter()
    positive_two_sided = 0
    for quote in quotes:
        try:
            if any(k not in quote for k in REQUIRED_FIELDS):
                raise ValueError("required field")
            expiry = date.fromisoformat(str(quote["expiration"])[:10])
            dte = (expiry - date.fromisoformat(AAL_DAY)).days
            if dte < 0 or not isinstance(quote["timestamp"], str):
                raise ValueError("date/timestamp")
            observed = datetime.fromisoformat(
                quote["timestamp"].replace("Z", "+00:00")
            )
            if observed.utcoffset() is None:
                raise ValueError("timestamp offset")
            # V10 accepted this original quote source by case-normalizing
            # option right and matching both compact and OCC option roots.
            # Replaying V11 must use the same rule: SDKs may return "CALL"
            # instead of "call", or "AAL211..." rather than bare "AAL".
            right = str(quote["right"]).lower()
            if right != "call" or not _symbol_matches_underlying(
                str(quote["symbol"]), "AAL"
            ):
                raise ValueError("quote identity")
            rights[right] += 1
            dates[expiry.isoformat()] += 1
            if dte <= 75:
                within += 1
            else:
                outside += 1
            dte_groups["0_14" if dte <= 14 else
                       "15_45" if dte <= 45 else
                       "46_75" if dte <= 75 else
                       "76_180" if dte <= 180 else
                       "181_PLUS"] += 1
            if (float(quote["bid"]) > 0 and
                    float(quote["ask"]) >= float(quote["bid"]) and
                    int(quote["bid_size"]) > 0 and
                    int(quote["ask_size"]) > 0):
                positive_two_sided += 1
        except (ValueError, TypeError, KeyError, OverflowError):
            invalid_rows += 1
    if invalid_rows:
        raise HybridAalAuditError("AAL_ARCHIVED_ROWS_FAIL_V10_IDENTITY_REPLAY")
    if outside == 0:
        raise HybridAalAuditError("AAL_ARCHIVED_DTE_OVERRUN_NOT_REPRODUCED")
    report = {
        "contract": CONTRACT,
        "status": "REPRODUCED_OUT_DTE_DIAGNOSTIC_SOURCE_ONLY",
        "v9_frozen_manifest_fingerprint": frozen["manifest_fingerprint"],
        "v9_source_query_id": AAL_QUERY_ID,
        "v11_started_fingerprint": start["fingerprint"],
        "v11_terminal_fingerprint": end["fingerprint"],
        "archived_full_raw_sha256": evidence["original_sha256"],
        "archived_compressed_sha256": evidence["compressed_sha256"],
        "raw_bytes": len(raw),
        "compressed_bytes": len(packed),
        "total_original_rows": len(quotes),
        "requested_max_dte": 75,
        "in_dte_rows": within,
        "over_dte_rows": outside,
        "dte_buckets": dict(sorted(dte_groups.items())),
        "distinct_expiration_count": len(dates),
        "positive_two_sided_displayed_size_rows": positive_two_sided,
        "observed_rights": dict(sorted(rights.items())),
        "invalid_basic_rows": invalid_rows,
        "max_dte_respected_by_provider": False,
        "sdk_vs_server_cause_proven": False,
        "unfiltered_original_retained": True,
        "source_coverage_proven": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_read": 0,
        "simulations_run": 0,
    }
    report["fingerprint"] = _fingerprint(report)
    return report
