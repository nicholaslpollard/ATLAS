from __future__ import annotations

"""V17 bounded parallel acquisition of immutable V9/V12 at-time option sources.

Only independent provider calls execute on worker threads. The coordinator
alone writes V12 started/terminal receipts, gzip archives and checks storage;
thus no two tasks write the same identity or compete to commit an original.
Thread-local ThetaData Python-library subprocesses already exist in the
isolated provider adapter. The Standard subscription supports at most four
account-wide in-flight calls; this runner caps itself at four.

Do not run this alongside another ThetaData acquisition process. The limit
is account-wide and this process cannot reserve slots owned by other tools.
No automatic retry after an ambiguous attempt, crash or worker failure.
No source qualification, fills, outcomes, or trading authority.
"""

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_at_time_one_call_v1 import _load_full_manifest
from packages.data.hybrid_options_at_time_source_gate_v1 import (
    diagnose_at_time_response, validate_exact_request,
)
from packages.data.hybrid_options_unattended_campaign_v1 import (
    CONTRACT, MIN_CAPACITY_PER_REQUEST, HybridCampaignError,
    _evidence, _inspect_attempt, _prior_external_source_ids,
    _safe_storage, _store_entire_source, _write_receipt, preview_campaign,
)
from packages.data.research_storage import inspect_research_storage
from packages.providers.thetadata.client import (
    ThetaDataResponse, option_at_time_quote_surface,
)

MAX_STANDARD_WORKERS = 4


def _finish(
    settings: AtlasSettings, row: dict[str, Any],
    started: dict[str, Any], future: Future,
    results: dict[str, Any],
) -> str:
    """Commit one already-dispatched result in the coordinator only."""
    qid = row["query_id"]
    diagnostic = None
    archive = None
    error_type = None
    state = "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
    try:
        source = future.result()
        if not isinstance(source, ThetaDataResponse):
            raise HybridCampaignError("SOURCE_RESPONSE_TYPE_CHANGED")
        if source.rows:
            archive = _store_entire_source(settings, qid, source)
            try:
                diagnostic = diagnose_at_time_response(row, source)
                state = (
                    "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC"
                    if diagnostic["outside_requested_dte_rows"] > 0
                    else "RAW_ARCHIVED_SCOPE_DIAGNOSTIC"
                )
            except Exception as exc:
                error_type = type(exc).__name__
                state = "RAW_ARCHIVED_INVALID_SCHEMA"
        else:
            diagnostic = diagnose_at_time_response(row, source)
            state = (
                "EXPLICIT_NO_DATA_SOURCE_ONLY"
                if diagnostic["status"] == "EXPLICIT_NO_DATA_NOT_COVERAGE"
                else "EMPTY_RESPONSE_SOURCE_ONLY"
            )
    except Exception as exc:
        error_type = type(exc).__name__
        if archive is not None:
            state = "RAW_ARCHIVED_INVALID_SCHEMA"
    finished = _evidence({
        "contract": CONTRACT, "kind": "terminal",
        "manifest_fingerprint": results["manifest_fingerprint"],
        "query_id": qid, "started_fingerprint": started["fingerprint"],
        "state": state, "archive": archive,
        "diagnostic_fingerprint": (
            diagnostic["diagnostic_fingerprint"] if diagnostic else None
        ),
        "error_type": error_type,
        "simulator_ready": False, "source_coverage_proven": False,
    })
    _write_receipt(settings, qid, "terminal", finished)
    results["completed_provider_calls_this_run"] += 1
    if archive is not None:
        results["archives_written_this_run"] += 1
    if state == "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC":
        results["out_of_dte_archives_this_run"] += 1
    if state == "RAW_ARCHIVED_INVALID_SCHEMA":
        results["invalid_schema_archives_this_run"] += 1
    return state


