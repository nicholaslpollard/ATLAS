from __future__ import annotations

"""V38 provider-backed read-through historical options cache for changing strategies.

A strategy may generate an unbounded *sequence* of exact source requirements.
Each source read is bounded by the provider response size and physical storage;
there is no frozen universe, fixed candidate roster or lifetime request quota.
Cache receipts are historical evidence only, not causal availability or fills.
"""

from datetime import date
from contextlib import contextmanager
import gzip
import hashlib
import inspect
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.providers.thetadata import client as theta

CONTRACT = "atlas-options-strategy-on-demand-source-cache-v38"
ROOT_REL = "data/options/hybrid/on_demand_source_cache_v38"
DB_REL = ROOT_REL + "/source_receipts.sqlite3"
ARCHIVE_REL = ROOT_REL + "/archive"
ALLOWED = frozenset({
    "option_at_time_quote",
    "option_history_exact_quote_tape",
    "option_at_time_quote_surface",
    "option_history_hourly_quote_surface",
    "option_history_open_interest_surface",
    "option_history_binomial_first_order_greeks_at_minute",
})
MAX_RAW_BYTES = 24 * 1024 * 1024
MAX_SOURCE_ROWS = 250_000
MIN_FREE_STORAGE_BYTES = 40 * 1024**3
ACTIVE_LEASE_SECONDS = 600
SHA = re.compile(r"[a-f0-9]{64}")


class OnDemandSourceError(ValueError):
    pass


def normalize_source_requirement(method: str, kwargs: dict[str, Any]) -> dict:
    """Exact SDK wrapper signature; changing ANY variable changes cache identity."""
    if method not in ALLOWED or not isinstance(kwargs, dict):
        raise OnDemandSourceError("UNSUPPORTED_READ_ONLY_PROVIDER_METHOD")
    try:
        bound = inspect.signature(getattr(theta, method)).bind(**kwargs)
        bound.apply_defaults()
        args = dict(bound.arguments)
        if not isinstance(args.get("symbol"), str) or not re.fullmatch(
            r"[A-Z][A-Z0-9.-]{0,15}", args["symbol"]
        ):
            raise ValueError("invalid underlying")
        if "date_et" not in args or not isinstance(args["date_et"], str):
            raise ValueError("missing exact date")
        day = date.fromisoformat(args["date_et"])
        if day.isoformat() != args["date_et"]:
            raise ValueError("noncanonical date")
        for field in ("expiration",):
            if field in args and (not isinstance(args[field], str)
                                 or date.fromisoformat(args[field]).isoformat() != args[field]):
                raise ValueError("noncanonical expiration")
        for field in ("max_dte", "strike_range"):
            if field in args and args[field] is not None and (
                type(args[field]) is not int or args[field] < 0
            ):
                raise ValueError("negative parameter")
        if args.get("right", "both") not in ("both", "call", "put"):
            raise ValueError("invalid option right")
        if method == "option_history_exact_quote_tape":
            if (args["right"] not in ("call", "put")
                    or args.get("interval") not in ("1s", "tick", "1m")):
                raise ValueError("non-exact source scope")
            if not re.fullmatch(r"[0-9]{1,6}(?:\\.[0-9]{1,3})?", str(args["strike"])):
                raise ValueError("non-canonical exact strike")
            # Require one session, exact contract, bounded clock range.
            from datetime import datetime as _datetime
            start = _datetime.strptime(args["start_time_et"], "%H:%M:%S.%f").time()
            end = _datetime.strptime(args["end_time_et"], "%H:%M:%S.%f").time()
            if (start > end or not (9 <= start.hour <= 16)
                    or not (9 <= end.hour <= 16)
                    or start < _datetime.strptime("09:30:00.000", "%H:%M:%S.%f").time()
                    or end > _datetime.strptime("16:00:00.000", "%H:%M:%S.%f").time()
                    or args["date_et"] > args["expiration"]):
                raise ValueError("source exact date/clock outside market bounds")
        # JSON serialization rejects NaNs and unsupported API input objects;
        # no mutable caller dict is passed into provider or source registry.
        json.dumps(args, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, AttributeError) as exc:
        raise OnDemandSourceError("SOURCE_REQUIREMENT_INVALID") from exc
    return {"provider": "thetadata", "method": method, "kwargs": args}


