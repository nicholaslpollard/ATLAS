from __future__ import annotations

"""Resumable ThetaData 09:35 candidate-surface acquisition.

This stage is inert by default and may perform provider reads only after a signed
qualification report proves the source for the exact plan. It preserves durable
pre-request intent, exact raw response bytes, immutable receipts, normalized surface
fingerprints, D:-bound storage guards, a run lock, and deterministic resume behavior.

The acquired surfaces remain entry-time source evidence only. No contract is selected
here and no exit quote, return, historical fill, account P&L, strategy, PAPER or LIVE
authority is created.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.research_storage import (
    ResearchStorageError,
    assert_category_acquisition_allowed,
)
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as PLAN_CONTRACT,
    EXPECTED_UNIQUE_SURFACES,
    PROVIDER_CANDIDATE,
)
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    CONTRACT as QUALIFICATION_CONTRACT,
    _normalize_rows,
)
from packages.providers.thetadata.client import (
    ThetaDataError,
    ThetaDataResponse,
    option_at_time_quote_surface,
)

CONTRACT = "atlas-thetadata-candidate-surface-cache-v1"
CACHE_REL = "data/options/candidate_cache/thetadata_surfaces_v1"
MANIFEST_REL = "data/options/manifests"
MAX_REQUESTS = 10000
MAX_WORKERS = 4
MAX_RAW_BYTES = 64 * 1024 * 1024
PROJECTED_RECEIPT_BYTES = 64 * 1024


class ThetaDataCandidateSurfaceCacheError(ValueError):
    pass


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _cache_paths(
    settings: AtlasSettings,
    *,
    plan_fingerprint: str,
    source_query_fingerprint: str,
) -> tuple[Path, Path, Path]:
    root = settings.resolved_path(
        f"{CACHE_REL}/{plan_fingerprint[:16]}"
    )
    stem = source_query_fingerprint
    return (
        root / f"{stem}.json",
        root / f"{stem}.receipt.json",
        root / f"{stem}.intent.json",
    )


def _checkpoint_path(settings: AtlasSettings, plan_fingerprint: str) -> Path:
    return settings.resolved_path(
        f"{MANIFEST_REL}/thetadata_candidate_surface_cache_v1_"
        f"{plan_fingerprint[:16]}.json"
    )


def _lock_path(settings: AtlasSettings, plan_fingerprint: str) -> Path:
    return settings.resolved_path(
        f"{MANIFEST_REL}/.thetadata_candidate_surface_cache_"
        f"{plan_fingerprint[:16]}.lock"
    )


def _request_identity(query: dict[str, Any]) -> str:
    return _fingerprint({
        "contract": CONTRACT,
        "endpoint": query["endpoint"],
        "params": query["params"],
        "source_query_fingerprint": query["source_query_fingerprint"],
    })


def _validate_plan_and_qualification(
    plan: dict[str, Any],
    qualification: dict[str, Any],
) -> None:
    _check_signature(plan, "plan_fingerprint")
    _check_signature(qualification, "qualification_fingerprint")
    requests = plan.get("provider_request_contract", {}).get("full_surface_queries")
    if (
        plan.get("contract") != PLAN_CONTRACT
        or plan.get("status") != "PLANNED_ZERO_PROVIDER_READS"
        or plan.get("provider_candidate") != PROVIDER_CANDIDATE
        or not isinstance(requests, list)
        or len(requests) != EXPECTED_UNIQUE_SURFACES
        or plan.get("provider_requests") != 0
        or plan.get("historical_fill_authority") is not False
        or plan.get("strategy_evidence_authority") is not False
    ):
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData surface plan lineage/authority changed"
        )
    if (
        qualification.get("contract") != QUALIFICATION_CONTRACT
        or qualification.get("plan_fingerprint") != plan["plan_fingerprint"]
        or qualification.get("decision_spot_fingerprint")
            != plan["decision_spot_fingerprint"]
        or qualification.get("provider_candidate") != PROVIDER_CANDIDATE
        or qualification.get("full_acquisition_source_qualified") is not True
        or qualification.get("oldest_2021_surface_proven") is not True
        or qualification.get("full_2021_2025_surface_coverage_proven") is not True
        or qualification.get("hard_validation_or_transport_errors") != 0
        or qualification.get("repeatability_probe", {}).get(
            "deterministic_normalized_surface"
        ) is not True
        or qualification.get("historical_fill_authority") is not False
        or qualification.get("strategy_evidence_authority") is not False
        or qualification.get("paper_authority") is not False
        or qualification.get("live_authority") is not False
    ):
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData qualification does not authorize bounded source acquisition"
        )


def _validate_query(query: dict[str, Any]) -> None:
    required = {
        "endpoint",
        "params",
        "source_query_fingerprint",
        "member_case_ids",
        "member_case_count",
    }
    if set(query) != required or query["endpoint"] != PROVIDER_CANDIDATE["at_time_endpoint"]:
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData full-surface query schema changed"
        )
    params = query["params"]
    if (
        not isinstance(params, dict)
        or params.get("expiration") != "*"
        or params.get("strike") != "*"
        or params.get("right") != "call"
        or params.get("max_dte") != 75
        or params.get("strike_range") is not None
        or params.get("time_of_day") != "09:35:00.000"
        or params.get("format") != "json"
        or params.get("start_date") != params.get("end_date")
    ):
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData provider request shape changed"
        )
    members = query["member_case_ids"]
    if (
        not isinstance(members, list)
        or not members
        or len(set(str(value) for value in members))
            != int(query["member_case_count"])
    ):
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData provider query members malformed"
        )


def _intent_payload(
    *,
    plan_fingerprint: str,
    qualification_fingerprint: str,
    query: dict[str, Any],
) -> dict[str, Any]:
    body = {
        "contract": CONTRACT,
        "status": "REQUEST_STARTED_SOURCE_RESULT_UNKNOWN_UNTIL_RECEIPT",
        "plan_fingerprint": plan_fingerprint,
        "qualification_fingerprint": qualification_fingerprint,
        "request_identity": _request_identity(query),
        "query": query,
        "automatic_retry_permitted": False,
    }
    body["intent_fingerprint"] = _fingerprint(body)
    return body


def _write_intent(
    path: Path,
    *,
    plan_fingerprint: str,
    qualification_fingerprint: str,
    query: dict[str, Any],
) -> dict[str, Any]:
    if path.exists() or path.is_symlink():
        raise ThetaDataCandidateSurfaceCacheError(
            "prior ThetaData request intent exists; review before any manual retry"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    intent = _intent_payload(
        plan_fingerprint=plan_fingerprint,
        qualification_fingerprint=qualification_fingerprint,
        query=query,
    )
    raw = (json.dumps(intent, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return intent


def _decode_raw_rows(raw: bytes) -> tuple[dict[str, Any], ...]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ThetaDataCandidateSurfaceCacheError(
            "cached ThetaData body is not valid JSON"
        ) from exc
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ThetaDataCandidateSurfaceCacheError(
            "cached ThetaData body schema changed"
        )
    return tuple(dict(row) for row in value)


def _normalize_for_query(
    rows: tuple[dict[str, Any], ...],
    query: dict[str, Any],
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    return _normalize_rows(rows, anchor={"query": query})


def _write_response(
    *,
    body_path: Path,
    receipt_path: Path,
    intent_path: Path,
    query: dict[str, Any],
    plan_fingerprint: str,
    qualification_fingerprint: str,
    response: ThetaDataResponse,
) -> dict[str, Any]:
    if body_path.exists() or receipt_path.exists():
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData raw body/receipt already exists: never overwrite"
        )
    if not intent_path.is_file() or intent_path.is_symlink():
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData durable request intent missing"
        )
    if not isinstance(response.raw_body, bytes) or len(response.raw_body) > MAX_RAW_BYTES:
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData candidate surface raw response is unbounded"
        )

    if response.rows:
        normalized, summary = _normalize_for_query(response.rows, query)
        status = "COMPLETE_CANDIDATE_SURFACE"
        normalized_fingerprint = _fingerprint(list(normalized))
    else:
        normalized = ()
        summary = {
            "row_count": 0,
            "two_sided_positive_displayed_size_rows": 0,
            "phase13_dte_14_45_rows": 0,
            "min_quote_staleness_seconds": None,
            "max_quote_staleness_seconds": None,
            "normalized_surface_fingerprint": _fingerprint([]),
        }
        status = "EXPLICIT_NO_DATA"
        normalized_fingerprint = summary["normalized_surface_fingerprint"]

    receipt = {
        "contract": CONTRACT,
        "status": status,
        "plan_fingerprint": plan_fingerprint,
        "qualification_fingerprint": qualification_fingerprint,
        "request_identity": _request_identity(query),
        "source_query_fingerprint": query["source_query_fingerprint"],
        "query": query,
        "http_status": response.http_status,
        "body_sha256": _sha256(response.raw_body),
        "body_bytes": len(response.raw_body),
        "row_count": len(response.rows),
        "surface_summary": summary,
        "normalized_surface_fingerprint": normalized_fingerprint,
        "raw_http_body_exact": True,
        "historical_fill_authority": False,
        "strategy_evidence_authority": False,
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)

    body_path.parent.mkdir(parents=True, exist_ok=True)
    with body_path.open("xb") as handle:
        handle.write(response.raw_body)
        handle.flush()
        os.fsync(handle.fileno())
    atomic_write_text(
        receipt_path,
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )
    return receipt


def _read_intact(
    *,
    body_path: Path,
    receipt_path: Path,
    intent_path: Path,
    query: dict[str, Any],
    plan_fingerprint: str,
    qualification_fingerprint: str,
) -> dict[str, Any] | None:
    exists = (body_path.exists(), receipt_path.exists(), intent_path.exists())
    if not any(exists):
        return None
    if not all(exists):
        raise ThetaDataCandidateSurfaceCacheError(
            "partial ThetaData cache/intent exists; manual review required"
        )
    if any(path.is_symlink() for path in (body_path, receipt_path, intent_path)):
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData cache evidence may not be symlinked"
        )
    try:
        raw = body_path.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData cache evidence unreadable"
        ) from exc

    rbody = dict(receipt)
    rfp = rbody.pop("receipt_fingerprint", None)
    ibody = dict(intent)
    ifp = ibody.pop("intent_fingerprint", None)
    expected_request = _request_identity(query)
    if (
        rfp != _fingerprint(rbody)
        or ifp != _fingerprint(ibody)
        or receipt.get("contract") != CONTRACT
        or intent.get("contract") != CONTRACT
        or receipt.get("plan_fingerprint") != plan_fingerprint
        or intent.get("plan_fingerprint") != plan_fingerprint
        or receipt.get("qualification_fingerprint") != qualification_fingerprint
        or intent.get("qualification_fingerprint") != qualification_fingerprint
        or receipt.get("request_identity") != expected_request
        or intent.get("request_identity") != expected_request
        or receipt.get("query") != query
        or intent.get("query") != query
        or intent.get("automatic_retry_permitted") is not False
        or receipt.get("body_sha256") != _sha256(raw)
        or receipt.get("body_bytes") != len(raw)
        or receipt.get("historical_fill_authority") is not False
        or receipt.get("strategy_evidence_authority") is not False
    ):
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData cached receipt/intent lineage changed"
        )

    if receipt.get("status") == "COMPLETE_CANDIDATE_SURFACE":
        rows = _decode_raw_rows(raw)
        normalized, summary = _normalize_for_query(rows, query)
        if (
            receipt.get("row_count") != len(rows)
            or receipt.get("surface_summary") != summary
            or receipt.get("normalized_surface_fingerprint")
                != _fingerprint(list(normalized))
        ):
            raise ThetaDataCandidateSurfaceCacheError(
                "ThetaData cached normalized surface changed"
            )
    elif receipt.get("status") == "EXPLICIT_NO_DATA":
        if receipt.get("row_count") != 0:
            raise ThetaDataCandidateSurfaceCacheError(
                "ThetaData no-data receipt row count changed"
            )
    else:
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData cached source status is not reusable"
        )
    return receipt


def _transport_one(
    *,
    settings: AtlasSettings,
    plan_fingerprint: str,
    qualification_fingerprint: str,
    query: dict[str, Any],
    reader: Callable[..., ThetaDataResponse],
) -> dict[str, Any]:
    body_path, receipt_path, intent_path = _cache_paths(
        settings,
        plan_fingerprint=plan_fingerprint,
        source_query_fingerprint=query["source_query_fingerprint"],
    )
    _write_intent(
        intent_path,
        plan_fingerprint=plan_fingerprint,
        qualification_fingerprint=qualification_fingerprint,
        query=query,
    )
    params = query["params"]
    try:
        response = reader(
            symbol=str(params["symbol"]),
            date_et=str(params["start_date"]),
            time_of_day_et=str(params["time_of_day"]),
            right=str(params["right"]),
            max_dte=int(params["max_dte"]),
            strike_range=params.get("strike_range"),
        )
    except ThetaDataError as exc:
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData provider request failed after durable intent; "
            "do not automatically retry"
        ) from exc
    return _write_response(
        body_path=body_path,
        receipt_path=receipt_path,
        intent_path=intent_path,
        query=query,
        plan_fingerprint=plan_fingerprint,
        qualification_fingerprint=qualification_fingerprint,
        response=response,
    )


def _write_checkpoint(
    settings: AtlasSettings,
    report: dict[str, Any],
) -> None:
    atomic_write_text(
        _checkpoint_path(settings, report["plan_fingerprint"]),
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )


def run_thetadata_candidate_surface_cache_v1(
    settings: AtlasSettings,
    plan: dict[str, Any],
    qualification: dict[str, Any],
    *,
    max_new_requests: int = 0,
    workers: int = 4,
    authorize_provider_reads: bool = False,
    reader: Callable[..., ThetaDataResponse] = option_at_time_quote_surface,
) -> dict[str, Any]:
    _validate_plan_and_qualification(plan, qualification)
    if (
        type(max_new_requests) is not int
        or not 0 <= max_new_requests <= MAX_REQUESTS
        or type(workers) is not int
        or not 1 <= workers <= MAX_WORKERS
    ):
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData request/concurrency cap invalid"
        )
    live = max_new_requests > 0
    if live != bool(authorize_provider_reads):
        raise ThetaDataCandidateSurfaceCacheError(
            "provider reads require both explicit authorization and positive request cap"
        )

    settings.assert_external_storage_binding("options")
    queries = list(plan["provider_request_contract"]["full_surface_queries"])
    if len(queries) != EXPECTED_UNIQUE_SURFACES:
        raise ThetaDataCandidateSurfaceCacheError(
            "ThetaData acquisition request denominator changed"
        )
    for query in queries:
        _validate_query(query)
    queries.sort(
        key=lambda item: (
            item["params"]["start_date"],
            item["params"]["symbol"],
            item["source_query_fingerprint"],
        )
    )

    report: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "PREVIEW" if not live else "RUNNING",
        "plan_fingerprint": plan["plan_fingerprint"],
        "qualification_fingerprint": qualification["qualification_fingerprint"],
        "decision_spot_fingerprint": plan["decision_spot_fingerprint"],
        "candidate_surface_requests": len(queries),
        "verified_cached_complete": 0,
        "verified_cached_no_data": 0,
        "pending_before_run": 0,
        "new_provider_attempts": 0,
        "new_complete": 0,
        "new_no_data": 0,
        "new_raw_bytes": 0,
        "workers": workers,
        "max_new_requests": max_new_requests,
        "provider_writes": 0,
        "option_exit_prices_read": 0,
        "single_contract_selected": False,
        "historical_fill_authority": False,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }

    pending: list[dict[str, Any]] = []
    for query in queries:
        body_path, receipt_path, intent_path = _cache_paths(
            settings,
            plan_fingerprint=plan["plan_fingerprint"],
            source_query_fingerprint=query["source_query_fingerprint"],
        )
        receipt = _read_intact(
            body_path=body_path,
            receipt_path=receipt_path,
            intent_path=intent_path,
            query=query,
            plan_fingerprint=plan["plan_fingerprint"],
            qualification_fingerprint=qualification["qualification_fingerprint"],
        )
        if receipt is None:
            pending.append(query)
        elif receipt["status"] == "COMPLETE_CANDIDATE_SURFACE":
            report["verified_cached_complete"] += 1
        else:
            report["verified_cached_no_data"] += 1

    report["pending_before_run"] = len(pending)
    if not live:
        report["status"] = (
            "COMPLETE_LOCAL_CACHE"
            if not pending
            else "PREVIEW_PENDING_SOURCE_REQUESTS"
        )
        report["pending_after_run"] = len(pending)
        report["complete_after_run"] = report["verified_cached_complete"]
        report["no_data_after_run"] = report["verified_cached_no_data"]
        report["cache_fingerprint"] = _fingerprint(report)
        return report

    lock = _lock_path(settings, plan["plan_fingerprint"])
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ThetaDataCandidateSurfaceCacheError(
            f"ThetaData acquisition lock already exists: {lock}; review process/cache before cleanup"
        ) from exc

    try:
        with os.fdopen(lock_fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "contract": CONTRACT,
                "plan_fingerprint": plan["plan_fingerprint"],
                "qualification_fingerprint": qualification["qualification_fingerprint"],
                "started_at_utc": datetime.now(UTC).isoformat(),
                "automatic_cleanup_after_normal_completion": True,
            }, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

        remaining = list(pending)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while remaining and report["new_provider_attempts"] < max_new_requests:
                batch_size = min(
                    workers,
                    len(remaining),
                    max_new_requests - report["new_provider_attempts"],
                )
                try:
                    assert_category_acquisition_allowed(
                        settings,
                        category="options_candidate_cache",
                        projected_additional_bytes=(
                            batch_size * (MAX_RAW_BYTES + PROJECTED_RECEIPT_BYTES)
                        ),
                    )
                except ResearchStorageError as exc:
                    report["status"] = "PARTIAL_STORAGE_BLOCKED"
                    report["storage_error"] = str(exc)
                    break

                batch = [remaining.pop(0) for _ in range(batch_size)]
                futures = {
                    pool.submit(
                        _transport_one,
                        settings=settings,
                        plan_fingerprint=plan["plan_fingerprint"],
                        qualification_fingerprint=qualification["qualification_fingerprint"],
                        query=query,
                        reader=reader,
                    ): query
                    for query in batch
                }
                for future in as_completed(futures):
                    report["new_provider_attempts"] += 1
                    try:
                        receipt = future.result()
                    except Exception as exc:
                        report["status"] = "STOPPED_UNCERTAIN_PROVIDER_ATTEMPT"
                        report["error"] = f"{type(exc).__name__}: {exc}"
                        report["pending_after_run"] = (
                            len(remaining)
                            + sum(1 for item in futures if not item.done())
                        )
                        _write_checkpoint(settings, report)
                        raise
                    report["new_raw_bytes"] += int(receipt["body_bytes"])
                    if receipt["status"] == "COMPLETE_CANDIDATE_SURFACE":
                        report["new_complete"] += 1
                    else:
                        report["new_no_data"] += 1
                    if (
                        report["new_provider_attempts"] % 25 == 0
                        or report["new_provider_attempts"] == max_new_requests
                    ):
                        _write_checkpoint(settings, report)

        complete = report["verified_cached_complete"] + report["new_complete"]
        no_data = report["verified_cached_no_data"] + report["new_no_data"]
        pending_after = len(queries) - complete - no_data
        report["complete_after_run"] = complete
        report["no_data_after_run"] = no_data
        report["pending_after_run"] = pending_after
        if report["status"] == "RUNNING":
            report["status"] = (
                "COMPLETE_SOURCE_CACHE"
                if pending_after == 0
                else "PARTIAL_REQUEST_CAP"
            )
        report["cache_fingerprint"] = _fingerprint(report)
        _write_checkpoint(settings, report)
        return report
    finally:
        if lock.exists() and report.get("status") != "STOPPED_UNCERTAIN_PROVIDER_ATTEMPT":
            lock.unlink()
