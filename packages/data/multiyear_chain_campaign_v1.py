from __future__ import annotations

"""Resumable, year-balanced historical chain acquisition for accepted 2021–2025 cases.

The four accepted local manifests are the starting evidence. Never reconstruct
the original stock selection, rescan the full old cache, or turn 2026 protected
outcomes into historical signals. Every genuinely new response is saved to the
existing D:-bound global physical cache before any quote-series selection.
"""

import os
import shutil
import time
import uuid
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    MAX_RAW_BYTES, CandidateChainCacheError, _assert_request_shape,
    _create_attempt, _expected_no_data_proof, _fingerprint, _no_data_path,
    _paths, _valid_receipt, _verified_no_data, _write_raw_and_receipt,
)
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object
from packages.data.research_storage import inspect_research_storage
from packages.providers.marketdata_app.client import (
    MarketDataResponse, get_json, rate_limit_snapshot,
)

CONTRACT = "atlas-multiyear-year-balanced-chain-acquisition-v1"
DEMAND_FP = "7890c81e62905307fb1cc2c1bf3f2205eece3dfdf04b712ee1b8a09d419f084c"
OVERLAP_FP = "056c70bc7163b793b3c4cc2c83bee48b19272d95171f8dee8c9d296b5c65d30b"
DEMAND_NAME = "multiyear_physical_chain_source_demand_v1_45bb0490a38d2b0b.json"
OVERLAP_NAME = "multiyear_global_chain_cache_overlap_v1_7890c81e62905307_98b593314e415ae5.json"
MANIFEST_REL = "data/options/manifests"
MISSING = "NO_LOCAL_MATCHING_PHYSICAL_CHAIN_SOURCE"
REUSED = "REUSED_VERIFIED_LOCAL_COMPLETE_CHAIN_FULL_STRIKE_COVERAGE"
NO_DATA = "VERIFIED_NO_DATA_FOR_EXACT_ORIGINAL_QUERY_ONLY"
MIN_REMAINING = 500
MAX_WORKERS = 24
MAX_NEW_REQUESTS = 7574
EASTERN = ZoneInfo("America/New_York")


class MultiYearChainCampaignError(RuntimeError):
    pass


def _floor(today: date) -> date:
    try:
        return today.replace(year=today.year - 5)
    except ValueError:
        return today.replace(year=today.year - 5, day=28)


def _signed(path: Path, signature: str, expected: str) -> dict[str, Any]:
    result = _read_object(path)
    body = dict(result)
    if body.pop(signature, None) != expected or _fingerprint(body) != expected:
        raise MultiYearChainCampaignError("frozen accepted source signature changed")
    return result


