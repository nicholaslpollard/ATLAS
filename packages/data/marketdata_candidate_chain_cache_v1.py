from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from datetime import UTC, datetime
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_batch_plan_v1 import (
    CandidateBatchPlanError,
    plan_candidate_chain_batches,
)
from packages.data.research_storage import (
    ResearchStorageError,
    assert_category_acquisition_allowed,
    inspect_research_storage,
)
from packages.providers.marketdata_app import MarketDataError, MarketDataResponse, array_rows, rate_limit_snapshot
from packages.providers.marketdata_app.client import get_json


CONTRACT = "atlas-marketdata-candidate-chain-cache-v1"
CACHE_SUBDIR = "data/options/candidate_cache/chains/marketdata_v1"
MAX_NEW_REQUESTS = 10
MAX_RAW_BYTES = 8 * 1024 * 1024
MAX_CHAIN_ROWS = 1000
MIN_REMAINING_CREDITS = 200
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CandidateChainCacheError(RuntimeError):
    pass


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), default=str) + "\n").encode("utf-8")


def _fingerprint(value: object) -> str:
    return _sha256(_json_bytes(value))


def verify_candidate_plan(plan: object) -> dict[str, Any]:
    """Rebuild the complete offline plan instead of trusting a claimed fingerprint."""
    if not isinstance(plan, dict):
        raise CandidateChainCacheError("planned acquisition must be a JSON object")
    source_bindings = plan.get("source_bindings")
    requests = plan.get("requests")
    if not isinstance(source_bindings, dict) or not isinstance(requests, list):
        raise CandidateChainCacheError("plan lacks source bindings or requests")

    ticker_by_id: dict[str, str] = {}
    for request in requests:
        if not isinstance(request, dict) or not isinstance(request.get("opportunity_ids"), list):
            raise CandidateChainCacheError("invalid planned request")
        ticker = request.get("ticker")
        for identifier in request["opportunity_ids"]:
            if not isinstance(identifier, str) or identifier in ticker_by_id:
                raise CandidateChainCacheError("opportunity assigned more than once")
            ticker_by_id[identifier] = ticker

    if set(ticker_by_id) != set(source_bindings):
        raise CandidateChainCacheError("plan source-binding identities differ from requests")

    rows = []
    for identifier, fields in source_bindings.items():
        if not isinstance(fields, dict) or set(fields) != {
            "stock_source_sha256", "decision_at_utc", "raw_underlying_price",
            "snapshot_date", "expiration", "side",
        }:
            raise CandidateChainCacheError("plan source binding has wrong fields")
        rows.append({
            "opportunity_id": identifier,
            "ticker": ticker_by_id[identifier],
            "underlying_price_basis": "RAW_AS_TRADED",
            **fields,
        })
    try:
        reconstructed = plan_candidate_chain_batches({
            "purpose": "SOURCE_ACQUISITION_ONLY",
            "opportunities": rows,
        })
    except (CandidateBatchPlanError, ValueError, TypeError) as exc:
        raise CandidateChainCacheError(f"invalid or unbound PIT plan: {exc}") from exc
    if reconstructed != plan:
        raise CandidateChainCacheError("plan does not match regenerated PIT source/requests/fingerprint")
    return reconstructed


