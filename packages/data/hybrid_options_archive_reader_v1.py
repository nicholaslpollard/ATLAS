from __future__ import annotations

"""V4: Read an exact historical option quote source from verified gzip + catalog.

Requires the already-indexed source, immutable compressed SHA receipt, and
every observed identity in the DuckDB catalog. Does NOT require re-opening
the original uncompressed source. The source remains diagnostic, not
complete-session coverage or executable simulation input. No provider calls.
"""

from collections import Counter
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.hybrid_options_coverage_catalog_v1 import (
    CATALOG_REL, MAX_RAW_BYTES, _canonical_rows,
)
from packages.data.hybrid_options_lossless_archive_v1 import (
    CONTRACT as ARCHIVE_CONTRACT,
    MAX_RECEIPT_BYTES, SHA_PATTERN,
    _archive_locations, _expected_receipt, _restore_bounded,
)

CONTRACT = "atlas-hybrid-options-verified-archive-reader-v1"
MAX_INDEXED_ROWS = 250_000


class HybridArchiveReaderError(ValueError):
    pass


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def load_verified_archived_option_quotes(
    settings: AtlasSettings, source_id: str,
) -> dict[str, Any]:
    """Return source observations only, paired with an explicit diagnostic flag.

    The caller must independently establish query coverage, PIT source and
    executable resolution; this method cannot promote source acceptance.
    """
    if not isinstance(source_id, str) or not SHA_PATTERN.fullmatch(source_id):
        raise HybridArchiveReaderError("INVALID_EXACT_SOURCE_ID")
    settings.assert_external_storage_binding("options")
    options_root = settings.resolved_path("data/options")
    catalog_path = settings.resolved_path(CATALOG_REL)
    if (not options_root.is_dir() or catalog_path.is_symlink()
            or not catalog_path.is_file()):
        raise HybridArchiveReaderError("VERIFIED_LOCAL_CATALOG_UNAVAILABLE")

    con = connect_utc(catalog_path, read_only=True)
    try:
        source = con.execute(
            "SELECT source_type, provider, symbol, session_et, "
            "interval_code, rights_requested, query_json, source_status, "
            "query_coverage_proven, simulator_ready, summary_relpath, "
            "raw_relpath, body_sha256, source_rows, source_bytes "
            "FROM source_units WHERE source_id=?",
            [source_id],
        ).fetchall()
        if len(source) != 1:
            raise HybridArchiveReaderError("EXACT_INDEXED_SOURCE_NOT_FOUND")
        (stype, provider, symbol, session_et, interval_code, rights,
         query_json, status, proven, ready, summary_relpath, raw_relpath,
         source_sha, source_rows, source_bytes) = source[0]
        if (stype != "THETADATA_OPTION_HISTORY_QUOTE"
                or provider != "thetadata"
                or status != "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED"
                or proven is not False or ready is not False
                or not isinstance(source_sha, str)
                or not SHA_PATTERN.fullmatch(source_sha)
                or not isinstance(source_rows, int)
                or not (0 < source_rows <= MAX_INDEXED_ROWS)
                or not isinstance(source_bytes, int)
                or not (0 < source_bytes <= MAX_RAW_BYTES)):
            raise HybridArchiveReaderError("CATALOG_SOURCE_IDENTITY_OR_STATUS_INVALID")
        try:
            scope = json.loads(query_json)
        except (TypeError, ValueError) as exc:
            raise HybridArchiveReaderError("CATALOG_QUERY_IDENTITY_INVALID") from exc
        if (not isinstance(scope, dict) or scope.get("symbol") != symbol
                or scope.get("date_et") != session_et
                or scope.get("interval") != interval_code
                or scope.get("right") != rights):
            raise HybridArchiveReaderError("CATALOG_SCOPE_IDENTITY_INVALID")
        indexed = con.execute(
            "SELECT ordinal, underlying, expiration, strike, option_right, "
            "observed_timestamp FROM observed_quote_keys WHERE source_id=? "
            "ORDER BY ordinal LIMIT ?",
            [source_id, MAX_INDEXED_ROWS + 1],
        ).fetchall()
    finally:
        con.close()
    if len(indexed) != source_rows:
        raise HybridArchiveReaderError("CATALOG_OBSERVATION_COUNT_INVALID")

    compressed_path, receipt_path = _archive_locations(settings, source_sha)
    archive_root = settings.resolved_path("data/options/hybrid/source_archive_v1")
    expected_root = options_root.resolve()
    for path in (compressed_path, receipt_path):
        if (path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(expected_root)
                or not path.resolve().is_relative_to(archive_root.resolve())):
            raise HybridArchiveReaderError("ARCHIVE_PATH_UNAVAILABLE_OR_UNSAFE")
    if (not 0 < compressed_path.stat().st_size <= MAX_RAW_BYTES
            or not 0 < receipt_path.stat().st_size <= MAX_RECEIPT_BYTES):
        raise HybridArchiveReaderError("ARCHIVE_FILE_SIZE_INVALID")
    try:
        receipt = json.loads(receipt_path.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise HybridArchiveReaderError("ARCHIVE_RECEIPT_JSON_INVALID") from exc
    compressed = compressed_path.read_bytes()
    expected_receipt = _expected_receipt({
        "source_id": source_id,
        "source_sha256": source_sha,
        "original_bytes": source_bytes,
        "observed_quotes": source_rows,
        "raw_relpath": raw_relpath,
        "summary_relpath": summary_relpath,
    }, compressed)
    if receipt != expected_receipt:
        raise HybridArchiveReaderError("ARCHIVE_RECEIPT_OR_SOURCE_IDENTITY_DRIFT")
    if _sha(compressed) != receipt["compressed_sha256"]:
        raise HybridArchiveReaderError("ARCHIVE_COMPRESSED_SHA_INVALID")
    raw = _restore_bounded(compressed, source_bytes)
    if _sha(raw) != source_sha:
        raise HybridArchiveReaderError("ARCHIVE_ORIGINAL_SHA_INVALID")
    rows = _canonical_rows(raw)
    if len(rows) != source_rows:
        raise HybridArchiveReaderError("ARCHIVE_QUOTE_ROW_COUNT_INVALID")

    rights_seen: Counter[str] = Counter()
    unique_contracts: set[tuple[str, str, str, str]] = set()
    clocks: list[str] = []
    for ordinal, (row, indexed_row) in enumerate(zip(rows, indexed)):
        try:
            expiry = date.fromisoformat(str(row["expiration"])[:10]).isoformat()
            clock = datetime.fromisoformat(
                str(row["timestamp"]).replace("Z", "+00:00")
            )
            if clock.tzinfo is None or clock.utcoffset() is None:
                raise ValueError("not timezone-aware")
            identity = (
                ordinal, str(row["symbol"]), expiry, str(row["strike"]),
                str(row["right"]).upper(), clock.isoformat(),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HybridArchiveReaderError("ARCHIVE_OBSERVATION_IDENTITY_INVALID") from exc
        if identity != tuple(indexed_row):
            raise HybridArchiveReaderError("ARCHIVE_VERSUS_CATALOG_KEY_DRIFT")
        rights_seen[identity[4]] += 1
        unique_contracts.add((identity[1], identity[2], identity[3], identity[4]))
        clocks.append(identity[5])

    return {
        "contract": CONTRACT,
        "source_id": source_id,
        "symbol": symbol,
        "session_et": session_et,
        "interval": interval_code,
        "query_scope": scope,
        "quote_rows": len(rows),
        "unique_contracts": len(unique_contracts),
        "rights_observed": dict(sorted(rights_seen.items())),
        "observed_timestamp_min": min(clocks),
        "observed_timestamp_max": max(clocks),
        "source_sha256": source_sha,
        "archive_sha256": receipt["compressed_sha256"],
        "compressed_bytes": len(compressed),
        "restored_original_bytes": len(raw),
        "retrieved_from": "VERIFIED_LOCAL_COMPRESSED_ARCHIVE",
        "original_uncompressed_source_opened": False,
        "source_status": status,
        "query_coverage_proven": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_read": 0,
        "rows": tuple(rows),
    }