def run_parallel_campaign(
    settings: AtlasSettings, manifest_path: Path, candidate_plan: Path,
    *,
    workers: int,
    max_calls: int | None = None,
    reader: Callable[..., ThetaDataResponse] = option_at_time_quote_surface,
    storage_reader: Callable[..., Any] = inspect_research_storage,
    progress: Callable[[dict[str, Any]], None] | None = None,
    progress_every: int = 25,
    allowed_origin: str | None = None,
) -> dict[str, Any]:
    """Parallel network reads; serialized provenance; no silent retry."""
    if type(workers) is not int or not 2 <= workers <= MAX_STANDARD_WORKERS:
        raise HybridCampaignError("PARALLEL_WORKERS_MUST_BE_2_TO_4")
    if max_calls is not None and (
        type(max_calls) is not int or max_calls < 1
    ):
        raise HybridCampaignError("MAX_CALLS_MUST_BE_POSITIVE_OR_OMITTED")
    if type(progress_every) is not int or progress_every < 1:
        raise HybridCampaignError("PROGRESS_CADENCE_MUST_BE_POSITIVE")
    if allowed_origin not in {
        None, "FROZEN_SPY_WEEKLY_OPTIONS_NATIVE",
        "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES",
    }:
        raise HybridCampaignError("ORIGIN_MUST_MATCH_EXACT_FROZEN_BRANCH")

    snapshot = preview_campaign(
        settings, manifest_path, candidate_plan, storage_reader=storage_reader,
    )
    frozen = _load_full_manifest(settings, manifest_path, candidate_plan)
    if frozen["source_request_count"] != 9866:
        raise HybridCampaignError("EXACT_PINNED_CAMPAIGN_SCOPE_DRIFT")
    excluded = _prior_external_source_ids(
        settings, frozen, candidate_plan, manifest_path,
    )
    results = {
        "contract": CONTRACT, "mode": "BOUNDED_PARALLEL_SOURCE_ACQUISITION",
        "manifest_fingerprint": frozen["manifest_fingerprint"],
        "provider_calls_this_run": 0,
        "completed_provider_calls_this_run": 0,
        "archives_written_this_run": 0,
        "out_of_dte_archives_this_run": 0,
        "invalid_schema_archives_this_run": 0,
        "skipped_existing_or_ambiguous": 0,
        "stop_reason": "FULL_FROZEN_MANIFEST_SCANNED",
        "last_query_id": None,
        "max_workers": workers,
        "simulator_ready": False, "source_coverage_proven": False,
    }
    if not snapshot["storage"]["safe"]:
        results["stop_reason"] = "SAFE_STORAGE_HEADROOM_INSUFFICIENT"
        return results

    eligible: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in frozen["requests"]:
        if allowed_origin is not None and row["origin"] != allowed_origin:
            continue
        qid = row["query_id"]
        if qid in excluded or _inspect_attempt(settings, qid) != "UNATTEMPTED":
            results["skipped_existing_or_ambiguous"] += 1
            continue
        # Validate every remaining query before any new paid dispatch.
        eligible.append((row, validate_exact_request(row)))

    cursor = 0
    stop_new = False
    pending: dict[Future, tuple[dict[str, Any], dict[str, Any]]] = {}
    with ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix="atlas-thetadata-standard",
    ) as pool:
        while cursor < len(eligible) or pending:
            while (
                not stop_new and cursor < len(eligible)
                and len(pending) < workers
                and (max_calls is None
                     or results["provider_calls_this_run"] < max_calls)
            ):
                budget = _safe_storage(settings, storage_reader)
                # Reserve worst-case bytes for ALL unfinished requests,
                # not just the one about to be dispatched.
                required = MIN_CAPACITY_PER_REQUEST * (len(pending) + 1)
                if (
                    not budget["safe"]
                    or budget["available_after_hourly_reservations"] < required
                ):
                    results["stop_reason"] = "SAFE_STORAGE_HEADROOM_INSUFFICIENT"
                    stop_new = True
                    break
                row, sdk = eligible[cursor]
                qid = row["query_id"]
                # Coordinator owns all receipt/file writes; a crash between
                # STARTED and dispatch is conservatively non-retryable.
                started = _evidence({
                    "contract": CONTRACT, "kind": "started",
                    "state": "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY",
                    "manifest_fingerprint": frozen["manifest_fingerprint"],
                    "query_id": qid,
                    "original_query_fingerprint": row[
                        "origin_query_fingerprint"
                    ],
                    "sdk_kwargs": sdk,
                    "simulator_ready": False, "source_coverage_proven": False,
                })
                _write_receipt(settings, qid, "started", started)
                results["provider_calls_this_run"] += 1
                results["last_query_id"] = qid
                future = pool.submit(reader, **sdk)
                pending[future] = (row, started)
                cursor += 1
            if (
                not stop_new and cursor < len(eligible)
                and max_calls is not None
                and results["provider_calls_this_run"] >= max_calls
            ):
                results["stop_reason"] = "OPTIONAL_RUN_REQUEST_LIMIT_REACHED"
                stop_new = True
            if not pending:
                break
            done, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            # Stable deterministic local terminal ordering for simultaneous
            # completions; provider calls have already been dispatched.
            for future in sorted(done, key=lambda f: pending[f][0]["priority"]):
                row, started = pending.pop(future)
                state = _finish(settings, row, started, future, results)
                count = results["completed_provider_calls_this_run"]
                if progress is not None and (
                    count % progress_every == 0
                    or state == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
                    or (max_calls is not None and count == max_calls)
                ):
                    progress({
                        "completed_calls": count,
                        "archived": results["archives_written_this_run"],
                        "out_of_dte": results["out_of_dte_archives_this_run"],
                        "invalid": results["invalid_schema_archives_this_run"],
                        "last_date": row["date_et"],
                        "last_symbol": row["symbol"],
                        "last_request_id": row["query_id"],
                        "state": state, "simulator_ready": False,
                    })
                if state == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY":
                    results["stop_reason"] = (
                        "PROVIDER_OR_STORAGE_FAILURE_STOPPED_RUN"
                    )
                    stop_new = True
    return results