def _verify_stock_source_files(
    settings: AtlasSettings,
    plan: dict[str, Any],
    paths: tuple[Path, ...],
) -> tuple[str, ...]:
    """Proof that each claimed plan SHA binds to an explicit on-disk stock artifact.

    This verifies bytes only. Whether the files are accepted DEVELOPMENT evidence
    remains a separate upstream contract and is not inferred from a SHA alone.
    """
    required = {row["stock_source_sha256"] for row in plan["source_bindings"].values()}
    if not paths:
        raise CandidateChainCacheError(
            "live acquisition requires --stock-source-file for every claimed source SHA"
        )
    verified: set[str] = set()
    # The accepted bundle lives beneath a project-visible logical binding.
    # Preserve that logical path on Windows: resolving its parent junction
    # would incorrectly reject a healthy external NVMe evidence directory.
    allowed = settings.resolved_path(
        "data/research/evidence/marketdata_candidate_stock_v1"
    )
    for supplied in paths:
        source = Path(os.path.abspath(supplied))
        if source.parent != allowed:
            raise CandidateChainCacheError(
                "stock source file must be an exact exported candidate evidence bundle"
            )
        # resolved_path already checked the configured external binding itself.
        # Neither a nested unexpected link nor a symlinked evidence file is allowed.
        if source.parent.is_symlink():
            raise CandidateChainCacheError("source bundle directory cannot be a symlink")
        if not source.is_file() or source.is_symlink():
            raise CandidateChainCacheError(f"stock source artifact is missing/invalid: {source}")
        hasher = hashlib.sha256()
        with source.open("rb") as handle:
            while chunk := handle.read(4 * 1024 * 1024):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        if digest not in required:
            raise CandidateChainCacheError(
                "stock source file SHA does not match any declared plan source binding"
            )
        verified.add(digest)
    if verified != required:
        raise CandidateChainCacheError(
            "one or more claimed stock source SHA values lack matching physical files"
        )
    return tuple(sorted(verified))


@dataclass(frozen=True, slots=True)
class ChainCachePaths:
    body: Path
    receipt: Path
    attempt: Path
    recovery: Path


def _paths(settings: AtlasSettings, request_identity: str) -> ChainCachePaths:
    if not SHA256_RE.fullmatch(request_identity):
        raise CandidateChainCacheError("invalid chain request identity")
    root = settings.resolved_path(CACHE_SUBDIR)
    directory = root / request_identity[:2]
    return ChainCachePaths(
        body=directory / f"{request_identity}.json",
        receipt=directory / f"{request_identity}.receipt.json",
        attempt=directory / f"{request_identity}.attempt.json",
        recovery=directory / f"{request_identity}.recovery.json",
    )


def _expiration_date(value: object) -> str:
    """Normalize provider UTC epoch seconds or an ISO date; reject other shapes."""
    if type(value) is int and 0 < value < 4102444800:
        return datetime.fromtimestamp(value, UTC).date().isoformat()
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    raise ValueError("invalid option expiration")


def _rows_match_explicit_request(
    rows: tuple[dict[str, Any], ...], request: dict[str, Any],
) -> bool:
    """Validate response columns AND OCC identities against the exact query."""
    try:
        lo_text, hi_text = request["params"]["strike"].split("-")
        lo, hi = Decimal(lo_text), Decimal(hi_text)
        expiry = request["params"]["expiration"]
        if not lo.is_finite() or not hi.is_finite() or lo > hi:
            return False
        symbols: set[str] = set()
        for row in rows:
            symbol = row.get("optionSymbol")
            if not isinstance(symbol, str) or symbol in symbols:
                return False
            symbols.add(symbol)
            strike = Decimal(str(row.get("strike")))
            side = row.get("side")
            match = re.fullmatch(r"([A-Z0-9.]+)(\d{6})([CP])(\d{8})", symbol)
            if (
                match is None
                or row.get("underlying") != request["ticker"]
                or _expiration_date(row.get("expiration")) != expiry
                or side not in {"call", "put"}
                or not strike.is_finite()
                or not lo <= strike <= hi
                or match.group(1) != request["ticker"]
                or "20" + match.group(2)[:2] + "-" + match.group(2)[2:4] + "-" + match.group(2)[4:] != expiry
                or match.group(3) != ("C" if side == "call" else "P")
                or Decimal(match.group(4)) / 1000 != strike
            ):
                return False
    except (KeyError, ValueError, InvalidOperation, TypeError, OverflowError, OSError):
        return False
    return True


