from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
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
from packages.providers.marketdata_app import MarketDataResponse, array_rows, rate_limit_snapshot
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


@dataclass(frozen=True, slots=True)
class ChainCachePaths:
    body: Path
    receipt: Path


def _paths(settings: AtlasSettings, request_identity: str) -> ChainCachePaths:
    if not SHA256_RE.fullmatch(request_identity):
        raise CandidateChainCacheError("invalid chain request identity")
    root = settings.resolved_path(CACHE_SUBDIR)
    directory = root / request_identity[:2]
    return ChainCachePaths(
        body=directory / f"{request_identity}.json",
        receipt=directory / f"{request_identity}.receipt.json",
    )


def _valid_receipt(paths: ChainCachePaths, request: dict[str, Any]) -> dict[str, Any] | None:
    body_exists = paths.body.exists()
    receipt_exists = paths.receipt.exists()
    if not body_exists and not receipt_exists:
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
    if receipt.get("row_count") != len(array_rows(payload)):
        raise CandidateChainCacheError("chain cache row count no longer reconciles")
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

    rows = array_rows(response.payload)
    required = ("optionSymbol", "underlying", "expiration", "side", "strike")
    status = "COMPLETE"
    failure: str | None = None
    if response.http_status not in {200, 203} or response.payload.get("s") != "ok":
        status, failure = "QUARANTINED", "unexpected provider response status"
    elif not 1 <= len(rows) <= MAX_CHAIN_ROWS:
        status, failure = "QUARANTINED", "historical chain empty or oversized"
    elif any(not all(key in row for key in required) for row in rows):
        status, failure = "QUARANTINED", "required chain identity fields missing"

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


def run_candidate_chain_cache(
    settings: AtlasSettings,
    plan: object,
    *,
    authorize_provider_reads: bool = False,
    confirm_paid_starter: bool = False,
    confirm_private_internal_use: bool = False,
    max_new_requests: int = 0,
    provider_read: Callable[[str, dict[str, str]], MarketDataResponse] | None = None,
) -> dict[str, Any]:
    """Bounded, restart-safe source acquisition. No quote, selector, P&L or trading."""
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

    storage = inspect_research_storage(settings)
    if storage.status == "BLOCKED_MINIMUM_FREE_SPACE":
        raise CandidateChainCacheError("storage minimum free-space gate blocked")
    report: dict[str, Any] = {
        "contract": CONTRACT,
        "plan_fingerprint": verified["plan_fingerprint"],
        "storage_mode": storage.storage_mode,
        "status": "PREVIEW" if not live else "IN_PROGRESS",
        "planned_chain_requests": len(verified["requests"]),
        "provider_reads": 0,
        "reused": 0,
        "new_complete": 0,
        "pending": 0,
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
    for request in verified["requests"]:
        _assert_request_shape(request)
        paths = _paths(settings, request["request_identity"])
        receipt = _valid_receipt(paths, request)
        if receipt is not None:
            report["reused"] += 1
            report["request_results"].append({
                "request_identity": request["request_identity"],
                "status": "REUSED_VERIFIED",
                "body_sha256": receipt["body_sha256"],
            })
            continue
        if not live or report["provider_reads"] >= max_new_requests:
            report["pending"] += 1
            report["request_results"].append({
                "request_identity": request["request_identity"],
                "status": "PENDING",
            })
            continue
        if remaining is not None and remaining < MIN_REMAINING_CREDITS:
            raise CandidateChainCacheError("provider credit safety floor reached")
        try:
            assert_category_acquisition_allowed(
                settings, category="options_candidate_cache",
                projected_additional_bytes=MAX_RAW_BYTES + 16384,
            )
        except ResearchStorageError as exc:
            raise CandidateChainCacheError(f"storage acquisition gate blocked: {exc}") from exc

        # A shared chain is one bounded server-side strike/expiration query, not
        # one quote-history call per stock opportunity. Actual charged credits
        # are taken only from returned provider headers.
        response = reader(request["endpoint"], request["params"])
        report["provider_reads"] += 1
        receipt = _write_raw_and_receipt(paths, request, response)
        report["new_complete"] += 1
        remaining = receipt["rate_limit"]["remaining"]
        report["request_results"].append({
            "request_identity": request["request_identity"],
            "status": "NEW_COMPLETE",
            "body_sha256": receipt["body_sha256"],
            "credits_remaining": remaining,
        })
        print(
            f"  chain {report['new_complete']}/{max_new_requests}: "
            f"{request['ticker']} {request['params']['date']} "
            f"rows={receipt['row_count']} remaining={remaining}",
            flush=True,
        )

    report["status"] = (
        "PREVIEW" if not live else
        "COMPLETE" if report["pending"] == 0 else "PARTIAL_RESUMABLE"
    )
    report["report_fingerprint"] = _fingerprint(report)
    if live:
        output = settings.resolved_path(
            "data/options/manifests/"
            f"marketdata_candidate_chain_cache_v1_{verified['plan_fingerprint'][:16]}.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(output, json.dumps(report, sort_keys=True, indent=2) + "\n")
    return report