def _digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _database(settings: AtlasSettings) -> Path:
    settings.assert_external_storage_binding("options")
    root = settings.resolved_path("data/options")
    if not root.is_dir():
        raise OnDemandSourceError("OPTIONS_EXTERNAL_STORAGE_UNAVAILABLE")
    db = settings.resolved_path(DB_REL)
    if db.is_symlink():
        raise OnDemandSourceError("SOURCE_INDEX_IS_SYMLINK")
    db.parent.mkdir(parents=True, exist_ok=True)
    return db


@contextmanager
def _connect(db: Path):
    """Ensure SQLite connections close on Windows even if a provider call fails."""
    con = sqlite3.connect(db, timeout=30)
    try:
        con.execute("PRAGMA busy_timeout=30000")
        con.execute("""
            CREATE TABLE IF NOT EXISTS sources (
              query_id TEXT PRIMARY KEY,
              request_json TEXT NOT NULL,
              state TEXT NOT NULL,
              touched REAL NOT NULL,
              source_sha TEXT,
              gzip_sha TEXT,
              stored_path TEXT,
              source_rows INTEGER
            )
        """)
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _unpack(settings: AtlasSettings, row: tuple, request: dict) -> dict:
    qid, raw_request, state, _, sha, gzip_sha, rel, size = row
    if raw_request != json.dumps(request, sort_keys=True, separators=(",", ":")):
        raise OnDemandSourceError("CACHED_QUERY_IDENTITY_DRIFT")
    if state == "NO_DATA_EXPLICIT":
        return _result(qid, request, (), "CACHED_EXPLICIT_NO_DATA", None)
    if (state != "ARCHIVED" or not sha or not SHA.fullmatch(sha)
            or not gzip_sha or not SHA.fullmatch(gzip_sha)
            or not isinstance(rel, str) or not rel.startswith(ARCHIVE_REL + "/")):
        raise OnDemandSourceError("CACHED_RECORD_NOT_ARCHIVED")
    root = settings.resolved_path(ARCHIVE_REL).resolve()
    path = settings.resolved_path(rel)
    if (path.is_symlink() or not path.is_file() or
            not path.resolve().is_relative_to(root) or
            path.stat().st_size > MAX_RAW_BYTES):
        raise OnDemandSourceError("CACHED_ARCHIVE_MISSING_OR_UNSAFE")
    packed = path.read_bytes()
    if _digest(packed) != gzip_sha:
        raise OnDemandSourceError("CACHED_GZIP_DIGEST_CHANGED")
    with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
        raw = stream.read(MAX_RAW_BYTES + 1)
        if stream.read(1) or not 0 < len(raw) <= MAX_RAW_BYTES:
            raise OnDemandSourceError("CACHED_SOURCE_TOO_LARGE")
    if _digest(raw) != sha:
        raise OnDemandSourceError("CACHED_SOURCE_DIGEST_CHANGED")
    rows = json.loads(raw)
    if (not isinstance(rows, list) or len(rows) != size or
            not 0 < len(rows) <= MAX_SOURCE_ROWS or
            any(not isinstance(r, dict) for r in rows) or
            theta._canonical_bytes(rows) != raw):
        raise OnDemandSourceError("CACHED_SOURCE_ROWS_CHANGED")
    return _result(qid, request, tuple(rows), "CACHE_HIT", sha)


def _result(qid: str, request: dict, rows: tuple, status: str, sha: str | None) -> dict:
    return {
        "contract": CONTRACT, "query_id": qid, "exact_requirement": request,
        "status": status, "source_rows": rows, "source_sha256": sha,
        "source_only_not_historical_execution": True,
        "historical_availability_qualified": False,
        "simulator_ready": False, "broker_requests": 0,
    }