def _valid_receipt(paths: ChainCachePaths, request: dict[str, Any]) -> dict[str, Any] | None:
    body_exists = paths.body.exists()
    receipt_exists = paths.receipt.exists()
    if not body_exists and not receipt_exists:
        if paths.attempt.exists():
            raise CandidateChainCacheError(
                "unresolved provider attempt: inspect saved attempt and provider usage; "
                "do not automatically spend credits again"
            )
        return None
    if not body_exists or not receipt_exists:
        raise CandidateChainCacheError("partial chain cache: raw body/receipt mismatch")
    if paths.body.is_symlink() or paths.receipt.is_symlink():
        raise CandidateChainCacheError("unexpected cache-file symlink")
    try:
        receipt = json.loads(paths.receipt.read_text(encoding="utf-8"))
        raw = paths.body.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        expected_receipt = dict(receipt)
        expected_hash = expected_receipt.pop("receipt_fingerprint")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise CandidateChainCacheError("cache receipt/body cannot be read or decoded") from exc

    if receipt.get("status") == "QUARANTINED" and paths.recovery.is_file():
        try:
            recovery = json.loads(paths.recovery.read_text(encoding="utf-8"))
            recovery_hash = recovery.pop("recovery_fingerprint")
            if (
                recovery_hash != _fingerprint(recovery)
                or recovery.get("contract") != "atlas-marketdata-chain-offline-recovery-v1"
                or recovery.get("original_receipt_fingerprint") != receipt.get("receipt_fingerprint")
                or recovery.get("body_sha256") != _sha256(raw)
                or recovery.get("request_identity") != request["request_identity"]
                or recovery.get("status") != "RECOVERED_VERIFIED"
                or not paths.attempt.is_file()
                or receipt.get("failure") != "chain rows violate ticker, expiry, strike or identity envelope"
                or receipt.get("http_status") not in {200, 203}
                or receipt.get("rate_limit", {}).get("consumed") is None
                or receipt.get("rate_limit", {}).get("remaining") is None
            ):
                raise ValueError("recovery proof mismatch")
            rows = array_rows(payload)
            if (payload.get("s") != "ok" or receipt.get("row_count") != len(rows)
                    or not _rows_match_explicit_request(rows, request)):
                raise ValueError("recovered rows do not match request")
            return {**receipt, "status": "COMPLETE", "offline_recovery": True}
        except (OSError, ValueError, TypeError, KeyError, MarketDataError) as exc:
            raise CandidateChainCacheError("offline recovery evidence invalid; never overwrite") from exc

    if (
        receipt.get("contract") != CONTRACT
        or receipt.get("status") != "COMPLETE"
        or receipt.get("request_identity") != request["request_identity"]
        or receipt.get("endpoint") != request["endpoint"]
        or receipt.get("params") != request["params"]
        or receipt.get("body_sha256") != _sha256(raw)
        or receipt.get("body_bytes") != len(raw)
        or expected_hash != _fingerprint(expected_receipt)
        or not isinstance(payload, dict)
        or payload.get("s") != "ok"
    ):
        raise CandidateChainCacheError("chain cache receipt/source mismatch: never overwrite")
    rows = array_rows(payload)
    if receipt.get("row_count") != len(rows) or not _rows_match_explicit_request(rows, request):
        raise CandidateChainCacheError("chain cache rows no longer match explicit source request")
    return receipt


