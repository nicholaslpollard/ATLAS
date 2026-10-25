from __future__ import annotations

"""V7 source-only, offline acquisition-request planner and reservation ledger.

This module deliberately has NO provider request/worker construction path.
It reconciles V1/V4 archived diagnostics and V6 verified source identities,
deduplicates exact requirements, limits the quote method to the currently
supported hourly SDK adapter, checks existing ATLAS secondary storage budgets,
and optionally reserves an immutable one-query intent. A reservation is not
a provider attempt, authorization, proof of no data, or an executable quote.
"""

import json
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.hybrid_options_archive_reader_v1 import (
    load_verified_archived_option_quotes,
)
from packages.data.hybrid_options_gap_planner_v1 import (
    plan_missing_sources, normalize_batch, _scope,
)
from packages.data.hybrid_options_lossless_archive_v1 import _write_immutable
from packages.data.hybrid_options_source_store_v2 import (
    CATALOG_REL as V6_CATALOG_REL,
    read_historical_quote_source,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.research_storage import (
    GIB, directory_size_bytes, inspect_research_storage,
)

CONTRACT = "atlas-hybrid-options-offline-acquisition-reservations-v1"
RESERVATION_ROOT = "data/options/hybrid/acquisition_reservations_v1"
MAX_VERIFIED_SOURCES = 16
MAX_LEDGER_RECEIPTS = 4096
DEFAULT_PER_QUERY_MIB = 128
DEFAULT_BATCH_MIB = 512
MAX_BATCH_MIB = 8192
MIB = 1024**2
MIN_FREE_GIB = 40
CANDIDATE_COMBINED_QUOTA_GIB = 120
HOURLY_METHOD = "option_history_hourly_quote_surface"


class HybridAcquisitionPlanError(ValueError):
    pass


def _adapter_status(query: dict[str, Any]) -> str:
    """One adapter mapping only; unsupported shapes may NOT be requested."""
    if (query["interval"] == "1h"
            and query["start_time"] == "09:30:00"
            and query["end_time"] == "16:00:00"
            and 1 <= query["max_dte"] <= 75
            and 0 <= query["strike_range"] <= 8
            and query["right"] in ("call", "put", "both")):
        return "HOURLY_SDK_ADAPTER_MATCH"
    return "NO_EXACT_PROVIDER_ADAPTER_YET"


def _reservation_path(settings: AtlasSettings, query_id: str) -> Path:
    return settings.resolved_path(RESERVATION_ROOT) / query_id[:2] / (
        query_id + ".json"
    )


def _reservation_body(query_id: str, query: dict[str, Any],
                      per_request_bytes: int, method: str) -> dict[str, Any]:
    body = {
        "contract": CONTRACT,
        "query_id": query_id,
        "query": query,
        "provider": "thetadata",
        "provider_method": method,
        "reserved_worst_case_bytes": per_request_bytes,
        "state": "RESERVED_NO_PROVIDER_CALL",
        "provider_attempts": 0,
        "provider_authorized": False,
        "automatic_retries_allowed": False,
        "provider_no_data_claimed": False,
        "source_coverage_proven": False,
        "simulator_ready": False,
    }
    body["fingerprint"] = _fingerprint(body)
    return body


def _existing_reservation(
    settings: AtlasSettings, query_id: str, query: dict[str, Any],
) -> dict[str, Any] | None:
    path = _reservation_path(settings, query_id)
    if path.is_symlink():
        raise HybridAcquisitionPlanError("RESERVATION_SYMLINK_UNSAFE")
    if not path.exists():
        return None
    root = settings.resolved_path("data/options").resolve()
    if (not path.is_file() or not path.resolve().is_relative_to(root)
            or not 0 < path.stat().st_size <= 16 * 1024):
        raise HybridAcquisitionPlanError("RESERVATION_FILE_UNSAFE")
    try:
        body = json.loads(path.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise HybridAcquisitionPlanError("RESERVATION_JSON_INVALID") from exc
    if (not isinstance(body, dict)
            or body.get("contract") != CONTRACT
            or body.get("query_id") != query_id
            or body.get("query") != query
            or body.get("state") != "RESERVED_NO_PROVIDER_CALL"
            or body.get("provider") != "thetadata"
            or body.get("provider_method") != HOURLY_METHOD
            or body.get("provider_attempts") != 0
            or body.get("provider_authorized") is not False
            or body.get("automatic_retries_allowed") is not False
            or body.get("provider_no_data_claimed") is not False
            or body.get("source_coverage_proven") is not False
            or body.get("simulator_ready") is not False
            or not isinstance(body.get("reserved_worst_case_bytes"), int)
            or isinstance(body["reserved_worst_case_bytes"], bool)
            or not 1 <= body["reserved_worst_case_bytes"] <= MAX_BATCH_MIB * MIB
            or set(body) != {
                "contract", "query_id", "query", "provider", "provider_method",
                "reserved_worst_case_bytes", "state", "provider_attempts",
                "provider_authorized", "automatic_retries_allowed",
                "provider_no_data_claimed", "source_coverage_proven",
                "simulator_ready", "fingerprint",
            }
            or body.get("fingerprint") != _fingerprint({
                k: v for k, v in body.items() if k != "fingerprint"
            })):
        raise HybridAcquisitionPlanError("RESERVATION_RECEIPT_OR_AUTHORITY_DRIFT")
    return body


def _outstanding_reservations(settings: AtlasSettings) -> dict[str, Any]:
    """Reverify ALL pending receipts before granting another budget slot.

    Even an unrelated prior batch consumes scarce storage headroom. Do not
    permit a later small batch to ignore outstanding reserved capacity.
    """
    root = settings.resolved_path(RESERVATION_ROOT)
    if root.is_symlink():
        raise HybridAcquisitionPlanError("RESERVATION_ROOT_SYMLINK_UNSAFE")
    if not root.exists():
        return {"count": 0, "bytes": 0}
    if not root.is_dir():
        raise HybridAcquisitionPlanError("RESERVATION_ROOT_NOT_DIRECTORY")
    total, count = 0, 0
    seen: set[str] = set()
    # Current ledger contains only bounded 2-level query-id paths. Any
    # unexpected files or nested symlinked directories are not ignored.
    for shard in sorted(root.iterdir()):
        if shard.is_symlink() or not shard.is_dir() or len(shard.name) != 2:
            raise HybridAcquisitionPlanError("RESERVATION_LEDGER_SHARD_UNSAFE")
        for proof in sorted(shard.iterdir()):
            count += 1
            if count > MAX_LEDGER_RECEIPTS:
                raise HybridAcquisitionPlanError("RESERVATION_LEDGER_SCAN_CAP")
            if (proof.is_symlink() or not proof.is_file()
                    or not proof.name.endswith(".json")
                    or len(proof.stem) != 64 or proof.stem[:2] != shard.name):
                raise HybridAcquisitionPlanError("RESERVATION_LEDGER_FILE_UNSAFE")
            try:
                header = json.loads(proof.read_bytes())
                qid = header["query_id"]
                query = _scope(header["query"])
            except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                raise HybridAcquisitionPlanError("RESERVATION_LEDGER_INVALID") from exc
            if qid != proof.stem or qid in seen:
                raise HybridAcquisitionPlanError("RESERVATION_LEDGER_DUPLICATE_ID")
            seen.add(qid)
            if qid != _fingerprint({
                "source_type": "option_history_quote", "query": query,
            }):
                raise HybridAcquisitionPlanError("RESERVATION_QUERY_FINGERPRINT_DRIFT")
            verified = _existing_reservation(settings, qid, query)
            if verified is None:
                raise HybridAcquisitionPlanError("RESERVATION_RECEIPT_MISSING")
            total += verified["reserved_worst_case_bytes"]
    return {"count": count, "bytes": total}


def _v6_exact_sources(
    settings: AtlasSettings, query_ids: set[str],
) -> dict[str, dict[str, Any]]:
    catalog = settings.resolved_path(V6_CATALOG_REL)
    if catalog.is_symlink() or (catalog.exists() and not catalog.is_file()):
        raise HybridAcquisitionPlanError("GENERAL_SOURCE_CATALOG_PATH_UNSAFE")
    if not catalog.is_file():
        return {}
    by_query: dict[str, dict[str, Any]] = {}
    con = connect_utc(catalog, read_only=True)
    try:
        for query_id in sorted(query_ids):
            records = con.execute(
                "SELECT source_id, record_json, source_status, "
                "source_rows, simulator_ready, query_coverage_proven "
                "FROM quote_sources WHERE query_id = ?", [query_id],
            ).fetchall()
            if len(records) > 1:
                raise HybridAcquisitionPlanError("GENERAL_DUPLICATE_QUERY_SOURCE")
            if not records:
                continue
            source_id, serialized, status, row_count, ready, proven = records[0]
            if (status != "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED"
                    or ready is not False or proven is not False):
                raise HybridAcquisitionPlanError("GENERAL_SOURCE_AUTHORITY_DRIFT")
            try:
                record = json.loads(serialized)
            except (TypeError, ValueError) as exc:
                raise HybridAcquisitionPlanError("GENERAL_SOURCE_RECORD_INVALID") from exc
            if (not isinstance(record, dict)
                    or record.get("query_id") != query_id
                    or record.get("source_id") != source_id
                    or record.get("diagnostics", {}).get("observed_rows") != row_count):
                raise HybridAcquisitionPlanError("GENERAL_QUERY_INDEX_IDENTITY_DRIFT")
            by_query[query_id] = {
                "source_id": source_id,
                "query": record["query"],
                "source_rows": row_count,
                "expected_sha256": record["body_sha256"],
            }
    finally:
        con.close()
    return by_query


def _storage_capacity(
    settings: AtlasSettings,
    storage_reader: Callable[[AtlasSettings], Any],
) -> dict[str, Any]:
    """Account for the uncategorized hybrid subtree in the shared D: budget."""
    snap = storage_reader(settings)
    hybrid_bytes = directory_size_bytes(
        settings.resolved_path("data/options/hybrid")
    )
    hybrid_gib = hybrid_bytes / GIB
    category_usage = snap.category_usage_gib
    category_quota = snap.category_quota_gib
    if ("options_candidate_cache" not in category_usage
            or "options_candidate_cache" not in category_quota):
        raise HybridAcquisitionPlanError("RESEARCH_CATEGORY_POLICY_MISSING")
    candidate_used = category_usage["options_candidate_cache"]
    quote_quota = min(
        float(category_quota["options_candidate_cache"]),
        CANDIDATE_COMBINED_QUOTA_GIB,
    )
    # Hybrid source bytes live outside the category roots inspected in V1
    # research_storage, so deduct the whole hybrid subtree separately.
    if snap.status == "BLOCKED_MINIMUM_FREE_SPACE":
        remaining = 0.0
    else:
        remaining = max(0.0, min(
            float(snap.disk_free_gib) - max(
                float(snap.warning_free_gib), MIN_FREE_GIB,
            ),
            float(snap.remaining_acquisition_budget_gib) - hybrid_gib,
            quote_quota - candidate_used - hybrid_gib,
        ))
    return {
        "storage_mode": snap.storage_mode,
        "disk_free_gib": round(float(snap.disk_free_gib), 6),
        "warning_free_gib": float(snap.warning_free_gib),
        "hybrid_source_and_catalog_gib": round(hybrid_gib, 8),
        "other_candidate_cache_gib": round(float(candidate_used), 8),
        "joint_candidate_quota_gib": quote_quota,
        "total_research_acquisition_budget_gib": float(
            snap.acquisition_budget_gib
        ),
        "remaining_safe_unreserved_gib": round(remaining, 8),
        "safe_available_bytes": int(remaining * GIB),
        "storage_status": snap.status,
        "storage_preflight_performed": True,
    }


def plan_acquisition_reservations(
    settings: AtlasSettings,
    batch: dict[str, Any],
    *,
    reserve: bool = False,
    per_request_mib: int = DEFAULT_PER_QUERY_MIB,
    batch_budget_mib: int = DEFAULT_BATCH_MIB,
    storage_reader: Callable[[AtlasSettings], Any] = inspect_research_storage,
) -> dict[str, Any]:
    """Reconcile sources and allocate a bounded *offline* request intention.

    reserve=True creates immutable NO_CALL receipts only for eligible queries.
    It does not import a provider adapter into the call path, attempt a network
    request, open outcomes, or mark anything as a usable simulation input.
    """
    if (type(per_request_mib) is not int or not 1 <= per_request_mib <= 512
            or type(batch_budget_mib) is not int
            or not 1 <= batch_budget_mib <= MAX_BATCH_MIB):
        raise HybridAcquisitionPlanError("UNBOUNDED_ACQUISITION_RESERVATION")
    normalize_batch(batch)
    settings.assert_external_storage_binding("options")
    gaps = plan_missing_sources(settings, batch)
    if (gaps.get("provider_requests") != 0
            or gaps.get("automatic_acquisition_authorized") is not False):
        raise HybridAcquisitionPlanError("SOURCE_GAP_AUTHORITY_CHANGED")
    by_query = _v6_exact_sources(
        settings, {r["query_id"] for r in gaps["queries"]},
    )
    verified_sources = (
        sum(len(r["exact_sources"]) for r in gaps["queries"])
        + len(by_query)
    )
    if verified_sources > MAX_VERIFIED_SOURCES:
        raise HybridAcquisitionPlanError("SOURCE_VERIFICATION_BATCH_CAP")
    by_source_hash: dict[str, dict[str, str]] = {}
    results: list[dict[str, Any]] = []
    for entry in gaps["queries"]:
        query, qid = entry["query"], entry["query_id"]
        known = []
        for observed in entry["exact_sources"]:
            verified = load_verified_archived_option_quotes(
                settings, observed["source_id"],
            )
            if (verified["query_scope"] != query
                    or verified["quote_rows"] != observed["observed_rows"]
                    or verified["simulator_ready"] is not False
                    or verified["provider_requests"] != 0):
                raise HybridAcquisitionPlanError("LEGACY_VERIFIED_SOURCE_MISMATCH")
            known.append({
                "store": "V4", "source_id": observed["source_id"],
                "source_sha256": verified["source_sha256"],
                "quotes": verified["quote_rows"],
            })
        if qid in by_query:
            item = by_query[qid]
            if item["query"] != query:
                raise HybridAcquisitionPlanError("GENERAL_QUERY_SCOPE_MISMATCH")
            verified = read_historical_quote_source(
                settings, item["source_id"],
            )
            if (verified["query"] != query
                    or verified["source_sha256"] != item["expected_sha256"]
                    or verified["quote_rows"] != item["source_rows"]
                    or verified["simulator_ready"] is not False
                    or verified["query_coverage_proven"] is not False
                    or verified["provider_requests"] != 0):
                raise HybridAcquisitionPlanError("GENERAL_ARCHIVE_VERIFICATION_FAILED")
            known.append({
                "store": "V6", "source_id": item["source_id"],
                "source_sha256": verified["source_sha256"],
                "quotes": verified["quote_rows"],
            })
        if len({src["source_sha256"] for src in known}) > 1:
            raise HybridAcquisitionPlanError("EXACT_QUERY_CONFLICTING_SOURCE_BODIES")
        for src in known:
            former = by_source_hash.get(src["source_id"])
            if former is not None and former["query_id"] != qid:
                raise HybridAcquisitionPlanError("SOURCE_ID_REUSED_FOR_OTHER_QUERY")
            by_source_hash[src["source_id"]] = {
                "query_id": qid, "body_sha256": src["source_sha256"],
            }
        reservation = _existing_reservation(settings, qid, query)
        results.append({
            "query_id": qid, "query": query, "uses": entry["uses"],
            "verified_sources": known,
            "adapter": _adapter_status(query),
            "existing_no_call_reservation": reservation is not None,
            "reservation_fingerprint": (
                reservation["fingerprint"] if reservation else None
            ),
            "status": "UNDECIDED",
            "simulator_ready": False,
        })

    storage = _storage_capacity(settings, storage_reader)
    outstanding = _outstanding_reservations(settings)
    bytes_per = per_request_mib * MIB
    batch_limit = min(
        batch_budget_mib * MIB,
        max(0, storage["safe_available_bytes"] - outstanding["bytes"]),
    )
    # Preserve old-session priority; user-requested discovery/use order does
    # not permit price/performance lookahead or newer sessions jumping first.
    queue = sorted(
        results, key=lambda r: (
            r["query"]["date_et"], r["query"]["symbol"],
            r["query"]["interval"], r["query_id"],
        ),
    )
    newly_planned = []
    charged = 0
    for item in queue:
        if item["verified_sources"]:
            item["status"] = "REUSE_VERIFIED_UNQUALIFIED_SOURCE"
        elif item["existing_no_call_reservation"]:
            item["status"] = "ALREADY_RESERVED_NO_PROVIDER_CALL"
        elif item["adapter"] != "HOURLY_SDK_ADAPTER_MATCH":
            item["status"] = "BLOCKED_EXACT_ADAPTER_UNAVAILABLE"
        elif charged + bytes_per > batch_limit:
            item["status"] = "DEFERRED_REQUEST_OR_STORAGE_BUDGET"
        else:
            item["status"] = "ELIGIBLE_FOR_OFFLINE_RESERVATION_ONLY"
            newly_planned.append(item)
            charged += bytes_per

    if reserve:
        # Verify that every proposed destination is new BEFORE any mutation.
        # A missing/invalid existing source or corrupt receipt fails closed.
        for item in newly_planned:
            target = _reservation_path(settings, item["query_id"])
            if target.exists() or target.is_symlink():
                raise HybridAcquisitionPlanError(
                    "RESERVATION_RACE_OR_DESTINATION_COLLISION"
                )
        for item in newly_planned:
            body = _reservation_body(
                item["query_id"], item["query"], bytes_per, HOURLY_METHOD,
            )
            target = _reservation_path(settings, item["query_id"])
            target.parent.mkdir(parents=True, exist_ok=True)
            contents = (json.dumps(body, sort_keys=True, indent=2) + "\n").encode()
            if len(contents) > 16 * 1024:
                raise HybridAcquisitionPlanError("RESERVATION_RECEIPT_TOO_LARGE")
            _write_immutable(target, contents)
            if _existing_reservation(
                settings, item["query_id"], item["query"],
            ) != body:
                raise HybridAcquisitionPlanError(
                    "RESERVATION_POSTWRITE_VERIFICATION_FAILED"
                )
            item["status"] = "RESERVED_NO_PROVIDER_CALL"
            item["reservation_fingerprint"] = body["fingerprint"]

    sorted_results = sorted(results, key=lambda x: x["query_id"])
    body: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "OFFLINE_SOURCE_RECONCILIATION_NO_PROVIDER_AUTHORITY",
        "requirement_uses": gaps["total_requirement_uses"],
        "unique_queries": gaps["unique_exact_queries"],
        "deduplicated_uses": gaps["deduplicated_uses"],
        "verified_local_queries": sum(bool(r["verified_sources"])
                                      for r in sorted_results),
        "missing_exact_queries": sum(not r["verified_sources"]
                                     for r in sorted_results),
        "new_reservations": len(newly_planned) if reserve else 0,
        "newly_reservable_queries": len(newly_planned),
        "already_reserved_queries": sum(
            r["status"] == "ALREADY_RESERVED_NO_PROVIDER_CALL"
            for r in sorted_results
        ),
        "blocked_adapter_queries": sum(
            r["status"] == "BLOCKED_EXACT_ADAPTER_UNAVAILABLE"
            for r in sorted_results
        ),
        "deferred_budget_queries": sum(
            r["status"] == "DEFERRED_REQUEST_OR_STORAGE_BUDGET"
            for r in sorted_results
        ),
        "reservation_bytes_per_query": bytes_per,
        "newly_planned_reservation_bytes": charged,
        "batch_budget_bytes": batch_budget_mib * MIB,
        "outstanding_no_call_reservations_before_batch": outstanding["count"],
        "outstanding_reservation_bytes_before_batch": outstanding["bytes"],
        "storage": storage,
        "queries": sorted_results,
        "provider_requests": 0, "broker_requests": 0,
        "simulations_run": 0, "protected_outcomes_read": 0,
        "paid_provider_authority": False,
        "automatic_provider_retry_allowed": False,
        "reservation_is_not_an_api_attempt": True,
        "simulator_ready": False,
    }
    body["report_fingerprint"] = _fingerprint(body)
    return body
