from __future__ import annotations

"""V19 frozen-SPY-pilot post-entry EXIT source acquisition, NOT backtesting.

The frozen 411 weekly SPY at-time entry identities generate 2,055 future
five-session review uses. Exactly 1,570 distinct exact provider query IDs
are outside those original 411 scopes. A matching original entry query
(including the separately retained 2025-06-09 identity) is REUSED, never
recopied, redownloaded, or falsely certified as a completed fill.

--run is an explicit acquisition action; offline preview is read-only.
A coordinator serially writes immutable per-query pre-dispatch receipts and
full-original lossless gzip archives, while 1-4 provider subprocesses may
fetch distinct query IDs concurrently. A crash or ambiguous provider result
can never silently retry the same identity. All quotes remain diagnostics
only: no provider-chain completeness, native fills or simulated returns.
"""

from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import date, datetime
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo
import zlib

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_at_time_one_call_v1 import (
    PINNED_MANIFEST_FINGERPRINT, _load_full_manifest,
)
from packages.data.hybrid_options_at_time_source_gate_v1 import (
    MAX_RESPONSE_BYTES, MAX_ROWS, REQUIRED_FIELDS,
)
from packages.data.hybrid_options_lossless_archive_v1 import _write_immutable
from packages.data.hybrid_options_unattended_campaign_v1 import (
    MIN_CAPACITY_PER_REQUEST, _safe_storage,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    EXPECTED_ALL_AT_TIME, EXPECTED_ENTRIES, SPY_ORIGIN,
    _exit_at_time_query, _exit_review_sessions,
)
from packages.data.research_storage import inspect_research_storage
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    _finite_number, _nonnegative_int, _symbol_matches_underlying,
    _validate_provider_provenance,
)
from packages.providers.thetadata.client import (
    ThetaDataResponse, _canonical_bytes, option_at_time_quote_surface,
)
from packages.strategies.options_native_pilot_v1_contract import (
    SPECIFICATION_FINGERPRINT,
)

CONTRACT = "atlas-spy-native-five-session-exit-original-source-campaign-v19"
ROOT_REL = "data/options/hybrid/spy_native_exit_source_campaign_v19"
EASTERN = ZoneInfo("America/New_York")
EXPECTED_EXIT_USES = 2055
EXPECTED_NEW_SCOPES = 1570
MAX_WORKERS = 4
MAX_RECEIPT_BYTES = 16 * 1024
MAX_ARCHIVE_BYTES = MAX_RESPONSE_BYTES + 4096
TERMINAL_STATES = frozenset({
    "RAW_ARCHIVED_SCOPE_DIAGNOSTIC", "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC",
    "RAW_ARCHIVED_INVALID_SCHEMA", "EXPLICIT_NO_DATA_SOURCE_ONLY",
    "EMPTY_RESPONSE_SOURCE_ONLY", "PROVIDER_OR_STORAGE_ERROR_NO_RETRY",
})


class SpyExitSourceError(ValueError):
    pass


