from __future__ import annotations

"""Bounded 2022-2024 expansion over accepted stock opportunities.

The first run exports native-raw-verified inputs once; subsequent runs reuse
the immutable bundle/plan. Existing chain cache owns all provider-side attempts.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_accepted_stock_candidate_export_v1 import (
    CONTRACT as EXPORT_CONTRACT, export_candidate_stock_manifest,
)
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, MAX_NEW_REQUESTS, MIN_REMAINING_CREDITS,
    _fingerprint, record_exact_query_no_data, run_candidate_chain_cache,
    verify_candidate_plan,
)
from packages.data.research_storage import inspect_research_storage

CONTRACT = "atlas-marketdata-candidate-expansion-2022-2024-v1"
BINDING_REL = "data/options/manifests/marketdata_candidate_expansion_v1"
ALLOWED_YEARS = frozenset({2022, 2023, 2024})
MAX_TOTAL_NEW_REQUESTS = 50
MAX_OBSERVED_CREDITS = 100
MAX_PER_MONTH = 3


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise CandidateChainCacheError("missing or linked immutable expansion evidence")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CandidateChainCacheError("expansion evidence root must be an object")
    return data


def _exclusive(path: Path, value: dict[str, Any]) -> None:
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(encoded)
        f.flush()
        os.fsync(f.fileno())
    if path.read_bytes() != encoded:
        raise CandidateChainCacheError("immutable expansion manifest read-back differs")


def _bound_path(settings: AtlasSettings, year: int, per_month: int) -> Path:
    return settings.resolved_path(f"{BINDING_REL}/year_{year}_per_month_{per_month}.json")


def _require_external(settings: AtlasSettings) -> None:
    snapshot = inspect_research_storage(settings)
    if (snapshot.storage_mode != "EXTERNAL_SECONDARY"
            or snapshot.status == "BLOCKED_MINIMUM_FREE_SPACE"
            or snapshot.category_quota_gib["options_candidate_cache"] < 120):
        raise CandidateChainCacheError(
            "expansion requires ready D: secondary research storage with 120 GiB candidate quota"
        )


def prepare_cohort(
    settings: AtlasSettings, *, year: int, per_month: int, duckdb_threads: int,
    exporter: Callable[..., dict[str, Any]] = export_candidate_stock_manifest,
) -> tuple[dict[str, Any], Path, dict[str, Any], str]:
    """Verify reused frozen output; never repeat expensive accepted-source loading."""
    if year not in ALLOWED_YEARS or not 1 <= per_month <= MAX_PER_MONTH:
        raise CandidateChainCacheError("cohort must be 2022..2024 and 1..3/month; 2025 pilot is separate")
    if not 1 <= duckdb_threads <= 8:
        raise CandidateChainCacheError("DuckDB threads must be 1..8")
    path = _bound_path(settings, year, per_month)
    if path.exists() or path.is_symlink():
        binding = _read_object(path)
        unsigned = dict(binding)
        fp = unsigned.pop("binding_fingerprint", None)
        if (fp != _fingerprint(unsigned)
                or binding.get("contract") != CONTRACT
                or binding.get("year") != year
                or binding.get("per_month") != per_month
                or binding.get("cohort_id") is None):
            raise CandidateChainCacheError("existing expansion binding differs; never overwrite")
        action = "REUSED_IMMUTABLE_EXPORTED_COHORT"
    else:
        exported = exporter(settings, year=year, per_month=per_month, duckdb_threads=duckdb_threads)
        if (exported["provider_reads"] != 0
                or not 1 <= exported["selected_opportunities"] <= 36
                or not 1 <= exported["shared_chain_requests"] <= 36):
            raise CandidateChainCacheError("accepted exporter returned unexpected authority/counts")
        binding = {
            "contract": CONTRACT,
            "year": year,
            "per_month": per_month,
            "cohort_id": exported["cohort_identity"],
            "source_sha256": exported["stock_source_sha256"],
            "plan_fingerprint": exported["plan_fingerprint"],
            "provider_reads_in_export": 0,
            "source_role": "ACCEPTED_NATIVE_RAW_DEVELOPMENT_ONLY",
            "no_option_price_or_strategy_promotion_authority": True,
        }
        binding["binding_fingerprint"] = _fingerprint(binding)
        _exclusive(path, binding)
        action = "EXPORTED_AND_BOUND_NEW_COHORT"
    cohort = binding["cohort_id"]
    if (not isinstance(cohort, str) or len(cohort) != 16
            or any(ch not in "0123456789abcdef" for ch in cohort)):
        raise CandidateChainCacheError("invalid frozen cohort identity")
    source = settings.resolved_path(
        f"data/research/evidence/marketdata_candidate_stock_v1/{cohort}.json"
    )
    plan_path = settings.resolved_path(
        f"data/options/manifests/marketdata_candidate_batch_plan_v1_{cohort}.json"
    )
    bundle = _read_object(source)
    plan = verify_candidate_plan(_read_object(plan_path))
    if (_sha(source) != binding["source_sha256"]
            or plan["plan_fingerprint"] != binding["plan_fingerprint"]
            or bundle.get("contract") != EXPORT_CONTRACT
            or bundle.get("year") != year
            or bundle.get("per_month") != per_month
            or bundle.get("protected_master_return_rows_read") != 0
            or bundle.get("authority", {}).get("provider_reads") is not False
            or len(bundle.get("rows", [])) != plan["opportunities"]
            or not 1 <= plan["shared_chain_requests"] <= 36
            or {row["stock_source_sha256"] for row in plan["source_bindings"].values()}
               != {binding["source_sha256"]}):
        raise CandidateChainCacheError("exported private native-raw source or plan lineage changed")
    return plan, source, binding, action


def _checkpoint(settings: AtlasSettings, plan: dict[str, Any]) -> dict[str, Any]:
    path = settings.resolved_path(
        "data/options/manifests/marketdata_candidate_chain_cache_v1_"
        + plan["plan_fingerprint"][:16] + ".json"
    )
    report = _read_object(path)
    unsigned = dict(report)
    signature = unsigned.pop("report_fingerprint", None)
    if (signature != _fingerprint(unsigned)
            or report.get("plan_fingerprint") != plan["plan_fingerprint"]
            or report.get("status") != "FAILED_REVIEW_REQUIRED"):
        raise CandidateChainCacheError("failure checkpoint identity/status mismatch; preserve evidence")
    return report


def _offline_404_sidecar(settings: AtlasSettings, plan: dict[str, Any]) -> str:
    """Only exact zero-credit 404/no_data with full original proof qualifies."""
    report = _checkpoint(settings, plan)
    rows = report.get("request_results") or []
    if (not rows or rows[-1].get("status") != "FAILED_REVIEW_REQUIRED"
            or rows[-1].get("exception_type") != "CandidateChainCacheError"
            or report.get("quarantined") != 1
            or not isinstance(rows[-1].get("request_identity"), str)):
        raise CandidateChainCacheError("not a proven exact zero-credit 404; no automated continuation")
    request_identity = rows[-1]["request_identity"]
    proof = record_exact_query_no_data(
        settings, plan, request_identity, authorize_offline_classification=True,
    )
    if proof["action"] not in ("RECORDED_VERIFIED_NO_DATA", "REUSED_VERIFIED_NO_DATA_PROOF"):
        raise CandidateChainCacheError("exact query gap not durably proven")
    return request_identity


def run_expansion(
    settings: AtlasSettings, plan: dict[str, Any], source: Path, *,
    max_total_new_requests: int = 0,
    max_observed_credits: int = MAX_OBSERVED_CREDITS,
    authorize: bool = False, paid: bool = False, private: bool = False,
    classify_no_data: bool = False,
    runner: Callable[..., dict[str, Any]] = run_candidate_chain_cache,
    no_data_handler: Callable[[AtlasSettings, dict[str, Any]], str] = _offline_404_sidecar,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if not 0 <= max_total_new_requests <= MAX_TOTAL_NEW_REQUESTS:
        raise CandidateChainCacheError("total request budget must be 0..50")
    if not 1 <= max_observed_credits <= MAX_OBSERVED_CREDITS:
        raise CandidateChainCacheError("observed credit budget must be 1..100")
    if max_total_new_requests and not (authorize and paid and private):
        raise CandidateChainCacheError("all three explicit paid-source confirmations required")
    if not max_total_new_requests and (authorize or paid or private or classify_no_data):
        raise CandidateChainCacheError("authorization flags require a positive request budget")
    verified = verify_candidate_plan(plan)
    if (verified["plan_fingerprint"] != plan["plan_fingerprint"]
            or not 1 <= len(verified["requests"]) <= 36
            or not source.is_file() or source.is_symlink()):
        raise CandidateChainCacheError("expanded chain plan/source is not accepted")
    if max_total_new_requests:
        _require_external(settings)
    before = runner(settings, plan)
    attempted = credits = proven_no_data = 0
    latest = before
    last_remaining = None
    while max_total_new_requests and latest["pending"] > 0 and attempted < max_total_new_requests:
        if credits >= max_observed_credits:
            break
        if last_remaining is not None and last_remaining < MIN_REMAINING_CREDITS:
            break
        budget = min(MAX_NEW_REQUESTS, max_total_new_requests - attempted)
        try:
            outcome = runner(
                settings, plan, authorize_provider_reads=True,
                confirm_paid_starter=True, confirm_private_internal_use=True,
                max_new_requests=budget, stock_source_files=(source,),
            )
        except CandidateChainCacheError:
            # Existing cache persists full failure evidence; only a user-enabled
            # exact 404/no_data zero-credit proof may be classified offline.
            failure = _checkpoint(settings, plan)
            attempted += failure["provider_reads"]
            credits += failure["observed_credits_consumed_this_run"]
            last_remaining = failure["last_observed_provider_credits_remaining"]
            if not classify_no_data:
                raise
            rid = no_data_handler(settings, plan)  # raises on any other error
            proven_no_data += 1
            if progress is not None:
                progress({
                    "stage": "VERIFIED_EXACT_QUERY_GAP", "request_identity": rid,
                    "attempted": attempted, "observed_credits": credits,
                })
        else:
            attempted += outcome["provider_reads"]
            credits += outcome["observed_credits_consumed_this_run"]
            last_remaining = outcome["last_observed_provider_credits_remaining"]
            if progress is not None:
                progress({
                    "stage": outcome["status"], "attempted": attempted,
                    "observed_credits": credits, "remaining": last_remaining,
                    "complete": outcome["reused"] + outcome["new_complete"],
                    "gaps": outcome["no_data_verified"], "pending": outcome["pending"],
                })
            if outcome["status"] in ("PARTIAL_CREDIT_FLOOR", "PARTIAL_STORAGE_BLOCKED"):
                break
            if outcome["provider_reads"] == 0:
                break
        # Read-only rehash of original receipts, including a proven 404 sidecar.
        latest = runner(settings, plan)
    final = runner(settings, plan)
    report = {
        "contract": CONTRACT,
        "plan_fingerprint": plan["plan_fingerprint"],
        "status": ("COMPLETE_WITH_EXACT_QUERY_GAPS" if not final["pending"] and final["no_data_verified"]
                   else "COMPLETE" if not final["pending"]
                   else "PREVIEW_NO_PROVIDER_READS" if max_total_new_requests == 0
                   else "PARTIAL_BOUND_REACHED"),
        "planned_requests": final["planned_chain_requests"],
        "completed_chains": final["reused"],
        "proven_exact_query_gaps": final["no_data_verified"],
        "pending": final["pending"],
        "new_provider_attempts_this_invocation": attempted,
        "observed_provider_credits_this_invocation": credits,
        "last_observed_credits_remaining": last_remaining,
        "new_offline_exact_gap_proofs": proven_no_data,
        "no_selected_quotes_or_option_pnl_authority": True,
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
