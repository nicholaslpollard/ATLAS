from __future__ import annotations

"""V30 bounded, immutable and resumable EXACT SPY option exit-source recovery.

Only frozen V29 physical-spot provisional one-pair/week selected demand.
No all-strikes campaigns, no original archive replacement, no broker calls,
no current/protected 2026 outcomes, and NO simulator fill or account authority.

PREVIEW is zero-provider. Paid run: one shared SDK authentication before any
started receipt; up to four exact contract/right quote requests per batch,
started identity written before dispatch, per-query immutable raw gzip and
terminal receipts. Ambiguous prior attempts and terminal failures NEVER retry.
"""

from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import gzip
import hashlib
import json
import re
import zlib
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_lossless_archive_v1 import _write_immutable
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_exit_source_campaign_v1 import (
    _ConservativeExitStorageMeter,
)
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    REQUIRED_FIELDS, _finite_number, _nonnegative_int,
    _symbol_matches_underlying, _validate_provider_provenance,
)
from packages.data.options_native_spy_development_clock_coverage_v1 import frozen_clock_demand
from packages.data.options_native_pilot_accelerated_readiness_v1 import (
    _exit_at_time_query, _exit_review_sessions,
)
from packages.data.options_native_spy_physical_spot_exact_demand_v29 import (
    CONTRACT as V29_CONTRACT, SOURCE_PREVIEW, MAX_MISSING_RIGHT_QUERIES,
)
from packages.data.options_native_original_pair_diagnostic_v26 import _decimal
from packages.data.research_storage import inspect_research_storage
from packages.providers.thetadata.client import (
    ThetaDataResponse, ThetaDataError, _canonical_bytes,
    establish_option_quote_shared_authenticated_session,
    option_at_time_quote_exact_shared_session_batch,
)

CONTRACT = "atlas-spy-exact-contract-shared-session-source-campaign-v30"
ROOT_REL = "data/options/hybrid/spy_exact_exit_source_campaign_v30"
MAX_RAW = 16 * 1024 * 1024
MAX_ARCHIVE = MAX_RAW + 4096
MAX_RECEIPT = 32 * 1024
MAX_INVALID_ARCHIVES_PER_RUN = 4
MAX_PROVIDER_FAULTS_PER_RUN = 4
MAX_WORKERS = 4
EASTERN = ZoneInfo("America/New_York")
TERMINAL = {
    "RAW_ARCHIVED_EXACT_CONTRACT_DIAGNOSTIC",
    "RAW_ARCHIVED_INVALID_OR_UNMATCHED_CONTRACT",
    "EXPLICIT_NO_DATA_SOURCE_ONLY",
    "EMPTY_RESPONSE_UNQUALIFIED",
    "PROVIDER_OR_STORAGE_ERROR_NO_RETRY",
}


class ExactExitSourceError(ValueError):
    pass


# The existing V29 CLI uses audit_original_spy_pair_observations (V26) as
# its SHA/provenance-verified original-source reader. That wrapper accepts
# V29's inner report WITH its own fingerprint, adds V26 metadata, hashes
# the entire compound object, and replaces the public fingerprint with
# the resulting outer hash. The published immutable V29 artifact therefore
# correctly has a two-layer fingerprint, not a single hash of visible keys.
# Reconstruct BOTH hashes rather than asking the user to modify or rerun it.
V26_WRAPPER_FIELDS = frozenset({
    "original_411_entry_plan", "distinct_new_exit_request_plan",
    "observed_source_identities_loaded", "source_plan_fingerprint",
    "note", "pricing", "fee_grid_is_model_assumption",
    "simulations_run", "account_pnl_reported",
    "historical_execution_qualified", "protected_outcomes_read",
    "strategy_promotion",
})


def _verify_v29_wrapped_fingerprint(plan: dict[str, Any]) -> bool:
    """Verify the exact immutable V29-on-V26 report hashing convention."""
    if (plan.get("original_411_entry_plan") != 411
            or plan.get("distinct_new_exit_request_plan") != 1570
            or plan.get("simulations_run") != 0
            or plan.get("account_pnl_reported") is not False
            or plan.get("historical_execution_qualified") is not False
            or plan.get("protected_outcomes_read") != 0
            or plan.get("strategy_promotion") is not False):
        return False
    outer = {key: value for key, value in plan.items() if key != "fingerprint"}
    inner = {
        key: value for key, value in outer.items()
        if key not in V26_WRAPPER_FIELDS
    }
    # The wrapper's four overlapping keys (contract, status, provider/broker
    # requests) are deliberately retained because V29's values supersede
    # the V26 defaults in **values.
    inner_fingerprint = _fingerprint(inner)
    return plan.get("fingerprint") == _fingerprint({
        **outer, "fingerprint": inner_fingerprint,
    })


