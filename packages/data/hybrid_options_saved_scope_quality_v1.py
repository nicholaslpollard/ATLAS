from __future__ import annotations

"""V13 read-only independent quality census of V12 saved at-time archives.

Replays the entire original SDK-normalized source for each completed
archival request from the exact frozen V9 manifest. Excludes existing
V11 AAL / V10 SPY (different original evidence roots). No provider calls,
new receipts, reclassification, locally projected source file, source
promotion, options fills, broker/trading or simulator activity.

The published v3 max_dte contract is compared to the *observed* DTE
distribution without assuming SDK wire forwarding or server behavior.
"""

from collections import Counter
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import zlib

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_at_time_one_call_v1 import _load_full_manifest
from packages.data.hybrid_options_at_time_source_gate_v1 import (
    MAX_RESPONSE_BYTES, REQUIRED_FIELDS, validate_exact_request,
)
from packages.data.hybrid_options_unattended_campaign_v1 import (
    ROOT_REL, _archive_path, _inspect_attempt, _read_receipt,
    MAX_ARCHIVE_BYTES,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    _finite_number, _nonnegative_int, _symbol_matches_underlying,
)
from packages.providers.thetadata.client import _canonical_bytes

CONTRACT = "atlas-hybrid-saved-at-time-quote-scope-quality-census-v13"
EASTERN = ZoneInfo("America/New_York")
MAX_ARCHIVES_INSPECTED = 9866


class HybridScopeCensusError(ValueError):
    pass


def _original_rows(
    settings: AtlasSettings,
    query_id: str,
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    path = _archive_path(settings, query_id)
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= MAX_ARCHIVE_BYTES
            or path.stat().st_size != source["compressed_bytes"]):
        raise HybridScopeCensusError("SOURCE_ARCHIVE_SIZE_OR_PATH_INVALID")
    packed = path.read_bytes()
    if hashlib.sha256(packed).hexdigest() != source["compressed_sha256"]:
        raise HybridScopeCensusError("SOURCE_GZIP_SHA_MISMATCH")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        raw = decoder.decompress(packed, MAX_RESPONSE_BYTES + 1)
    except zlib.error as exc:
        raise HybridScopeCensusError("SOURCE_GZIP_DECODE_FAILED") from exc
    if (not decoder.eof or decoder.unconsumed_tail or decoder.unused_data
            or len(raw) != source["original_bytes"]
            or hashlib.sha256(raw).hexdigest() != source["original_sha256"]):
        raise HybridScopeCensusError("SOURCE_ORIGINAL_SHA_OR_BOUNDARY_DRIFT")
    try:
        rows = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise HybridScopeCensusError("SOURCE_JSON_UNREADABLE") from exc
    if (not isinstance(rows, list)
            or len(rows) != source["observed_rows"]
            or any(not isinstance(q, dict) for q in rows)
            or _canonical_bytes(rows) != raw):
        raise HybridScopeCensusError("SOURCE_ORIGINAL_CANONICAL_CONTENT_CHANGED")
    return rows


def _one_source_quality(row: dict[str, Any],
                        rows: list[dict[str, Any]]) -> dict[str, Any]:
    sdk = validate_exact_request(row)
    request_day = date.fromisoformat(sdk["date_et"])
    decision_clock = datetime.combine(
        request_day,
        datetime.strptime(sdk["time_of_day_et"], "%H:%M:%S.%f").time(),
        EASTERN,
    )
    status = Counter()
    buckets = Counter()
    staleness_seconds: list[int] = []
    unique = set()
    expirations = set()
    valid_displayed = 0
    for item in rows:
        try:
            if any(key not in item for key in REQUIRED_FIELDS):
                raise ValueError("SOURCE_ROW_REQUIRED_FIELD_MISSING")
            expiration = date.fromisoformat(str(item["expiration"])[:10])
            dte = (expiration - request_day).days
            if dte < 0:
                raise ValueError("CONTRACT_ALREADY_EXPIRED")
            strike = _finite_number(item["strike"], "strike")
            if strike <= 0:
                raise ValueError("STRIKE_NONPOSITIVE")
            right = str(item["right"]).lower()
            if (right not in {"call", "put"}
                    or sdk["right"] != "both" and right != sdk["right"]
                    or not _symbol_matches_underlying(
                        str(item["symbol"]), sdk["symbol"]
                    )):
                raise ValueError("CONTRACT_IDENTITY_OUTSIDE_REQUEST")
            key = (expiration.isoformat(), strike, right)
            if key in unique:
                raise ValueError("DUPLICATE_CONTRACT")
            unique.add(key)
            stamp = item["timestamp"]
            if not isinstance(stamp, str):
                raise ValueError("TIMESTAMP_MISSING")
            ts = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if ts.tzinfo is None or ts.utcoffset() is None:
                raise ValueError("TIMESTAMP_MISSING_UTC_OFFSET")
            et = ts.astimezone(EASTERN)
            if et.date() != request_day or et > decision_clock:
                raise ValueError("NOT_CAUSAL_AT_TIME")
            staleness_seconds.append(
                int((decision_clock - et).total_seconds())
            )
            bid = _finite_number(item["bid"], "bid")
            ask = _finite_number(item["ask"], "ask")
            bid_size = _nonnegative_int(item["bid_size"], "bid_size")
            ask_size = _nonnegative_int(item["ask_size"], "ask_size")
            for field in (
                "bid_exchange", "ask_exchange",
                "bid_condition", "ask_condition",
            ):
                _nonnegative_int(item[field], field)
            if bid > 0 and ask > 0 and ask < bid:
                raise ValueError("CROSSED_TWO_SIDED_QUOTE")
            if bid > 0 and ask > 0 and bid_size > 0 and ask_size > 0:
                valid_displayed += 1
            expirations.add(expiration.isoformat())
            status["within" if dte <= sdk["max_dte"] else "outside"] += 1
            buckets[
                "0_14" if dte <= 14 else
                "15_45" if dte <= 45 else
                "46_75" if dte <= 75 else
                "76_180" if dte <= 180 else
                "181_PLUS"
            ] += 1
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            status["invalid"] += 1
    return {
        "query_id": row["query_id"],
        "symbol": sdk["symbol"],
        "session": sdk["date_et"],
        "clock": sdk["time_of_day_et"],
        "requested_right": sdk["right"],
        "requested_dte": sdk["max_dte"],
        "original_quote_rows": len(rows),
        "in_requested_dte": status["within"],
        "outside_requested_dte": status["outside"],
        "other_invalid_rows": status["invalid"],
        "dte_buckets": dict(sorted(buckets.items())),
        "observed_distinct_expirations": len(expirations),
        "positive_two_sided_displayed_size_rows": valid_displayed,
        "oldest_quote_age_seconds": (
            max(staleness_seconds) if staleness_seconds else None
        ),
        "original_chain_completeness_proven": False,
        "locally_projected_view_written": False,
        "simulator_ready": False,
    }


