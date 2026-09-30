from __future__ import annotations

"""Lineage-preserving recovery of still-accessible tails of stale exact quote windows.

The original immutable quote request is never rewritten or declared complete.
A recovery request may expose only the currently entitled suffix of that exact
OCC history. It is source augmentation, not evidence for an original signal-time
fill and not a substitute for unavailable earlier dates.
"""

from collections import defaultdict
from datetime import UTC, date, datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import (
    CONTRACT as QUOTE_CONTRACT, _floor, _write_new,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature

RECOVERY_CONTRACT = "atlas-multiyear-stale-exact-quote-tail-recovery-v1"
OVERLAY_CONTRACT = "atlas-multiyear-stale-exact-quote-recovery-overlay-v1"
PLAN_REL = "data/options/manifests/multiyear_stale_quote_tail_recovery_v1"
OVERLAY_REL = "data/options/manifests/multiyear_stale_quote_recovery_overlay_v1"
EASTERN = ZoneInfo("America/New_York")


class QuoteTailRecoveryError(ValueError):
    pass


def build_tail_recovery_plan(
    original_plan: dict[str, Any], original_census: dict[str, Any], *,
    asof_utc: datetime,
) -> dict[str, Any]:
    """Freeze only the suffix still inside today's Starter rolling window."""
    if not isinstance(asof_utc, datetime) or asof_utc.tzinfo is None:
        raise QuoteTailRecoveryError("aware recovery as-of required")
    _check_signature(original_plan, "plan_fingerprint")
    _check_signature(original_census, "report_fingerprint")
    requests = original_plan.get("requests")
    memberships = original_plan.get("memberships")
    entries = original_census.get("source_entries")
    if (
        original_plan.get("contract") != QUOTE_CONTRACT
        or original_plan.get("status") != "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS"
        or original_plan.get("provider_requests") != 0
        or original_plan.get("strategy_authority") is not False
        or original_census.get("plan_fingerprint") != original_plan["plan_fingerprint"]
        or original_census.get("new_provider_attempts") != 0
        or original_census.get("observed_credits") != 0
        or not isinstance(requests, list) or not isinstance(memberships, list)
        or not isinstance(entries, list)
    ):
        raise QuoteTailRecoveryError("original quote plan/census lineage changed")
    by_request = {x["request_identity"]: x for x in requests}
    by_entry = {x["request_identity"]: x for x in entries}
    by_member = {x["case_id"]: x for x in memberships}
    if (
        len(by_request) != len(requests)
        or len(by_entry) != len(entries)
        or len(by_member) != len(memberships)
        or len(memberships) != original_plan.get("requested_case_denominator")
        or original_plan.get("unique_physical_quote_queries") != len(requests)
        or any(
            item["request_identity"] != _fingerprint({
                "contract": QUOTE_CONTRACT,
                "query": {
                    "option_symbol": item["option_symbol"],
                    "from_inclusive": item["from_inclusive"],
                    "to_exclusive": item["to_exclusive"],
                },
            })
            for item in requests
        )
        or any(
            member.get("request_identity") not in by_request
            or member["case_id"] not in by_request[member["request_identity"]].get(
                "member_case_ids", []
            )
            for member in memberships
        )
        or not set(by_entry).issubset(by_request)
        or original_census.get("original_requested_case_denominator") != len(memberships)
        or original_census.get("unique_physical_quote_queries") != len(requests)
        or original_census.get("reused_original_2022") != sum(
            x.get("status") == "REUSED_ACCEPTED_2022_FULL_SERIES"
            for x in entries
        )
        or original_census.get("new_cache_complete") != sum(
            x.get("status") == "COMPLETE_SOURCE_ONLY" for x in entries
        )
        or original_census.get("exact_source_gaps") != sum(
            x.get("status") == "EXACT_QUERY_SOURCE_GAP" for x in entries
        )
    ):
        raise QuoteTailRecoveryError("original request/membership/source partition changed")
    pending = set(by_request) - set(by_entry)
    if len(entries) + len(pending) != len(requests):
        raise QuoteTailRecoveryError("original source partition changed")

    recovery_day = asof_utc.astimezone(EASTERN).date()
    floor = _floor(recovery_day)
    stable_asof = datetime.combine(recovery_day, dt_time.min, tzinfo=EASTERN).astimezone(UTC)
    recovery_by_id: dict[str, dict[str, Any]] = {}
    old_to_recovery: dict[str, str] = {}
    expired: list[str] = []
    stale: list[str] = []
    for oid in sorted(pending):
        original = by_request[oid]
        start = date.fromisoformat(original["from_inclusive"])
        end = date.fromisoformat(original["to_exclusive"])
        if start >= floor:
            continue
        stale.append(oid)
        if floor >= end:
            expired.append(oid)
            continue
        query = {
            "option_symbol": original["option_symbol"],
            "from_inclusive": floor.isoformat(),
            "to_exclusive": end.isoformat(),
        }
        rid = _fingerprint({"contract": QUOTE_CONTRACT, "query": query})
        item = recovery_by_id.setdefault(rid, {
            **query,
            "request_identity": rid,
            "member_case_ids": [],
            "recovery_of_request_identities": [],
            "source_only_not_validated_trade": True,
            "clipped_prefix_is_permanently_unavailable_from_this_request": True,
        })
        item["recovery_of_request_identities"].append(oid)
        item["member_case_ids"].extend(original.get("member_case_ids", []))
        old_to_recovery[oid] = rid

    for item in recovery_by_id.values():
        item["recovery_of_request_identities"] = sorted(set(
            item["recovery_of_request_identities"]
        ))
        item["member_case_ids"] = sorted(set(item["member_case_ids"]))

    recovery_memberships = []
    for member in memberships:
        oid = member.get("request_identity")
        rid = old_to_recovery.get(oid)
        if rid is None:
            continue
        recovery_memberships.append({
            **member,
            "request_identity": rid,
            "recovery_of_request_identity": oid,
            "original_disposition": member.get("disposition"),
            "disposition": "SOURCE_DEMAND_READY",
        })

    out = {
        # Kept equal to the accepted cache contract so the same strict receipt
        # executor can persist the exact clipped query without a second writer.
        "contract": QUOTE_CONTRACT,
        "recovery_contract": RECOVERY_CONTRACT,
        "status": "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS",
        "asof_utc": stable_asof.isoformat(),
        "recovery_asof_day_et": recovery_day.isoformat(),
        "rolling_five_year_floor": floor.isoformat(),
        "last_completed_session": original_plan["last_completed_session"],
        "requested_case_denominator": len(recovery_memberships),
        "unique_physical_quote_queries": len(recovery_by_id),
        "memberships": sorted(recovery_memberships, key=lambda x: x["case_id"]),
        "requests": sorted(recovery_by_id.values(), key=lambda x: x["request_identity"]),
        "provider_requests": 0,
        "strategy_authority": False,
        "no_future_liquidity_contract_selection": True,
        "recovery_origin_plan_fingerprint": original_plan["plan_fingerprint"],
        "recovery_origin_census_fingerprint": original_census["report_fingerprint"],
        "original_pending_queries": len(pending),
        "original_stale_queries": len(stale),
        "recoverable_stale_queries": len(old_to_recovery),
        "distinct_recovery_queries": len(recovery_by_id),
        "expired_before_current_floor_queries": len(expired),
        "expired_original_request_identities": expired,
        "missing_prefix_not_reconstructed": True,
        "historical_fill_or_pnl_authority": False,
    }
    out["plan_fingerprint"] = _fingerprint(out)
    return out


def persist_tail_recovery_plan(
    settings: AtlasSettings, report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "plan_fingerprint")
    if report.get("recovery_contract") != RECOVERY_CONTRACT:
        raise QuoteTailRecoveryError("recovery plan contract changed")
    path = settings.resolved_path(
        f"{PLAN_REL}_{report['plan_fingerprint'][:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != report:
            raise QuoteTailRecoveryError("immutable recovery plan differs")
        return path, "REUSED_IDENTICAL_TAIL_RECOVERY_PLAN"
    _write_new(path, report)
    return path, "WRITTEN_IMMUTABLE_TAIL_RECOVERY_PLAN"


def build_recovery_overlay(
    original_plan: dict[str, Any], recovery_plan: dict[str, Any],
    recovery_census: dict[str, Any],
) -> dict[str, Any]:
    """Map clipped verified source bodies back to original exact request IDs."""
    for doc, field in (
        (original_plan, "plan_fingerprint"),
        (recovery_plan, "plan_fingerprint"),
        (recovery_census, "report_fingerprint"),
    ):
        _check_signature(doc, field)
    if (
        recovery_plan.get("recovery_contract") != RECOVERY_CONTRACT
        or recovery_plan.get("recovery_origin_plan_fingerprint")
            != original_plan["plan_fingerprint"]
        or recovery_census.get("plan_fingerprint") != recovery_plan["plan_fingerprint"]
        or recovery_census.get("new_provider_attempts") != 0
        or recovery_census.get("observed_credits") != 0
        or recovery_census.get("status") not in (
            "PREVIEW_ONLY_NO_PROVIDER_GETS", "ALL_ELIGIBLE_SOURCE_QUERIES_ACCOUNTED"
        )
    ):
        raise QuoteTailRecoveryError("recovery overlay requires zero-GET verified census")
    rec_requests = {
        x["request_identity"]: x for x in recovery_plan.get("requests", [])
    }
    entries = {
        x["request_identity"]: x for x in recovery_census.get("source_entries", [])
    }
    if len(rec_requests) != recovery_plan.get("unique_physical_quote_queries"):
        raise QuoteTailRecoveryError("recovery request denominator changed")

    rows = []
    complete = gaps = pending = 0
    seen_original = set()
    for rid, req in sorted(rec_requests.items()):
        entry = entries.get(rid)
        if entry is None:
            status = "TAIL_RECOVERY_NOT_ACQUIRED"
            pending += 1
        elif entry["status"] == "COMPLETE_SOURCE_ONLY":
            status = "VERIFIED_CLIPPED_DEMAND_CACHE_QUOTE_HISTORY"
            complete += 1
        elif entry["status"] == "EXACT_QUERY_SOURCE_GAP":
            status = "CLIPPED_RECOVERY_QUERY_NO_DATA"
            gaps += 1
        else:
            raise QuoteTailRecoveryError("unexpected recovery cache status")
        origins = req.get("recovery_of_request_identities")
        if not isinstance(origins, list) or not origins:
            raise QuoteTailRecoveryError("recovery request lost origin identity")
        for oid in origins:
            if oid in seen_original:
                raise QuoteTailRecoveryError("original request recovered more than once")
            seen_original.add(oid)
            rows.append({
                "original_request_identity": oid,
                "recovery_request_identity": rid,
                "option_symbol": req["option_symbol"],
                "source_from_inclusive": req["from_inclusive"],
                "source_to_exclusive": req["to_exclusive"],
                "status": status,
                "quote_body_sha256": entry.get("body_sha256") if entry else None,
                "observed_quote_rows": entry.get("cached_observed_rows") if entry else None,
                "missing_original_prefix_is_not_reconstructed": True,
                "historical_fill_or_pnl_authority": False,
            })
    out = {
        "contract": OVERLAY_CONTRACT,
        "status": "CLIPPED_SOURCE_OVERLAY_NO_ORIGINAL_WINDOW_COMPLETENESS_CLAIM",
        "original_plan_fingerprint": original_plan["plan_fingerprint"],
        "recovery_plan_fingerprint": recovery_plan["plan_fingerprint"],
        "recovery_census_fingerprint": recovery_census["report_fingerprint"],
        "current_floor_et": recovery_plan["rolling_five_year_floor"],
        "recoverable_original_requests": len(rows),
        "distinct_recovery_queries": len(rec_requests),
        "complete_recovery_queries": complete,
        "recovery_query_gaps": gaps,
        "pending_recovery_queries": pending,
        "rows": sorted(rows, key=lambda x: x["original_request_identity"]),
        "provider_requests": 0,
        "original_window_fully_reconstructed": False,
        "historical_fill_or_pnl_authority": False,
    }
    out["overlay_fingerprint"] = _fingerprint(out)
    return out


def persist_recovery_overlay(
    settings: AtlasSettings, report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "overlay_fingerprint")
    if report.get("contract") != OVERLAY_CONTRACT:
        raise QuoteTailRecoveryError("recovery overlay contract changed")
    path = settings.resolved_path(
        f"{OVERLAY_REL}_{report['overlay_fingerprint'][:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != report:
            raise QuoteTailRecoveryError("immutable recovery overlay differs")
        return path, "REUSED_IDENTICAL_TAIL_RECOVERY_OVERLAY"
    _write_new(path, report)
    return path, "WRITTEN_IMMUTABLE_TAIL_RECOVERY_OVERLAY"