def _demand(manifest: dict[str, Any]) -> dict[str, Any]:
    """Derive every exact exit ID from frozen pilot; never inspect returns."""
    if (manifest.get("source_request_count") != EXPECTED_ALL_AT_TIME
            or manifest.get("manifest_fingerprint") != PINNED_MANIFEST_FINGERPRINT):
        raise SpyExitSourceError("V9_ORIGINAL_MANIFEST_DRIFT")
    spy = [r for r in manifest["requests"] if r["origin"] == SPY_ORIGIN]
    originals = {r["query_id"] for r in spy}
    if len(spy) != EXPECTED_ENTRIES or len(originals) != EXPECTED_ENTRIES:
        raise SpyExitSourceError("FROZEN_411_ENTRY_SCOPE_DRIFT")
    exit_queries: dict[str, dict[str, Any]] = {}
    uses = 0
    for entry in spy:
        for day in _exit_review_sessions(date.fromisoformat(entry["date_et"])):
            req = _exit_at_time_query(day)
            exit_queries[req["query_id"]] = req
            uses += 1
    if uses != EXPECTED_EXIT_USES:
        raise SpyExitSourceError("FIVE_SESSION_EXIT_USES_DRIFT")
    reused = sorted(set(exit_queries) & originals)
    missing = sorted(
        (q for qid, q in exit_queries.items() if qid not in originals),
        key=lambda r: (r["session_et"], r["query_id"]),
    )
    if len(missing) != EXPECTED_NEW_SCOPES or len(reused) + len(missing) != len(exit_queries):
        raise SpyExitSourceError("DISTINCT_EXIT_SCOPE_CENSUS_DRIFT")
    for req in missing:
        _sdk_request(req)
    body = {
        "contract": CONTRACT,
        "frozen_manifest_fingerprint": PINNED_MANIFEST_FINGERPRINT,
        "pilot_specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "exit_review_uses": uses,
        "reused_original_entry_queries": len(reused),
        "additional_distinct_exit_requests": len(missing),
        "new_query_ids": [r["query_id"] for r in missing],
    }
    return {
        "plan_fingerprint": _fingerprint(body),
        "requests": missing,
        "reused_original_entry_queries": len(reused),
        "exit_review_uses": uses,
    }


def _sdk_request(req: dict[str, Any]) -> dict[str, Any]:
    params = req["params"]
    stamp = date.fromisoformat(req["session_et"]).strftime("%Y%m%d")
    if (req["query_id"] != _fingerprint({
            "provider": "thetadata",
            "endpoint": req["endpoint"], "params": params,
        })
            or req["source_role"] != "POST_ENTRY_MARK_REVIEW_NOT_FILL"
            or req["source_complete"] is not False
            or req["simulator_ready"] is not False
            or req["provider_requests"] != 0
            or req["endpoint"] != "/v3/option/at_time/quote"
            or params != {
                "symbol": "SPY", "expiration": "*", "strike": "*",
                "right": "both", "start_date": stamp, "end_date": stamp,
                "time_of_day": "10:00:00.000", "max_dte": 45,
                "strike_range": 2, "format": "json",
            }):
        raise SpyExitSourceError("EXIT_EXACT_PROVIDER_SCOPE_DRIFT")
    return {
        "symbol": "SPY", "date_et": req["session_et"],
        "time_of_day_et": "10:00:00.000",
        "right": "both", "max_dte": 45, "strike_range": 2,
    }


def _path(settings: AtlasSettings, qid: str, kind: str) -> Path:
    return settings.resolved_path(ROOT_REL) / kind / qid[:2] / (
        qid + (".json.gz" if kind == "sources" else ".json")
    )


