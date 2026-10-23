from __future__ import annotations

"""Provider-free hybrid historical-options coverage catalog, source-evidence V1.

Catalogs one explicitly selected immutable ThetaData hourly SPY source receipt.
This is *observed source evidence*, not accepted continuous hourly coverage, a
simulator-ready cache, an acquisition scheduler, or permission to place trades.
No provider client is imported or called. No source files are overwritten.
"""

from datetime import date, datetime
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_hourly_source_canary_v1 import (
    CONTRACT as CANARY_CONTRACT,
    OUTPUT_REL as CANARY_OUTPUT_REL,
    design as canary_design,
)

CATALOG_CONTRACT = "atlas-hybrid-options-coverage-catalog-v1"
CATALOG_REL = "data/options/hybrid/coverage_catalog_v1.duckdb"
MAX_REPORT_BYTES = 64 * 1024
MAX_RECEIPT_BYTES = 16 * 1024
MAX_RAW_BYTES = 24 * 1024 * 1024
MAX_SOURCE_ROWS = 250_000
MIN_FREE_BYTES = 40 * 1024**3


class HybridCoverageError(ValueError):
    pass


def _json_object(path: Path, *, limit: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise HybridCoverageError("REQUIRED_SOURCE_FILE_MISSING_OR_LINKED")
    length = path.stat().st_size
    if not (0 < length <= limit):
        raise HybridCoverageError("SOURCE_METADATA_SIZE_OUTSIDE_CAP")
    try:
        value = json.loads(path.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise HybridCoverageError("SOURCE_METADATA_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise HybridCoverageError("SOURCE_METADATA_NOT_OBJECT")
    return value


def _canonical_rows(raw: bytes) -> list[dict[str, Any]]:
    try:
        rows = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise HybridCoverageError("SOURCE_BODY_JSON_INVALID") from exc
    if (not isinstance(rows, list) or len(rows) > MAX_SOURCE_ROWS
            or any(not isinstance(row, dict) for row in rows)):
        raise HybridCoverageError("SOURCE_BODY_ROWS_INVALID")
    canonical = (
        json.dumps(rows, sort_keys=True, separators=(",", ":"),
                   allow_nan=False, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if canonical != raw:
        raise HybridCoverageError("SOURCE_BODY_CANONICAL_DRIFT")
    return rows


def _source_path(settings: AtlasSettings, requested: Path) -> tuple[Path, Path]:
    """Allow exactly one explicit retained source under the options binding."""
    settings.assert_external_storage_binding("options")
    root = settings.resolved_path("data/options")
    if not root.is_dir():
        raise HybridCoverageError("OPTIONS_BINDING_UNAVAILABLE")
    root_resolved = root.resolve()
    path = requested if requested.is_absolute() else settings.resolved_path(requested)
    path_resolved = path.resolve()
    allow_root = (root / "provider_qualification" /
                  "thetadata_hourly_spy_v1").resolve()
    if (path.name != "summary.json" or path.is_symlink()
            or not path_resolved.is_relative_to(allow_root)
            or not path_resolved.is_relative_to(root_resolved)
            or path_resolved.parent.parent.parent != allow_root):
        raise HybridCoverageError("SOURCE_PATH_OUTSIDE_EXACT_HOURLY_CANARY")
    return root_resolved, path_resolved


def inspect_hourly_source(
    settings: AtlasSettings, summary_path: Path,
) -> dict[str, Any]:
    """Verify one raw source and derive observed keys; do not create a DB."""
    options_root, summary_file = _source_path(settings, summary_path)
    summary = _json_object(summary_file, limit=MAX_REPORT_BYTES)
    frozen = canary_design()
    if (summary.get("contract") != CANARY_CONTRACT
            or summary.get("design_fingerprint") != frozen["design_fingerprint"]
            or summary.get("requested") != frozen["scope"]
            or summary.get("status") != "HOURLY_SOURCE_DIAGNOSTIC_NO_PROMOTION"
            or summary.get("provider_result") != "OBSERVED_HOURLY_ROWS_SOURCE_DIAGNOSTIC"
            or summary.get("source_accepted") is not False
            or summary.get("sdk_normalized_response_retained") is not True
            or summary.get("historical_replay_authority") is not False
            or summary.get("requests_attempted") != 1
            or summary.get("request_cap") != 1
            or summary.get("report_fingerprint") != _fingerprint({
                key: val for key, val in summary.items()
                if key != "report_fingerprint"
            })):
        raise HybridCoverageError("HISTORICAL_CANARY_IDENTITY_OR_PROVENANCE_DRIFT")

    attempt_path = summary_file.parent / "attempt.json"
    attempt = _json_object(attempt_path, limit=MAX_RECEIPT_BYTES)
    if (attempt.get("contract") != CANARY_CONTRACT
            or attempt.get("design_fingerprint") != frozen["design_fingerprint"]
            or attempt.get("request") != frozen["scope"]
            or attempt.get("attempt_reserved") is not True
            or attempt.get("attempt_count_cap") != 1
            or attempt.get("no_retry") is not True):
        raise HybridCoverageError("HISTORICAL_ATTEMPT_PROOF_DRIFT")

    receipt_path = summary_file.parent / "raw" / "hourly_quote.receipt.json"
    body_path = summary_file.parent / "raw" / "hourly_quote.json"
    if (receipt_path.is_symlink() or body_path.is_symlink()
            or not receipt_path.is_file() or not body_path.is_file()):
        raise HybridCoverageError("HISTORICAL_RAW_SOURCE_UNAVAILABLE")
    receipt = _json_object(receipt_path, limit=MAX_RECEIPT_BYTES)
    if (Path(str(summary.get("receipt_path", ""))).resolve() != receipt_path.resolve()
            or Path(str(receipt.get("body_path", ""))).resolve() != body_path.resolve()
            or receipt.get("query") != frozen["scope"]
            or receipt.get("plan_fingerprint") != frozen["design_fingerprint"]
            or receipt.get("provider_transport") != "THETADATA_PYTHON_LIBRARY_ISOLATED_WORKER"
            or receipt.get("provider_library_version") != "1.0.12"
            or receipt.get("evidence_encoding") != "CANONICAL_PROVIDER_DATAFRAME_JSON"
            or receipt.get("explicit_no_data") is not False
            or receipt.get("http_status") != 200
            or receipt.get("body_sha256") != summary.get("sdk_normalized_sha256")):
        raise HybridCoverageError("HISTORICAL_RECEIPT_IDENTITY_OR_SHA_DRIFT")

    size = body_path.stat().st_size
    if (not (0 < size <= MAX_RAW_BYTES)
            or size != receipt.get("body_bytes")
            or size != summary.get("source_bytes")):
        raise HybridCoverageError("HISTORICAL_RAW_SOURCE_SIZE_CHANGED")
    raw = body_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != receipt["body_sha256"]:
        raise HybridCoverageError("HISTORICAL_RAW_SOURCE_SHA_CHANGED")
    rows = _canonical_rows(raw)
    diagnostics = summary.get("source_diagnostics")
    if (not isinstance(diagnostics, dict)
            or diagnostics.get("rows") != len(rows)
            or diagnostics.get("out_of_requested_dte_rows") != 0
            or diagnostics.get("invalid_expiration_rows") != 0
            or diagnostics.get("missing_required_quote_fields") != 0
            or diagnostics.get("invalid_or_naive_timestamps") != 0
            or len(gzip.compress(raw, compresslevel=9))
            != summary.get("gzip_9_size_bytes")):
        raise HybridCoverageError("HISTORICAL_SOURCE_DIAGNOSTICS_DRIFT")

    keys: list[tuple[int, str, str, str, str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for ordinal, row in enumerate(rows):
        try:
            symbol = str(row["symbol"])
            expiration = date.fromisoformat(str(row["expiration"])[:10]).isoformat()
            right = str(row["right"]).upper()
            strike = str(row["strike"])
            stamp = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            if (symbol != frozen["scope"]["symbol"]
                    or right not in {"CALL", "PUT"}
                    or stamp.tzinfo is None or stamp.utcoffset() is None
                    or not (0 <= (date.fromisoformat(expiration)
                                  - date.fromisoformat(frozen["scope"]["date_et"])).days
                            <= frozen["scope"]["max_dte"])):
                raise ValueError("row identity outside requested bounds")
        except (KeyError, TypeError, ValueError) as exc:
            raise HybridCoverageError("HISTORICAL_OBSERVATION_IDENTITY_INVALID") from exc
        key = (symbol, expiration, strike, right, stamp.isoformat())
        if key in seen:
            # Do not infer completeness from duplicates; for now a collision
            # blocks ingestion and leaves the original receipt unchanged.
            raise HybridCoverageError("HISTORICAL_OBSERVATION_KEY_DUPLICATE")
        seen.add(key)
        keys.append((ordinal, *key))

    fp = _fingerprint({
        "contract": CATALOG_CONTRACT,
        "report_fingerprint": summary["report_fingerprint"],
        "body_sha256": digest,
    })
    return {
        "contract": CATALOG_CONTRACT,
        "source_id": fp,
        "source_type": "THETADATA_OPTION_HISTORY_QUOTE",
        "provider": "thetadata",
        "source_status": "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED",
        "query_coverage_proven": False,
        "simulator_ready": False,
        "source_scope": frozen["scope"],
        "source_rows": len(keys),
        "unique_observed_contracts": len({(x[1], x[2], x[3], x[4]) for x in keys}),
        "source_bytes": len(raw),
        "gzip_9_estimate_bytes": summary["gzip_9_size_bytes"],
        "source_sha256": digest,
        "report_fingerprint": summary["report_fingerprint"],
        "summary_relpath": summary_file.relative_to(options_root).as_posix(),
        "raw_relpath": body_path.relative_to(options_root).as_posix(),
        "receipt_relpath": receipt_path.relative_to(options_root).as_posix(),
        "_observation_keys": keys,
        "provider_requests": 0,
        "broker_requests": 0,
        "simulations_run": 0,
    }


def _create_schema(con: Any) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS source_units (
            source_id VARCHAR PRIMARY KEY,
            source_type VARCHAR NOT NULL,
            provider VARCHAR NOT NULL,
            symbol VARCHAR NOT NULL,
            session_et VARCHAR NOT NULL,
            interval VARCHAR NOT NULL,
            rights_requested VARCHAR NOT NULL,
            query_json VARCHAR NOT NULL,
            source_status VARCHAR NOT NULL,
            query_coverage_proven BOOLEAN NOT NULL,
            simulator_ready BOOLEAN NOT NULL,
            summary_relpath VARCHAR NOT NULL,
            receipt_relpath VARCHAR NOT NULL,
            raw_relpath VARCHAR NOT NULL,
            body_sha256 VARCHAR NOT NULL,
            report_fingerprint VARCHAR NOT NULL,
            source_rows BIGINT NOT NULL,
            source_bytes BIGINT NOT NULL,
            gzip_estimate_bytes BIGINT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS observed_quote_keys (
            source_id VARCHAR NOT NULL,
            ordinal BIGINT NOT NULL,
            underlying VARCHAR NOT NULL,
            expiration VARCHAR NOT NULL,
            strike VARCHAR NOT NULL,
            right VARCHAR NOT NULL,
            observed_timestamp VARCHAR NOT NULL,
            PRIMARY KEY(source_id, ordinal)
        )
    """)


def ingest_hourly_source(
    settings: AtlasSettings, summary_path: Path,
) -> dict[str, Any]:
    """Idempotently register one verified but *unqualified* hourly source."""
    source = inspect_hourly_source(settings, summary_path)
    options_root = settings.resolved_path("data/options")
    if shutil.disk_usage(options_root).free < MIN_FREE_BYTES:
        raise HybridCoverageError("SECONDARY_STORAGE_HEADROOM_UNQUALIFIED")
    db_path = settings.resolved_path(CATALOG_REL)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = connect_utc(db_path)
    inserted = False
    try:
        con.begin()
        _create_schema(con)
        stored = con.execute(
            "SELECT body_sha256, report_fingerprint, source_rows "
            "FROM source_units WHERE source_id = ?", [source["source_id"]],
        ).fetchone()
        if stored:
            if stored != (
                source["source_sha256"],
                source["report_fingerprint"],
                source["source_rows"],
            ):
                raise HybridCoverageError("EXISTING_CATALOG_SOURCE_CONFLICT")
        else:
            scope = source["source_scope"]
            con.execute(
                "INSERT INTO source_units VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    source["source_id"], source["source_type"], source["provider"],
                    scope["symbol"], scope["date_et"], scope["interval"],
                    scope["right"], json.dumps(scope, sort_keys=True),
                    source["source_status"], False, False,
                    source["summary_relpath"], source["receipt_relpath"],
                    source["raw_relpath"], source["source_sha256"],
                    source["report_fingerprint"], source["source_rows"],
                    source["source_bytes"], source["gzip_9_estimate_bytes"],
                ],
            )
            observations = [
                (source["source_id"], *item)
                for item in source["_observation_keys"]
            ]
            con.executemany(
                "INSERT INTO observed_quote_keys VALUES (?,?,?,?,?,?,?)",
                observations,
            )
            inserted = True
        count = con.execute(
            "SELECT COUNT(*) FROM observed_quote_keys WHERE source_id = ?",
            [source["source_id"]],
        ).fetchone()[0]
        if count != source["source_rows"]:
            raise HybridCoverageError("EXISTING_CATALOG_OBSERVATION_COUNT_CONFLICT")
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return {
        key: value for key, value in source.items()
        if not key.startswith("_")
    } | {
        "catalog_path": str(db_path),
        "catalog_inserted": inserted,
        "catalog_observation_rows": count,
        "simulation_inputs_authorized": False,
        "automatic_acquisition_authorized": False,
    }


def inspect_exact_hourly_request(
    settings: AtlasSettings, *,
    symbol: str, date_et: str, right: str,
) -> dict[str, Any]:
    """Return source-presence versus usable-data as separate facts.

    This V1 NEVER claims a full session or a qualifying simulation dataset.
    """
    settings.assert_external_storage_binding("options")
    db_path = settings.resolved_path(CATALOG_REL)
    if not db_path.is_file():
        return {
            "source_present": False, "simulator_ready": False,
            "status": "NOT_INDEXED", "provider_requests": 0,
        }
    con = connect_utc(db_path, read_only=True)
    try:
        items = con.execute(
            "SELECT source_id, source_status, query_coverage_proven, "
            "simulator_ready, source_rows FROM source_units "
            "WHERE symbol=? AND session_et=? AND "
            "(rights_requested=? OR rights_requested='both')",
            [symbol, date_et, right],
        ).fetchall()
    finally:
        con.close()
    return {
        "source_present": bool(items),
        "status": "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED"
                  if items else "NOT_INDEXED",
        "sources_found": len(items),
        "observed_rows": sum(item[4] for item in items),
        "query_coverage_proven": False,
        "simulator_ready": False,
        "provider_requests": 0,
        "automatic_acquisition_authorized": False,
    }
