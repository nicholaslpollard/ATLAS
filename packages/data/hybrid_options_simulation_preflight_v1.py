from __future__ import annotations

"""Fail-closed, provider-free preflight for hybrid options simulation inputs.

V5 bridges the exact-query gap planner with the verified compressed-archive
reader. It does not infer session completeness, executable quotes or strategy
authority from a successfully archived diagnostic source. No outcomes are read
and no backtest or provider/broker call is made.
"""

from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_archive_reader_v1 import (
    load_verified_archived_option_quotes,
)
from packages.data.hybrid_options_gap_planner_v1 import plan_missing_sources
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-hybrid-options-simulation-input-preflight-v1"
MAX_VERIFIED_ARCHIVES = 8


class HybridSimulationPreflightError(ValueError):
    pass


def preflight_simulation_inputs(
    settings: AtlasSettings,
    batch: dict[str, Any],
) -> dict[str, Any]:
    """Verify available exact-match archives; always keep V1 sources blocked.

    Current V1 catalog sources explicitly have no proof of full query coverage
    or simulator acceptance. The gate can report verifiable input diagnostics,
    but cannot grant trade-performance, account replay, PAPER or LIVE authority.
    """
    plan = plan_missing_sources(settings, batch)
    if (plan.get("automatic_acquisition_authorized") is not False
            or plan.get("qualified_for_simulator") != 0
            or plan.get("provider_requests") != 0
            or plan.get("simulations_run") != 0):
        raise HybridSimulationPreflightError("GAP_PLANNER_AUTHORITY_DRIFT")

    sources_by_id: dict[str, dict[str, Any]] = {}
    source_queries: dict[str, dict[str, Any]] = {}
    for requirement in plan["queries"]:
        for source in requirement["exact_sources"]:
            source_id = source["source_id"]
            if source_id in source_queries and source_queries[source_id] != requirement["query"]:
                raise HybridSimulationPreflightError("SOURCE_ID_MULTIPLE_QUERY_SCOPES")
            source_queries[source_id] = requirement["query"]
            if source["source_status"] != "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED" or source["simulator_ready"] is not False:
                raise HybridSimulationPreflightError("UNQUALIFIED_SOURCE_STATE_DRIFT")
    if len(source_queries) > MAX_VERIFIED_ARCHIVES:
        raise HybridSimulationPreflightError("ARCHIVE_VERIFICATION_BATCH_CAP")

    # Each source is opened at most once, from its immutable compressed archive.
    # A corrupt/missing archive is an integrity failure, not a cache miss; never
    # conceal it by asking a provider to refresh the same data.
    for source_id, expected_scope in sorted(source_queries.items()):
        info = load_verified_archived_option_quotes(settings, source_id)
        if (info["source_id"] != source_id
                or info["query_scope"] != expected_scope
                or info["source_status"] != "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED"
                or info["query_coverage_proven"] is not False
                or info["simulator_ready"] is not False
                or info["retrieved_from"] != "VERIFIED_LOCAL_COMPRESSED_ARCHIVE"
                or info["original_uncompressed_source_opened"] is not False
                or info["provider_requests"] != 0
                or info["broker_requests"] != 0
                or info["protected_outcomes_read"] != 0):
            raise HybridSimulationPreflightError("ARCHIVED_SOURCE_IDENTITY_OR_AUTHORITY_DRIFT")
        sources_by_id[source_id] = {
            "source_id": source_id,
            "original_sha256": info["source_sha256"],
            "archive_sha256": info["archive_sha256"],
            "observed_quotes_verified": info["quote_rows"],
            "distinct_contracts_observed": info["unique_contracts"],
            "compressed_bytes": info["compressed_bytes"],
            "restored_bytes": info["restored_original_bytes"],
            "source_status": info["source_status"],
            "query_coverage_proven": False,
            "simulator_ready": False,
        }

    query_results: list[dict[str, Any]] = []
    for requirement in plan["queries"]:
        verified = []
        for source in requirement["exact_sources"]:
            recorded = sources_by_id[source["source_id"]]
            if recorded["observed_quotes_verified"] != source["observed_rows"]:
                raise HybridSimulationPreflightError("INDEXED_ARCHIVE_ROW_COUNT_DRIFT")
            verified.append(recorded["source_id"])
        query_results.append({
            "query_id": requirement["query_id"],
            "query": requirement["query"],
            "uses": requirement["uses"],
            "source_presence": requirement["source_state"],
            "verified_archive_source_ids": sorted(verified),
            "readiness": "ARCHIVED_DIAGNOSTIC_NOT_EXECUTABLE" if verified
                         else "MISSING_EXACT_LOCAL_SOURCE",
            "query_coverage_proven": False,
            "simulator_ready": False,
        })

    # V1 is deliberately blocked even when every requested query has a
    # losslessly recovered source: no complete entry/exit path is qualified.
    report: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "SIMULATION_INPUTS_BLOCKED_SOURCE_ONLY",
        "requirement_batch_fingerprint": _fingerprint(batch),
        "gap_report_fingerprint": plan["report_fingerprint"],
        "requirement_uses": plan["total_requirement_uses"],
        "unique_queries": plan["unique_exact_queries"],
        "deduplicated_uses": plan["deduplicated_uses"],
        "verified_archives": len(sources_by_id),
        "missing_exact_queries": plan["queries_missing_exact_local_source"],
        "unqualified_observed_queries": plan["exact_sources_observed_not_qualified"],
        "verified_archive_receipts": [
            sources_by_id[k] for k in sorted(sources_by_id)
        ],
        "queries": query_results,
        "all_required_sources_qualified": False,
        "frozen_simulation_dataset_created": False,
        "simulator_run_permitted": False,
        "automatic_acquisition_authorized": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_read": 0,
        "simulations_run": 0,
        "uncompressed_original_sources_opened": 0,
        "missing_is_not_provider_no_data": True,
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report


def require_qualified_simulation_inputs(report: dict[str, Any]) -> None:
    """Explicit gate for a future simulator caller. There is no bypass flag."""
    if (not isinstance(report, dict)
            or report.get("contract") != CONTRACT
            or report.get("report_fingerprint") != _fingerprint({
                k: v for k, v in report.items() if k != "report_fingerprint"
            })
            or report.get("simulator_run_permitted") is not True
            or report.get("all_required_sources_qualified") is not True
            or report.get("frozen_simulation_dataset_created") is not True):
        raise HybridSimulationPreflightError("SIMULATION_INPUTS_NOT_QUALIFIED")
    # No V1 report can authorize a simulator: this version has no promotion
    # procedure, even if arbitrary fields are edited and the hash recomputed.
    raise HybridSimulationPreflightError("V1_HAS_NO_SIMULATOR_PROMOTION_AUTHORITY")