def read_accepted_source(settings: AtlasSettings) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read two small accepted manifests only; original raw bodies stay closed."""
    settings.assert_external_storage_binding("options")
    root = settings.resolved_path(MANIFEST_REL)
    demand = _signed(root / DEMAND_NAME, "demand_fingerprint", DEMAND_FP)
    overlap = _signed(root / OVERLAP_NAME, "overlap_fingerprint", OVERLAP_FP)
    if (
        demand.get("unique_unreconciled_physical_preview_queries") != 7646
        or demand.get("case_denominator") != 14902
        or demand.get("original_2022_exact_quote_histories_reused_by_pointer_only") != 6398
        or overlap.get("source_demand_fingerprint") != DEMAND_FP
        or overlap.get("accepted_case_denominator") != 14902
        or overlap.get("unique_physical_preview_queries") != 7646
        or overlap.get("provider_requests") != 0
    ):
        raise MultiYearChainCampaignError("accepted cohort or original local overlap changed")
    return demand, overlap


def freeze_execution_order(
    demand: dict[str, Any], overlap: dict[str, Any],
) -> dict[str, Any]:
    """Pure conversion from the already audited physical identities to a balanced queue."""
    requests = demand["requests"]
    observations = overlap["rows"]
    if len(requests) != len(observations) or len(requests) != 7646:
        raise MultiYearChainCampaignError("accepted physical count changed")
    known = {r["physical_request_identity"]: r for r in observations}
    if len(known) != len(observations):
        raise MultiYearChainCampaignError("duplicate physical overlap identity")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    statuses: Counter[str] = Counter()
    seen: set[str] = set()
    for ticket in requests:
        identity = ticket["physical_request_identity"]
        prior = known.get(identity)
        if prior is None or identity in seen:
            raise MultiYearChainCampaignError("source request missing or duplicated")
        seen.add(identity)
        year = ticket["snapshot_date"][:4]
        if (
            year not in {"2021", "2022", "2023", "2024", "2025"}
            or prior["key"] != [
                ticket["ticker"], ticket["snapshot_date"], ticket["expiration"]
            ]
            or prior["case_ids"] != ticket["member_case_ids"]
            or prior["requested_strike_window"] != ticket["params"]["strike"].split("-")
            or ticket["request_sides"] != ["call", "put"]
        ):
            raise MultiYearChainCampaignError("physical identity or year membership changed")
        status = prior["source_status"]
        if status not in {MISSING, REUSED, NO_DATA}:
            raise MultiYearChainCampaignError("unresolved local source may not be retried")
        statuses[status] += 1
        if status == MISSING:
            request = {
                "request_identity": identity,
                "ticker": ticket["ticker"],
                "endpoint": ticket["endpoint"],
                "params": ticket["params"],
                "bounded_query": True,
            }
            _assert_request_shape(request)
            if prior["intersecting_orphan_attempt_ids"] or prior["verified_existing_overlaps"]:
                raise MultiYearChainCampaignError("missing source has prior unresolved evidence")
            groups[year].append(request)
    if (
        statuses != Counter({MISSING: 7574, REUSED: 71, NO_DATA: 1})
        or len(seen) != 7646
    ):
        raise MultiYearChainCampaignError("accepted exact cache disposition changed")
    buckets = {year: deque(sorted(groups[year], key=lambda x: (
        x["params"]["date"], x["ticker"], x["params"]["expiration"],
        x["params"]["strike"], x["request_identity"],
    ))) for year in ("2021", "2022", "2023", "2024", "2025")}
    ordered: list[dict[str, Any]] = []
    while any(buckets.values()):
        for year in buckets:
            if buckets[year]:
                ordered.append(buckets[year].popleft())
    plan = {
        "contract": CONTRACT,
        "source_demand_fingerprint": DEMAND_FP,
        "source_overlap_fingerprint": OVERLAP_FP,
        "original_case_denominator": 14902,
        "original_2022_exact_quote_histories_pointer_reused": 6398,
        "preexisting_complete_physical_sources": 71,
        "preexisting_exact_no_data_physical_queries": 1,
        "missing_physical_sources": 7574,
        "by_year_missing": {year: len(groups[year]) for year in buckets},
        "requests": ordered,
        "no_2026_replayed_signal_or_option_fill_authority": True,
    }
    plan["plan_fingerprint"] = _fingerprint(plan)
    return plan


def _capture(
    settings: AtlasSettings, request: dict[str, Any], plan_fp: str,
    run_id: str, reader: Callable[[str, dict[str, str]], MarketDataResponse],
) -> dict[str, Any]:
    """One request, original intent and exact-body receipt, never an automatic retry."""
    identity = request["request_identity"]
    paths = _paths(settings, identity)
    prior = _valid_receipt(paths, request)
    if prior is not None:
        return {
            "request_identity": identity, "status": "REUSED_EXISTING_EXACT_SOURCE",
            "credits": 0, "body_bytes": 0, "remaining": None,
        }
    _create_attempt(paths, request, run_id=run_id, plan_fingerprint=plan_fp)
    response = reader(request["endpoint"], request["params"])
    rates = rate_limit_snapshot(response.headers)
    try:
        receipt = _write_raw_and_receipt(paths, request, response)
    except CandidateChainCacheError:
        # The original 404 raw body, quarantine receipt and attempt already
        # exist. Only a strict zero-credit exact no_data proof may become terminal.
        if response.http_status != 404:
            raise
        proof = _expected_no_data_proof(paths, request)
        no_data_path = _no_data_path(paths)
        if not no_data_path.exists():
            _exclusive(no_data_path, proof)
        if _verified_no_data(paths, request) != proof:
            raise MultiYearChainCampaignError("exact 404 proof readback differs")
        return {
            "request_identity": identity, "status": "EXACT_QUERY_NO_DATA_PROVEN",
            "credits": 0, "body_bytes": proof["body_bytes"],
            "remaining": rates["remaining"],
        }
    return {
        "request_identity": identity, "status": "NEW_COMPLETE",
        "credits": rates["consumed"], "body_bytes": receipt["body_bytes"],
        "remaining": rates["remaining"],
    }


def _next_wave_size(
    *, outstanding: int, workers: int, observed_credits: int,
    max_observed_credits: int, remaining: int | None,
    min_remaining_credits: int,
) -> tuple[int, str | None]:
    """Reserve two potential credits per in-flight GET, shrinking the final wave."""
    budget_slots = (max_observed_credits - observed_credits) // 2
    if budget_slots < 1:
        return 0, "PARTIAL_OBSERVED_CREDIT_BUDGET"
    if remaining is not None:
        provider_slots = (remaining - min_remaining_credits) // 2
        if provider_slots < 1:
            return 0, "PARTIAL_PROVIDER_CREDIT_FLOOR"
        budget_slots = min(budget_slots, provider_slots)
    return min(outstanding, workers if remaining is not None else 1, budget_slots), None


def run_campaign(
    settings: AtlasSettings, *,
    max_new_requests: int = 0, max_observed_credits: int = 0,
    workers: int = 16, min_remaining_credits: int = MIN_REMAINING,
    authorize_provider_reads: bool = False,
    confirm_paid_starter: bool = False, confirm_private_internal_use: bool = False,
    token: str | None = None,
    reader: Callable[[str, dict[str, str]], MarketDataResponse] | None = None,
    today: date | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    demand, overlap = read_accepted_source(settings)
    plan = freeze_execution_order(demand, overlap)
    if (
        type(max_new_requests) is not int
        or type(max_observed_credits) is not int
        or not 0 <= max_new_requests <= MAX_NEW_REQUESTS
        or not 0 <= max_observed_credits <= MAX_NEW_REQUESTS * 2
        or (max_new_requests == 0) != (max_observed_credits == 0)
        or type(workers) is not int or not 1 <= workers <= MAX_WORKERS
        or type(min_remaining_credits) is not int
        or not 0 <= min_remaining_credits <= 10000
    ):
        raise MultiYearChainCampaignError("invalid explicit request/credit/worker ceilings")
    live = max_new_requests > 0
    if live != all((authorize_provider_reads, confirm_paid_starter, confirm_private_internal_use)):
        raise MultiYearChainCampaignError("all three paid operator confirmations are required")
    if live and not (token or os.getenv("MARKETDATA_TOKEN", "")).strip() and reader is None:
        raise MultiYearChainCampaignError("MARKETDATA_TOKEN not configured")
    if today is None:
        today = datetime.now(EASTERN).date()
    floor = _floor(today)
    by_year = Counter()
    rolled = Counter()
    existing = Counter()
    queued: list[dict[str, Any]] = []
    for request in plan["requests"]:
        year = request["params"]["date"][:4]
        # The accepted overlap already verified the original 71 reuse cases.
        # Only the 7,574 original misses require a current exact-receipt lookup.
        prior = _valid_receipt(_paths(settings, request["request_identity"]), request)
        if prior is not None:
            existing[year] += 1
        elif date.fromisoformat(request["params"]["date"]) < floor:
            rolled[year] += 1
        else:
            queued.append(request)
            by_year[year] += 1
    report: dict[str, Any] = {
        "contract": CONTRACT,
        "plan_fingerprint": plan["plan_fingerprint"],
        "status": "OFFLINE_PREVIEW" if not live else "RUNNING",
        "accepted_cases": 14902,
        "existing_2022_quote_series_pointer_reused": 6398,
        "original_missing": 7574,
        "preexisting_global_complete": 71,
        "preexisting_global_exact_no_data": 1,
        "newly_reused_exact_source": dict(sorted(existing.items())),
        "current_rolling_floor": floor.isoformat(),
        "rolled_out_of_current_provider_window": dict(sorted(rolled.items())),
        "pending_by_year": dict(sorted(by_year.items())),
        "pending_eligible": len(queued),
        "new_attempts": 0,
        "new_complete": 0,
        "exact_no_data": 0,
        "observed_credits": 0,
        "new_raw_bytes": 0,
        "new_complete_by_year": {},
        "last_reported_remaining": None,
        "max_new_requests": max_new_requests,
        "max_observed_credits": max_observed_credits,
        "min_remaining_credits": min_remaining_credits,
        "workers": workers,
        "provider_calls_in_preview": 0,
        "2026_new_accepted_replay_cases": 0,
        "quote_selection_or_option_pnl_authority": False,
    }
    if not live:
        return report
    storage = inspect_research_storage(settings)
    if storage.storage_mode != "EXTERNAL_SECONDARY" or storage.status == "BLOCKED_MINIMUM_FREE_SPACE":
        raise MultiYearChainCampaignError("ready D: external storage required")
    available_gib = min(
        storage.remaining_acquisition_budget_gib,
        storage.maximum_safe_additional_gib,
        storage.category_quota_gib["options_candidate_cache"]
            - storage.category_usage_gib["options_candidate_cache"],
    )
    if available_gib <= 0:
        raise MultiYearChainCampaignError("D: candidate cache budget exhausted")
    available_bytes = int(available_gib * 1024**3)
    report["D_initial_free_gib"] = storage.disk_free_gib
    report["D_initial_candidate_cache_gib"] = storage.category_usage_gib["options_candidate_cache"]
    root = settings.resolved_path(MANIFEST_REL)
    lock = root / "multiyear_chain_campaign_v1.lock"
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid.uuid4().hex[:8]
    run_path = root / f"multiyear_chain_campaign_v1_{run_id}.json"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise MultiYearChainCampaignError(
            "another acquisition/uncertain run owns the global campaign lock"
        ) from exc
    t0 = time.monotonic()
    from packages.core.atomic_io import atomic_write_text  # original durable manifest writer
    import json
    def checkpoint() -> None:
        report["elapsed_seconds"] = round(time.monotonic() - t0, 2)
        payload = dict(report)
        payload["report_fingerprint"] = _fingerprint(payload)
        atomic_write_text(run_path, json.dumps(payload, sort_keys=True, indent=2) + "\n")

    def transport(endpoint: str, params: dict[str, str]) -> MarketDataResponse:
        return get_json(
            endpoint, params=params, token=token, max_attempts=1,
            max_response_bytes=MAX_RAW_BYTES,
        )
    read = reader or transport
    remaining = None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"contract": CONTRACT, "run_id": run_id,
                                     "plan_fingerprint": plan["plan_fingerprint"]}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        report["run_report_path"] = str(run_path)
        checkpoint()
        selected = queued[:max_new_requests]
        year_for_identity = {
            request["request_identity"]: request["params"]["date"][:4]
            for request in selected
        }
        offset = 0
        while offset < len(selected):
            # First GET establishes the authoritative balance. Thereafter
            # shrink the final wave instead of refusing a full 24-worker batch.
            # Two credits are reserved per request despite typically lower
            # charges; a final 1-credit fragment remains unspent unless proven safe.
            wave_size, blocked = _next_wave_size(
                outstanding=len(selected) - offset, workers=workers,
                observed_credits=report["observed_credits"],
                max_observed_credits=max_observed_credits, remaining=remaining,
                min_remaining_credits=min_remaining_credits,
            )
            if blocked is not None:
                report["status"] = blocked
                break
            wave = selected[offset:offset + wave_size]
            worst = len(wave) * (MAX_RAW_BYTES + 16384)
            if (
                report["new_raw_bytes"] + worst > available_bytes
                or shutil.disk_usage(settings.external_data_root()).free
                    < int(storage.minimum_free_gib * 1024**3) + worst
            ):
                report["status"] = "PARTIAL_D_STORAGE_BUDGET"
                break
            results: list[dict[str, Any]] = []
            errors: list[str] = []
            with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                futures = {
                    pool.submit(
                        _capture, settings, request, plan["plan_fingerprint"],
                        run_id, read,
                    ): request for request in wave
                }
                for future in as_completed(futures):
                    request = futures[future]
                    try:
                        results.append(future.result())
                    except BaseException as exc:
                        errors.append(
                            f"{request['request_identity']}: {type(exc).__name__}: {exc}"
                        )
            # The whole started wave finishes and persists before any next wave.
            report["new_attempts"] += (
                sum(item["status"] != "REUSED_EXISTING_EXACT_SOURCE" for item in results)
                + len(errors)
            )
            for item in results:
                report["new_complete"] += item["status"] == "NEW_COMPLETE"
                if item["status"] == "NEW_COMPLETE":
                    year = year_for_identity[item["request_identity"]]
                    report["new_complete_by_year"][year] = (
                        report["new_complete_by_year"].get(year, 0) + 1
                    )
                report["exact_no_data"] += item["status"] == "EXACT_QUERY_NO_DATA_PROVEN"
                if type(item["credits"]) is int:
                    report["observed_credits"] += item["credits"]
                else:
                    errors.append("missing or malformed original credit header")
                report["new_raw_bytes"] += item["body_bytes"]
                if item["remaining"] is not None:
                    remaining = (
                        item["remaining"] if remaining is None
                        else min(remaining, item["remaining"])
                    )
            report["last_reported_remaining"] = remaining
            report["D_latest_free_gib"] = round(
                shutil.disk_usage(settings.external_data_root()).free / 1024**3, 3
            )
            checkpoint()
            if progress:
                progress({
                    "stage": "YEAR_BALANCED_CHAIN_WAVE", "new_attempts": report["new_attempts"],
                    "complete": report["new_complete"], "exact_no_data": report["exact_no_data"],
                    "credits": report["observed_credits"], "provider_remaining": remaining,
                    "batch_errors": len(errors), "D_new_raw_bytes": report["new_raw_bytes"],
                    "D_free_gib": report["D_latest_free_gib"],
                    "new_complete_by_year": dict(sorted(report["new_complete_by_year"].items())),
                })
            offset += len(wave)
            if errors:
                report["status"] = "STOP_UNCERTAIN_OR_QUARANTINED_OR_INVALID_RESPONSE"
                report["error_summaries"] = errors[:24]
                checkpoint()
                break
        if report["status"] == "RUNNING":
            report["status"] = (
                "COMPLETE_ELIGIBLE_SOURCE_WORK" if len(selected) == len(queued)
                else "PARTIAL_REQUEST_LIMIT_REACHED"
            )
        checkpoint()
        return report
    except BaseException:
        report["status"] = "STOP_EXCEPTION_REVIEW_ORIGINAL_EVIDENCE"
        checkpoint()
        raise
    finally:
        lock.unlink(missing_ok=True)