def _write_raw_and_receipt(
    paths: ChainCachePaths,
    request: dict[str, Any],
    response: MarketDataResponse,
) -> dict[str, Any]:
    if paths.body.exists() or paths.receipt.exists():
        raise CandidateChainCacheError("refusing to overwrite existing chain cache")
    raw = response.raw_body
    if raw is None:
        raise CandidateChainCacheError("provider transport did not preserve exact raw HTTP bytes")
    if not isinstance(raw, bytes) or len(raw) > MAX_RAW_BYTES:
        raise CandidateChainCacheError("provider response has invalid/unbounded raw bytes")
    if json.loads(raw.decode("utf-8")) != response.payload:
        raise CandidateChainCacheError("exact HTTP body differs from decoded provider payload")

    schema_failure = False
    try:
        rows = array_rows(response.payload)
    except (MarketDataError, ValueError, TypeError):
        # Preserve exact raw bytes even when provider column vectors disagree.
        rows = ()
        schema_failure = True
    required = ("optionSymbol", "underlying", "expiration", "side", "strike")
    status = "COMPLETE"
    failure: str | None = None
    if schema_failure:
        status, failure = "QUARANTINED", "provider response arrays inconsistent"
    elif response.http_status not in {200, 203} or response.payload.get("s") != "ok":
        status, failure = "QUARANTINED", "unexpected provider response status"
    elif not 1 <= len(rows) <= MAX_CHAIN_ROWS:
        status, failure = "QUARANTINED", "historical chain empty or oversized"
    elif any(not all(key in row for key in required) for row in rows):
        status, failure = "QUARANTINED", "required chain identity fields missing"
    elif not _rows_match_explicit_request(rows, request):
        status, failure = "QUARANTINED", "chain rows violate ticker, expiry, strike or identity envelope"

    rates = rate_limit_snapshot(response.headers)
    if rates["remaining"] is None or rates["consumed"] is None:
        status, failure = "QUARANTINED", "required provider credit headers missing"
    elif rates["consumed"] < 0 or rates["remaining"] < 0:
        status, failure = "QUARANTINED", "invalid provider credit headers"

    receipt = {
        "contract": CONTRACT,
        "status": status,
        "failure": failure,
        "request_identity": request["request_identity"],
        "endpoint": request["endpoint"],
        "params": request["params"],
        "body_sha256": _sha256(raw),
        "body_bytes": len(raw),
        "row_count": len(rows),
        "http_status": response.http_status,
        "raw_http_body_exact": True,
        "rate_limit": rates,
        "source_role": "HISTORICAL_EOD_CHAIN_SOURCE_ONLY",
        "no_execution_price_or_option_pnl_authority": True,
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)

    paths.body.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(paths.body)
    try:
        with temp.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        replace_with_retry(temp, paths.body)
        atomic_write_text(paths.receipt, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    finally:
        temp.unlink(missing_ok=True)

    if status != "COMPLETE":
        raise CandidateChainCacheError(
            f"provider chain quarantined with exact raw receipt: {failure}"
        )
    return receipt


def _assert_request_shape(request: dict[str, Any]) -> None:
    ticker = request["ticker"]
    if (
        request["endpoint"] != f"options/chain/{ticker}/"
        or set(request["params"]) != {"date", "expiration", "strike"}
        or request.get("bounded_query") is not True
    ):
        raise CandidateChainCacheError("unbounded or inconsistent chain request")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _create_attempt(paths: ChainCachePaths, request: dict[str, Any], *,
                    run_id: str, plan_fingerprint: str) -> None:
    """Durable request intent BEFORE touching a potentially billable provider.

    A timeout or killed process must never make the next invocation silently
    send the same historical request and possibly pay for it twice.
    """
    paths.attempt.parent.mkdir(parents=True, exist_ok=True)
    intent = {
        "contract": CONTRACT,
        "status": "REQUEST_STARTED_CHARGE_UNKNOWN_UNTIL_RECEIPT",
        "run_id": run_id,
        "plan_fingerprint": plan_fingerprint,
        "request_identity": request["request_identity"],
        "endpoint": request["endpoint"],
        "params": request["params"],
        "created_at_utc": _utc_now(),
        "automatic_retry_permitted": False,
    }
    intent["intent_fingerprint"] = _fingerprint(intent)
    try:
        with paths.attempt.open("x", encoding="utf-8", newline="") as handle:
            handle.write(json.dumps(intent, sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise CandidateChainCacheError(
            "a prior provider attempt exists: do not automatically spend credits twice"
        ) from exc


def _checkpoint_report(report: dict[str, Any], *, run_path: Path,
                       latest_path: Path, started: float) -> None:
    """Atomic, per-stage run-level checkpoint, not only an end-of-run summary."""
    report["last_updated_at_utc"] = _utc_now()
    report["elapsed_seconds"] = round(max(0.0, time.monotonic() - started), 3)
    report["processed_requests"] = len(report["request_results"])
    report["completed_chains"] = report["reused"] + report["new_complete"]
    report["pending"] = (
        report["planned_chain_requests"] - report["completed_chains"]
    )
    elapsed = report["elapsed_seconds"]
    report["processed_per_second"] = (
        round(report["processed_requests"] / elapsed, 4) if elapsed else None
    )
    # ETA is a rough OBSERVED processing rate, not a promised runtime.
    report["estimated_remaining_seconds"] = (
        round(report["pending"] / report["processed_per_second"], 1)
        if report["processed_per_second"] and report["status"] == "RUNNING"
        else None
    )
    report.pop("report_fingerprint", None)
    report["report_fingerprint"] = _fingerprint(report)
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(run_path, encoded)
    atomic_write_text(latest_path, encoded)


def _storage_metrics(snapshot: object) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "status": getattr(snapshot, "status", None),
        "mode": getattr(snapshot, "storage_mode", None),
        "disk_free_gib": getattr(snapshot, "disk_free_gib", None),
        "minimum_free_gib": getattr(snapshot, "minimum_free_gib", None),
        "remaining_acquisition_budget_gib": getattr(
            snapshot, "remaining_acquisition_budget_gib", None
        ),
        "maximum_safe_additional_gib": getattr(
            snapshot, "maximum_safe_additional_gib", None
        ),
        "category_usage_gib": getattr(snapshot, "category_usage_gib", None),
        "category_quota_gib": getattr(snapshot, "category_quota_gib", None),
    }


def run_candidate_chain_cache(
    settings: AtlasSettings,
    plan: object,
    *,
    authorize_provider_reads: bool = False,
    confirm_paid_starter: bool = False,
    confirm_private_internal_use: bool = False,
    max_new_requests: int = 0,
    provider_read: Callable[[str, dict[str, str]], MarketDataResponse] | None = None,
    stock_source_files: tuple[Path, ...] = (),
) -> dict[str, Any]:
    """Sequential bounded source-only cache with durable per-request accounting."""
    started = time.monotonic()
    verified = verify_candidate_plan(plan)
    if not 0 <= max_new_requests <= MAX_NEW_REQUESTS:
        raise CandidateChainCacheError(f"max_new_requests must be 0..{MAX_NEW_REQUESTS}")
    live = max_new_requests > 0
    if live and not (
        authorize_provider_reads and confirm_paid_starter and confirm_private_internal_use
    ):
        raise CandidateChainCacheError(
            "provider reads require explicit authorization, paid Starter and private-use confirmations"
        )
    if authorize_provider_reads and not live:
        raise CandidateChainCacheError("authorization requires an explicit positive max_new_requests")
    if live and provider_read is None and not os.getenv("MARKETDATA_TOKEN", "").strip():
        raise CandidateChainCacheError(
            "MARKETDATA_TOKEN must be configured before recording any provider attempt"
        )

    verified_sources = (
        _verify_stock_source_files(settings, verified, stock_source_files)
        if live else ()
    )
    # A zero-network preview verifies exact cached receipts but does not need
    # an expensive full research-directory quota census.
    storage = inspect_research_storage(settings) if live else None
    if storage is not None and storage.status == "BLOCKED_MINIMUM_FREE_SPACE":
        raise CandidateChainCacheError("storage minimum free-space gate blocked")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    fingerprint = verified["plan_fingerprint"]
    report: dict[str, Any] = {
        "contract": CONTRACT,
        "run_id": run_id,
        "started_at_utc": _utc_now(),
        "plan_fingerprint": fingerprint,
        "storage_mode": (
            storage.storage_mode if storage is not None
            else "EXTERNAL_SECONDARY" if settings.external_data_root() is not None
            else "PROJECT_LOCAL"
        ),
        "storage_initial": _storage_metrics(storage),
        "storage_latest": _storage_metrics(storage),
        "verified_stock_source_sha256": list(verified_sources),
        "status": "PREVIEW" if not live else "RUNNING",
        "planned_opportunities": verified["opportunities"],
        "planned_chain_requests": len(verified["requests"]),
        "max_new_requests": max_new_requests,
        "provider_reads": 0,       # attempts initiated, including errors
        "reused": 0,
        "new_complete": 0,
        "quarantined": 0,
        "verified_reused_bytes": 0,
        "new_raw_bytes": 0,
        "provider_response_bytes_observed": 0,
        "observed_credits_consumed_this_run": 0,
        "credits_unknown_after_failed_request": False,
        "last_observed_provider_credits_remaining": None,
        "request_results": [],
        "no_quote_paths_or_option_pnl_authority": True,
        "no_broker_reads_writes": True,
    }
    remaining: int | None = None
    reader = provider_read or (
        lambda endpoint, params: get_json(
            endpoint, params=params, max_attempts=1, max_response_bytes=MAX_RAW_BYTES,
        )
    )
    if not live:
        # Preview: no lock, cache modification, manifests, credentials or API calls.
        for index, request in enumerate(verified["requests"], start=1):
            _assert_request_shape(request)
            receipt = _valid_receipt(_paths(settings, request["request_identity"]), request)
            if receipt is None:
                report["request_results"].append({
                    "request_identity": request["request_identity"], "status": "PENDING",
                })
            else:
                report["reused"] += 1
                report["verified_reused_bytes"] += receipt["body_bytes"]
                report["request_results"].append({
                    "request_identity": request["request_identity"],
                    "status": "REUSED_VERIFIED",
                    "body_sha256": receipt["body_sha256"],
                })
            if index % 25 == 0 or index == len(verified["requests"]):
                print(
                    f"  preview {index}/{len(verified['requests'])}: "
                    f"verified={report['reused']}, pending={index-report['reused']}",
                    flush=True,
                )
        report["processed_requests"] = len(report["request_results"])
        report["completed_chains"] = report["reused"]
        report["pending"] = report["planned_chain_requests"] - report["reused"]
        report["elapsed_seconds"] = round(max(0.0, time.monotonic() - started), 3)
        report["report_fingerprint"] = _fingerprint(report)
        return report

    # Exclusive plan lock: another workstation process cannot concurrently
    # issue duplicate paid queries for this plan. A hard crash leaves the lock
    # for explicit human inspection rather than guessing a safe automatic retry.
    latest_path = settings.resolved_path(
        "data/options/manifests/"
        f"marketdata_candidate_chain_cache_v1_{fingerprint[:16]}.json"
    )
    # Keep the physical checkpoint short enough for legacy Windows path APIs.
    # The full 64-character plan fingerprint remains inside the signed report;
    # runtime directory names are non-authoritative and need no full SHA.
    run_path = settings.resolved_path(
        "data/options/manifests/md_chain_runs/"
        f"{fingerprint[:16]}/{run_id}.json"
    )
    lock_path = latest_path.with_suffix(".lock")
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise CandidateChainCacheError(
            f"another run or unresolved crash owns the plan lock: {lock_path}; "
            "review process and receipts before manual cleanup"
        ) from exc
    try:
        with os.fdopen(lock_fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "contract": CONTRACT, "run_id": run_id, "pid": os.getpid(),
                "created_at_utc": _utc_now(), "plan_fingerprint": fingerprint,
            }, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        report["run_report_path"] = str(run_path)
        report["latest_report_path"] = str(latest_path)
        _checkpoint_report(report, run_path=run_path, latest_path=latest_path, started=started)
        try:
            for index, request in enumerate(verified["requests"], start=1):
                _assert_request_shape(request)
                paths = _paths(settings, request["request_identity"])
                receipt = _valid_receipt(paths, request)
                if receipt is not None:
                    report["reused"] += 1
                    report["verified_reused_bytes"] += receipt["body_bytes"]
                    report["request_results"].append({
                        "request_identity": request["request_identity"],
                        "status": "REUSED_VERIFIED",
                        "body_sha256": receipt["body_sha256"],
                    })
                    # Avoid hundreds of repeated manifest writes for free cache hits.
                    if report["reused"] % 10 == 0 or index == len(verified["requests"]):
                        _checkpoint_report(
                            report, run_path=run_path, latest_path=latest_path,
                            started=started,
                        )
                    continue
                if report["provider_reads"] >= max_new_requests:
                    report["request_results"].append({
                        "request_identity": request["request_identity"], "status": "PENDING_LIMIT",
                    })
                    continue
                if remaining is not None and remaining < MIN_REMAINING_CREDITS:
                    report["status"] = "PARTIAL_CREDIT_FLOOR"
                    report["request_results"].append({
                        "request_identity": request["request_identity"],
                        "status": "BLOCKED_CREDIT_FLOOR",
                    })
                    _checkpoint_report(
                        report, run_path=run_path, latest_path=latest_path, started=started,
                    )
                    break
                try:
                    storage_before = assert_category_acquisition_allowed(
                        settings, category="options_candidate_cache",
                        projected_additional_bytes=MAX_RAW_BYTES + 16384,
                    )
                    if storage_before is not None:
                        report["storage_latest"] = _storage_metrics(storage_before)
                except ResearchStorageError:
                    report["status"] = "PARTIAL_STORAGE_BLOCKED"
                    report["request_results"].append({
                        "request_identity": request["request_identity"],
                        "status": "BLOCKED_STORAGE",
                    })
                    _checkpoint_report(
                        report, run_path=run_path, latest_path=latest_path, started=started,
                    )
                    break

                # Persist intent and in-progress checkpoint before the first
                # potentially billable byte; never auto-retry an ambiguous failure.
                _create_attempt(
                    paths, request, run_id=run_id, plan_fingerprint=fingerprint,
                )
                report["provider_reads"] += 1
                report["request_results"].append({
                    "request_identity": request["request_identity"],
                    "status": "REQUEST_STARTED_CHARGE_UNKNOWN",
                    "attempt_path": str(paths.attempt),
                })
                _checkpoint_report(
                    report, run_path=run_path, latest_path=latest_path, started=started,
                )
                try:
                    response = reader(request["endpoint"], request["params"])
                    rates = rate_limit_snapshot(response.headers)
                    report["provider_response_bytes_observed"] += response.response_bytes
                    if rates["consumed"] is None:
                        report["credits_unknown_after_failed_request"] = True
                    elif rates["consumed"] >= 0:
                        report["observed_credits_consumed_this_run"] += rates["consumed"]
                    if rates["remaining"] is not None:
                        remaining = rates["remaining"]
                        report["last_observed_provider_credits_remaining"] = remaining
                    receipt = _write_raw_and_receipt(paths, request, response)
                except BaseException as exc:
                    report["request_results"][-1]["status"] = (
                        "INTERRUPTED_REVIEW_REQUIRED"
                        if isinstance(exc, KeyboardInterrupt)
                        else "FAILED_REVIEW_REQUIRED"
                    )
                    report["request_results"][-1]["exception_type"] = type(exc).__name__
                    report["credits_unknown_after_failed_request"] = True
                    # No provider payload, API key or raw error message in the ledger.
                    report["status"] = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "FAILED_REVIEW_REQUIRED"
                    if paths.receipt.is_file():
                        try:
                            saved = json.loads(paths.receipt.read_text(encoding="utf-8"))
                            if saved.get("status") == "QUARANTINED":
                                report["quarantined"] += 1
                        except (OSError, ValueError):
                            pass
                    _checkpoint_report(
                        report, run_path=run_path, latest_path=latest_path, started=started,
                    )
                    raise
                report["new_complete"] += 1
                report["new_raw_bytes"] += receipt["body_bytes"]
                report["request_results"][-1].update({
                    "status": "NEW_COMPLETE",
                    "body_sha256": receipt["body_sha256"],
                    "body_bytes": receipt["body_bytes"],
                    "rows": receipt["row_count"],
                    "credits_remaining": remaining,
                    "credits_consumed_observed": rates["consumed"],
                })
                _checkpoint_report(
                    report, run_path=run_path, latest_path=latest_path, started=started,
                )
                print(
                    f"  {index}/{len(verified['requests'])} chains | "
                    f"reused={report['reused']} acquired={report['new_complete']} "
                    f"API_attempts={report['provider_reads']} "
                    f"credits_used_observed={report['observed_credits_consumed_this_run']} "
                    f"remaining={remaining} elapsed={report['elapsed_seconds']:.1f}s",
                    flush=True,
                )
            if report["status"] == "RUNNING":
                report["status"] = (
                    "COMPLETE" if report["pending"] == 0 else "PARTIAL_RESUMABLE"
                )
            _checkpoint_report(
                report, run_path=run_path, latest_path=latest_path, started=started,
            )
            return report
        except BaseException as exc:
            if report["status"] == "RUNNING":
                report["status"] = (
                    "INTERRUPTED" if isinstance(exc, KeyboardInterrupt)
                    else "FAILED_REVIEW_REQUIRED"
                )
                report["failure_stage_type"] = type(exc).__name__
                _checkpoint_report(
                    report, run_path=run_path, latest_path=latest_path, started=started,
                )
            raise
    finally:
        # Ordinary failure releases the run lock; each unresolved per-query
        # attempt remains independently guarded. Killed processes leave the
        # lock intentionally, requiring manual verification before re-entry.
        lock_path.unlink(missing_ok=True)
