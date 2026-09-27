from __future__ import annotations

"""Bounded resumable 2022 additive chain acquisition across consecutive frozen shards.

This module does not call a provider: the existing immutable cache owns every
request, source check, storage reservation, credit observation, and no-data proof.
"""

from pathlib import Path
from typing import Any, Callable

from packages.backtesting.recurrent_successor_outcome_replay import load_selected_replay_opportunities
from packages.core.settings import AtlasSettings
from packages.data.marketdata_additive_2022_shards_v1 import (
    KEYS_PER_SHARD, YEAR, prepare_additive_shard,
)
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, MIN_REMAINING_CREDITS, _fingerprint,
)
from packages.data.marketdata_candidate_expansion_v1 import (
    _read_object, _require_external, run_expansion,
)

CONTRACT = "atlas-marketdata-additive-2022-campaign-v1"
MAX_SHARDS_PER_RUN = 10
MAX_NEW_REQUESTS = 400
MAX_OBSERVED_CREDITS = 500


def run_additive_campaign(
    settings: AtlasSettings, *, start_shard: int = 0, max_shards: int = 6,
    duckdb_threads: int = 4, max_total_new_requests: int = 0,
    max_observed_credits: int = 250,
    authorize: bool = False, paid: bool = False, private: bool = False,
    classify_no_data: bool = False,
    preparer: Callable[..., Any] = prepare_additive_shard,
    runner: Callable[..., dict[str, Any]] = run_expansion,
    loader: Callable[..., Any] = load_selected_replay_opportunities,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if type(start_shard) is not int or not 0 <= start_shard <= 999:
        raise CandidateChainCacheError("start shard outside registered bounds")
    if type(max_shards) is not int or not 1 <= max_shards <= MAX_SHARDS_PER_RUN:
        raise CandidateChainCacheError("campaign shard count outside 1..10")
    if not 1 <= duckdb_threads <= 8:
        raise CandidateChainCacheError("DuckDB threads outside 1..8")
    if (type(max_total_new_requests) is not int
            or not 0 <= max_total_new_requests <= MAX_NEW_REQUESTS):
        raise CandidateChainCacheError("campaign request cap outside 0..400")
    if (type(max_observed_credits) is not int
            or not 1 <= max_observed_credits <= MAX_OBSERVED_CREDITS):
        raise CandidateChainCacheError("campaign observed-credit target outside 1..500")
    if max_total_new_requests and not (authorize and paid and private):
        raise CandidateChainCacheError("explicit provider/paid/private confirmations required")
    if not max_total_new_requests and any((authorize, paid, private, classify_no_data)):
        raise CandidateChainCacheError("authorization requires a positive request budget")
    _require_external(settings)

    def emit(item: dict[str, Any]) -> None:
        if progress is not None:
            progress(item)

    source_loads = 0
    cached_source: Any = None

    def load_once(*args: Any, **kwargs: Any) -> Any:
        nonlocal cached_source, source_loads
        if cached_source is None:
            cached_source = loader(*args, **kwargs)
            source_loads += 1
        return cached_source

    def prepare(index: int) -> tuple[dict[str, Any], Path, dict[str, Any], str, dict[str, Any]]:
        plan, path, binding, action = preparer(
            settings, shard_index=index, duckdb_threads=duckdb_threads,
            loader=load_once, progress=lambda item: emit({"shard_index": index, **item}),
        )
        if (binding.get("shard_index") != index or binding.get("year") != YEAR
                or binding.get("plan_fingerprint") != plan.get("plan_fingerprint")
                or binding.get("shared_chains") != plan.get("shared_chain_requests")
                or not path.is_file() or path.is_symlink()):
            raise CandidateChainCacheError("additive source/plan binding mismatch")
        source = _read_object(path)
        keys = source.get("selected_query_keys")
        if (source.get("shard_index") != index
                or not isinstance(source.get("total_additive_shards"), int)
                or not isinstance(source.get("all_additive_query_keys_fingerprint"), str)
                or not isinstance(keys, list)
                or not 1 <= len(keys) <= KEYS_PER_SHARD
                or len(keys) != binding["shared_chains"]):
            raise CandidateChainCacheError("frozen shard census missing or malformed")
        return plan, path, binding, action, source

    # Shard zero is the original accepted 2,812-key / 71-shard census anchor.
    # It is reused without reloading native sources or repeating paid calls.
    anchor = prepare(0)
    anchor_source = anchor[4]
    total_shards = anchor_source["total_additive_shards"]
    if start_shard >= total_shards or start_shard + max_shards > total_shards:
        raise CandidateChainCacheError(
            f"requested range exceeds original {total_shards}-shard source census"
        )
    census = anchor_source["all_additive_query_keys_fingerprint"]
    emit({"stage": "FROZEN_CENSUS", "year": YEAR, "total_shards": total_shards,
          "census_fingerprint": census, "anchor_action": anchor[3]})
    attempts = credits = 0
    last_remaining: int | None = None
    results: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    status = "PREVIEW_NO_PROVIDER_READS" if not max_total_new_requests else "COMPLETE_CAMPAIGN_RANGE"
    for index in range(start_shard, start_shard + max_shards):
        remaining_calls = max_total_new_requests - attempts
        remaining_credits = max_observed_credits - credits
        if max_total_new_requests and (remaining_calls <= 0 or remaining_credits <= 0):
            status = "PARTIAL_CAMPAIGN_BUDGET"
            break
        if last_remaining is not None and last_remaining < MIN_REMAINING_CREDITS:
            status = "PARTIAL_PROVIDER_CREDIT_FLOOR"
            break
        plan, path, binding, action, source = anchor if index == 0 else prepare(index)
        if (source["all_additive_query_keys_fingerprint"] != census
                or source["total_additive_shards"] != total_shards):
            raise CandidateChainCacheError("shard disagrees with frozen global source census")
        keys: set[tuple[str, str, str]] = set()
        for raw in source["selected_query_keys"]:
            if (not isinstance(raw, list) or len(raw) != 3
                    or any(not isinstance(part, str) or not part for part in raw)):
                raise CandidateChainCacheError("malformed physical option query key")
            key = (raw[0], raw[1], raw[2])
            if key in keys or key in seen_keys:
                raise CandidateChainCacheError("duplicate physical option query across campaign shards")
            keys.add(key)
        seen_keys.update(keys)
        emit({"stage": "SHARD_BOUND", "shard_index": index,
              "source_action": action, "source_sha256": binding["source_sha256"],
              "plan_fingerprint": plan["plan_fingerprint"], "chains": len(keys),
              "remaining_request_budget": remaining_calls,
              "remaining_credit_target": remaining_credits})
        local_calls = min(KEYS_PER_SHARD, remaining_calls) if max_total_new_requests else 0
        local_credit_target = min(100, max(1, remaining_credits))
        result = runner(
            settings, plan, path,
            max_total_new_requests=local_calls,
            max_observed_credits=local_credit_target,
            authorize=authorize, paid=paid, private=private,
            classify_no_data=classify_no_data,
            progress=lambda row, i=index: emit({"shard_index": i, **row}),
        )
        used_calls = result["new_provider_attempts_this_invocation"]
        used_credits = result["observed_provider_credits_this_invocation"]
        if (type(used_calls) is not int or not 0 <= used_calls <= local_calls
                or type(used_credits) is not int or used_credits < 0
                or result["completed_chains"] + result["proven_exact_query_gaps"]
                   + result["pending"] != len(keys)):
            raise CandidateChainCacheError("cache returned inconsistent original receipt census/accounting")
        attempts += used_calls
        credits += used_credits
        if result["last_observed_credits_remaining"] is not None:
            last_remaining = result["last_observed_credits_remaining"]
        results.append({
            "shard_index": index, "source_action": action,
            "source_sha256": binding["source_sha256"],
            "plan_fingerprint": plan["plan_fingerprint"],
            "report_fingerprint": result["report_fingerprint"],
            "completed_chains": result["completed_chains"],
            "proven_exact_query_gaps": result["proven_exact_query_gaps"],
            "pending": result["pending"],
            "new_provider_attempts": used_calls,
            "observed_credits": used_credits,
        })
        emit({"stage": "SHARD_FINISHED", "shard_index": index,
              "completed": result["completed_chains"],
              "gaps": result["proven_exact_query_gaps"], "pending": result["pending"],
              "new_attempts_total": attempts, "observed_credits_total": credits,
              "last_provider_remaining": last_remaining})
        if result["pending"]:
            status = ("PREVIEW_NO_PROVIDER_READS" if not max_total_new_requests else
                      "PARTIAL_CAMPAIGN_BUDGET" if (
                          attempts >= max_total_new_requests or credits >= max_observed_credits
                      ) else "PARTIAL_SHARD_REQUIRES_REVIEW")
            break
    if max_total_new_requests and len(results) < max_shards and status == "COMPLETE_CAMPAIGN_RANGE":
        status = "PARTIAL_CAMPAIGN_BUDGET"
    report = {
        "contract": CONTRACT, "status": status, "year": YEAR,
        "start_shard": start_shard, "requested_shards": max_shards,
        "total_frozen_shards": total_shards,
        "global_keys_fingerprint": census,
        "anchor_plan_fingerprint": anchor[0]["plan_fingerprint"],
        "accepted_source_loads_this_run": source_loads,
        "new_provider_attempts": attempts,
        "observed_credits": credits,
        "last_observed_provider_remaining": last_remaining,
        "shard_reports": results,
        "original_2022_and_2025_provider_requests_replayed": 0,
        "historical_option_fill_or_pnl_authority": False,
        "paper_live_or_broker_authority": False,
    }
    report["campaign_fingerprint"] = _fingerprint(report)
    return report
