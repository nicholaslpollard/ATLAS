from __future__ import annotations

"""One authorized, resumable 2022 additive chain + full monthly CALL EOD backfill.

No new physical provider contract: original source/intent/body/receipt/no-data
cache owns all GETs. Never issue both chain and quote stages concurrently.
"""

import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.backtesting.recurrent_successor_outcome_replay import load_selected_replay_opportunities
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data import marketdata_additive_2022_shards_v1 as shards
from packages.data.marketdata_2022_broad_quote_campaign_v2 import (
    PLAN_REL, freeze_broad_quote_plan, run_broad_quote_histories,
)
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, MIN_REMAINING_CREDITS, _fingerprint,
)
from packages.data.marketdata_candidate_expansion_v1 import (
    _exclusive, _read_object, _require_external, run_expansion,
)

CONTRACT = "atlas-marketdata-2022-additive-full-bulk-v1"
START_SHARD = 26
END_SHARD = 70
CENSUS_SHARDS = 71
MAX_CHAIN_WORKERS = 8
MAX_QUOTE_WORKERS = 24
MAX_NEW_REQUESTS = 12000
MAX_TOTAL_OBSERVED_CREDITS = 9000
MAX_CREDIT_WINDOWS = 2
QUOTE_CHUNK = 1024
RESET_ZONE = ZoneInfo("America/New_York")
REPORT_REL = "data/options/manifests/marketdata_2022_full_bulk_v1"


def _next_reset(now: datetime) -> datetime:
    """9:30 Eastern, including local DST transitions, plus 90 seconds of slack."""
    east = now.astimezone(RESET_ZONE)
    target = east.replace(hour=9, minute=31, second=30, microsecond=0)
    if east >= target:
        target = (east + timedelta(days=1)).replace(
            hour=9, minute=31, second=30, microsecond=0
        )
    return target


def _adapt_chain_workers(workers: int, previous_gets_per_second: float,
                         current_gets_per_second: float) -> int:
    """Use whole-wave GETs/s to adapt concurrent independent shard jobs."""
    if previous_gets_per_second and current_gets_per_second < previous_gets_per_second * 0.80:
        return max(2, workers - 2)
    if not previous_gets_per_second or current_gets_per_second >= previous_gets_per_second * 0.90:
        return min(MAX_CHAIN_WORKERS, workers + 2)
    return workers


def _adapt_quote_workers(workers: int, previous_gets_per_second: float,
                         current_gets_per_second: float, observed_gets: int) -> int:
    """Conservative cross-chunk AIMD; cap account-wide headroom at 24."""
    if observed_gets < 128:
        return workers
    if previous_gets_per_second and current_gets_per_second < previous_gets_per_second * 0.80:
        return max(8, workers - 4)
    if not previous_gets_per_second or current_gets_per_second >= previous_gets_per_second * 0.90:
        return min(MAX_QUOTE_WORKERS, workers + 4)
    return workers


