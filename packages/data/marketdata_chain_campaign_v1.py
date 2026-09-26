from __future__ import annotations

"""One workstation gate for a bounded multi-year historical chain campaign.

Per-year immutable source exports and the original receipt-level cache remain
the sole authority. This composer never calls a provider directly.
"""

from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import (
    _require_external, prepare_cohort, run_expansion,
)

CONTRACT = "atlas-marketdata-development-chain-campaign-v1"
YEARS = (2024, 2023, 2022)
MAX_TOTAL_NEW_REQUESTS = 100
MAX_OBSERVED_CREDITS = 100


def run_chain_campaign(
    settings: AtlasSettings, *,
    years: tuple[int, ...] = YEARS,
    per_month: int = 3, duckdb_threads: int = 4,
    max_total_new_requests: int = 0, max_observed_credits: int = 80,
    authorize: bool = False, paid: bool = False, private: bool = False,
    classify_no_data: bool = False,
    preparer: Callable[..., tuple[dict[str, Any], object, dict[str, Any], str]] = prepare_cohort,
    runner: Callable[..., dict[str, Any]] = run_expansion,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not years or len(set(years)) != len(years) or any(x not in YEARS for x in years):
        raise CandidateChainCacheError("campaign years must be a nonduplicate subset of 2024/2023/2022")
    if not 1 <= per_month <= 3 or not 1 <= duckdb_threads <= 8:
        raise CandidateChainCacheError("campaign sampling or DuckDB thread bound invalid")
    if not 0 <= max_total_new_requests <= MAX_TOTAL_NEW_REQUESTS:
        raise CandidateChainCacheError("campaign new request limit must be 0..100")
    if not 1 <= max_observed_credits <= MAX_OBSERVED_CREDITS:
        raise CandidateChainCacheError("campaign observed credit budget must be 1..100")
    if max_total_new_requests and not (authorize and paid and private):
        raise CandidateChainCacheError("campaign needs explicit provider/paid/private confirmations")
    if not max_total_new_requests and any((authorize, paid, private, classify_no_data)):
        raise CandidateChainCacheError("campaign provider authorizations require positive request cap")
    _require_external(settings)
    total_attempts = total_credits = 0
    year_reports: list[dict[str, Any]] = []
    status = "PREVIEW_NO_PROVIDER_READS" if not max_total_new_requests else "COMPLETE"
    for year in years:
        remaining_calls = max_total_new_requests - total_attempts
        remaining_credits = max_observed_credits - total_credits
        if max_total_new_requests and (remaining_calls <= 0 or remaining_credits <= 0):
            status = "PARTIAL_CAMPAIGN_BUDGET"
            break
        if progress is not None:
            progress({"stage": "COHORT_START", "year": year,
                      "remaining_request_budget": remaining_calls,
                      "remaining_observed_credit_budget": remaining_credits})
        plan, source, binding, action = preparer(
            settings, year=year, per_month=per_month,
            duckdb_threads=duckdb_threads,
        )
        if not isinstance(binding, dict) or binding.get("year") != year:
            raise CandidateChainCacheError("campaign exporter year binding mismatch")
        if progress is not None:
            progress({
                "stage": "COHORT_BOUND", "year": year, "action": action,
                "cohort_id": binding["cohort_id"],
                "plan_fingerprint": plan["plan_fingerprint"],
                "shared_chains": plan["shared_chain_requests"],
            })
        year_result = runner(
            settings, plan, source,
            max_total_new_requests=min(50, remaining_calls) if max_total_new_requests else 0,
            max_observed_credits=max(1, remaining_credits),
            authorize=authorize, paid=paid, private=private,
            classify_no_data=classify_no_data,
            progress=(
                (lambda item, target_year=year: progress({"year": target_year, **item}))
                if progress is not None else None
            ),
        )
        spent_calls = year_result["new_provider_attempts_this_invocation"]
        spent_credits = year_result["observed_provider_credits_this_invocation"]
        if (type(spent_calls) is not int or not 0 <= spent_calls <= remaining_calls
                or type(spent_credits) is not int or spent_credits < 0):
            raise CandidateChainCacheError("underlying cache reported inconsistent budget accounting")
        total_attempts += spent_calls
        total_credits += spent_credits
        row = {
            "year": year,
            "cohort_id": binding["cohort_id"],
            "binding_fingerprint": binding["binding_fingerprint"],
            "plan_fingerprint": plan["plan_fingerprint"],
            "source_sha256": binding["source_sha256"],
            "export_action": action,
            **year_result,
        }
        year_reports.append(row)
        if progress is not None:
            progress({"stage": "COHORT_FINISHED", "year": year,
                      "status": row["status"], "complete": row["completed_chains"],
                      "gaps": row["proven_exact_query_gaps"], "pending": row["pending"],
                      "total_new_attempts": total_attempts,
                      "total_observed_credits": total_credits})
        if year_result["pending"]:
            status = ("PREVIEW_NO_PROVIDER_READS" if not max_total_new_requests
                      else "PARTIAL_CAMPAIGN_BUDGET" if (
                          total_attempts >= max_total_new_requests
                          or total_credits >= max_observed_credits
                      ) else "PARTIAL_COHORT_REQUIRES_REVIEW")
            break
        if max_total_new_requests and total_credits >= max_observed_credits and year != years[-1]:
            status = "PARTIAL_CAMPAIGN_BUDGET"
            break
    if max_total_new_requests and len(year_reports) < len(years) and status == "COMPLETE":
        status = "PARTIAL_CAMPAIGN_BUDGET"
    result = {
        "contract": CONTRACT, "status": status, "years_in_order": list(years),
        "per_month": per_month, "max_total_new_requests": max_total_new_requests,
        "max_observed_credits": max_observed_credits,
        "new_provider_attempts": total_attempts, "observed_credits": total_credits,
        "completed_years": [row["year"] for row in year_reports if not row["pending"]],
        "year_reports": year_reports,
        "selected_quotes_acquired": 0,
        "source_only_no_option_pnl_paper_live_or_broker_authority": True,
    }
    result["campaign_fingerprint"] = _fingerprint(result)
    return result
