from __future__ import annotations

"""SPY options exit source campaign using one authenticated ThetaData session.

Reuses the exact frozen V19 1,570 query identities, immutable started/terminal
receipts, original SHA+gzip archive and independent source qualification.
Unlike V19, this dispatcher does NOT create four independently authenticated
provider processes. It submits 1..4 independent query IDs within one isolated
SDK process whose derived ThetaClients share an authorized base session.
No exact preexisting original is retried. No simulator runs or fill promotion.
"""

from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_at_time_one_call_v1 import _load_full_manifest
from packages.data.options_native_exit_source_campaign_v1 import (
    CONTRACT, MAX_INVALID_SCHEMAS_PER_RUN, SpyExitSourceError,
    _ConservativeExitStorageMeter, _demand, _diagnose, _evidence,
    _receipt, _save_original, _safe_provider_failure_category,
    _sdk_request, _state, _write_receipt, preview_exit_campaign,
)
from packages.data.research_storage import inspect_research_storage
from packages.providers.thetadata.client import (
    ThetaDataError, ThetaDataResponse,
    option_at_time_quote_shared_session_batch,
)


def run_shared_exit_campaign(
    settings: AtlasSettings,
    manifest_path: Path,
    candidate_plan: Path,
    *,
    max_calls: int | None = None,
    reader: Callable[[list[dict[str, Any]]], list[
        ThetaDataResponse | ThetaDataError
    ]] = option_at_time_quote_shared_session_batch,
    storage_reader: Callable[..., Any] = inspect_research_storage,
    progress: Callable[[dict[str, Any]], None] | None = None,
    progress_every: int = 4,
) -> dict[str, Any]:
    """Bounded shared authenticated SDK batching with immutable per-ID proof."""
    if max_calls is not None and (
        type(max_calls) is not int or max_calls < 1
    ):
        raise SpyExitSourceError("SHARED_SESSION_MAX_CALLS_INVALID")
    if type(progress_every) is not int or progress_every < 1:
        raise SpyExitSourceError("SHARED_SESSION_PROGRESS_CADENCE_INVALID")
    before = preview_exit_campaign(
        settings, manifest_path, candidate_plan,
        storage_reader=storage_reader,
    )
    plan = _demand(_load_full_manifest(settings, manifest_path, candidate_plan))
    result = {
        "contract": CONTRACT,
        "mode": "SHARED_AUTHENTICATED_SESSION_BATCH_SOURCE_ONLY",
        "plan_fingerprint": plan["plan_fingerprint"],
        "account_authenticated_sessions": 1,
        "max_concurrent_queries_per_batch": 4,
        "provider_calls_this_run": 0,
        "completed_provider_calls_this_run": 0,
        "archives_this_run": 0,
        "outside_dte_archives_this_run": 0,
        "invalid_archives_this_run": 0,
        "provider_faults_this_run": 0,
        "full_storage_audits_this_run": 0,
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
    meter = _ConservativeExitStorageMeter(settings, storage_reader)
    index = 0
    stopped = False
    while index < len(eligible) and not stopped:
        batch: list[tuple[dict[str, Any], dict[str, Any]]] = []
        while index < len(eligible) and len(batch) < 4 and (
            max_calls is None
            or result["provider_calls_this_run"] < max_calls
        ):
            if not meter.allow_next():
                result["stop_reason"] = "SHARED_STORAGE_HEADROOM_INSUFFICIENT"
                stopped = True
                break
            req = eligible[index]
            started = _evidence({
                "contract": CONTRACT, "kind": "started",
                "plan_fingerprint": plan["plan_fingerprint"],
                "session_et": req["session_et"],
                "query_id": req["query_id"],
                "sdk_kwargs": _sdk_request(req),
                "state": "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY",
                "source_complete": False, "simulator_ready": False,
            })
            _write_receipt(
                settings, req, plan["plan_fingerprint"], "started", started,
            )
            batch.append((req, started))
            index += 1
            result["provider_calls_this_run"] += 1
        if not batch:
            break
        try:
            observations = reader([
                _sdk_request(req) for req, _ in batch
            ])
            if (not isinstance(observations, list)
                    or len(observations) != len(batch)):
                raise SpyExitSourceError("SHARED_BATCH_RESPONSE_COUNT_DRIFT")
        except Exception as exc:
            # All pre-dispatched identities are unknown if whole-batch RPC
            # fails; terminal receipts must be persisted, not retried.
            observations = [exc] * len(batch)
        for (req, started), observed in zip(batch, observations):
            archive = None
            state = "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
            error_type = None
            provider_class = None
            grpc_status = None
            try:
                if isinstance(observed, Exception):
                    raise observed
                if not isinstance(observed, ThetaDataResponse):
                    raise SpyExitSourceError("SHARED_BATCH_ITEM_TYPE_UNQUALIFIED")
                if observed.rows:
                    archive = _save_original(settings, req, observed)
                try:
                    state = _diagnose(req, observed)
                except Exception as exc:
                    error_type = type(exc).__name__
                    provider_class, grpc_status = (
                        _safe_provider_failure_category(exc)
                    )
                    if archive is not None:
                        state = "RAW_ARCHIVED_INVALID_SCHEMA"
            except Exception as exc:
                error_type = type(exc).__name__
                provider_class, grpc_status = (
                    _safe_provider_failure_category(exc)
                )
                if archive is not None:
                    state = "RAW_ARCHIVED_INVALID_SCHEMA"
            terminal = _evidence({
                "contract": CONTRACT, "kind": "terminal",
                "plan_fingerprint": plan["plan_fingerprint"],
                "session_et": req["session_et"], "query_id": req["query_id"],
                "started_fingerprint": started["fingerprint"],
                "archive": archive, "state": state,
                "error_type": error_type,
                "provider_failure_class": provider_class,
                "provider_grpc_status": grpc_status,
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
            if state == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY":
                result["provider_faults_this_run"] += 1
            count = result["completed_provider_calls_this_run"]
            if progress is not None and (
                count % progress_every == 0
                or state == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
                or (max_calls is not None and count == max_calls)
            ):
                progress({
                    "calls": count,
                    "archived": result["archives_this_run"],
                    "over_dte": result["outside_dte_archives_this_run"],
                    "date_et": req["session_et"],
                    "query_id": req["query_id"],
                    "state": state,
                    "provider_failure_class": provider_class,
                    "provider_grpc_status": grpc_status,
                    "simulator_ready": False,
                })
        if result["provider_faults_this_run"]:
            result["stop_reason"] = "PROVIDER_OR_STORAGE_FAILURE_STOP"
            stopped = True
        elif (result["invalid_archives_this_run"]
              >= MAX_INVALID_SCHEMAS_PER_RUN):
            result["stop_reason"] = "REPEATED_INVALID_SOURCE_SCHEMA_STOPPED_RUN"
            stopped = True
        elif (max_calls is not None
              and result["provider_calls_this_run"] == max_calls
              and index < len(eligible)):
            result["stop_reason"] = "OPTIONAL_GLOBAL_CALL_LIMIT_REACHED"
            stopped = True
    result["full_storage_audits_this_run"] = meter.full_audits
    return result
