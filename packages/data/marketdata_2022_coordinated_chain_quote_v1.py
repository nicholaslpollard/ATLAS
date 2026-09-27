from __future__ import annotations

"""One bounded chain-then-history acquisition for 2022 PIT monthly CALL sources.

All original physical-provider work is delegated to audited source/quote caches.
A partial chain source is a hard barrier: no quote-plan expansion until every
requested original shard has reached an accepted terminal receipt state.
"""

from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_additive_2022_campaign_v1 import (
    run_additive_campaign, MAX_NEW_REQUESTS as CHAIN_MAX_REQUESTS,
)
from packages.data.marketdata_2022_broad_quote_campaign_v2 import (
    PLAN_REL, freeze_broad_quote_plan, run_broad_quote_histories,
)
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, MIN_REMAINING_CREDITS, _fingerprint,
)
from packages.data.marketdata_candidate_expansion_v1 import (
    _exclusive, _read_object, _require_external,
)
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    MAX_NEW_QUOTE_REQUESTS, MAX_OBSERVED_CREDITS as QUOTE_MAX_CREDITS,
    MAX_WORKERS,
)

CONTRACT = "atlas-marketdata-2022-coordinated-chain-quote-batch-v1"
MAX_SHARDS_PER_BATCH = 10
MAX_TOTAL_OBSERVED_CREDITS = 4000