def _receipt(settings: AtlasSettings, req: dict[str, Any],
             plan_fp: str, kind: str) -> dict[str, Any] | None:
    qid = req["query_id"]
    path = _path(settings, qid, kind)
    if path.is_symlink() or path.parent.is_symlink():
        raise SpyExitSourceError("EXIT_RECEIPT_SYMLINK_FORBIDDEN")
    if not path.exists():
        return None
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_RECEIPT_BYTES:
        raise SpyExitSourceError("EXIT_RECEIPT_SIZE_OR_TYPE")
    try:
        value = json.loads(path.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise SpyExitSourceError("EXIT_RECEIPT_INVALID_JSON") from exc
    if (not isinstance(value, dict)
            or value.get("contract") != CONTRACT
            or value.get("kind") != kind
            or value.get("query_id") != qid
            or value.get("session_et") != req["session_et"]
            or value.get("plan_fingerprint") != plan_fp
            or value.get("simulator_ready") is not False
            or value.get("source_complete") is not False
            or value.get("fingerprint") != _fingerprint({
                k: v for k, v in value.items() if k != "fingerprint"
            })):
        raise SpyExitSourceError("EXIT_RECEIPT_IDENTITY_OR_FINGERPRINT_DRIFT")
    if kind == "started":
        if value.get("state") != "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY":
            raise SpyExitSourceError("EXIT_STARTED_STATE_CHANGED")
    elif value.get("state") not in TERMINAL_STATES:
        raise SpyExitSourceError("EXIT_TERMINAL_STATE_CHANGED")
    return value


def _write_receipt(settings: AtlasSettings, req: dict[str, Any],
                   plan_fp: str, kind: str, data: dict[str, Any]) -> None:
    path = _path(settings, req["query_id"], kind)
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise SpyExitSourceError("EXIT_IMMUTABLE_RECEIPT_COLLISION")
    raw = (json.dumps(data, sort_keys=True, indent=2, allow_nan=False)
           + "\n").encode()
    if not 0 < len(raw) <= MAX_RECEIPT_BYTES:
        raise SpyExitSourceError("EXIT_RECEIPT_EXCEEDS_MAXIMUM")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_immutable(path, raw)
    if _receipt(settings, req, plan_fp, kind) != data:
        raise SpyExitSourceError("EXIT_RECEIPT_POSTWRITE_DRIFT")


def _verify_source(settings: AtlasSettings, qid: str,
                   archive: dict[str, Any]) -> None:
    path = _path(settings, qid, "sources")
    if (path.is_symlink() or path.parent.is_symlink()
            or not path.is_file()
            or not 0 < path.stat().st_size <= MAX_ARCHIVE_BYTES
            or path.stat().st_size != archive["compressed_bytes"]
            or not 0 < archive["original_bytes"] <= MAX_RESPONSE_BYTES):
        raise SpyExitSourceError("EXIT_ARCHIVE_SIZE_OR_PATH_DRIFT")
    packed = path.read_bytes()
    if hashlib.sha256(packed).hexdigest() != archive["compressed_sha256"]:
        raise SpyExitSourceError("EXIT_COMPRESSED_SOURCE_SHA_DRIFT")
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        raw = decoder.decompress(packed, MAX_RESPONSE_BYTES + 1)
    except zlib.error as exc:
        raise SpyExitSourceError("EXIT_SOURCE_GZIP_INVALID") from exc
    if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
            or len(raw) != archive["original_bytes"]
            or hashlib.sha256(raw).hexdigest() != archive["original_sha256"]):
        raise SpyExitSourceError("EXIT_SOURCE_LOSSLESS_HASH_DRIFT")
    try:
        rows = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise SpyExitSourceError("EXIT_SOURCE_NOT_CANONICAL_JSON") from exc
    if (not isinstance(rows, list)
            or len(rows) != archive["observed_rows"]
            or any(not isinstance(r, dict) for r in rows)
            or _canonical_bytes(rows) != raw):
        raise SpyExitSourceError("EXIT_ORIGINAL_CANONICAL_SOURCE_DRIFT")


def _state(settings: AtlasSettings, req: dict[str, Any], fp: str) -> str:
    started = _receipt(settings, req, fp, "started")
    terminal = _receipt(settings, req, fp, "terminal")
    if terminal is not None and (
        started is None or terminal["started_fingerprint"] != started["fingerprint"]
    ):
        raise SpyExitSourceError("EXIT_TERMINAL_WITHOUT_MATCHED_START")
    if started is None:
        return "UNATTEMPTED"
    if terminal is None:
        return "UNCERTAIN_PRIOR_ATTEMPT_NO_RETRY"
    source = terminal.get("archive")
    if terminal["state"].startswith("RAW_ARCHIVED"):
        if not isinstance(source, dict):
            raise SpyExitSourceError("EXIT_TERMINAL_MISSING_SOURCE")
        _verify_source(settings, req["query_id"], source)
    elif source is not None:
        raise SpyExitSourceError("EXIT_NONSOURCE_TERMINAL_HAS_ARCHIVE")
    return terminal["state"]


