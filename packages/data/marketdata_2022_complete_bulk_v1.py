from __future__ import annotations

"""Single resumable 2022 source-only bulk acquisition, remaining frozen 26..70.

Original exact receipts own paid effects. This orchestrator owns only range
gates, adaptive inter-shard network concurrency and a non-authoritative
progress summary; it does not rewrite source plans, receipts or query identity.
"""

import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from packages.backtesting.recurrent_successor_outcome_replay import load_selected_replay_opportunities
from packages.core.settings import AtlasSettings
from packages.data import marketdata_additive_2022_shards_v1 as shards
from packages.data.marketdata_additive_2022_shards_v1 import (
    KEYS_PER_SHARD, YEAR, prepare_additive_shard,
)
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, MIN_REMAINING_CREDITS, _fingerprint,
)
from packages.data.marketdata_candidate_expansion_v1 import (
    _read_object, _require_external, run_expansion,
)
from packages.data.marketdata_2022_broad_quote_campaign_v2 import (
    PLAN_REL, freeze_broad_quote_plan, run_broad_quote_histories,
)
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    MAX_NEW_QUOTE_REQUESTS, MAX_OBSERVED_CREDITS as QUOTE_CREDIT_CAP,
)
from packages.data.marketdata_2022_native_batch_v1 import batched_native_reader
from packages.data.marketdata_2022_quote_coverage_audit_v1 import audit_frozen_quote_coverage
from packages.data.research_storage import assert_category_acquisition_allowed

CONTRACT = "atlas-2022-complete-additive-source-and-call-eod-bulk-v1"
FIRST_NEW_SHARD = 26
LAST_SHARD = 70
MAX_CHAIN_GETS = 45 * KEYS_PER_SHARD
MAX_QUOTE_GETS = 6500
MAX_TOTAL_CREDIT_TARGET = 6600
MAX_NETWORK_SHARDS = 24
MAX_QUOTE_WORKERS = 24
MIN_NETWORK_SHARDS = 4


def _source_report_complete(report: dict[str, Any], planned: int) -> bool:
    return (
        report.get("status") in ("COMPLETE", "COMPLETE_WITH_EXACT_QUERY_GAPS")
        and report.get("pending") == 0
        and report.get("completed_chains", -1) + report.get("proven_exact_query_gaps", -1) == planned
        and type(report.get("new_provider_attempts_this_invocation")) is int
        and 0 <= report["new_provider_attempts_this_invocation"] <= planned
        and type(report.get("observed_provider_credits_this_invocation")) is int
        and report["observed_provider_credits_this_invocation"] >= 0
    )


