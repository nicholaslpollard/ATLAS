from __future__ import annotations

"""V3: Immutable, lossless compressed copy of one existing verified hourly source.

Strictly source-only. The original canonical JSON and receipts remain intact.
A registered diagnostic is still not qualified for complete query coverage,
historical fills, strategies or paper/live. Zero provider/broker requests.
"""

import gzip
import hashlib
import zlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any

from packages.core.atomic_io import unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.hybrid_options_coverage_catalog_v1 import (
    CATALOG_REL, MAX_RAW_BYTES, MIN_FREE_BYTES, inspect_hourly_source,
)

CONTRACT = "atlas-hybrid-options-immutable-compressed-source-archive-v1"
ROOT_REL = "data/options/hybrid/source_archive_v1"
MAX_RECEIPT_BYTES = 16 * 1024
SHA_PATTERN = re.compile(r"[0-9a-f]{64}")


class HybridArchiveError(ValueError):
    pass


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source_from_catalog(settings: AtlasSettings, source_id: str) -> dict[str, Any]:
    if not isinstance(source_id, str) or not SHA_PATTERN.fullmatch(source_id):
        raise HybridArchiveError("INVALID_EXACT_SOURCE_ID")
    settings.assert_external_storage_binding("options")
    options_root = settings.resolved_path("data/options")
    catalog_path = settings.resolved_path(CATALOG_REL)
    if (catalog_path.is_symlink() or not catalog_path.is_file()
            or not options_root.is_dir()):
        raise HybridArchiveError("VERIFIED_LOCAL_CATALOG_UNAVAILABLE")
    con = connect_utc(catalog_path, read_only=True)
    try:
        rows = con.execute(
            "SELECT source_type, source_status, query_coverage_proven, "
            "simulator_ready, summary_relpath, raw_relpath, receipt_relpath, "
            "body_sha256, source_rows, source_bytes, report_fingerprint "
            "FROM source_units WHERE source_id = ?", [source_id],
        ).fetchall()
    finally:
        con.close()
    if len(rows) != 1:
        raise HybridArchiveError("EXACT_CATALOG_SOURCE_NOT_FOUND")
    (source_type, status, coverage, ready, summary_relpath, raw_relpath,
     receipt_relpath, digest, nrows, nbytes, report_fp) = rows[0]
    if (source_type != "THETADATA_OPTION_HISTORY_QUOTE"
            or status != "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED"
            or coverage is not False or ready is not False):
        raise HybridArchiveError("CATALOG_SOURCE_AUTHORITY_CHANGED")

    summary = options_root / summary_relpath
    if summary.is_symlink() or not summary.resolve().is_relative_to(options_root.resolve()):
        raise HybridArchiveError("CATALOG_SOURCE_PATH_INVALID")
    observed = inspect_hourly_source(settings, summary)
    if (observed["source_id"] != source_id
            or observed["source_sha256"] != digest
            or observed["source_rows"] != nrows
            or observed["source_bytes"] != nbytes
            or observed["report_fingerprint"] != report_fp
            or observed["raw_relpath"] != raw_relpath
            or observed["receipt_relpath"] != receipt_relpath
            or observed["summary_relpath"] != summary_relpath
            or observed["simulator_ready"] is not False):
        raise HybridArchiveError("CATALOG_VERSUS_ORIGINAL_SOURCE_DRIFT")
    raw_file = options_root / raw_relpath
    if raw_file.is_symlink() or not raw_file.is_file():
        raise HybridArchiveError("ORIGINAL_SOURCE_FILE_UNAVAILABLE")
    if raw_file.stat().st_size != nbytes or not 0 < nbytes <= MAX_RAW_BYTES:
        raise HybridArchiveError("ORIGINAL_SOURCE_SIZE_CHANGED")
    raw = raw_file.read_bytes()
    if _digest(raw) != digest:
        raise HybridArchiveError("ORIGINAL_SOURCE_SHA_CHANGED")
    return {
        "source_id": source_id,
        "source_sha256": digest,
        "original_bytes": nbytes,
        "observed_quotes": nrows,
        "summary_relpath": summary_relpath,
        "raw_relpath": raw_relpath,
        "raw": raw,
    }


def _archive_locations(settings: AtlasSettings, digest: str) -> tuple[Path, Path]:
    folder = settings.resolved_path(ROOT_REL) / digest[:2]
    return (
        folder / (digest + ".json.gz"),
        folder / (digest + ".receipt.json"),
    )


def _expected_receipt(source: dict[str, Any], compressed: bytes) -> dict[str, Any]:
    return {
        "contract": CONTRACT,
        "source_id": source["source_id"],
        "source_type": "THETADATA_OPTION_HISTORY_QUOTE",
        "source_status": "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED",
        "original_relpath": source["raw_relpath"],
        "summary_relpath": source["summary_relpath"],
        "original_sha256": source["source_sha256"],
        "compressed_sha256": _digest(compressed),
        "original_bytes": source["original_bytes"],
        "compressed_bytes": len(compressed),
        "observed_quotes": source["observed_quotes"],
        "compression": "gzip_level9_mtime0",
        "codec": "gzip",
        "lossless_verified": True,
        "source_coverage_accepted": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
    }