def _save_original(settings: AtlasSettings, req: dict[str, Any],
                   response: ThetaDataResponse) -> dict[str, Any]:
    if (not isinstance(response, ThetaDataResponse)
            or response.response_bytes != len(response.raw_body)
            or not 0 < len(response.raw_body) <= MAX_RESPONSE_BYTES
            or _canonical_bytes(response.rows) != response.raw_body):
        raise SpyExitSourceError("EXIT_SOURCE_CANONICAL_RECEIPT_INVALID")
    packed = gzip.compress(response.raw_body, compresslevel=9, mtime=0)
    path = _path(settings, req["query_id"], "sources")
    if (path.exists() or path.is_symlink() or path.parent.is_symlink()
            or not 0 < len(packed) <= MAX_ARCHIVE_BYTES):
        raise SpyExitSourceError("EXIT_ARCHIVE_ALREADY_PRESENT_OR_OVERSIZE")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_immutable(path, packed)
    archive = {
        "original_sha256": hashlib.sha256(response.raw_body).hexdigest(),
        "compressed_sha256": hashlib.sha256(packed).hexdigest(),
        "original_bytes": len(response.raw_body),
        "compressed_bytes": len(packed),
        "observed_rows": len(response.rows),
        "source_complete": False, "simulator_ready": False,
    }
    _verify_source(settings, req["query_id"], archive)
    return archive


def _diagnose(req: dict[str, Any], response: ThetaDataResponse) -> str:
    """Strict source schema/clock validation; out-of-DTE is diagnostic."""
    _validate_provider_provenance(response)
    if (response.http_status != 200 or len(response.rows) > MAX_ROWS
            or response.response_bytes != len(response.raw_body)
            or _canonical_bytes(response.rows) != response.raw_body):
        raise SpyExitSourceError("EXIT_PROVIDER_BODY_OR_PROVENANCE_INVALID")
    if response.explicit_no_data and response.rows:
        raise SpyExitSourceError("EXIT_CONTRADICTORY_NO_DATA")
    if not response.rows:
        return ("EXPLICIT_NO_DATA_SOURCE_ONLY" if response.explicit_no_data
                else "EMPTY_RESPONSE_SOURCE_ONLY")
    day = date.fromisoformat(req["session_et"])
    clock = datetime.combine(day, datetime.strptime(
        "10:00:00.000", "%H:%M:%S.%f").time(), EASTERN)
    seen = set()
    out_dte = False
    for quote in response.rows:
        if not isinstance(quote, dict) or any(
            key not in quote for key in REQUIRED_FIELDS
        ):
            raise SpyExitSourceError("EXIT_QUOTE_REQUIRED_FIELD_MISSING")
        if not _symbol_matches_underlying(str(quote["symbol"]), "SPY"):
            raise SpyExitSourceError("EXIT_OPTION_SYMBOL_OUTSIDE_SCOPE")
        expiry = date.fromisoformat(str(quote["expiration"])[:10])
        dte = (expiry - day).days
        if dte < 0:
            raise SpyExitSourceError("EXIT_QUOTE_EXPIRED_BEFORE_REVIEW")
        right = str(quote["right"]).lower()
        strike = _finite_number(quote["strike"], "strike")
        if right not in {"call", "put"} or strike <= 0:
            raise SpyExitSourceError("EXIT_RIGHT_OR_STRIKE_DRIFT")
        key = (expiry.isoformat(), strike, right)
        if key in seen:
            raise SpyExitSourceError("EXIT_DUPLICATE_CONTRACT")
        seen.add(key)
        stamp = datetime.fromisoformat(
            str(quote["timestamp"]).replace("Z", "+00:00")
        )
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise SpyExitSourceError("EXIT_QUOTE_TIMESTAMP_NAIVE")
        et = stamp.astimezone(EASTERN)
        if et.date() != day or et > clock:
            raise SpyExitSourceError("EXIT_QUOTE_ESCAPES_REVIEW_CLOCK")
        bid = _finite_number(quote["bid"], "bid")
        ask = _finite_number(quote["ask"], "ask")
        if bid > 0 and ask > 0 and ask < bid:
            raise SpyExitSourceError("EXIT_QUOTE_POSITIVE_CROSSED")
        for field in (
            "bid_size", "ask_size", "bid_exchange", "ask_exchange",
            "bid_condition", "ask_condition",
        ):
            _nonnegative_int(quote[field], field)
        if dte > 45:
            out_dte = True
    return ("RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC" if out_dte
            else "RAW_ARCHIVED_SCOPE_DIAGNOSTIC")