def read_through_historical_options(
    settings: AtlasSettings, method: str, kwargs: dict[str, Any], *,
    provider_call: Callable[[str, dict[str, Any]], theta.ThetaDataResponse] | None = None,
) -> dict:
    """Cache hit: reuse original immutable receipt. Miss: SDK read, persist, return.

    IN_FLIGHT protects concurrent workers from dispatching the same exact GET.
    A lease expiration permits a subsequent idempotent historical GET if the
    process crashed. FAILED_RETRYABLE permits new simulation runs to retry.
    Never turn an implicit empty result into provider-confirmed no-data.
    """
    req = normalize_source_requirement(method, kwargs)
    qid = _fingerprint(req)
    req_json = json.dumps(req, sort_keys=True, separators=(",", ":"))
    db = _database(settings)
    now = time.time()
    with _connect(db) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM sources WHERE query_id=?", (qid,)).fetchone()
        if row and row[2] in ("ARCHIVED", "NO_DATA_EXPLICIT"):
            return _unpack(settings, row, req)
        if row and row[2] == "IN_FLIGHT" and now - row[3] < ACTIVE_LEASE_SECONDS:
            raise OnDemandSourceError("SAME_EXACT_QUERY_ALREADY_IN_FLIGHT")
        if row is None:
            con.execute(
                "INSERT INTO sources (query_id,request_json,state,touched) VALUES (?,?,?,?)",
                (qid, req_json, "IN_FLIGHT", now),
            )
        else:
            if row[1] != req_json:
                raise OnDemandSourceError("EXACT_QUERY_IDENTITY_COLLISION")
            con.execute(
                "UPDATE sources SET state='IN_FLIGHT',touched=? WHERE query_id=?",
                (now, qid),
            )

    try:
        fetch = provider_call or (lambda name, values: getattr(theta, name)(**values))
        response = fetch(method, dict(req["kwargs"]))
        if not isinstance(response, theta.ThetaDataResponse):
            raise OnDemandSourceError("PROVIDER_RESPONSE_NOT_TYPED")
        raw = response.raw_body
        rows = response.rows
        if (response.http_status != 200 or not isinstance(rows, tuple)
                or len(rows) > MAX_SOURCE_ROWS
                or not isinstance(raw, bytes)
                or not 0 < len(raw) <= MAX_RAW_BYTES
                or theta._canonical_bytes(rows) != raw
                or response.response_bytes != len(raw)):
            raise OnDemandSourceError("PROVIDER_SOURCE_CANONICAL_OR_SIZE_UNQUALIFIED")
        if response.explicit_no_data:
            if rows:
                raise OnDemandSourceError("PROVIDER_NO_DATA_WITH_ROWS")
            # A zero-row source is only cached as no-data when explicitly
            # certified by the worker's no-data evidence.
            with _connect(db) as con:
                con.execute(
                    "UPDATE sources SET state='NO_DATA_EXPLICIT',touched=?,source_rows=0 "
                    "WHERE query_id=? AND state='IN_FLIGHT'",
                    (time.time(), qid),
                )
            return _result(qid, req, (), "FETCHED_EXPLICIT_NO_DATA", None)
        if not rows:
            raise OnDemandSourceError("EMPTY_UNQUALIFIED_PROVIDER_RESPONSE")
        packed = gzip.compress(raw, compresslevel=9, mtime=0)
        options = settings.resolved_path("data/options")
        if shutil.disk_usage(options).free < MIN_FREE_STORAGE_BYTES + len(packed) + 32768:
            raise OnDemandSourceError("PHYSICAL_STORAGE_HEADROOM_UNAVAILABLE")
        rel = f"{ARCHIVE_REL}/{qid[:2]}/{qid}_{_digest(raw)}.json.gz"
        path = settings.resolved_path(rel)
        if path.is_symlink():
            raise OnDemandSourceError("ARCHIVE_LINK_UNSAFE")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if not path.is_file() or _digest(path.read_bytes()) != _digest(packed):
                raise OnDemandSourceError("IMMUTABLE_EXISTING_ARCHIVE_DISAGREES")
        else:
            try:
                with path.open("xb") as out:
                    out.write(packed)
                    out.flush()
                    os.fsync(out.fileno())
            except FileExistsError:
                if not path.is_file() or _digest(path.read_bytes()) != _digest(packed):
                    raise OnDemandSourceError("CONCURRENT_ARCHIVE_DISAGREES")
        with _connect(db) as con:
            cursor = con.execute(
                "UPDATE sources SET state='ARCHIVED',touched=?,source_sha=?,gzip_sha=?,"
                "stored_path=?,source_rows=? WHERE query_id=? AND state='IN_FLIGHT'",
                (time.time(), _digest(raw), _digest(packed), rel, len(rows), qid),
            )
            if cursor.rowcount != 1:
                raise OnDemandSourceError("SOURCE_RESERVATION_LOST")
        return _result(qid, req, rows, "FETCHED_AND_ARCHIVED", _digest(raw))
    except Exception:
        with _connect(db) as con:
            con.execute(
                "UPDATE sources SET state='FAILED_RETRYABLE',touched=? "
                "WHERE query_id=? AND state='IN_FLIGHT'", (time.time(), qid),
            )
        raise