def _restore_bounded(packed: bytes, expected_length: int) -> bytes:
    """Decompress at most the original source size plus one byte."""
    try:
        decoder = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
        restored = decoder.decompress(packed, expected_length + 1)
        if (len(restored) != expected_length or not decoder.eof
                or decoder.unconsumed_tail or decoder.unused_data):
            raise HybridArchiveError("ARCHIVE_DECOMPRESSED_LENGTH_OR_TRAILING_DATA")
        return restored
    except zlib.error as exc:
        raise HybridArchiveError("ARCHIVE_GZIP_INVALID") from exc


def _verify_existing(
    archive_file: Path, receipt_file: Path,
    source: dict[str, Any],
) -> None:
    if (archive_file.is_symlink() or receipt_file.is_symlink()
            or not archive_file.is_file() or not receipt_file.is_file()):
        raise HybridArchiveError("ARCHIVE_OR_RECEIPT_MISSING_OR_LINKED")
    if (not 0 < archive_file.stat().st_size <= MAX_RAW_BYTES
            or not 0 < receipt_file.stat().st_size <= MAX_RECEIPT_BYTES):
        raise HybridArchiveError("ARCHIVE_OR_RECEIPT_SIZE_INVALID")
    try:
        receipt = json.loads(receipt_file.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise HybridArchiveError("ARCHIVE_RECEIPT_INVALID") from exc
    archived = archive_file.read_bytes()
    # zlib/gzip builds can produce distinct but equally lossless compressed
    # bytes. Existing evidence is verified by its original stored hash,
    # not by recompressing and expecting byte-for-byte equality.
    if receipt != _expected_receipt(source, archived):
        raise HybridArchiveError("ARCHIVE_RECEIPT_IDENTITY_OR_SIZE_DRIFT")
    if _digest(archived) != receipt["compressed_sha256"]:
        raise HybridArchiveError("ARCHIVE_GZIP_HASH_DRIFT")
    restored = _restore_bounded(archived, source["original_bytes"])
    if _digest(restored) != source["source_sha256"]:
        raise HybridArchiveError("ARCHIVE_LOSSLESS_RESTORATION_FAILED")


def _write_immutable(final: Path, body: bytes) -> None:
    """Build sibling temporary file then hardlink atomically without overwrite.

    A crash between archive promotion and receipt promotion deliberately
    leaves an incomplete pair that fails closed; it is never auto-retried.
    """
    if final.is_symlink() or final.exists():
        raise HybridArchiveError("IMMUTABLE_DESTINATION_ALREADY_EXISTS")
    temporary = unique_temp_path(final)
    try:
        with temporary.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        # os.link refuses an existing destination on Windows and Linux,
        # unlike os.replace, and avoids accidental evidence replacement.
        try:
            os.link(temporary, final)
        except FileExistsError as exc:
            raise HybridArchiveError("IMMUTABLE_DESTINATION_COLLISION") from exc
    finally:
        temporary.unlink(missing_ok=True)


def archive_existing_source(
    settings: AtlasSettings,
    source_id: str,
    *,
    write_archive: bool = False,
) -> dict[str, Any]:
    """Read one exact catalog source; preview by default, write only if told."""
    source = _source_from_catalog(settings, source_id)
    packed = gzip.compress(source["raw"], compresslevel=9, mtime=0)
    restored = _restore_bounded(packed, source["original_bytes"])
    if restored != source["raw"]:
        raise HybridArchiveError("COMPRESSION_ROUNDTRIP_CHANGED_SOURCE")

    archive_path, receipt_path = _archive_locations(settings, source["source_sha256"])
    if archive_path.is_symlink() or receipt_path.is_symlink():
        raise HybridArchiveError("ARCHIVE_SYMLINK_FORBIDDEN")
    any_present = archive_path.exists() or receipt_path.exists()
    both_present = archive_path.is_file() and receipt_path.is_file()
    if any_present and not both_present:
        raise HybridArchiveError("INCOMPLETE_ARCHIVE_PAIR_NO_AUTOMATIC_RETRY")
    if both_present:
        _verify_existing(archive_path, receipt_path, source)
    inserted = False
    if write_archive and not both_present:
        root = settings.resolved_path("data/options")
        if shutil.disk_usage(root).free < MIN_FREE_BYTES + len(packed) + MAX_RECEIPT_BYTES:
            raise HybridArchiveError("SECONDARY_STORAGE_HEADROOM_UNQUALIFIED")
        archive_body = _expected_receipt(source, packed)
        serialized = (json.dumps(archive_body, indent=2, sort_keys=True) + "\n").encode()
        if len(serialized) > MAX_RECEIPT_BYTES:
            raise HybridArchiveError("ARCHIVE_RECEIPT_SIZE_LIMIT")
        _write_immutable(archive_path, packed)
        _write_immutable(receipt_path, serialized)
        _verify_existing(archive_path, receipt_path, source)
        inserted = True

    actual_compressed_size = (archive_path.stat().st_size
                              if both_present else len(packed))
    return {
        "contract": CONTRACT,
        "source_id": source_id,
        "source_status": "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED",
        "original_bytes": source["original_bytes"],
        "compressed_bytes": actual_compressed_size,
        "saved_fraction": (source["original_bytes"] - actual_compressed_size)
                          / source["original_bytes"],
        "observed_quotes": source["observed_quotes"],
        "archive_present": both_present or inserted,
        "archive_inserted": inserted,
        "archive_path": str(archive_path),
        "receipt_path": str(receipt_path),
        "lossless_source_verification": True,
        "original_source_preserved": True,
        "simulator_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
    }