def _check_lock(settings: AtlasSettings, run_id: str) -> Path:
    path = settings.resolved_path(f"{REPORT_REL}/acquisition.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"contract": CONTRACT, "run_id": run_id, "pid": os.getpid(),
            "created_at": datetime.now(RESET_ZONE).isoformat()}
    try:
        with path.open("x", encoding="utf-8") as f:
            f.write(json.dumps(data, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except FileExistsError as exc:
        raise CandidateChainCacheError(
            "another 2022 full-bulk run or unresolved killed process owns the lock; "
            "inspect process/intents before manual cleanup"
        ) from exc
    return path


def _source_plans(
    settings: AtlasSettings, *, duckdb_threads: int,
    progress: Callable[[dict[str, Any]], None],
    loader: Callable[..., Any] = load_selected_replay_opportunities,
) -> list[tuple[int, dict[str, Any], Path, int]]:
    """Verify every original key, freeze all new local sources, load native replay ONCE."""
    prior = shards._prior(settings)
    prior_fp = prior[0]["plan_fingerprint"]
    anchor = shards._read_bound(settings, 0, prior_fp)
    source_zero = _read_object(anchor[1])
    global_fp = source_zero["all_additive_query_keys_fingerprint"]
    if source_zero["total_additive_shards"] != CENSUS_SHARDS:
        raise CandidateChainCacheError("accepted 2022 global 71-shard census changed")
    cached_source = None
    loads = 0

    def load_once(*a: Any, **kw: Any) -> Any:
        nonlocal cached_source, loads
        if cached_source is None:
            cached_source = loader(*a, **kw)
            loads += 1
            progress({"stage": "ACCEPTED_2022_SOURCE_LOADED_ONCE",
                      "accepted_source_loads": loads})
        return cached_source

    plans: list[tuple[int, dict[str, Any], Path, int]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for index in range(CENSUS_SHARDS):
        if index == 0:
            plan, source_path, binding = anchor
            action = "REUSED_IMMUTABLE_ADDITIVE_SHARD"
        elif shards._binding_path(settings, index).exists():
            plan, source_path, binding = shards._read_bound(settings, index, prior_fp)
            action = "REUSED_IMMUTABLE_ADDITIVE_SHARD"
        else:
            plan, source_path, binding, action = shards.prepare_additive_shard(
                settings, shard_index=index, duckdb_threads=duckdb_threads,
                loader=load_once, verified_prior=prior,
                external_preflight_done=True,
                progress=lambda row, i=index: progress({"shard_index": i, **row})
                if row.get("stage") == "SHARD_SOURCE_WRITTEN" else None,
            )
        source = _read_object(source_path)
        keys = source.get("selected_query_keys")
        if (source.get("shard_index") != index
                or source.get("all_additive_query_keys_fingerprint") != global_fp
                or source.get("total_additive_shards") != CENSUS_SHARDS
                or binding.get("plan_fingerprint") != plan.get("plan_fingerprint")
                or not isinstance(keys, list) or len(keys) != len(plan["requests"])
                or len(keys) != binding["shared_chains"]):
            raise CandidateChainCacheError("one source disagrees with original 2022 census")
        for key in keys:
            if (not isinstance(key, list) or len(key) != 3
                    or any(not isinstance(v, str) or not v for v in key)):
                raise CandidateChainCacheError("malformed original physical source key")
            k = tuple(key)
            if k in seen_keys:
                raise CandidateChainCacheError("duplicate physical key across 2022 shards")
            seen_keys.add(k)
        if index >= START_SHARD:
            plans.append((index, plan, source_path, len(keys)))
        if index % 10 == 0 or index == END_SHARD:
            progress({"stage": "SOURCE_BINDING_CENSUS", "shards_verified": index + 1,
                      "unique_physical_keys": len(seen_keys), "source_loads": loads})
    if len(seen_keys) != 2812 or len(plans) != END_SHARD - START_SHARD + 1:
        raise CandidateChainCacheError("original additive key count or remaining shard range changed")
    return plans


def _verify_or_freeze_quote_plan(settings: AtlasSettings) -> dict[str, Any]:
    plan = freeze_broad_quote_plan(settings, last_shard_inclusive=END_SHARD)
    path = settings.resolved_path(f"{PLAN_REL}/through_shard_{END_SHARD:03d}.json")
    if path.exists() or path.is_symlink():
        if _read_object(path) != plan:
            raise CandidateChainCacheError("previous broad full-year plan changed; no paid quotes")
    else:
        _exclusive(path, plan)
        if _read_object(path) != plan:
            raise CandidateChainCacheError("frozen full-year quote plan readback differs")
    return plan


def run_full_bulk(
    settings: AtlasSettings, *, max_new_requests: int = 12000,
    max_total_observed_credits: int = 8000, max_credit_windows: int = 2,
    initial_chain_workers: int = 4, initial_quote_workers: int = 16,
    duckdb_threads: int = 4, authorize: bool = False,
    paid: bool = False, private: bool = False, token: str | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
    # Injection below enables completely offline tests; never use this for live data.
    prepare_sources: Callable[..., Any] = _source_plans,
    chain_runner: Callable[..., Any] = run_expansion,
    plan_builder: Callable[..., Any] = _verify_or_freeze_quote_plan,
    quote_runner: Callable[..., Any] = run_broad_quote_histories,
    clock: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if (type(max_new_requests) is not int
            or not 1 <= max_new_requests <= MAX_NEW_REQUESTS
            or type(max_total_observed_credits) is not int
            or not 1 <= max_total_observed_credits <= MAX_TOTAL_OBSERVED_CREDITS
            or type(max_credit_windows) is not int
            or not 1 <= max_credit_windows <= MAX_CREDIT_WINDOWS
            or type(initial_chain_workers) is not int
            or not 1 <= initial_chain_workers <= MAX_CHAIN_WORKERS
            or type(initial_quote_workers) is not int
            or not 8 <= initial_quote_workers <= MAX_QUOTE_WORKERS
            or type(duckdb_threads) is not int or not 1 <= duckdb_threads <= 8):
        raise CandidateChainCacheError("full-bulk bounds malformed")
    if not (authorize and paid and private and isinstance(token, str) and token.strip()):
        raise CandidateChainCacheError("explicit paid/private/source confirmations and token required")
    _require_external(settings)
    emit = progress if progress is not None else lambda _: None
    now = clock if clock is not None else lambda: datetime.now(RESET_ZONE)
    run_id = datetime.now(RESET_ZONE).strftime("%Y%m%dT%H%M%S%f") + "-" + uuid.uuid4().hex[:8]
    lock = _check_lock(settings, run_id)
    report_path = settings.resolved_path(f"{REPORT_REL}/{run_id}.json")
    latest_path = settings.resolved_path(f"{REPORT_REL}/latest.json")
    state: dict[str, Any] = {
        "contract": CONTRACT, "run_id": run_id, "status": "STARTED",
        "source_shards": f"{START_SHARD}..{END_SHARD}",
        "new_chain_gets": 0, "new_quote_gets": 0,
        "observed_chain_credits": 0, "observed_quote_credits": 0,
        "observed_total_credits": 0, "credit_windows_started": 1,
        "last_provider_remaining": None, "chain_workers": initial_chain_workers,
        "quote_workers": initial_quote_workers, "total_new_request_cap": max_new_requests,
        "total_observed_credit_target": max_total_observed_credits,
        "no_option_0935_fill_or_pnl_authority": True,
    }

    def save(stage: str) -> None:
        state["status"] = stage
        state["last_updated_et"] = now().astimezone(RESET_ZONE).isoformat()
        state.pop("report_fingerprint", None)
        state["report_fingerprint"] = _fingerprint(state)
        encoded = json.dumps(state, indent=2, sort_keys=True) + "\n"
        atomic_write_text(report_path, encoded)
        atomic_write_text(latest_path, encoded)

    def wait_window() -> bool:
        if state["credit_windows_started"] >= max_credit_windows:
            return False
        if state["observed_total_credits"] >= max_total_observed_credits:
            return False
        if state["new_chain_gets"] + state["new_quote_gets"] >= max_new_requests:
            return False
        target = _next_reset(now())
        seconds = (target - now().astimezone(RESET_ZONE)).total_seconds()
        if not 0 < seconds <= 25 * 3600:
            raise CandidateChainCacheError("next provider reset window malformed")
        emit({"stage": "WAITING_FOR_DAILY_RESET", "target_et": target.isoformat(),
              "seconds": round(seconds), "credit_windows_completed": state["credit_windows_started"],
              "no_provider_reads_during_wait": True})
        save("WAITING_FOR_DAILY_RESET")
        while (target - now().astimezone(RESET_ZONE)).total_seconds() > 0:
            left = (target - now().astimezone(RESET_ZONE)).total_seconds()
            sleeper(min(60.0, max(0.001, left)))
        state["credit_windows_started"] += 1
        state["last_provider_remaining"] = None
        save("DAILY_RESET_WINDOW_ENTERED")
        return True

    try:
        emit({"stage": "FULL_BULK_PREFLIGHT", "source_shards": state["source_shards"],
              "maximum_paid_requests": max_new_requests,
              "maximum_observed_credits_across_windows": max_total_observed_credits,
              "maximum_credit_windows": max_credit_windows,
              "original_2022_pit_source_only": True})
        save("SOURCE_FREEZING")
        plans = prepare_sources(settings, duckdb_threads=duckdb_threads, progress=emit)
        if len(plans) != END_SHARD - START_SHARD + 1:
            raise CandidateChainCacheError("source preparer returned incomplete full range")
        # Full immutable source preparation is sequential; provider requests
        # are concurrently dispatched only for different proven physical keys.
        remaining_sources: list[tuple[int, dict[str, Any], Path, int]] = []
        source_terminal = 0
        source_gaps = 0
        prior_gaps: dict[int, int] = {}
        for index, plan, path, physical in plans:
            census = chain_runner(settings, plan, path)
            if (census["completed_chains"] + census["proven_exact_query_gaps"]
                    + census["pending"] != physical):
                raise CandidateChainCacheError("read-only source shard receipt census malformed")
            prior_gaps[index] = census["proven_exact_query_gaps"]
            source_gaps += prior_gaps[index]
            if census["pending"]:
                remaining_sources.append((index, plan, path, census["pending"]))
            else:
                source_terminal += 1
        state["source_shards_already_complete"] = source_terminal
        state["source_shards_initially_pending"] = len(remaining_sources)
        state["existing_exact_source_gaps_26_to_70"] = source_gaps
        emit({"stage": "ALL_SOURCES_FROZEN", "remaining_shards": len(remaining_sources),
              "already_complete_shards": source_terminal, "source_gaps": source_gaps})
        save("SOURCE_ACQUIRING")
        shard_workers = initial_chain_workers
        last_source_speed = 0.0
        while remaining_sources:
            remaining_gets = max_new_requests - state["new_chain_gets"] - state["new_quote_gets"]
            remaining_target = max_total_observed_credits - state["observed_total_credits"]
            if remaining_gets <= 0 or remaining_target <= 0:
                save("PARTIAL_GLOBAL_BUDGET")
                return state
            # One original historical query is <=1000 rows, normally <=1 credit.
            # Reserve the entire pending shard count before dispatch; observed
            # provider charges remain authoritative after response.
            wave = []
            available = remaining_gets
            available_credits = remaining_target
            for item in remaining_sources[:shard_workers]:
                need = item[3]
                if need > available or need > available_credits:
                    break
                header = state["last_provider_remaining"]
                if header is not None and header - MIN_REMAINING_CREDITS < (sum(x[3] for x in wave) + need + 8):
                    break
                wave.append(item)
                available -= need
                available_credits -= need
            if not wave:
                if state["last_provider_remaining"] is not None and (
                    state["last_provider_remaining"] < MIN_REMAINING_CREDITS + remaining_sources[0][3] + 8
                ) and wait_window():
                    continue
                save("PARTIAL_BUDGET_OR_PROVIDER_FLOOR")
                return state
            began = time.perf_counter()
            outcomes: dict[int, dict[str, Any]] = {}
            first_error: BaseException | None = None
            with ThreadPoolExecutor(max_workers=len(wave)) as pool:
                futures = {
                    pool.submit(
                        chain_runner, settings, plan, path,
                        max_total_new_requests=need, max_observed_credits=max(1, need),
                        authorize=True, paid=True, private=True, classify_no_data=True,
                    ): index for index, plan, path, need in wave
                }
                for future in as_completed(futures):
                    index = futures[future]
                    try:
                        outcomes[index] = future.result()
                    except BaseException as exc:
                        if first_error is None:
                            first_error = exc
            if first_error is not None:
                raise CandidateChainCacheError(
                    "original chain worker uncertain/quarantined; wave joined, inspect all durable original receipts before any retry"
                ) from first_error
            for index, plan, path, need in wave:
                result = outcomes[index]
                calls = result["new_provider_attempts_this_invocation"]
                charge = result["observed_provider_credits_this_invocation"]
                if (type(calls) is not int or not 0 <= calls <= need
                        or type(charge) is not int or charge < 0
                        or result["completed_chains"] + result["proven_exact_query_gaps"]
                        + result["pending"] != len(plan["requests"])):
                    raise CandidateChainCacheError("chain wave original receipt accounting inconsistent")
                state["new_chain_gets"] += calls
                state["observed_chain_credits"] += charge
                state["observed_total_credits"] += charge
                remain = result["last_observed_credits_remaining"]
                if remain is not None:
                    state["last_provider_remaining"] = (
                        remain if state["last_provider_remaining"] is None else
                        min(state["last_provider_remaining"], remain)
                    )
                gap_delta = result["proven_exact_query_gaps"] - prior_gaps[index]
                if gap_delta < 0:
                    raise CandidateChainCacheError("previously proved source gap disappeared")
                source_gaps += gap_delta
                prior_gaps[index] = result["proven_exact_query_gaps"]
                if result["pending"]:
                    # Valid terminal-free partial (e.g. provider floor). Never
                    # replay an original attempted GET; reentry verifies receipts.
                    if (result["pending"] >= need
                            or result["last_observed_credits_remaining"] is None):
                        raise CandidateChainCacheError("partial source made no safely explainable progress")
                else:
                    source_terminal += 1
            unresolved = [
                (index, plan, path, outcomes[index]["pending"])
                for index, plan, path, need in wave if outcomes[index]["pending"]
            ]
            remaining_sources = unresolved + remaining_sources[len(wave):]
            state["source_shards_complete_26_to_70"] = source_terminal
            state["source_exact_gaps_26_to_70"] = source_gaps
            state["source_shards_pending"] = len(remaining_sources)
            elapsed = max(0.001, time.perf_counter() - began)
            emit({"stage": "SOURCE_PARALLEL_WAVE", "shards": [x[0] for x in wave],
                  "workers": len(wave), "elapsed_seconds": round(elapsed, 3),
                  "new_chain_gets_total": state["new_chain_gets"],
                  "observed_chain_credits_total": state["observed_chain_credits"],
                  "last_remaining": state["last_provider_remaining"],
                  "remaining_source_shards": len(remaining_sources),
                  "completed_per_second": round(sum(x[3] for x in wave) / elapsed, 2)})
            save("SOURCE_ACQUIRING")
            if len(wave) == shard_workers:
                current_source_speed = sum(x[3] for x in wave) / elapsed
                shard_workers = _adapt_chain_workers(
                    shard_workers, last_source_speed, current_source_speed,
                )
                last_source_speed = current_source_speed
                state["chain_workers"] = shard_workers
        state["source_shards_complete_26_to_70"] = END_SHARD - START_SHARD + 1
        emit({"stage": "ALL_2022_ADDITIVE_CHAINS_TERMINAL",
              "new_chain_gets": state["new_chain_gets"],
              "observed_chain_credits": state["observed_chain_credits"]})
        save("QUOTE_PLAN_FREEZING")
        plan = plan_builder(settings)
        state["quote_plan_fingerprint"] = plan["plan_fingerprint"]
        state["unique_exact_quote_histories"] = plan["unique_exact_quote_series"]
        state["selected_candidate_memberships"] = plan["selected_candidate_memberships"]
        emit({"stage": "FULL_YEAR_QUOTE_PLAN_FROZEN",
              "unique_exact_histories": state["unique_exact_quote_histories"],
              "selected_memberships": state["selected_candidate_memberships"],
              "plan_fingerprint": plan["plan_fingerprint"]})
        save("QUOTE_ACQUIRING")
        quote_workers = initial_quote_workers
        last_speed = 0.0
        while True:
            remaining_gets = max_new_requests - state["new_chain_gets"] - state["new_quote_gets"]
            remaining_target = max_total_observed_credits - state["observed_total_credits"]
            if remaining_gets <= 0 or remaining_target <= 0:
                save("PARTIAL_GLOBAL_BUDGET")
                return state
            header = state["last_provider_remaining"]
            if header is not None and header <= MIN_REMAINING_CREDITS + quote_workers + 8:
                if wait_window():
                    continue
                save("PARTIAL_PROVIDER_CREDIT_FLOOR")
                return state
            chunk = min(QUOTE_CHUNK, remaining_gets, remaining_target)
            def quote_progress(row: dict[str, Any]) -> None:
                if row.get("stage") != "BOUNDED_QUOTE_BATCH":
                    return
                attempts = row.get("new_attempts")
                if (type(attempts) is int
                        and (attempts == row.get("batch_size")
                             or attempts % 128 == 0
                             or row.get("pending") == 0)):
                    emit({"stage": "QUOTE_DOWNLOAD_PROGRESS", **{
                        k: v for k, v in row.items() if k != "stage"
                    }})

            start = time.perf_counter()
            quote = quote_runner(
                settings, plan, max_new_requests=chunk,
                max_observed_credits=min(3500, remaining_target),
                workers=quote_workers, authorize=True, paid=True, private=True, token=token,
                progress=quote_progress,
            )
            calls = quote["new_provider_attempts"]
            charge = quote["observed_credits_this_invocation"]
            if (type(calls) is not int or not 0 <= calls <= chunk
                    or type(charge) is not int or charge < 0
                    or quote["plan_fingerprint"] != plan["plan_fingerprint"]
                    or quote["unique_exact_quote_series"] != state["unique_exact_quote_histories"]
                    or (quote["complete_source_series"] + quote["exact_source_gaps"]
                        + quote["pending"] != state["unique_exact_quote_histories"])):
                raise CandidateChainCacheError("quote original receipt/plan accounting inconsistent")
            state["new_quote_gets"] += calls
            state["observed_quote_credits"] += charge
            state["observed_total_credits"] += charge
            remain = quote["last_observed_provider_remaining"]
            if remain is not None:
                state["last_provider_remaining"] = (
                    remain if state["last_provider_remaining"] is None else
                    min(state["last_provider_remaining"], remain)
                )
            state["complete_exact_quote_histories"] = quote["complete_source_series"]
            state["exact_quote_gaps"] = quote["exact_source_gaps"]
            state["pending_exact_quote_histories"] = quote["pending"]
            state["verified_original_quote_body_bytes"] = quote["verified_and_new_raw_body_bytes"]
            elapsed = max(0.001, time.perf_counter() - start)
            speed = calls / elapsed if calls else 0.0
            emit({"stage": "QUOTE_BULK_CHUNK", "workers": quote_workers,
                  "new_gets": calls, "new_gets_per_second": round(speed, 2),
                  "completed_exact_histories": quote["complete_source_series"],
                  "pending_exact_histories": quote["pending"],
                  "observed_quote_credits_total": state["observed_quote_credits"],
                  "last_provider_remaining": state["last_provider_remaining"],
                  "raw_quote_body_bytes": state["verified_original_quote_body_bytes"]})
            save("QUOTE_ACQUIRING")
            if quote["pending"] == 0:
                state["status"] = "COMPLETE_SOURCE_ONLY"
                state["original_exact_provider_receipts_replayed"] = 0
                save("COMPLETE_SOURCE_ONLY")
                return state
            if calls == 0:
                if state["last_provider_remaining"] is not None and wait_window():
                    continue
                save("PARTIAL_QUOTE_NO_PROGRESS")
                return state
            if calls >= 128:
                quote_workers = _adapt_quote_workers(quote_workers, last_speed, speed, calls)
                last_speed = speed
                state["quote_workers"] = quote_workers
    except BaseException as exc:
        state["failure_class"] = type(exc).__name__
        save("STOPPED_ORIGINAL_EVIDENCE_REVIEW_REQUIRED")
        raise
    finally:
        # A killed process leaves its exclusive lock for manual original-attempt
        # inspection. A normal exception is already checkpointed and unlocks.
        lock.unlink(missing_ok=True)
