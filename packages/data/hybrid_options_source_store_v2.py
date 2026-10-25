from __future__ import annotations

"""V6 generalized, compressed-at-ingestion historical option quote source store.

Supports a bounded single-session quote query for arbitrary symbols, rights,
and 1h/1m/1s intervals. Source material is diagnostic, not proof of complete
coverage or an executable bid/ask. Two explicit provenance types are supported:
a freshly returned, SDK-normalized source, and the *already verified* V4
immutable archive. No provider calls, retry logic or simulator integration.

V1's accepted SPY archive/catalog are never rewritten or promoted.
"""

from datetime import date, datetime
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.hybrid_options_gap_planner_v1 import _scope
from packages.data.hybrid_options_lossless_archive_v1 import (
    _restore_bounded, _write_immutable,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)

CONTRACT = "atlas-hybrid-options-generalized-source-store-v2"
CATALOG_REL = "data/options/hybrid/source_store_v2.duckdb"
ARCHIVE_REL = "data/options/hybrid/source_archive_v2"
SOURCE_STATUS = "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED"
MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_ROWS = 250_000
MAX_RECEIPT_BYTES = 16 * 1024
FREE_WARNING_BYTES = 40 * 1024**3
STORE_QUOTA_BYTES = 120 * 1024**3
SHA = re.compile(r"[a-f0-9]{64}")
EASTERN = ZoneInfo("America/New_York")