def run_coordinated_batch(
    settings: AtlasSettings, *, start_shard: int = 16, shard_count: int = 10,
    max_new_chain_requests: int = 400, max_new_quote_requests: int = 3000,
    max_total_observed_credits: int = 3500, workers: int = 16,
    duckdb_threads: int = 4,
    authorize: bool = False, paid: bool = False, private: bool = False,
    token: str | None = None,
    chain_runner: Callable[..., dict[str, Any]] = run_additive_campaign,
    plan_builder: Callable[..., dict[str, Any]] = freeze_broad_quote_plan,
    quote_runner: Callable[..., dict[str, Any]] = run_broad_quote_histories,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Progress 10 new shards then all unique quote series through that shard.

    Protects both stages with the SAME account/credit cap, source completion
    barrier, original exact cache identities and explicit operator authorization.
    """
    if (type(start_shard) is not int or type(shard_count) is not int
            or not 16 <= start_shard <= 70
            or not 1 <= shard_count <= MAX_SHARDS_PER_BATCH
            or start_shard + shard_count > 71):
        raise CandidateChainCacheError("source range must be 16..70 and <=10 consecutive shards")
    if (type(max_new_chain_requests) is not int
            or not 0 <= max_new_chain_requests <= CHAIN_MAX_REQUESTS
            or type(max_new_quote_requests) is not int
            or not 0 <= max_new_quote_requests <= MAX_NEW_QUOTE_REQUESTS
            or not max_new_chain_requests and not max_new_quote_requests):
        raise CandidateChainCacheError("new chain/quote request limits malformed")
    if (type(max_total_observed_credits) is not int
            or not 1 <= max_total_observed_credits <= MAX_TOTAL_OBSERVED_CREDITS
            or not 1 <= workers <= MAX_WORKERS
            or not 1 <= duckdb_threads <= 8):
        raise CandidateChainCacheError("combined observed credit, worker or DuckDB cap invalid")
    if not (authorize and paid and private and isinstance(token, str) and token.strip()):
        raise CandidateChainCacheError("explicit paid/private/source confirmations and MarketData token required")
    _require_external(settings)
    end = start_shard + shard_count - 1

    def emit(stage: str, item: dict[str, Any]) -> None:
        if progress is not None:
            progress({"stage": stage, **item})

    source_credit_target = min(500, max_total_observed_credits)
    emit("COORDINATED_PREFLIGHT", {
        "source_range": f"{start_shard}..{end}",
        "chain_get_limit": max_new_chain_requests,
        "quote_get_limit": max_new_quote_requests,
        "observed_total_credit_target": max_total_observed_credits,
        "quote_network_workers": workers,
        "prior_completed_quote_responses_to_refetch": 0,
    })
    source = chain_runner(
        settings, start_shard=start_shard, max_shards=shard_count,
        duckdb_threads=duckdb_threads,
        max_total_new_requests=max_new_chain_requests,
        max_observed_credits=source_credit_target,
        authorize=authorize, paid=paid, private=private,
        classify_no_data=True,
        progress=lambda row: emit("CHAIN", row),
    )
    source_rows = source.get("shard_reports")
    chain_credits = source.get("observed_credits")
    if (type(chain_credits) is not int or chain_credits < 0
            or chain_credits > max_total_observed_credits
            or not isinstance(source_rows, list)
            or type(source.get("new_provider_attempts")) is not int
            or source["new_provider_attempts"] > max_new_chain_requests):
        raise CandidateChainCacheError("original source runner accounting malformed")
    complete_source_range = (
        source.get("status") == "COMPLETE_CAMPAIGN_RANGE"
        and len(source_rows) == shard_count
        and [x.get("shard_index") for x in source_rows] == list(range(start_shard, end + 1))
        and all(x.get("pending") == 0 for x in source_rows)
    )
    emit("SOURCE_RANGE_FINISHED", {
        "status": source.get("status"), "new_chain_gets": source["new_provider_attempts"],
        "chain_credits": chain_credits,
        "completed_shards": len(source_rows),
        "source_report_fingerprint": source.get("campaign_fingerprint"),
        "last_provider_remaining": source.get("last_observed_provider_remaining"),
    })
    if not complete_source_range:
        # Do not write a broader quote plan, dispatch a quote, or hide partial
        # status behind the original chain runner's CLI exit code of zero.
        return {
            "contract": CONTRACT, "status": "SOURCE_RANGE_INCOMPLETE_NO_QUOTE_REQUESTS",
            "source_report_fingerprint": source.get("campaign_fingerprint"),
            "source_status": source.get("status"), "source_shards_completed": len(source_rows),
            "target_last_shard": end,
            "new_chain_requests": source["new_provider_attempts"],
            "new_quote_requests": 0,
            "observed_chain_credits": chain_credits, "observed_quote_credits": 0,
            "observed_total_credits": chain_credits,
            "original_paid_receipts_replayed": 0,
        }

    remaining_target = max_total_observed_credits - chain_credits
    remaining_header = source.get("last_observed_provider_remaining")
    if (remaining_target < 1 or (remaining_header is not None and (
            type(remaining_header) is not int
            or remaining_header <= MIN_REMAINING_CREDITS + workers))):
        return {
            "contract": CONTRACT, "status": "SOURCE_COMPLETE_QUOTE_CREDIT_GATE",
            "source_report_fingerprint": source["campaign_fingerprint"],
            "target_last_shard": end,
            "new_chain_requests": source["new_provider_attempts"],
            "new_quote_requests": 0,
            "observed_chain_credits": chain_credits, "observed_quote_credits": 0,
            "observed_total_credits": chain_credits,
            "original_paid_receipts_replayed": 0,
        }
    if max_new_quote_requests == 0:
        return {
            "contract": CONTRACT, "status": "SOURCE_COMPLETE_QUOTE_REQUEST_BUDGET_ZERO",
            "source_report_fingerprint": source["campaign_fingerprint"],
            "target_last_shard": end,
            "new_chain_requests": source["new_provider_attempts"],
            "new_quote_requests": 0,
            "observed_chain_credits": chain_credits, "observed_quote_credits": 0,
            "observed_total_credits": chain_credits,
            "original_paid_receipts_replayed": 0,
        }

    plan = plan_builder(settings, last_shard_inclusive=end)
    plan_path = settings.resolved_path(
        f"{PLAN_REL}/through_shard_{end:03d}.json"
    )
    if plan_path.exists() or plan_path.is_symlink():
        if _read_object(plan_path) != plan:
            raise CandidateChainCacheError("previously frozen quote plan differs; stop before paid read")
        plan_action = "REUSED_IDENTICAL_IMMUTABLE_PLAN"
    else:
        _exclusive(plan_path, plan)
        if _read_object(plan_path) != plan:
            raise CandidateChainCacheError("new immutable quote plan readback differs")
        plan_action = "WRITTEN_NEW_IMMUTABLE_PLAN"
    emit("QUOTE_PLAN_VERIFIED", {
        "plan_action": plan_action,
        "source_shards": f"0..{end}", "plan_fingerprint": plan["plan_fingerprint"],
        "source_abstention_entries": len(plan["source_gaps"]),
        "candidate_memberships": plan["selected_candidate_memberships"],
        "unique_exact_series_including_prior": plan["unique_exact_quote_series"],
        "new_get_limit": max_new_quote_requests,
        "remaining_combined_observed_credit_target": remaining_target,
        "workers": workers,
    })
    quote = quote_runner(
        settings, plan, max_new_requests=max_new_quote_requests,
        max_observed_credits=min(QUOTE_MAX_CREDITS, remaining_target),
        workers=workers,
        authorize=authorize, paid=paid, private=private, token=token,
        progress=lambda row: emit("QUOTES", row),
    )
    quote_credits = quote.get("observed_credits_this_invocation")
    quote_gets = quote.get("new_provider_attempts")
    if (type(quote_credits) is not int or quote_credits < 0
            or type(quote_gets) is not int or quote_gets < 0
            or quote_gets > max_new_quote_requests
            or quote.get("unique_exact_quote_series") != plan["unique_exact_quote_series"]
            or quote.get("plan_fingerprint") != plan["plan_fingerprint"]):
        raise CandidateChainCacheError("original quote source report accounting differs")
    total = chain_credits + quote_credits
    result = {
        "contract": CONTRACT,
        "status": (
            "COMPLETE_CHAIN_AND_QUOTE_RANGE" if (
                quote.get("status") == "COMPLETE_SOURCE_ONLY" and quote.get("pending") == 0
            ) else "SOURCE_COMPLETE_QUOTE_PARTIAL"
        ),
        "source_report_fingerprint": source["campaign_fingerprint"],
        "source_status": source["status"],
        "source_range": f"{start_shard}..{end}",
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "quote_report_fingerprint": quote["report_fingerprint"],
        "unique_exact_histories_including_reused": plan["unique_exact_quote_series"],
        "complete_exact_histories_including_reused": quote["complete_source_series"],
        "exact_quote_no_data_gaps": quote["exact_source_gaps"],
        "pending_quote_histories": quote["pending"],
        "new_chain_requests": source["new_provider_attempts"],
        "new_quote_requests": quote_gets,
        "observed_chain_credits": chain_credits,
        "observed_quote_credits": quote_credits,
        "observed_total_credits": total,
        "last_provider_remaining": quote["last_observed_provider_remaining"] or remaining_header,
        "verified_original_quote_body_bytes": quote["verified_and_new_raw_body_bytes"],
        "original_paid_receipts_replayed": 0,
        "source_only_no_0935_option_fill_pnl_paper_live_or_broker_authority": True,
    }
    result["report_fingerprint"] = _fingerprint(result)
    return result