def _evidence(data: dict[str, Any]) -> dict[str, Any]:
    return dict(data, fingerprint=_fingerprint(data))


def preview_exit_campaign(
    settings: AtlasSettings, manifest_path: Path, candidate_plan: Path,
    *, storage_reader: Callable[..., Any] = inspect_research_storage,
) -> dict[str, Any]:
    settings.assert_external_storage_binding("options")
    plan = _demand(_load_full_manifest(settings, manifest_path, candidate_plan))
    states = Counter()
    for req in plan["requests"]:
        states[_state(settings, req, plan["plan_fingerprint"])] += 1
    available = _safe_storage(settings, storage_reader)
    result = {
        "contract": CONTRACT, "mode": "EXIT_SOURCE_OFFLINE_PREVIEW",
        "plan_fingerprint": plan["plan_fingerprint"],
        "exit_review_uses": plan["exit_review_uses"],
        "reused_original_entry_queries": plan["reused_original_entry_queries"],
        "additional_distinct_exit_requests": len(plan["requests"]),
        "exit_source_states": dict(sorted(states.items())),
        "remaining_unattempted": states["UNATTEMPTED"],
        "shared_storage_safe": available["safe"],
        "safe_available_bytes": available["available_after_hourly_reservations"],
        "provider_requests": 0, "simulator_ready": False,
        "source_complete": False,
    }
    result["fingerprint"] = _fingerprint(result)
    return result