def run_complete_2022_bulk(
    settings: AtlasSettings, *,
    max_total_new_chain_requests: int = MAX_CHAIN_GETS,
    max_total_new_quote_requests: int = MAX_QUOTE_GETS,
    max_total_observed_credits: int = 6400,
    initial_chain_workers: int = 8,
    max_chain_workers: int = MAX_NETWORK_SHARDS,
    quote_workers: int = 24,
    duckdb_threads: int = 4,
    authorize: bool = False, paid: bool = False, private: bool = False,
    token: str | None = None,
    prior_reader: Callable[..., Any] = shards._prior,
    preparer: Callable[..., Any] = prepare_additive_shard,
    loader: Callable[..., Any] = load_selected_replay_opportunities,
    native_batch_builder: Callable[..., Any] = batched_native_reader,
    source_runner: Callable[..., dict[str, Any]] = run_expansion,
    plan_builder: Callable[..., dict[str, Any]] = freeze_broad_quote_plan,
    quote_runner: Callable[..., dict[str, Any]] = run_broad_quote_histories,
    coverage_auditor: Callable[..., dict[str, Any]] = audit_frozen_quote_coverage,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if (type(max_total_new_chain_requests) is not int or not 0 <= max_total_new_chain_requests <= MAX_CHAIN_GETS
            or type(max_total_new_quote_requests) is not int or not 0 <= max_total_new_quote_requests <= MAX_QUOTE_GETS
            or type(max_total_observed_credits) is not int
            or not 1 <= max_total_observed_credits <= MAX_TOTAL_CREDIT_TARGET):
        raise CandidateChainCacheError("bulk chain/quote request or aggregate credit cap malformed")
    if (type(initial_chain_workers) is not int or type(max_chain_workers) is not int
            or not MIN_NETWORK_SHARDS <= initial_chain_workers <= max_chain_workers <= MAX_NETWORK_SHARDS
            or type(quote_workers) is not int or not 1 <= quote_workers <= MAX_QUOTE_WORKERS
            or type(duckdb_threads) is not int or not 1 <= duckdb_threads <= 8):
        raise CandidateChainCacheError("bulk worker/CPU bounds malformed")
    if not max_total_new_chain_requests and not max_total_new_quote_requests:
        raise CandidateChainCacheError("bulk acquisition needs a positive bounded original-request budget")
    if not (authorize and paid and private and isinstance(token, str) and token.strip()):
        raise CandidateChainCacheError("three paid/private confirmations and MarketData token required")
    _require_external(settings)
    started = time.perf_counter()
    emit_lock = threading.Lock()

    def emit(stage: str, **values: Any) -> None:
        if progress is not None:
            with emit_lock:
                progress({"stage": stage, **values})

    emit("BULK_PREFLIGHT", source_range="26..70", known_complete_source_range="0..25",
         source_global_keys=2812, chain_limit=max_total_new_chain_requests,
         quote_limit=max_total_new_quote_requests, aggregate_observed_credit_target=max_total_observed_credits,
         chain_workers_start=initial_chain_workers, chain_workers_max=max_chain_workers,
         quote_workers=quote_workers, original_paid_receipts_to_replay=0)
    prior = prior_reader(settings)
    if (not isinstance(prior, tuple) or len(prior) != 3
            or prior[0].get("plan_fingerprint") != shards.FROZEN_PRIOR_PLAN):
        raise CandidateChainCacheError("original accepted 2022 source/prior plan changed")
    original_fp = prior[0]["plan_fingerprint"]
    # All previously acquired keys are original SHA-bound, not trusted merely
    # because the operator supplied the names of successful shards.
    previous_keys: set[tuple[str, str, str]] = set()
    anchor_total = anchor_census = None
    for index in range(FIRST_NEW_SHARD):
        _, source_path, _ = shards._read_bound(settings, index, original_fp)
        source = _read_object(source_path)
        if index == 0:
            anchor_total = source["total_additive_shards"]
            anchor_census = source["all_additive_query_keys_fingerprint"]
        if (source["total_additive_shards"] != anchor_total
                or source["all_additive_query_keys_fingerprint"] != anchor_census):
            raise CandidateChainCacheError("existing source disagrees with original global census")
        for raw in source["selected_query_keys"]:
            if (not isinstance(raw, list) or len(raw) != 3
                    or any(not isinstance(s, str) or not s for s in raw)):
                raise CandidateChainCacheError("previous source key malformed")
            key = tuple(raw)
            if key in previous_keys:
                raise CandidateChainCacheError("existing source key collision")
            previous_keys.add(key)
    if anchor_total != LAST_SHARD + 1 or not isinstance(anchor_census, str):
        raise CandidateChainCacheError("frozen 2022 global 71-shard source census changed")
    emit("PREVIOUS_SOURCE_BOUND", previous_shards=FIRST_NEW_SHARD,
         verified_exact_chain_keys=len(previous_keys), original_global_source_fp=anchor_census)

    cached_source: Any = None
    source_loads = 0

    def load_once(*args: Any, **kwargs: Any) -> Any:
        nonlocal cached_source, source_loads
        if cached_source is None:
            cached_source = loader(*args, **kwargs)
            source_loads += 1
        return cached_source

    # Only the production preparer accepts the once-batched native source.
    # Injected synthetic preparers retain their old test contract.
    native_subset = (native_batch_builder(
        settings, load_once, prior, duckdb_threads=duckdb_threads,
        progress=lambda row: emit("NATIVE_BATCH", **{
            k: v for k, v in row.items() if k != "stage"
        }, native_stage=row.get("stage")),
    ) if preparer is prepare_additive_shard else None)
    source_tasks: list[tuple[int, dict[str, Any], Path, str, int]] = []
    for index in range(FIRST_NEW_SHARD, LAST_SHARD + 1):
        plan, path, bound, action = preparer(
            settings, shard_index=index, duckdb_threads=duckdb_threads,
            loader=load_once, verified_prior=prior,
            **({"native_reader": native_subset} if native_subset is not None else {}),
            progress=lambda item, idx=index: emit("SHARD_PREPARATION", shard_index=idx, source_event=item),
        )
        source = _read_object(path)
        if (not path.is_file() or path.is_symlink()
                or bound.get("shard_index") != index
                or bound.get("source_sha256") is None
                or plan.get("plan_fingerprint") != bound.get("plan_fingerprint")
                or source.get("all_additive_query_keys_fingerprint") != anchor_census
                or source.get("total_additive_shards") != anchor_total):
            raise CandidateChainCacheError("new source/binding/census mismatch")
        keys = source.get("selected_query_keys")
        if not isinstance(keys, list) or not 1 <= len(keys) <= KEYS_PER_SHARD:
            raise CandidateChainCacheError("new source has malformed physical keys")
        for raw in keys:
            if (not isinstance(raw, list) or len(raw) != 3
                    or any(not isinstance(s, str) or not s for s in raw)):
                raise CandidateChainCacheError("new source key malformed")
            key = tuple(raw)
            if key in previous_keys:
                raise CandidateChainCacheError("cross-shard physical query collision")
            previous_keys.add(key)
        if plan["shared_chain_requests"] != len(keys):
            raise CandidateChainCacheError("bound original source physical query count differs")
        source_tasks.append((index, plan, path, action, len(keys)))
        if (index - FIRST_NEW_SHARD + 1) % 10 == 0 or index == LAST_SHARD:
            emit("ORIGINAL_NEW_SOURCES_BOUND", prepared=index-FIRST_NEW_SHARD+1,
                 total=len(range(FIRST_NEW_SHARD, LAST_SHARD+1)),
                 accepted_source_loads=source_loads, frozen_global_keys=len(previous_keys))
    if len(previous_keys) != 2812 or len(source_tasks) != LAST_SHARD-FIRST_NEW_SHARD+1:
        raise CandidateChainCacheError("original 2,812-key global source count changed")

    attempted = chain_credits = 0
    last_remaining: int | None = None
    finished: list[dict[str, Any]] = []
    next_task = 0
    capacity = initial_chain_workers
    previous_rate: float | None = None
    with ThreadPoolExecutor(max_workers=max_chain_workers) as pool:
        while next_task < len(source_tasks):
            left = max_total_new_chain_requests - attempted
            credit_left = max_total_observed_credits - chain_credits
            if left < 1 or credit_left < 1:
                break
            if last_remaining is not None and last_remaining <= MIN_REMAINING_CREDITS + KEYS_PER_SHARD:
                break
            # Conservative upfront reservation of 40 possible new GETs/credits
            # per original shard. No second paid process should share account.
            maximum_by_calls = left // KEYS_PER_SHARD
            maximum_by_credit = credit_left // KEYS_PER_SHARD
            maximum_by_header = (
                max_chain_workers if last_remaining is None else
                max(0, (last_remaining-MIN_REMAINING_CREDITS)//KEYS_PER_SHARD)
            )
            count = min(capacity, len(source_tasks)-next_task, maximum_by_calls,
                        maximum_by_credit, maximum_by_header)
            if count < 1:
                break
            # Reserve the whole wave's maximum raw responses before dispatch.
            assert_category_acquisition_allowed(
                settings, category="options_candidate_cache",
                projected_additional_bytes=count * KEYS_PER_SHARD * (8*1024*1024+16384),
            )
            wave = source_tasks[next_task:next_task+count]
            wave_started = time.perf_counter()
            emit("CHAIN_WAVE_STARTED", start_shard=wave[0][0], through_shard=wave[-1][0],
                 active_network_workers=count, possible_original_gets=sum(x[4] for x in wave),
                 credits_observed_so_far=chain_credits)
            futures = {
                pool.submit(
                    source_runner, settings, plan, path,
                    max_total_new_requests=size, max_observed_credits=100,
                    authorize=authorize, paid=paid, private=private, classify_no_data=True,
                ): (index, size)
                for index, plan, path, _, size in wave
            }
            results: dict[int, dict[str, Any]] = {}
            error: BaseException | None = None
            # Each immutable per-plan lock and durable per-query intent is owned
            # by the existing source cache. A single failure blocks NEXT wave.
            for future in as_completed(futures):
                index, size = futures[future]
                try:
                    report = future.result()
                    if not _source_report_complete(report, size):
                        error = error or CandidateChainCacheError(
                            f"source shard {index} incomplete; original evidence review required"
                        )
                    results[index] = report
                except BaseException as exc:
                    error = error or exc
            if error is not None:
                raise CandidateChainCacheError(
                    "chain wave contains incomplete/uncertain original; all in-flight receipts retained; "
                    "no additional chain wave or quote stage"
                ) from error
            for index, _, path, action, size in wave:
                report = results[index]
                attempted += report["new_provider_attempts_this_invocation"]
                chain_credits += report["observed_provider_credits_this_invocation"]
                rem = report.get("last_observed_credits_remaining")
                if rem is not None:
                    if type(rem) is not int or rem < 0:
                        raise CandidateChainCacheError("source remaining-credit header malformed")
                    last_remaining = rem if last_remaining is None else min(last_remaining, rem)
                finished.append({"shard_index": index, "source_action": action,
                                 "completed_chains": report["completed_chains"],
                                 "proven_exact_query_gaps": report["proven_exact_query_gaps"],
                                 "new_provider_attempts": report["new_provider_attempts_this_invocation"],
                                 "observed_credits": report["observed_provider_credits_this_invocation"],
                                 "report_fingerprint": report["report_fingerprint"]})
            seconds = max(0.000001, time.perf_counter()-wave_started)
            rate = sum(results[x[0]]["new_provider_attempts_this_invocation"] for x in wave)/seconds
            elapsed = max(0.000001, time.perf_counter()-started)
            emit("CHAIN_WAVE_COMPLETE", through_shard=wave[-1][0], completed_new_shards=len(finished),
                 target_new_shards=len(source_tasks), new_chain_gets=attempted,
                 observed_chain_credits=chain_credits, last_provider_remaining=last_remaining,
                 active_network_workers=count, elapsed_seconds=round(elapsed, 2),
                 wave_seconds=round(seconds, 2), original_gets_per_second=round(rate, 2))
            next_task += count
            # Additive increase after a clean, stable wave; reduce on a marked
            # throughput collapse. This measures network throughput, not CPU load.
            if previous_rate is None or rate >= previous_rate*0.85:
                capacity = min(max_chain_workers, capacity+4)
            elif rate < previous_rate*0.70:
                capacity = max(MIN_NETWORK_SHARDS, capacity-4)
            previous_rate = rate
    if len(finished) != len(source_tasks):
        out = {
            "contract": CONTRACT, "status": "PARTIAL_CHAIN_BUDGET_OR_PROVIDER_FLOOR_NO_QUOTES",
            "last_completed_shard": finished[-1]["shard_index"] if finished else FIRST_NEW_SHARD-1,
            "source_shards_completed_this_run": len(finished),
            "new_chain_requests": attempted, "new_quote_requests": 0,
            "observed_chain_credits": chain_credits, "observed_quote_credits": 0,
            "observed_total_credits": chain_credits, "last_provider_remaining": last_remaining,
            "accepted_replay_source_loads": source_loads,
            "original_paid_receipts_replayed": 0,
        }
        out["report_fingerprint"] = _fingerprint(out)
        return out

    emit("CHAIN_UNIVERSE_COMPLETE", verified_global_source_keys=len(previous_keys),
         original_frozen_shards=LAST_SHARD+1, new_chain_gets=attempted,
         observed_chain_credits=chain_credits)
    remaining_credit_target = max_total_observed_credits-chain_credits
    if (not max_total_new_quote_requests or remaining_credit_target < 1
            or (last_remaining is not None and
                last_remaining <= MIN_REMAINING_CREDITS+quote_workers)):
        out = {
            "contract": CONTRACT, "status": "FULL_CHAIN_SOURCE_QUOTE_CREDIT_OR_REQUEST_GATE",
            "source_shards_completed_this_run": len(finished), "new_chain_requests": attempted,
            "new_quote_requests": 0, "observed_chain_credits": chain_credits,
            "observed_quote_credits": 0, "observed_total_credits": chain_credits,
            "last_provider_remaining": last_remaining, "accepted_replay_source_loads": source_loads,
            "original_paid_receipts_replayed": 0,
        }
        out["report_fingerprint"] = _fingerprint(out)
        return out

    plan = plan_builder(settings, last_shard_inclusive=LAST_SHARD)
    path = settings.resolved_path(f"{PLAN_REL}/through_shard_{LAST_SHARD:03d}.json")
    from packages.data.marketdata_candidate_expansion_v1 import _exclusive
    if path.exists() or path.is_symlink():
        if _read_object(path) != plan:
            raise CandidateChainCacheError("previously frozen full-universe quote plan differs")
        action = "REUSED_IMMUTABLE_PLAN"
    else:
        _exclusive(path, plan)
        if _read_object(path) != plan:
            raise CandidateChainCacheError("full-universe quote plan readback mismatch")
        action = "WRITTEN_IMMUTABLE_PLAN"
    emit("QUOTE_PLAN_FROZEN", plan_action=action, plan_fingerprint=plan["plan_fingerprint"],
         source_abstention_ledger_entries=len(plan["source_gaps"]),
         opportunity_contract_memberships=plan["selected_candidate_memberships"],
         unique_exact_occ_histories=plan["unique_exact_quote_series"],
         previously_completed_exact_occ_histories=2725, previous_receipts_to_refetch=0)
    quote_attempts = quote_credits = 0
    quote_report: dict[str, Any] | None = None
    while quote_attempts < max_total_new_quote_requests:
        left = max_total_new_quote_requests-quote_attempts
        credit_left = max_total_observed_credits-chain_credits-quote_credits
        if credit_left < 1:
            break
        if last_remaining is not None and last_remaining <= MIN_REMAINING_CREDITS+quote_workers:
            break
        quote_report = quote_runner(
            settings, plan,
            max_new_requests=min(MAX_NEW_QUOTE_REQUESTS, left),
            max_observed_credits=min(QUOTE_CREDIT_CAP, credit_left),
            workers=quote_workers, authorize=authorize, paid=paid, private=private,
            token=token, progress=lambda row: emit("QUOTES", quote_event=row),
        )
        used=quote_report.get("new_provider_attempts")
        charge=quote_report.get("observed_credits_this_invocation")
        if (type(used) is not int or type(charge) is not int
                or not 0 <= used <= min(MAX_NEW_QUOTE_REQUESTS, left)
                or charge < 0
                or quote_report.get("plan_fingerprint") != plan["plan_fingerprint"]
                or quote_report.get("unique_exact_quote_series") != plan["unique_exact_quote_series"]):
            raise CandidateChainCacheError("quote original receipt/credit accounting mismatch")
        quote_attempts += used
        quote_credits += charge
        rem=quote_report.get("last_observed_provider_remaining")
        if rem is not None:
            if type(rem) is not int or rem < 0:
                raise CandidateChainCacheError("quote remaining-credit header malformed")
            last_remaining=rem if last_remaining is None else min(last_remaining, rem)
        emit("QUOTE_PASS_COMPLETE", new_quote_gets=quote_attempts, observed_quote_credits=quote_credits,
             complete_quote_histories=quote_report["complete_source_series"],
             pending=quote_report["pending"], last_provider_remaining=last_remaining,
             cumulative_elapsed_seconds=round(time.perf_counter()-started, 2))
        if quote_report.get("status") == "COMPLETE_SOURCE_ONLY" and quote_report.get("pending") == 0:
            break
        if not used:
            break
    if quote_report is None:
        # Quota floor reached before a request; source and immutable plan exist.
        return {
            "contract": CONTRACT, "status": "FULL_CHAIN_SOURCE_QUOTE_CREDIT_OR_REQUEST_GATE",
            "new_chain_requests": attempted, "new_quote_requests": 0,
            "observed_chain_credits": chain_credits, "observed_quote_credits": 0,
            "observed_total_credits": chain_credits,
            "last_provider_remaining": last_remaining, "quote_plan_fingerprint": plan["plan_fingerprint"],
            "original_paid_receipts_replayed": 0,
        }
    # One local full-corpus audit only at terminal quote coverage, never
    # between paid batches. SHA/receipt checks are inherited from the reader.
    coverage = None
    if quote_report.get("status") == "COMPLETE_SOURCE_ONLY" and quote_report.get("pending") == 0:
        coverage = coverage_auditor(settings, last_shard_inclusive=LAST_SHARD)
        if (coverage.get("status") != "COMPLETE_SOURCE_ONLY"
                or coverage.get("frozen_plan_fingerprint") != plan["plan_fingerprint"]
                or coverage.get("unique_exact_quote_series") != plan["unique_exact_quote_series"]
                or coverage.get("complete_exact_histories") != quote_report["complete_source_series"]
                or coverage.get("exact_quote_no_data_gaps") != quote_report["exact_source_gaps"]
                or coverage.get("pending_exact_histories") != 0
                or coverage.get("provider_requests_this_audit") != 0):
            raise CandidateChainCacheError("terminal local EOD audit disagrees with original receipts")
        emit("FULL_2022_LOCAL_COVERAGE", audit_fingerprint=coverage["audit_fingerprint"],
             reported_eod_rows=coverage["total_observed_eod_rows"],
             positive_volume_rows=coverage["rows_with_positive_reported_volume"],
             zero_volume_rows=coverage["rows_with_zero_reported_volume"],
             histories_without_positive_volume=coverage["histories_with_no_positive_reported_volume"],
             provider_reads=0)
    result = {
        "contract": CONTRACT,
        "status": ("COMPLETE_FROZEN_2022_SOURCE_AND_QUOTE_CORPUS"
                   if quote_report.get("status") == "COMPLETE_SOURCE_ONLY" and quote_report.get("pending") == 0
                   else "PARTIAL_QUOTES_BUDGET_OR_PROVIDER_FLOOR"),
        "source_range_new": "26..70", "source_range_total": "0..70",
        "frozen_global_chain_keys": len(previous_keys),
        "source_shards_completed_this_run": len(finished),
        "accepted_replay_source_loads": source_loads,
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "quote_report_fingerprint": quote_report["report_fingerprint"],
        "unique_exact_histories_including_reused": plan["unique_exact_quote_series"],
        "complete_exact_histories_including_reused": quote_report["complete_source_series"],
        "exact_quote_no_data_gaps": quote_report["exact_source_gaps"],
        "pending_quote_histories": quote_report["pending"],
        "new_chain_requests": attempted, "new_quote_requests": quote_attempts,
        "observed_chain_credits": chain_credits, "observed_quote_credits": quote_credits,
        "observed_total_credits": chain_credits+quote_credits,
        "last_provider_remaining": last_remaining,
        "verified_original_quote_body_bytes": quote_report["verified_and_new_raw_body_bytes"],
        "original_paid_receipts_replayed": 0,
        "terminal_local_audit_fingerprint": coverage["audit_fingerprint"] if coverage else None,
        "terminal_observed_eod_rows": coverage["total_observed_eod_rows"] if coverage else None,
        "terminal_positive_volume_rows": coverage["rows_with_positive_reported_volume"] if coverage else None,
        "terminal_zero_volume_rows": coverage["rows_with_zero_reported_volume"] if coverage else None,
        "source_only_no_0935_option_fill_pnl_paper_live_or_broker_authority": True,
    }
    result["report_fingerprint"] = _fingerprint(result)
    return result