class HybridSourceStoreError(ValueError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _paths(settings: AtlasSettings, source_id: str) -> tuple[Path, Path]:
    base = settings.resolved_path(ARCHIVE_REL) / source_id[:2]
    return base / (source_id + ".json.gz"), base / (source_id + ".receipt.json")


def _validate_query(query: dict[str, Any]) -> dict[str, Any]:
    try:
        norm = _scope(query)
    except (ValueError, TypeError) as exc:
        raise HybridSourceStoreError("INVALID_EXACT_HISTORICAL_SOURCE_QUERY") from exc
    # Match the currently pinned provider worker rather than accepting queries
    # which that adapter cannot represent.
    if norm["max_dte"] > 75 or norm["strike_range"] > 8:
        raise HybridSourceStoreError("QUERY_OUTSIDE_WORKER_BOUNDS")
    return norm


def _source_keys(raw: bytes, query: dict[str, Any]) -> tuple[
    list[tuple[int, str, str, str, str, str]], dict[str, Any]
]:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_SOURCE_BYTES:
        raise HybridSourceStoreError("CANONICAL_SOURCE_SIZE_INVALID")
    try:
        rows = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise HybridSourceStoreError("SOURCE_JSON_INVALID") from exc
    if (not isinstance(rows, list) or not 0 < len(rows) <= MAX_ROWS
            or any(not isinstance(x, dict) for x in rows)
            or _canonical_bytes(rows) != raw):
        raise HybridSourceStoreError("SOURCE_CANONICAL_ROWS_INVALID")
    keys: list[tuple[int, str, str, str, str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    duplicates = 0
    out_of_dte = 0
    out_of_window = 0
    crossed_books = 0
    expiry_min = None
    expiry_max = None
    day = date.fromisoformat(query["date_et"])
    begin = datetime.combine(day, datetime.fromisoformat(
        query["date_et"] + "T" + query["start_time"]
    ).time(), tzinfo=EASTERN)
    end = datetime.combine(day, datetime.fromisoformat(
        query["date_et"] + "T" + query["end_time"]
    ).time(), tzinfo=EASTERN)
    for ordinal, row in enumerate(rows):
        try:
            symbol = row["symbol"]
            if not isinstance(symbol, str) or symbol != query["symbol"]:
                raise ValueError("underlying mismatch")
            expiry = date.fromisoformat(str(row["expiration"])[:10])
            right = str(row["right"]).upper()
            if right not in ("CALL", "PUT") or (
                query["right"] != "both" and right.lower() != query["right"]
            ):
                raise ValueError("option right mismatch")
            strike_num = float(row["strike"])
            if not math.isfinite(strike_num) or strike_num <= 0:
                raise ValueError("invalid strike")
            stamp = datetime.fromisoformat(
                str(row["timestamp"]).replace("Z", "+00:00")
            )
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("timestamp not offset-aware")
            # Parse identity and numeric values even when source diagnostics
            # are unfavorable: do not filter the provider's original rows.
            bid, ask = float(row["bid"]), float(row["ask"])
            bid_size, ask_size = float(row["bid_size"]), float(row["ask_size"])
            if not all(math.isfinite(v) and v >= 0 for v in (
                    bid, ask, bid_size, ask_size)):
                raise ValueError("negative/nonfinite book")
            if int(bid_size) != bid_size or int(ask_size) != ask_size:
                raise ValueError("fractional book size")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise HybridSourceStoreError(
                "SOURCE_ROW_IDENTITY_OR_BOOK_SCHEMA_INVALID"
            ) from exc

        clock_et = stamp.astimezone(EASTERN)
        if clock_et.date() != day or clock_et < begin or clock_et >= end:
            out_of_window += 1
        dte = (expiry - day).days
        if not 0 <= dte <= query["max_dte"]:
            out_of_dte += 1
        if ask < bid:
            crossed_books += 1
        expiry_text = expiry.isoformat()
        expiry_min = expiry_text if expiry_min is None else min(expiry_min, expiry_text)
        expiry_max = expiry_text if expiry_max is None else max(expiry_max, expiry_text)
        identity = (symbol, expiry_text, str(row["strike"]), right,
                    stamp.isoformat())
        if identity in seen:
            duplicates += 1
        seen.add(identity)
        keys.append((ordinal, *identity))
    diagnostics = {
        "observed_rows": len(keys),
        "distinct_contracts": len({k[1:5] for k in keys}),
        "duplicate_observation_keys": duplicates,
        "outside_requested_dte": out_of_dte,
        "outside_requested_clock_window": out_of_window,
        "crossed_bid_ask": crossed_books,
        "minimum_expiration": expiry_min,
        "maximum_expiration": expiry_max,
        "query_coverage_proven": False,
        "timestamp_lookahead_semantics_qualified": False,
        "simulator_ready": False,
    }
    return keys, diagnostics


def _provenance(response: ThetaDataResponse | None,
                verified_v4: dict[str, Any] | None) -> tuple[bytes, dict[str, Any]]:
    if (response is None) == (verified_v4 is None):
        raise HybridSourceStoreError("EXACTLY_ONE_PROVENANCE_REQUIRED")
    if response is not None:
        if (not isinstance(response, ThetaDataResponse)
                or response.transport != TRANSPORT
                or response.library_version != TARGET_LIBRARY_VERSION
                or response.evidence_encoding != EVIDENCE_ENCODING
                or not isinstance(response.provider_environment_fingerprint, str)
                or not SHA.fullmatch(response.provider_environment_fingerprint)
                or response.explicit_no_data
                or response.http_status != 200
                or response.response_bytes != len(response.raw_body)
                or response.raw_body != _canonical_bytes(response.rows)):
            raise HybridSourceStoreError("PROVIDER_SOURCE_ENVELOPE_INVALID")
        return response.raw_body, {
            "origin": "THETADATA_ISOLATED_SDK",
            "transport": TRANSPORT,
            "sdk_version": TARGET_LIBRARY_VERSION,
            "environment_fingerprint": response.provider_environment_fingerprint,
            "provider_method": "option_history_quote",
        }
    assert verified_v4 is not None
    if (verified_v4.get("retrieved_from") != "VERIFIED_LOCAL_COMPRESSED_ARCHIVE"
            or verified_v4.get("source_status") != SOURCE_STATUS
            or verified_v4.get("query_coverage_proven") is not False
            or verified_v4.get("simulator_ready") is not False
            or verified_v4.get("original_uncompressed_source_opened") is not False
            or verified_v4.get("provider_requests") != 0
            or not isinstance(verified_v4.get("source_id"), str)
            or not SHA.fullmatch(verified_v4["source_id"])
            or not isinstance(verified_v4.get("source_sha256"), str)
            or not SHA.fullmatch(verified_v4["source_sha256"])
            or not isinstance(verified_v4.get("archive_sha256"), str)
            or not SHA.fullmatch(verified_v4["archive_sha256"])
            or not isinstance(verified_v4.get("rows"), tuple)):
        raise HybridSourceStoreError("LEGACY_ARCHIVE_PROVENANCE_INVALID")
    raw = _canonical_bytes(verified_v4["rows"])
    if (len(raw) != verified_v4["restored_original_bytes"]
            or _sha(raw) != verified_v4["source_sha256"]
            or len(verified_v4["rows"]) != verified_v4["quote_rows"]):
        raise HybridSourceStoreError("LEGACY_ARCHIVE_SOURCE_DRIFT")
    return raw, {
        "origin": "VERIFIED_EXISTING_V4_ARCHIVE",
        "original_source_id": verified_v4["source_id"],
        "original_sha256": verified_v4["source_sha256"],
        "original_archive_sha256": verified_v4["archive_sha256"],
    }


def _receipt(record: dict[str, Any], packed: bytes) -> dict[str, Any]:
    return {
        "contract": CONTRACT,
        "source_id": record["source_id"],
        "query": record["query"],
        "query_id": record["query_id"],
        "body_sha256": record["body_sha256"],
        "compressed_sha256": _sha(packed),
        "source_bytes": record["source_bytes"],
        "compressed_bytes": len(packed),
        "observed_rows": record["diagnostics"]["observed_rows"],
        "observed_key_fingerprint": record["key_fingerprint"],
        "diagnostics": record["diagnostics"],
        "provenance": record["provenance"],
        "source_status": SOURCE_STATUS,
        "compression": "gzip_level9_mtime0",
        "query_coverage_proven": False,
        "simulator_ready": False,
    }


def _verify_archive(settings: AtlasSettings,
                    record: dict[str, Any]) -> bytes:
    path, proof = _paths(settings, record["source_id"])
    root = settings.resolved_path("data/options").resolve()
    for item in (path, proof):
        if (item.is_symlink() or not item.is_file()
                or not item.resolve().is_relative_to(root)):
            raise HybridSourceStoreError("ARCHIVE_OR_RECEIPT_MISSING_OR_UNSAFE")
    if (not 0 < path.stat().st_size <= MAX_SOURCE_BYTES
            or not 0 < proof.stat().st_size <= MAX_RECEIPT_BYTES):
        raise HybridSourceStoreError("ARCHIVE_OR_RECEIPT_SIZE_OUTSIDE_CAP")
    packed = path.read_bytes()
    try:
        stored = json.loads(proof.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise HybridSourceStoreError("ARCHIVE_RECEIPT_INVALID") from exc
    if stored != _receipt(record, packed):
        raise HybridSourceStoreError("ARCHIVE_RECEIPT_OR_PROVENANCE_CHANGED")
    raw = _restore_bounded(packed, record["source_bytes"])
    if _sha(raw) != record["body_sha256"]:
        raise HybridSourceStoreError("ARCHIVE_RESTORED_HASH_CHANGED")
    keys, diagnostics = _source_keys(raw, record["query"])
    if diagnostics != record["diagnostics"] or _fingerprint(keys) != record["key_fingerprint"]:
        raise HybridSourceStoreError("ARCHIVE_OBSERVATION_KEYS_CHANGED")
    return raw


def _create_schema(con: Any) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS quote_sources (
            source_id VARCHAR PRIMARY KEY,
            query_id VARCHAR UNIQUE NOT NULL,
            query_json VARCHAR NOT NULL,
            record_json VARCHAR NOT NULL,
            source_status VARCHAR NOT NULL,
            source_rows BIGINT NOT NULL,
            compressed_bytes BIGINT NOT NULL,
            simulator_ready BOOLEAN NOT NULL,
            query_coverage_proven BOOLEAN NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS quote_keys (
            source_id VARCHAR NOT NULL,
            ordinal BIGINT NOT NULL,
            symbol VARCHAR NOT NULL,
            expiration VARCHAR NOT NULL,
            strike VARCHAR NOT NULL,
            option_right VARCHAR NOT NULL,
            observed_timestamp VARCHAR NOT NULL,
            PRIMARY KEY (source_id, ordinal)
        )
    """)


def store_historical_quote_source(
    settings: AtlasSettings,
    query: dict[str, Any],
    *,
    response: ThetaDataResponse | None = None,
    verified_v4: dict[str, Any] | None = None,
    write: bool = False,
) -> dict[str, Any]:
    """Preview by default; write a compressed archive and index only if opted in.

    The caller performs provider calls separately. A never-requested local
    source cannot be silently synthesized or treated as explicit no-data.
    """
    settings.assert_external_storage_binding("options")
    options = settings.resolved_path("data/options")
    if not options.is_dir():
        raise HybridSourceStoreError("OPTIONS_STORAGE_UNAVAILABLE")
    normalized = _validate_query(query)
    if verified_v4 is not None:
        # Provenance is never established by trusting a caller-crafted flag.
        # Reopen the *compressed*, V4-verified original by its exact source ID.
        from packages.data.hybrid_options_archive_reader_v1 import (
            load_verified_archived_option_quotes,
        )
        if not isinstance(verified_v4, dict):
            raise HybridSourceStoreError("LEGACY_ARCHIVE_PROVENANCE_INVALID")
        verified_again = load_verified_archived_option_quotes(
            settings, verified_v4.get("source_id"),
        )
        if (
            verified_v4.get("source_sha256") != verified_again["source_sha256"]
            or verified_v4.get("archive_sha256") != verified_again["archive_sha256"]
            or verified_v4.get("query_scope") != verified_again["query_scope"]
            or verified_v4.get("rows") != verified_again["rows"]
        ):
            raise HybridSourceStoreError("LEGACY_ARCHIVE_CALLER_VERSUS_RECEIPT_DRIFT")
        verified_v4 = verified_again
    raw, origin = _provenance(response, verified_v4)
    if verified_v4 is not None and verified_v4.get("query_scope") != normalized:
        raise HybridSourceStoreError("LEGACY_ARCHIVE_QUERY_MISMATCH")
    keys, diag = _source_keys(raw, normalized)
    query_id = _fingerprint({
        "source_type": "option_history_quote", "query": normalized,
    })
    record = {
        "source_id": _fingerprint({
            "contract": CONTRACT, "query_id": query_id,
            "body_sha256": _sha(raw), "provenance": origin,
        }),
        "query_id": query_id, "query": normalized,
        "body_sha256": _sha(raw),
        "source_bytes": len(raw),
        "key_fingerprint": _fingerprint(keys),
        "provenance": origin, "diagnostics": diag,
    }
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    if _restore_bounded(compressed, len(raw)) != raw:
        raise HybridSourceStoreError("LOSSLESS_GZIP_ROUNDTRIP_FAILED")
    destination, receipt_path = _paths(settings, record["source_id"])
    db_path = settings.resolved_path(CATALOG_REL)

    # A preview is strictly read-only and leaves even parent directories alone.
    if not write:
        return {
            "contract": CONTRACT, **record,
            "compressed_bytes": len(compressed), "archived": False,
            "indexed": False, "written": False,
            "simulator_ready": False, "provider_requests": 0,
        }

    free = shutil.disk_usage(options).free
    if free < FREE_WARNING_BYTES + len(compressed) + MAX_RECEIPT_BYTES:
        raise HybridSourceStoreError("SECONDARY_STORAGE_HEADROOM_UNQUALIFIED")
    existing_record = None
    indexed = False
    if db_path.is_symlink():
        raise HybridSourceStoreError("CATALOG_PATH_UNSAFE")
    if db_path.is_file():
        con = connect_utc(db_path, read_only=True)
        try:
            existing = con.execute(
                "SELECT record_json FROM quote_sources WHERE query_id=?",
                [query_id],
            ).fetchone()
            existing_record = json.loads(existing[0]) if existing else None
        finally:
            con.close()
    if existing_record is not None and existing_record != record:
        raise HybridSourceStoreError("EXACT_QUERY_HAS_DIFFERENT_IMMUTABLE_SOURCE")

    if destination.is_symlink() or receipt_path.is_symlink():
        raise HybridSourceStoreError("ARCHIVE_SYMLINK_FORBIDDEN")
    if destination.exists() != receipt_path.exists():
        raise HybridSourceStoreError("INCOMPLETE_ARCHIVE_PAIR_NO_AUTO_RETRY")
    already = destination.exists()
    if already:
        _verify_archive(settings, record)
    elif existing_record is not None:
        raise HybridSourceStoreError("INDEXED_ARCHIVE_MISSING_NO_FALLBACK")
    else:
        if (db_path.is_file()):
            con = connect_utc(db_path, read_only=True)
            try:
                total = con.execute(
                    "SELECT COALESCE(SUM(compressed_bytes),0) FROM quote_sources"
                ).fetchone()[0]
            finally:
                con.close()
        else:
            total = 0
        if total + len(compressed) > STORE_QUOTA_BYTES:
            raise HybridSourceStoreError("SOURCE_ARCHIVE_QUOTA_EXCEEDED")
        destination.parent.mkdir(parents=True, exist_ok=True)
        receipt_bytes = (json.dumps(_receipt(record, compressed),
                                    sort_keys=True, indent=2) + "\n").encode("utf-8")
        if len(receipt_bytes) > MAX_RECEIPT_BYTES:
            raise HybridSourceStoreError("SOURCE_RECEIPT_SIZE_EXCEEDED")
        _write_immutable(destination, compressed)
        _write_immutable(receipt_path, receipt_bytes)
        _verify_archive(settings, record)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = connect_utc(db_path)
    try:
        con.begin()
        _create_schema(con)
        old = con.execute(
            "SELECT record_json FROM quote_sources WHERE query_id=?",
            [query_id],
        ).fetchone()
        if old is None:
            con.execute(
                "INSERT INTO quote_sources VALUES(?,?,?,?,?,?,?,?,?)",
                [
                    record["source_id"], query_id,
                    json.dumps(normalized, sort_keys=True),
                    json.dumps(record, sort_keys=True), SOURCE_STATUS,
                    len(keys), len(compressed), False, False,
                ],
            )
            con.executemany(
                "INSERT INTO quote_keys VALUES(?,?,?,?,?,?,?)",
                [(record["source_id"], *key) for key in keys],
            )
            indexed = True
        elif json.loads(old[0]) != record:
            raise HybridSourceStoreError("CATALOG_IDENTITY_CONFLICT")
        count = con.execute(
            "SELECT COUNT(*) FROM quote_keys WHERE source_id=?",
            [record["source_id"]],
        ).fetchone()[0]
        if count != len(keys):
            raise HybridSourceStoreError("CATALOG_OBSERVATION_COUNT_MISMATCH")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return {
        "contract": CONTRACT, **record,
        "compressed_bytes": len(compressed), "archived": True,
        "indexed": True, "written": indexed or not already,
        "new_archive": not already, "new_catalog_entry": indexed,
        "simulator_ready": False, "provider_requests": 0,
    }


def read_historical_quote_source(
    settings: AtlasSettings, source_id: str,
) -> dict[str, Any]:
    """Read a V6 compressed source, independently checking index and receipt."""
    if not isinstance(source_id, str) or not SHA.fullmatch(source_id):
        raise HybridSourceStoreError("INVALID_SOURCE_ID")
    settings.assert_external_storage_binding("options")
    db_path = settings.resolved_path(CATALOG_REL)
    if db_path.is_symlink() or not db_path.is_file():
        raise HybridSourceStoreError("V6_CATALOG_MISSING")
    con = connect_utc(db_path, read_only=True)
    try:
        stored = con.execute(
            "SELECT record_json, source_status, source_rows, compressed_bytes, "
            "simulator_ready, query_coverage_proven FROM quote_sources "
            "WHERE source_id=?", [source_id],
        ).fetchall()
        if len(stored) != 1:
            raise HybridSourceStoreError("V6_EXACT_SOURCE_NOT_INDEXED")
        record = json.loads(stored[0][0])
        if (record["source_id"] != source_id
                or stored[0][1] != SOURCE_STATUS
                or stored[0][2] != record["diagnostics"]["observed_rows"]
                or stored[0][4] is not False
                or stored[0][5] is not False
                or record["query_id"] != _fingerprint({
                    "source_type": "option_history_quote",
                    "query": record["query"],
                })):
            raise HybridSourceStoreError("V6_SOURCE_AUTHORITY_CHANGED")
        indices = con.execute(
            "SELECT ordinal,symbol,expiration,strike,option_right,"
            "observed_timestamp FROM quote_keys WHERE source_id=? "
            "ORDER BY ordinal LIMIT ?", [source_id, MAX_ROWS + 1],
        ).fetchall()
    finally:
        con.close()
    raw = _verify_archive(settings, record)
    if _paths(settings, source_id)[0].stat().st_size != stored[0][3]:
        raise HybridSourceStoreError("V6_CATALOG_COMPRESSED_SIZE_CHANGED")
    keys, diagnostic = _source_keys(raw, record["query"])
    if tuple(indices) != tuple(keys):
        raise HybridSourceStoreError("V6_INDEX_VERSUS_ARCHIVED_ROWS_CHANGED")
    if len(raw) != record["source_bytes"]:
        raise HybridSourceStoreError("V6_RESTORED_SOURCE_BYTES_CHANGED")
    return {
        "contract": CONTRACT, "source_id": source_id,
        "query": record["query"], "provenance": record["provenance"],
        "diagnostics": diagnostic, "source_sha256": record["body_sha256"],
        "quote_rows": len(keys), "retrieved_from": "V6_VERIFIED_GZIP",
        "simulator_ready": False, "query_coverage_proven": False,
        "provider_requests": 0, "broker_requests": 0, "simulations_run": 0,
    }