def run_exit_campaign(
    settings: AtlasSettings, manifest_path: Path, candidate_plan: Path,
    *, workers: int = 4,
    max_calls: int | None = None,
    reader: Callable[..., ThetaDataResponse] = option_at_time_quote_surface,
    storage_reader: Callable[..., Any] = inspect_research_storage,
    progress: Callable[[dict[str, Any]], None] | None = None,
    progress_every: int = 50,
) -> dict[str, Any]:
    if type(workers) is not int or not 1 <= workers <= MAX_WORKERS:
        raise SpyExitSourceError("EXIT_WORKER_COUNT_OUTSIDE_STANDARD_1_TO_4")
    if (max_calls is not None
            and (type(max_calls) is not int or max_calls <= 0)):
        raise SpyExitSourceError("EXIT_MAX_CALLS_INVALID")
    if type(progress_every) is not int or progress_every < 1:
        raise SpyExitSourceError("EXIT_PROGRESS_FREQUENCY_INVALID")
    before = preview_exit_campaign(
        settings, manifest_path, candidate_plan, storage_reader=storage_reader,
    )
    plan = _demand(_load_full_manifest(settings, manifest_path, candidate_plan))
    result = {
        "contract": CONTRACT, "mode": "EXIT_SOURCE_UNATTENDED_ACQUISITION",
        "plan_fingerprint": plan["plan_fingerprint"],
        "workers": workers, "provider_calls_this_run": 0,
        "completed_provider_calls_this_run": 0, "archives_this_run": 0,
        "outside_dte_archives_this_run": 0,
        "invalid_archives_this_run": 0,
        "stop_reason": "ALL_NEW_EXIT_SCOPES_SCANNED",
        "simulator_ready": False, "source_complete": False,
    }
    if not before["shared_storage_safe"]:
        result["stop_reason"] = "SHARED_STORAGE_HEADROOM_INSUFFICIENT"
        return result
    eligible = [
        req for req in plan["requests"]
        if _state(settings, req, plan["plan_fingerprint"]) == "UNATTEMPTED"
    ]
    cursor = 0
    stop_new = False
    pending: dict[Future, tuple[dict[str, Any], dict[str, Any]]] = {}
    with ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix="atlas-native-exit-source",
    ) as pool:
        while cursor < len(eligible) or pending:
            while (not stop_new and cursor < len(eligible)
                   and len(pending) < workers
                   and (max_calls is None
                        or result["provider_calls_this_run"] < max_calls)):
                safe = _safe_storage(settings, storage_reader)
                required = MIN_CAPACITY_PER_REQUEST * (len(pending) + 1)
                if (not safe["safe"]
                        or safe["available_after_hourly_reservations"] < required):
                    result["stop_reason"] = "SHARED_STORAGE_HEADROOM_INSUFFICIENT"
                    stop_new = True
                    break
                req = eligible[cursor]
                started = _evidence({
                    "contract": CONTRACT, "kind": "started",
                    "plan_fingerprint": plan["plan_fingerprint"],
                    "session_et": req["session_et"], "query_id": req["query_id"],
                    "sdk_kwargs": _sdk_request(req),
                    "state": "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY",
                    "source_complete": False, "simulator_ready": False,
                })
                _write_receipt(
                    settings, req, plan["plan_fingerprint"], "started", started,
                )
                result["provider_calls_this_run"] += 1
                future = pool.submit(reader, **_sdk_request(req))
                pending[future] = (req, started)
                cursor += 1
            if (not stop_new and cursor < len(eligible)
                    and max_calls is not None
                    and result["provider_calls_this_run"] >= max_calls):
                result["stop_reason"] = "OPTIONAL_GLOBAL_CALL_LIMIT_REACHED"
                stop_new = True
            if not pending:
                break
            done, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for future in sorted(done, key=lambda f: pending[f][0]["session_et"]):
                req, started = pending.pop(future)
                state = "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
                archive = None
                error_type = None
                try:
                    response = future.result()
                    if not isinstance(response, ThetaDataResponse):
                        raise SpyExitSourceError("EXIT_RESPONSE_TYPE_CHANGED")
                    if response.rows:
                        archive = _save_original(settings, req, response)
                    try:
                        state = _diagnose(req, response)
                    except Exception as exc:
                        error_type = type(exc).__name__
                        if archive is not None:
                            state = "RAW_ARCHIVED_INVALID_SCHEMA"
                except Exception as exc:
                    error_type = type(exc).__name__
                    if archive is not None:
                        state = "RAW_ARCHIVED_INVALID_SCHEMA"
                terminal = _evidence({
                    "contract": CONTRACT, "kind": "terminal",
                    "plan_fingerprint": plan["plan_fingerprint"],
                    "session_et": req["session_et"], "query_id": req["query_id"],
                    "started_fingerprint": started["fingerprint"],
                    "archive": archive, "state": state,
                    "error_type": error_type,
                    "source_complete": False, "simulator_ready": False,
                })
                _write_receipt(
                    settings, req, plan["plan_fingerprint"], "terminal", terminal,
                )
                result["completed_provider_calls_this_run"] += 1
                if archive is not None:
                    result["archives_this_run"] += 1
                if state == "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC":
                    result["outside_dte_archives_this_run"] += 1
                if state == "RAW_ARCHIVED_INVALID_SCHEMA":
                    result["invalid_archives_this_run"] += 1
                count = result["completed_provider_calls_this_run"]
                if progress is not None and (
                    count % progress_every == 0
                    or state == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
                    or (max_calls is not None and count == max_calls)
                ):
                    progress({
                        "calls": count, "archived": result["archives_this_run"],
                        "over_dte": result["outside_dte_archives_this_run"],
                        "date_et": req["session_et"], "query_id": req["query_id"],
                        "state": state, "simulator_ready": False,
                    })
                if state == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY":
                    result["stop_reason"] = "PROVIDER_OR_STORAGE_FAILURE_STOP"
                    stop_new = True
    return result