def audit_campaign_scope(
    settings: AtlasSettings,
    manifest_path: Path,
    candidate_plan: Path,
) -> dict[str, Any]:
    settings.assert_external_storage_binding("options")
    frozen = _load_full_manifest(settings, manifest_path, candidate_plan)
    if (frozen["source_request_count"] != 9866
            or frozen["manifest_fingerprint"] !=
                "138234eb2276409ae641f6e40d7f6eb3c779502ffb5459b612e0dbc439cb4b63"):
        raise HybridScopeCensusError("FROZEN_9866_SCOPE_DRIFT")
    summary = Counter()
    compressed_bytes = 0
    raw_bytes = 0
    per_source = []
    all_buckets = Counter()
    attempted = 0
    for row in frozen["requests"]:
        validate_exact_request(row)
        qid = row["query_id"]
        state = _inspect_attempt(settings, qid)
        if state == "UNATTEMPTED":
            continue
        attempted += 1
        if state == "UNCERTAIN_PRIOR_ATTEMPT_NO_RETRY":
            summary["uncertain"] += 1
            continue
        terminal = _read_receipt(
            settings.resolved_path(ROOT_REL) / "attempts"
            / qid[:2] / (qid + ".terminal.json"),
            qid, "terminal",
        )
        if state.startswith("RAW_ARCHIVED"):
            src = terminal["archive"]
            if not isinstance(src, dict):
                raise HybridScopeCensusError("TERMINAL_MISSING_ORIGINAL_ARCHIVE")
            source_rows = _original_rows(settings, qid, src)
            detail = _one_source_quality(row, source_rows)
            if (detail["original_quote_rows"] !=
                    detail["in_requested_dte"]
                    + detail["outside_requested_dte"]
                    + detail["other_invalid_rows"]):
                raise HybridScopeCensusError("ROW_RECONCILIATION_FAILED")
            per_source.append(detail)
            compressed_bytes += src["compressed_bytes"]
            raw_bytes += src["original_bytes"]
            summary["archived"] += 1
            summary["rows"] += detail["original_quote_rows"]
            summary["in_dte"] += detail["in_requested_dte"]
            summary["out_dte"] += detail["outside_requested_dte"]
            summary["invalid_rows"] += detail["other_invalid_rows"]
            summary["two_sided"] += detail[
                "positive_two_sided_displayed_size_rows"
            ]
            if detail["outside_requested_dte"]:
                summary["scope_overruns"] += 1
            if detail["other_invalid_rows"]:
                summary["semantic_defects"] += 1
            all_buckets.update(detail["dte_buckets"])
        else:
            summary["no_source_terminal"] += 1
    if attempted > MAX_ARCHIVES_INSPECTED:
        raise HybridScopeCensusError("ARCHIVE_CENSUS_COUNT_EXCEEDS_PLAN")
    if (summary["archived"] != len(per_source)
            or attempted != (
                summary["archived"] + summary["uncertain"]
                + summary["no_source_terminal"]
            )):
        raise HybridScopeCensusError("SOURCE_CENSUS_COUNT_INCONSISTENT")
    result = {
        "contract": CONTRACT,
        "status": "OBSERVED_AT_TIME_SOURCE_QUALITY_DIAGNOSTIC_ONLY",
        "manifest_fingerprint": frozen["manifest_fingerprint"],
        "archived_sources": summary["archived"],
        "attempted_source_ids": attempted,
        "uncertain_attempt_ids": summary["uncertain"],
        "no_source_terminals": summary["no_source_terminal"],
        "sources_with_dte_overruns": summary["scope_overruns"],
        "sources_with_non_dte_semantic_defects": summary["semantic_defects"],
        "total_original_quote_rows": summary["rows"],
        "observed_in_requested_dte_rows": summary["in_dte"],
        "observed_outside_requested_dte_rows": summary["out_dte"],
        "observed_other_invalid_rows": summary["invalid_rows"],
        "observed_positive_two_sided_rows": summary["two_sided"],
        "dte_buckets": dict(sorted(all_buckets.items())),
        "original_bytes": raw_bytes,
        "gzip_bytes": compressed_bytes,
        "estimated_compression_savings_percent": (
            round(100 * (1 - compressed_bytes / raw_bytes), 2)
            if raw_bytes else None
        ),
        "source_details": per_source,
        "provider_semantics_max_dte_proven": False,
        "source_chain_completeness_proven": False,
        "locally_projected_view_written": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_read": 0,
        "simulations_run": 0,
    }
    result["fingerprint"] = _fingerprint(result)
    return result