def load_exact_exit_plan(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= 8 * 1024 * 1024:
        raise ExactExitSourceError("V30_V29_PLAN_PATH_OR_SIZE_INVALID")
    def disallow_constants(value: str):
        raise ExactExitSourceError("V30_V29_PLAN_NONFINITE_JSON")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"), parse_constant=disallow_constants)
    except (UnicodeError, ValueError) as exc:
        raise ExactExitSourceError("V30_V29_PLAN_UNREADABLE") from exc
    if (not isinstance(plan, dict)
            or plan.get("contract") != V29_CONTRACT
            or plan.get("original_entry_clocks") != 411
            or plan.get("source_quote_selection_used_future_prices") is not False
            or plan.get("entry_physical_spot_historical_availability_qualified") is not False
            or plan.get("historical_options_fill_authority") is not False
            or plan.get("provider_requests") != 0
            or plan.get("broker_requests") != 0
            or plan.get("protected_2026_outcomes_read") != 0
            or not _verify_v29_wrapped_fingerprint(plan)):
        raise ExactExitSourceError("V30_V29_FROZEN_PLAN_FINGERPRINT_OR_SCOPE_DRIFT")
    requests = plan.get("missing_exact_contract_right_requests")
    cases = plan.get("cases")
    if (not isinstance(requests, list)
            or not isinstance(cases, list) or len(cases) != 411
            or not 0 <= len(requests) <= MAX_MISSING_RIGHT_QUERIES
            or plan.get("missing_exact_contract_right_request_count") != len(requests)):
        raise ExactExitSourceError("V30_V29_REQUEST_COUNT_OR_CASE_SCHEMA_DRIFT")
    original_case = {}
    for case in cases:
        if not isinstance(case, dict) or case.get("date_et") in original_case:
            raise ExactExitSourceError("V30_CASE_IDENTITY_DUPLICATE")
        original_case[case["date_et"]] = case
    frozen, _ = frozen_clock_demand()
    expected_days = {case["decision_date"] for case in frozen["cases"]}
    if len(original_case) != 411 or set(original_case) != expected_days:
        raise ExactExitSourceError("V30_WEEKLY_CASES_NOT_IN_ORIGINAL_SPY_PLAN")
    seen = set()
    for row in requests:
        if (not isinstance(row, dict)
                or row.get("request_state") != SOURCE_PREVIEW
                or row.get("sdk_method") != "option_at_time_quote"
                or row.get("entry_spot_unqualified") is not True
                or row.get("source_response_absence_not_market_absence") is not True
                or type(row.get("hold_sessions")) is not int
                or not 1 <= row["hold_sessions"] <= 5
                or not isinstance(row.get("source_original_exit_query_id"), str)
                or len(row["source_original_exit_query_id"]) != 64):
            raise ExactExitSourceError("V30_REQUEST_ORIGINAL_EVIDENCE_DRIFT")
        q = row.get("sdk_kwargs")
        if (not isinstance(q, dict) or set(q) != {
            "symbol", "date_et", "time_of_day_et", "expiration", "strike", "right",
        } or q["symbol"] != "SPY" or q["right"] not in {"call", "put"}
                or q["time_of_day_et"] != "10:00:00.000"
                or type(q["strike"]) is not str
                or re.fullmatch(r"[0-9]+(?:\.[0-9]{1,3})?", q["strike"]) is None):
            raise ExactExitSourceError("V30_EXACT_SDK_KWARGS_DRIFT")
        try:
            day = date.fromisoformat(q["date_et"])
            expiry = date.fromisoformat(q["expiration"])
        except (ValueError, TypeError) as exc:
            raise ExactExitSourceError("V30_INVALID_EXACT_REQUEST_DATE") from exc
        if (day > date(2025, 12, 31) or expiry < day
                or _decimal(q["strike"]) <= 0
                or row.get("query_id") != _fingerprint({
                    "provider": "thetadata", "method": "option_at_time_quote",
                    "kwargs": q,
                })
                or row["query_id"] in seen):
            raise ExactExitSourceError("V30_EXACT_REQUEST_IDENTITY_OR_2026_DRIFT")
        seen.add(row["query_id"])
        case = original_case.get(row.get("case_date"))
        if (case is None or case.get("status") != "PHYSICAL_SPOT_PROVISIONAL_PAIR_ONLY"
                or case.get("selected_expiration") != q["expiration"]
                or case.get("selected_strike") != q["strike"]):
            raise ExactExitSourceError("V30_NOT_SELECTED_ENTRY_PAIR")
        reviews = case.get("review_results")
        if not isinstance(reviews, list):
            raise ExactExitSourceError("V30_REVIEW_CHAIN_MISSING")
        matches = [x for x in reviews if x.get("hold_sessions") == row["hold_sessions"]]
        expected_review_day = _exit_review_sessions(
            date.fromisoformat(row["case_date"])
        )[row["hold_sessions"] - 1]
        expected_original = _exit_at_time_query(expected_review_day)["query_id"]
        if (len(matches) != 1
                or matches[0]["session_et"] != q["date_et"]
                or q["date_et"] != expected_review_day.isoformat()
                or row["source_original_exit_query_id"] != expected_original
                or q["right"] not in matches[0]["missing_exact_rights"]):
            raise ExactExitSourceError("V30_REVIEW_ORIGINAL_ABSENCE_NOT_SUPPORTED")
    return plan


def _path(settings: AtlasSettings, qid: str, kind: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", qid) or kind not in {"started", "terminal", "sources"}:
        raise ExactExitSourceError("V30_BAD_QUERY_PATH_IDENTITY")
    name = qid + (".json.gz" if kind == "sources" else "." + kind + ".json")
    return settings.resolved_path(ROOT_REL) / kind / qid[:2] / name


def _read_receipt(settings: AtlasSettings, row: dict, fp: str, kind: str) -> dict | None:
    path = _path(settings, row["query_id"], kind)
    if path.is_symlink() or path.parent.is_symlink():
        raise ExactExitSourceError("V30_RECEIPT_SYMLINK_FORBIDDEN")
    if not path.exists():
        return None
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_RECEIPT:
        raise ExactExitSourceError("V30_RECEIPT_SIZE_INVALID")
    try:
        value = json.loads(path.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise ExactExitSourceError("V30_RECEIPT_JSON_INVALID") from exc
    if (not isinstance(value, dict)
            or value.get("contract") != CONTRACT
            or value.get("kind") != kind
            or value.get("query_id") != row["query_id"]
            or value.get("plan_fingerprint") != fp
            or value.get("simulator_ready") is not False
            or value.get("fingerprint") != _fingerprint({
                k: v for k, v in value.items() if k != "fingerprint"
            })):
        raise ExactExitSourceError("V30_RECEIPT_FINGERPRINT_DRIFT")
    return value


def _save_receipt(settings, row, fp, kind, body):
    path = _path(settings, row["query_id"], kind)
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise ExactExitSourceError("V30_IMMUTABLE_RECEIPT_COLLISION")
    content = dict(body)
    content["fingerprint"] = _fingerprint(content)
    raw = (json.dumps(content, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    if len(raw) > MAX_RECEIPT:
        raise ExactExitSourceError("V30_RECEIPT_EXCEEDS_LIMIT")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_immutable(path, raw)
    if _read_receipt(settings, row, fp, kind) != content:
        raise ExactExitSourceError("V30_RECEIPT_POSTWRITE_HASH_FAILED")
    return content


def _verify_source(settings, qid, archive):
    path = _path(settings, qid, "sources")
    if (path.is_symlink() or path.parent.is_symlink()
            or not path.is_file() or not 0 < path.stat().st_size <= MAX_ARCHIVE
            or path.stat().st_size != archive["compressed_bytes"]):
        raise ExactExitSourceError("V30_ARCHIVE_SOURCE_FILE_DRIFT")
    packed = path.read_bytes()
    if hashlib.sha256(packed).hexdigest() != archive["compressed_sha256"]:
        raise ExactExitSourceError("V30_SOURCE_COMPRESSED_SHA_DRIFT")
    z = zlib.decompressobj(16 + zlib.MAX_WBITS)
    raw = z.decompress(packed, MAX_RAW + 1)
    if (not z.eof or z.unconsumed_tail or z.unused_data
            or len(raw) != archive["original_bytes"]
            or hashlib.sha256(raw).hexdigest() != archive["original_sha256"]):
        raise ExactExitSourceError("V30_ARCHIVE_ORIGINAL_SHA_DRIFT")
    if _canonical_bytes(json.loads(raw)) != raw:
        raise ExactExitSourceError("V30_ARCHIVE_CONTENT_IS_NOT_CANONICAL")


def _state(settings: AtlasSettings, row: dict, fp: str) -> str:
    a = _read_receipt(settings, row, fp, "started")
    b = _read_receipt(settings, row, fp, "terminal")
    if b is not None and (a is None or b.get("started_fingerprint") != a["fingerprint"]):
        raise ExactExitSourceError("V30_TERMINAL_WITHOUT_START")
    if a is None:
        return "UNATTEMPTED"
    if b is None:
        return "UNCERTAIN_PREVIOUS_DISPATCH_NO_RETRY"
    state = b.get("state")
    if state not in TERMINAL:
        raise ExactExitSourceError("V30_UNKNOWN_TERMINAL_STATE")
    archived = b.get("archive")
    if state.startswith("RAW_ARCHIVED"):
        if not isinstance(archived, dict):
            raise ExactExitSourceError("V30_ARCHIVED_TERMINAL_WITHOUT_SOURCE")
        _verify_source(settings, row["query_id"], archived)
    elif archived is not None:
        raise ExactExitSourceError("V30_NONARCHIVED_TERMINAL_HAS_SOURCE")
    return state


def preview_exact_exit_campaign(
    settings: AtlasSettings,
    report: dict[str, Any],
) -> dict[str, Any]:
    settings.assert_external_storage_binding("options")
    rows = report["missing_exact_contract_right_requests"]
    states = Counter(_state(settings, r, report["fingerprint"]) for r in rows)
    out = {
        "contract": CONTRACT, "mode": "OFFLINE_SOURCE_RECEIPT_PREVIEW",
        "plan_fingerprint": report["fingerprint"],
        "total_exact_right_requests": len(rows),
        "states": dict(sorted(states.items())),
        "remaining_unattempted": states["UNATTEMPTED"],
        "provider_requests": 0, "broker_requests": 0,
        "simulator_ready": False, "source_promoted": False,
    }
    out["fingerprint"] = _fingerprint(out)
    return out


def _save_original(settings, row, response: ThetaDataResponse):
    if (response.response_bytes != len(response.raw_body)
            or not 0 < response.response_bytes <= MAX_RAW
            or _canonical_bytes(response.rows) != response.raw_body):
        raise ExactExitSourceError("V30_NONCANONICAL_PROVIDER_SOURCE")
    packed = gzip.compress(response.raw_body, compresslevel=9, mtime=0)
    path = _path(settings, row["query_id"], "sources")
    if (path.exists() or path.is_symlink() or path.parent.is_symlink()
            or not 0 < len(packed) <= MAX_ARCHIVE):
        raise ExactExitSourceError("V30_ARCHIVE_ALREADY_EXISTS_OR_OVERSIZE")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_immutable(path, packed)
    archived = {
        "original_sha256": hashlib.sha256(response.raw_body).hexdigest(),
        "compressed_sha256": hashlib.sha256(packed).hexdigest(),
        "original_bytes": len(response.raw_body),
        "compressed_bytes": len(packed),
        "observed_rows": len(response.rows),
        "simulator_ready": False,
        "source_complete": False,
    }
    _verify_source(settings, row["query_id"], archived)
    return archived


def _diagnose(row: dict, response: ThetaDataResponse) -> str:
    _validate_provider_provenance(response)
    if response.http_status != 200:
        raise ExactExitSourceError("V30_NON200_UNEXPECTED")
    if response.explicit_no_data:
        if response.rows:
            raise ExactExitSourceError("V30_CONTRADICTORY_EXPLICIT_NO_DATA")
        return "EXPLICIT_NO_DATA_SOURCE_ONLY"
    if not response.rows:
        return "EMPTY_RESPONSE_UNQUALIFIED"
    q = row["sdk_kwargs"]
    selected = []
    # ThetaData's historical broad responses have returned extra DTE rows
    # despite explicit filters. Preserve ALL original rows in the immutable
    # archive, but qualify only the exact requested right/strike/expiry.
    # Never assume a filtered provider request returned only one identity.
    for source in response.rows:
        if not isinstance(source, dict) or any(
            name not in source
            for name in ("symbol", "expiration", "strike", "right")
        ):
            raise ExactExitSourceError("V30_REQUIRED_CONTRACT_IDENTITY_MISSING")
        if (_symbol_matches_underlying(str(source["symbol"]), "SPY")
                and date.fromisoformat(str(source["expiration"])[:10]) == date.fromisoformat(q["expiration"])
                and _decimal(source["strike"]) == _decimal(q["strike"])
                and str(source["right"]).lower() == q["right"]):
            selected.append(source)
    if len(selected) != 1:
        raise ExactExitSourceError("V30_EXACT_PROVIDER_CONTRACT_MISSING_OR_DUPLICATED")
    src = selected[0]
    if any(k not in src for k in REQUIRED_FIELDS):
        raise ExactExitSourceError("V30_REQUIRED_SOURCE_FIELDS_MISSING")
    timestamp = datetime.fromisoformat(str(src["timestamp"]).replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ExactExitSourceError("V30_SOURCE_QUOTE_TIMESTAMP_NAIVE")
    actual = timestamp.astimezone(EASTERN)
    cutoff = datetime.combine(
        date.fromisoformat(q["date_et"]),
        datetime.strptime("10:00:00.000", "%H:%M:%S.%f").time(), EASTERN,
    )
    if actual.date() != cutoff.date() or actual > cutoff:
        raise ExactExitSourceError("V30_SOURCE_CLOCK_AFTER_FROZEN_REVIEW")
    bid, ask = _decimal(src["bid"]), _decimal(src["ask"])
    if ask > 0 and bid > 0 and ask < bid:
        raise ExactExitSourceError("V30_PROVIDER_CROSSED_QUOTE")
    for name in ("bid_size", "ask_size", "bid_exchange", "ask_exchange",
                 "bid_condition", "ask_condition"):
        _nonnegative_int(src[name], name)
    return "RAW_ARCHIVED_EXACT_CONTRACT_DIAGNOSTIC"


def run_exact_exit_campaign(
    settings: AtlasSettings,
    report: dict[str, Any],
    *,
    max_calls: int | None = None,
    batch_reader: Callable[[list[dict]], list[ThetaDataResponse | ThetaDataError]] = option_at_time_quote_exact_shared_session_batch,
    authenticator: Callable[[], None] = establish_option_quote_shared_authenticated_session,
    meter_factory: Callable[..., Any] = _ConservativeExitStorageMeter,
    storage_reader: Callable[..., Any] = inspect_research_storage,
    progress: Callable[[dict], None] | None = None,
    progress_every: int = 50,
) -> dict[str, Any]:
    if max_calls is not None and (type(max_calls) is not int or max_calls < 1):
        raise ExactExitSourceError("V30_MAX_CALLS_INVALID")
    if type(progress_every) is not int or progress_every < 1:
        raise ExactExitSourceError("V30_PROGRESS_INVALID")
    before = preview_exact_exit_campaign(settings, report)
    rows = [r for r in report["missing_exact_contract_right_requests"]
            if _state(settings, r, report["fingerprint"]) == "UNATTEMPTED"]
    result = {
        "contract": CONTRACT, "mode": "PAID_EXACT_CONTRACT_SHARED_AUTH_SOURCE_ONLY",
        "plan_fingerprint": report["fingerprint"],
        "original_preview_fingerprint": before["fingerprint"],
        "provider_requests_this_run": 0, "archived_this_run": 0,
        "no_data_this_run": 0, "invalid_archives_this_run": 0,
        "provider_failures_this_run": 0, "storage_audits_this_run": 0,
        "stop_reason": "ALL_ELIGIBLE_EXACT_RIGHT_QUERIES_SCANNED",
        "source_only": True, "simulator_ready": False,
        "broker_requests": 0, "protected_2026_outcomes_read": 0,
    }
    if not rows:
        result["remaining"] = 0
        result["states"] = before["states"]
        result["source_promotion"] = False
        result["historical_account_replay"] = False
        return result
    # Authenticate/construct one four-client shared session BEFORE ANY
    # started receipt or paid quote dispatch.
    authenticator()
    meter = meter_factory(settings, storage_reader)
    idx = 0
    stop = False
    while idx < len(rows) and not stop:
        batch = []
        for req in rows[idx: idx + MAX_WORKERS]:
            if max_calls is not None and result["provider_requests_this_run"] + len(batch) >= max_calls:
                result["stop_reason"] = "CALL_LIMIT_REACHED"
                stop = True
                break
            if not meter.allow_next():
                result["stop_reason"] = "SAFE_STORAGE_BUDGET_EXHAUSTED"
                stop = True
                break
            batch.append(req)
        if not batch:
            break
        started = []
        for req in batch:
            origin = {
                "contract": CONTRACT, "kind": "started",
                "plan_fingerprint": report["fingerprint"],
                "query_id": req["query_id"],
                "sdk_kwargs": req["sdk_kwargs"],
                "state": "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY",
                "simulator_ready": False,
            }
            started.append(_save_receipt(
                settings, req, report["fingerprint"], "started", origin,
            ))
        result["provider_requests_this_run"] += len(batch)
        idx += len(batch)
        hard_failure = False
        try:
            received = batch_reader([req["sdk_kwargs"] for req in batch])
            if not isinstance(received, list) or len(received) != len(batch):
                raise ExactExitSourceError("V30_BATCH_RESULT_LENGTH_DRIFT")
        except Exception:
            # Batch transport ambiguity means every STARTED identity is
            # potentially dispatched; leave terminal uncertain and STOP.
            result["stop_reason"] = "AMBIGUOUS_SHARED_BATCH_NO_SAME_QUERY_RETRY"
            stop = True
            break
        for req, started_record, value in zip(batch, started, received, strict=True):
            state, archive, error_type, grpc = (
                "PROVIDER_OR_STORAGE_ERROR_NO_RETRY", None, None, None
            )
            if isinstance(value, ThetaDataResponse):
                try:
                    if value.rows:
                        archive = _save_original(settings, req, value)
                    try:
                        state = _diagnose(req, value)
                    except Exception as exc:
                        error_type = type(exc).__name__
                        if archive is not None:
                            state = "RAW_ARCHIVED_INVALID_OR_UNMATCHED_CONTRACT"
                except Exception as exc:
                    error_type = type(exc).__name__
                    if archive is not None:
                        state = "RAW_ARCHIVED_INVALID_OR_UNMATCHED_CONTRACT"
            elif isinstance(value, ThetaDataError):
                error_type = value.provider_error_type or type(value).__name__
                grpc = value.provider_grpc_status
                if grpc in {
                    "UNAUTHENTICATED", "PERMISSION_DENIED", "RESOURCE_EXHAUSTED",
                    "UNAVAILABLE", "DEADLINE_EXCEEDED",
                }:
                    hard_failure = True
            else:
                error_type = "UNQUALIFIED_PROVIDER_RESULT"
                hard_failure = True
            if state == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY":
                result["provider_failures_this_run"] += 1
                if result["provider_failures_this_run"] >= MAX_PROVIDER_FAULTS_PER_RUN:
                    hard_failure = True
            elif state == "EXPLICIT_NO_DATA_SOURCE_ONLY":
                result["no_data_this_run"] += 1
            if archive is not None:
                result["archived_this_run"] += 1
            if state == "RAW_ARCHIVED_INVALID_OR_UNMATCHED_CONTRACT":
                result["invalid_archives_this_run"] += 1
                if result["invalid_archives_this_run"] >= MAX_INVALID_ARCHIVES_PER_RUN:
                    hard_failure = True
            terminal = {
                "contract": CONTRACT, "kind": "terminal",
                "plan_fingerprint": report["fingerprint"],
                "query_id": req["query_id"],
                "started_fingerprint": started_record["fingerprint"],
                "state": state, "archive": archive,
                "error_type": error_type, "grpc_status": grpc,
                "simulator_ready": False,
            }
            _save_receipt(settings, req, report["fingerprint"], "terminal", terminal)
            done = (result["provider_requests_this_run"]
                    - len(batch) + batch.index(req) + 1)
            if progress is not None and (done % progress_every == 0 or hard_failure):
                progress({
                    "calls": done, "archives": result["archived_this_run"],
                    "explicit_no_data": result["no_data_this_run"],
                    "provider_faults": result["provider_failures_this_run"],
                    "invalid_archives": result["invalid_archives_this_run"],
                    "last_date": req["sdk_kwargs"]["date_et"],
                })
        if hard_failure:
            result["stop_reason"] = "HARD_PROVIDER_OR_REPEATED_SOURCE_SCHEMA_FAILURE"
            stop = True
    result["storage_audits_this_run"] = meter.full_audits
    after = preview_exact_exit_campaign(settings, report)
    result["remaining"] = after["remaining_unattempted"]
    result["states"] = after["states"]
    result["source_promotion"] = False
    result["historical_account_replay"] = False
    return result
