from __future__ import annotations

"""One resumable 2022 PIT monthly-CALL bulk backfill (shards 26..70).

Only the existing original source/quote caches may make provider requests.
Original per-physical-query intents and SHA receipts remain authoritative.
Concurrency operates on DISJOINT original chain shards; quote concurrency is
adaptive within the existing fail-closed full-series executor.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from packages.backtesting.recurrent_successor_outcome_replay import load_selected_replay_opportunities
from packages.core.settings import AtlasSettings
from packages.data import marketdata_additive_2022_shards_v1 as shards
from packages.data.marketdata_2022_broad_quote_campaign_v2 import (
    PLAN_REL, freeze_broad_quote_plan, run_broad_quote_histories,
)
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, MIN_REMAINING_CREDITS, MAX_RAW_BYTES as CHAIN_MAX_RAW_BYTES,
    _fingerprint, run_candidate_chain_cache,
)
from packages.data.marketdata_candidate_expansion_v1 import (
    _exclusive, _read_object, _require_external, run_expansion,
)
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    MAX_NEW_QUOTE_REQUESTS, MAX_OBSERVED_CREDITS as QUOTE_CREDIT_CAP,
)
from packages.data.marketdata_2022_quote_coverage_audit_v1 import audit_frozen_quote_coverage
from packages.data.research_storage import assert_category_acquisition_allowed

CONTRACT = "atlas-marketdata-2022-bulk-local-first-v1"
FROZEN_LAST_DONE_SHARD = 25
FINAL_SHARD = 70
BASE_QUOTE_FINGERPRINT = "afded87e25f9b9233c31c0a8b1b98495bc448b8ce74c95d57df4ef8109d98291"
BASE_QUOTE_SERIES = 2725
MAX_SOURCE_WORKERS = 8
MAX_SOURCE_GETS = 1800
MAX_QUOTE_GETS = 6000
MAX_TOTAL_CREDITS = 6500
MIN_SAFE_ACCOUNT_REMAINING = 400
PLAN_REL_PATH = "data/options/manifests/marketdata_bulk_2022_26_70_v1.json"


def prepare_frozen_bulk_sources(
    settings: AtlasSettings, *,
    duckdb_threads: int = 4,
    prior_reader: Callable[..., Any] = shards._prior,
    preparer: Callable[..., Any] = shards.prepare_additive_shard,
    loader: Callable[..., Any] = load_selected_replay_opportunities,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], dict[int, tuple[dict[str, Any], Path, dict[str, Any]]]]:
    """Verify original cohort once, read native DEVELOPMENT once, freeze all new shards."""
    if type(duckdb_threads) is not int or not 1 <= duckdb_threads <= 8:
        raise CandidateChainCacheError("bulk DuckDB thread bound invalid")
    prior = prior_reader(settings)
    if (prior[0]["plan_fingerprint"] != shards.FROZEN_PRIOR_PLAN
            or len(prior[1]) != 36 or not 1 <= len(prior[2]) <= 36):
        raise CandidateChainCacheError("bulk original 2022 prior cohort failed integrity gate")
    cached_native: Any = None

    def one_native_load(*args: Any, **kwargs: Any) -> Any:
        nonlocal cached_native
        if cached_native is None:
            cached_native = loader(*args, **kwargs)
            if progress:
                progress({"stage": "ONE_ACCEPTED_2022_NATIVE_SOURCE_LOADED"})
        return cached_native

    bound: dict[int, tuple[dict[str, Any], Path, dict[str, Any]]] = {}
    seen: set[tuple[str, str, str]] = set()
    global_fp: str | None = None
    for index in range(FROZEN_LAST_DONE_SHARD + 1, FINAL_SHARD + 1):
        plan, path, binding, action = preparer(
            settings, shard_index=index, duckdb_threads=duckdb_threads,
            loader=one_native_load, verified_prior=prior,
        )
        source = _read_object(path)
        keys = source.get("selected_query_keys")
        if (binding.get("plan_fingerprint") != plan.get("plan_fingerprint")
                or binding.get("source_sha256") != shards._sha(path)
                or source.get("shard_index") != index
                or source.get("total_additive_shards") != FINAL_SHARD + 1
                or not isinstance(keys, list)
                or len(keys) != plan.get("shared_chain_requests")
                or not 1 <= len(keys) <= shards.KEYS_PER_SHARD
                or source.get("protected_master_return_rows_read") != 0):
            raise CandidateChainCacheError(f"bulk shard {index} source binding changed")
        fp = source.get("all_additive_query_keys_fingerprint")
        if global_fp is None:
            global_fp = fp
        elif fp != global_fp:
            raise CandidateChainCacheError("bulk shards have divergent frozen physical universe")
        for raw in keys:
            if (not isinstance(raw, list) or len(raw) != 3
                    or any(not isinstance(value, str) or not value for value in raw)):
                raise CandidateChainCacheError("bulk physical key malformed")
            key = tuple(raw)
            if key in seen:
                raise CandidateChainCacheError("bulk physical key duplicated across shards")
            seen.add(key)
        bound[index] = (plan, path, binding)
        if progress and (index % 5 == 0 or index == FINAL_SHARD):
            progress({"stage": "BULK_SOURCE_FROZEN", "shard": index,
                      "frozen_shards": len(bound), "physical_keys": len(seen),
                      "source_action": action})
    manifest = {
        "contract": CONTRACT,
        "purpose": "IMMUTABLE_DEVELOPMENT_SOURCE_ONLY",
        "prior_original_2022_plan_fingerprint": prior[0]["plan_fingerprint"],
        "all_additive_keys_fingerprint": global_fp,
        "base_completed_shards": "0..25",
        "new_shards": "26..70",
        "new_physical_chain_keys": len(seen),
        "shards": [{
            "shard_index": i,
            "plan_fingerprint": bound[i][0]["plan_fingerprint"],
            "source_sha256": bound[i][2]["source_sha256"],
            "physical_requests": len(bound[i][0]["requests"]),
        } for i in sorted(bound)],
        "quote_policy": "FULL_CAPTURED_PRIOR_SESSION_CALL_8_PERCENT_SINGLE_MONTHLY_EXPIRY",
        "protected_master_return_rows_read": 0,
        "provider_reads_in_planning": 0,
        "no_0935_option_fill_or_pnl_authority": True,
    }
    manifest["manifest_fingerprint"] = _fingerprint(manifest)
    stored = settings.resolved_path(PLAN_REL_PATH)
    if stored.exists() or stored.is_symlink():
        if _read_object(stored) != manifest:
            raise CandidateChainCacheError("bulk frozen source manifest differs; do not overwrite")
    else:
        _exclusive(stored, manifest)
        if _read_object(stored) != manifest:
            raise CandidateChainCacheError("bulk source manifest failed readback")
    return manifest, bound


def _checked_source_state(
    settings: AtlasSettings, plan: dict[str, Any],
    reader: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    state = reader(settings, plan)
    if (state.get("planned_chain_requests") != len(plan["requests"])
            or type(state.get("pending")) is not int
            or state["pending"] < 0
            or (state.get("reused", 0) + state.get("no_data_verified", 0)
                + state["pending"] != len(plan["requests"]))):
        raise CandidateChainCacheError("bulk source physical receipt census invalid")
    return state


def run_bulk_2022(
    settings: AtlasSettings, *,
    max_new_chain_requests: int = MAX_SOURCE_GETS,
    max_new_quote_requests: int = MAX_QUOTE_GETS,
    max_total_observed_credits: int = 6300,
    source_workers: int = 4,
    source_worker_ceiling: int = MAX_SOURCE_WORKERS,
    quote_workers: int = 16,
    quote_worker_ceiling: int = 24,
    duckdb_threads: int = 4,
    authorize: bool = False, paid: bool = False, private: bool = False,
    token: str | None = None,
    source_builder: Callable[..., Any] = prepare_frozen_bulk_sources,
    source_reader: Callable[..., dict[str, Any]] = run_candidate_chain_cache,
    source_runner: Callable[..., dict[str, Any]] = run_expansion,
    quote_plan_builder: Callable[..., dict[str, Any]] = freeze_broad_quote_plan,
    quote_runner: Callable[..., dict[str, Any]] = run_broad_quote_histories,
    coverage_auditor: Callable[..., dict[str, Any]] = audit_frozen_quote_coverage,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """One explicit-credit-budget local-first run. Resume via unchanged source/receipt keys."""
    if (type(max_new_chain_requests) is not int
            or not 0 <= max_new_chain_requests <= MAX_SOURCE_GETS
            or type(max_new_quote_requests) is not int
            or not 0 <= max_new_quote_requests <= MAX_QUOTE_GETS
            or max_new_chain_requests + max_new_quote_requests < 1
            or type(max_total_observed_credits) is not int
            or not 1 <= max_total_observed_credits <= MAX_TOTAL_CREDITS):
        raise CandidateChainCacheError("bulk original GET/credit ceilings invalid")
    if (type(source_workers) is not int or type(source_worker_ceiling) is not int
            or not 1 <= source_workers <= source_worker_ceiling <= MAX_SOURCE_WORKERS
            or type(quote_workers) is not int or type(quote_worker_ceiling) is not int
            or not 1 <= quote_workers <= quote_worker_ceiling <= 24):
        raise CandidateChainCacheError("bulk network worker range invalid")
    if not (authorize and paid and private and isinstance(token, str) and token.strip()):
        raise CandidateChainCacheError("bulk paid/provider/private confirmations and token required")
    _require_external(settings)
    start = time.perf_counter()

    def emit(stage: str, **row: Any) -> None:
        if progress:
            progress({"stage": stage, **row})

    base_path = settings.resolved_path(
        f"{PLAN_REL}/through_shard_{FROZEN_LAST_DONE_SHARD:03d}.json"
    )
    base = _read_object(base_path)
    unsigned = dict(base)
    fp = unsigned.pop("plan_fingerprint", None)
    if (fp != BASE_QUOTE_FINGERPRINT or fp != _fingerprint(unsigned)
            or base.get("unique_exact_quote_series") != BASE_QUOTE_SERIES):
        raise CandidateChainCacheError("accepted 0..25 base quote plan altered/missing")
    emit("BASE_LOCAL_QUOTE_PLAN", completed_baseline=BASE_QUOTE_SERIES,
         exact_plan_fingerprint=fp, provider_requests=0)
    manifest, sources = source_builder(settings, duckdb_threads=duckdb_threads,
                                       progress=lambda x: emit(**x))
    pending: list[int] = []
    source_complete = source_gaps = source_pending = 0
    for i, (plan, _, _) in sources.items():
        local = _checked_source_state(settings, plan, source_reader)
        if local["pending"]:
            pending.append(i)
        source_complete += local["reused"]
        source_gaps += local["no_data_verified"]
        source_pending += local["pending"]
    if source_complete + source_gaps + source_pending != manifest["new_physical_chain_keys"]:
        raise CandidateChainCacheError("bulk overall original source count differs")
    emit("SOURCE_CENSUS", new_source_shards=len(sources),
         original_new_physical_queries=manifest["new_physical_chain_keys"],
         complete=source_complete, exact_gaps=source_gaps,
         pending_shards=len(pending),
         pending_physical_keys=source_pending)

    chain_gets = chain_credits = quote_gets = quote_credits = 0
    lowest_remaining: int | None = None
    live_source_workers = source_workers
    last_source_rate: float | None = None
    last_source_level = source_workers

    # Disjoint shards own different immutable exact-query request and lock keys.
    # Every wave must finish and reconcile receipts before any later dispatch.
    with ThreadPoolExecutor(max_workers=source_worker_ceiling) as pool:
        while pending and chain_gets < max_new_chain_requests:
            available_calls = max_new_chain_requests - chain_gets
            available_credits = max_total_observed_credits - chain_credits - quote_credits
            if (available_credits < 2 or
                    (lowest_remaining is not None and
                     lowest_remaining <= MIN_SAFE_ACCOUNT_REMAINING + 2 * source_worker_ceiling)):
                break
            n = min(live_source_workers, len(pending), available_calls, available_credits // 2)
            if n < 1:
                break
            per_shard_gets = min(10, available_calls // n, available_credits // (2*n))
            if per_shard_gets < 1:
                break
            indices = pending[:n]
            # Concurrent per-shard preflights alone could each approve against
            # the same free bytes. Reserve the entire wave BEFORE dispatch.
            assert_category_acquisition_allowed(
                settings, category="options_candidate_cache",
                projected_additional_bytes=n * per_shard_gets * (CHAIN_MAX_RAW_BYTES + 16384),
            )
            started_wave = time.perf_counter()
            jobs = {
                pool.submit(
                    source_runner, settings, sources[i][0], sources[i][1],
                    max_total_new_requests=per_shard_gets,
                    max_observed_credits=min(100, 2 * per_shard_gets + 1),
                    authorize=True, paid=True, private=True,
                    classify_no_data=True,
                ): i for i in indices
            }
            error: Exception | None = None
            wave_gets = wave_credits = 0
            for job in as_completed(jobs):
                i = jobs[job]
                try:
                    result = job.result()
                    calls = result["new_provider_attempts_this_invocation"]
                    charge = result["observed_provider_credits_this_invocation"]
                    if (type(calls) is not int or not 0 <= calls <= per_shard_gets
                            or type(charge) is not int or charge < 0
                            or (result["completed_chains"] + result["proven_exact_query_gaps"]
                                + result["pending"] != len(sources[i][0]["requests"]))):
                        raise CandidateChainCacheError("original chain runner accounting invalid")
                    wave_gets += calls
                    wave_credits += charge
                    reported_remaining = result.get("last_observed_credits_remaining")
                    if reported_remaining is not None:
                        if type(reported_remaining) is not int or reported_remaining < 0:
                            raise CandidateChainCacheError("chain provider credit header malformed")
                        lowest_remaining = (reported_remaining if lowest_remaining is None
                                            else min(lowest_remaining, reported_remaining))
                    if result["pending"] == 0:
                        pending.remove(i)
                    emit("SOURCE_SHARD_PROGRESS", shard=i, new_gets=calls, credits=charge,
                         complete=result["completed_chains"],
                         gaps=result["proven_exact_query_gaps"], pending=result["pending"])
                except Exception as exc:
                    if error is None:
                        error = exc
            chain_gets += wave_gets
            chain_credits += wave_credits
            seconds = max(0.000001, time.perf_counter() - started_wave)
            rate = wave_gets / seconds
            used_workers = live_source_workers
            if error is None and pending:
                if (last_source_rate is not None and used_workers > last_source_level
                        and rate < last_source_rate * 0.85):
                    live_source_workers = last_source_level
                    last_source_rate = None
                elif used_workers < source_worker_ceiling:
                    last_source_rate = rate
                    last_source_level = used_workers
                    live_source_workers = min(source_worker_ceiling, used_workers + 2)
                else:
                    last_source_rate = rate
                    last_source_level = used_workers
            emit("SOURCE_WAVE", new_chain_gets=chain_gets, credits=chain_credits,
                 pending_shards=len(pending), wave_gets=wave_gets,
                 seconds=round(seconds, 3), gets_per_second=round(rate, 2),
                 workers_used=n, next_worker_target=live_source_workers,
                 lowest_observed_remaining=lowest_remaining,
                 elapsed_seconds=round(time.perf_counter()-start, 1))
            if error is not None:
                raise CandidateChainCacheError(
                    "uncertain/invalid original chain attempt in concurrent wave; "
                    "all started originals have drained, inspect original evidence; no auto-retry"
                ) from error
            if wave_gets == 0 and pending:
                break

    # A post-wave exact SHA census, not another provider acquisition.
    complete = gaps = residual = 0
    for plan, _, _ in sources.values():
        state = _checked_source_state(settings, plan, source_reader)
        complete += state["reused"]
        gaps += state["no_data_verified"]
        residual += state["pending"]
    if complete + gaps + residual != manifest["new_physical_chain_keys"]:
        raise CandidateChainCacheError("bulk original source census mismatch")
    if residual:
        report = {
            "contract": CONTRACT, "status": "SOURCE_PARTIAL_SAFE_STOP_NO_QUOTES",
            "source_manifest_fingerprint": manifest["manifest_fingerprint"],
            "new_source_complete": complete, "new_source_exact_gaps": gaps,
            "pending_source_requests": residual, "pending_source_shards": len(pending),
            "new_chain_gets": chain_gets, "new_quote_gets": 0,
            "chain_credits": chain_credits, "quote_credits": 0,
            "total_observed_credits": chain_credits,
            "lowest_observed_provider_remaining": lowest_remaining,
            "elapsed_seconds": round(time.perf_counter()-start, 1),
            "next_action": "RESUME_SAME_FROZEN_PROGRAM_AFTER_CREDIT_RESET_OR_REVIEW",
            "at_0935_option_fill_pnl_paper_live_authority": False,
        }
        report["report_fingerprint"] = _fingerprint(report)
        return report

    # Source-only point-in-time quote plan; ALL prior 2725 exact series are reused.
    plan = quote_plan_builder(settings, last_shard_inclusive=FINAL_SHARD)
    path = settings.resolved_path(f"{PLAN_REL}/through_shard_{FINAL_SHARD:03d}.json")
    if path.exists() or path.is_symlink():
        if _read_object(path) != plan:
            raise CandidateChainCacheError("frozen full-2022 quote plan differs")
        action = "REUSED_FROZEN_FULL_2022_QUOTE_PLAN"
    else:
        _exclusive(path, plan)
        if _read_object(path) != plan:
            raise CandidateChainCacheError("full-2022 quote plan readback mismatch")
        action = "WRITTEN_IMMUTABLE_FULL_2022_QUOTE_PLAN"
    emit("FULL_2022_QUOTE_PLAN", action=action,
         unique_exact_histories=plan["unique_exact_quote_series"],
         memberships=plan["selected_candidate_memberships"],
         source_gaps=len(plan["source_gaps"]),
         previous_exact_series_reused=BASE_QUOTE_SERIES,
         fingerprint=plan["plan_fingerprint"])

    latest_quote: dict[str, Any] | None = None
    while quote_gets < max_new_quote_requests:
        remaining_credits = max_total_observed_credits - chain_credits - quote_credits
        if (remaining_credits < quote_worker_ceiling * 2
                or (lowest_remaining is not None and
                    lowest_remaining <= MIN_SAFE_ACCOUNT_REMAINING + quote_worker_ceiling * 2)):
            break
        wave_limit = min(MAX_NEW_QUOTE_REQUESTS, max_new_quote_requests-quote_gets)
        latest_quote = quote_runner(
            settings, plan, max_new_requests=wave_limit,
            max_observed_credits=min(QUOTE_CREDIT_CAP, remaining_credits),
            workers=quote_workers, adaptive_workers=True,
            worker_ceiling=quote_worker_ceiling,
            authorize=True, paid=True, private=True, token=token,
            progress=lambda row: emit("QUOTES", quote_stage=row.get("stage"),
                                      **{k: v for k, v in row.items() if k != "stage"}),
        )
        used = latest_quote["new_provider_attempts"]
        charges = latest_quote["observed_credits_this_invocation"]
        if (type(used) is not int or not 0 <= used <= wave_limit
                or type(charges) is not int or charges < 0
                or latest_quote["plan_fingerprint"] != plan["plan_fingerprint"]
                or latest_quote["unique_exact_quote_series"] != plan["unique_exact_quote_series"]):
            raise CandidateChainCacheError("bulk exact quote report accounting invalid")
        quote_gets += used
        quote_credits += charges
        remaining = latest_quote.get("last_observed_provider_remaining")
        if remaining is not None:
            if type(remaining) is not int or remaining < 0:
                raise CandidateChainCacheError("bulk exact quote credit header invalid")
            lowest_remaining = remaining if lowest_remaining is None else min(lowest_remaining, remaining)
        emit("QUOTE_WAVE", new_quote_gets=quote_gets, quote_credits=quote_credits,
             total_credits=chain_credits+quote_credits,
             complete=latest_quote["complete_source_series"],
             exact_quote_gaps=latest_quote["exact_source_gaps"],
             pending=latest_quote["pending"],
             provider_remaining=lowest_remaining,
             elapsed_seconds=round(time.perf_counter()-start, 1))
        if latest_quote["pending"] == 0 or used == 0:
            break
    if latest_quote is None:
        # Read-only exact source census; no live authorization on this audit.
        latest_quote = quote_runner(settings, plan, max_new_requests=0)
    # Perform the full source-quality census ONCE after bulk acquisition;
    # no extra provider reads or paid attempts. Preserve sparse volume facts.
    coverage: dict[str, Any] | None = None
    if latest_quote["pending"] == 0:
        coverage = coverage_auditor(settings, last_shard_inclusive=FINAL_SHARD)
        if (coverage.get("status") != "COMPLETE_SOURCE_ONLY"
                or coverage.get("frozen_plan_fingerprint") != plan["plan_fingerprint"]
                or coverage.get("unique_exact_quote_series") != plan["unique_exact_quote_series"]
                or coverage.get("complete_exact_histories") != latest_quote["complete_source_series"]
                or coverage.get("exact_quote_no_data_gaps") != latest_quote["exact_source_gaps"]
                or coverage.get("pending_exact_histories") != 0
                or coverage.get("provider_requests_this_audit") != 0):
            raise CandidateChainCacheError("full original quote coverage audit disagrees with acquired receipts")
        emit("FULL_OFFLINE_2022_EOD_COVERAGE", **{
            key: coverage[key] for key in (
                "audit_fingerprint", "total_observed_eod_rows",
                "rows_with_positive_reported_volume",
                "rows_with_zero_reported_volume",
                "histories_with_no_positive_reported_volume",
                "first_observed_session", "last_observed_session",
            )
        })
    total = chain_credits + quote_credits
    report = {
        "contract": CONTRACT,
        "status": ("COMPLETE_2022_ADDITIVE_CHAINS_AND_QUOTE_SERIES"
                   if latest_quote["pending"] == 0 else "SOURCE_COMPLETE_QUOTES_PARTIAL_SAFE_STOP"),
        "source_manifest_fingerprint": manifest["manifest_fingerprint"],
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "original_source_only_404_gaps": gaps,
        "new_source_complete": complete,
        "pending_source_requests": 0,
        "unique_quote_series_including_reused": plan["unique_exact_quote_series"],
        "quote_series_complete": latest_quote["complete_source_series"],
        "quote_exact_gaps": latest_quote["exact_source_gaps"],
        "quote_pending": latest_quote["pending"],
        "new_chain_gets": chain_gets, "new_quote_gets": quote_gets,
        "chain_credits": chain_credits, "quote_credits": quote_credits,
        "total_observed_credits": total,
        "lowest_observed_provider_remaining": lowest_remaining,
        "original_verified_quote_response_bytes": latest_quote["verified_and_new_raw_body_bytes"],
        "elapsed_seconds": round(time.perf_counter()-start, 1),
        "post_bulk_offline_coverage_audit_fingerprint": (
            coverage["audit_fingerprint"] if coverage is not None else None
        ),
        "post_bulk_observed_eod_rows": (
            coverage["total_observed_eod_rows"] if coverage is not None else None
        ),
        "post_bulk_positive_reported_volume_rows": (
            coverage["rows_with_positive_reported_volume"] if coverage is not None else None
        ),
        "post_bulk_zero_reported_volume_rows": (
            coverage["rows_with_zero_reported_volume"] if coverage is not None else None
        ),
        "source_only_no_0935_option_fill_pnl_paper_live_or_broker_authority": True,
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
