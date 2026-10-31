from __future__ import annotations

"""V39 streaming strategy-data-demand coordinator.

A changed strategy version or newly selected contract may request any supported
historical ThetaData source. Each source demand is resolved through V38's
persistent, immutable, exact-query read-through cache, never through a frozen
candidate roster or a per-run/lifetime request quota.

This is the simulator-facing DATA boundary. Historical source presence does
not establish contemporaneous availability, complete chain coverage, fills,
P&L or permission to use future observations in an entry decision.
"""

from collections import Counter
from datetime import UTC, datetime
import json
import re
from typing import Any, Callable, Iterable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.providers.thetadata import client as theta
from packages.data.options_on_demand_source_cache_v38 import (
    _connect, _database, normalize_source_requirement,
    read_through_historical_options,
)

CONTRACT = "atlas-strategy-options-data-demand-runtime-v39"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
OUTCOMES = frozenset({
    "FETCHED_AND_ARCHIVED", "CACHE_HIT",
    "FETCHED_EXPLICIT_NO_DATA", "CACHED_EXPLICIT_NO_DATA",
})
SUCCESS = frozenset({"FETCHED_AND_ARCHIVED", "CACHE_HIT"})
NO_DATA = frozenset({"FETCHED_EXPLICIT_NO_DATA", "CACHED_EXPLICIT_NO_DATA"})


class StrategySourceRuntimeError(ValueError):
    pass


def _journal(db) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS strategy_source_uses (
            strategy_version TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            purpose TEXT NOT NULL,
            query_id TEXT NOT NULL,
            method TEXT NOT NULL,
            requested_args TEXT NOT NULL,
            status TEXT NOT NULL,
            source_sha TEXT,
            updated_at_utc TEXT NOT NULL,
            PRIMARY KEY(strategy_version,candidate_id,purpose,query_id)
        )
    """)


def _name(s: Any, label: str) -> str:
    if not isinstance(s, str) or NAME.fullmatch(s) is None:
        raise StrategySourceRuntimeError("INVALID_" + label)
    return s


def _put(db, *, version: str, candidate: str, purpose: str,
         request: dict, query_id: str, status: str, source_sha: str | None) -> None:
    _journal(db)
    db.execute("""
        INSERT INTO strategy_source_uses
          (strategy_version,candidate_id,purpose,query_id,method,
           requested_args,status,source_sha,updated_at_utc)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(strategy_version,candidate_id,purpose,query_id)
        DO UPDATE SET status=excluded.status,source_sha=excluded.source_sha,
                      updated_at_utc=excluded.updated_at_utc
    """, (
        version, candidate, purpose, query_id, request["method"],
        json.dumps(request["kwargs"], sort_keys=True, separators=(",", ":")),
        status, source_sha, datetime.now(UTC).isoformat(),
    ))



def _source_receipt_state(db_path, requirement: dict, query_id: str) -> str:
    """Read exact original V38 state before allowing any new provider dispatch.

    V38 legacy FAILED_RETRYABLE and expired IN_FLIGHT leases do not prove that
    a previous provider call was never received. Never automatically dispatch
    that indistinguishable query again from this strategy runtime.
    """
    with _connect(db_path) as db:
        row = db.execute(
            "SELECT request_json,state FROM sources WHERE query_id=?",
            (query_id,),
        ).fetchone()
    if row is None:
        return "NOT_REGISTERED"
    expected = json.dumps(requirement, sort_keys=True, separators=(",", ":"))
    if row[0] != expected:
        raise StrategySourceRuntimeError("SOURCE_QUERY_FINGERPRINT_COLLISION")
    if row[1] not in {
        "ARCHIVED", "NO_DATA_EXPLICIT", "FAILED_RETRYABLE", "IN_FLIGHT",
    }:
        raise StrategySourceRuntimeError("SOURCE_RECEIPT_UNKNOWN_STATE")
    return row[1]


def resolve_strategy_source_demands(
    settings: AtlasSettings,
    strategy_version: str,
    demands: Iterable[dict[str, Any]],
    *,
    provider_call: Callable | None = None,
    on_source: Callable[[dict, dict], None] | None = None,
    on_progress: Callable[[str, dict], None] | None = None,
    continue_on_error: bool = False,
) -> dict:
    """Consume arbitrarily many dynamic requirements one at a time.

    Producer yields one current-strategy source need (even for candidates
    discovered during simulation). A missing exact query automatically calls
    ThetaData; it is archived/indexed before the source callback runs. The
    strategy may request additional sources after inspecting qualifying
    *causal* observations. The coordinator does not itself grant that gate.

    Rerun/resume simply replays needs: completed source queries are cache hits,
    ambiguous earlier dispatches require reconciliation; independent requirements
    continue and all strategy/candidate source needs stay persisted in SQLite.
    """
    version = _name(strategy_version, "STRATEGY_VERSION")
    if type(continue_on_error) is not bool:
        raise StrategySourceRuntimeError("INVALID_CONTINUE_ON_ERROR")
    db_path = _database(settings)
    with _connect(db_path) as db:
        _journal(db)
    counts = Counter()
    current = {"candidate_id": "", "purpose": "", "method": "", "query_id": "", "date_et": ""}

    def notify(event: str, *, status: str | None = None, error: str | None = None):
        if on_progress is not None:
            on_progress(event, {
                **current, "status": status, "error": error,
                "counts": dict(counts),
            })

    def counted_provider_call(method: str, kwargs: dict):
        # Count *attempts* at runtime, including a provider failure; neither
        # cache hits nor a printed preflight can predict this number.
        counts["provider_dispatch_attempts"] += 1
        notify("provider_dispatch")
        if provider_call is not None:
            return provider_call(method, kwargs)
        return getattr(theta, method)(**kwargs)

    for item in demands:
        if not isinstance(item, dict) or set(item) != {
            "candidate_id", "purpose", "method", "kwargs",
        }:
            raise StrategySourceRuntimeError("DEMAND_SHAPE_INVALID")
        candidate = _name(item["candidate_id"], "CANDIDATE_ID")
        purpose = _name(item["purpose"], "PURPOSE")
        normalized = normalize_source_requirement(item["method"], item["kwargs"])
        query_id = _fingerprint(normalized)
        with _connect(db_path) as db:
            _put(db, version=version, candidate=candidate, purpose=purpose,
                 request=normalized, query_id=query_id, status="SOURCE_REQUIRED",
                 source_sha=None)
        counts["source_uses_requested"] += 1
        current = {
            "candidate_id": candidate, "purpose": purpose,
            "method": item["method"], "query_id": query_id,
            "date_et": normalized["kwargs"].get("date_et", ""),
        }
        notify("source_started")
        prior_state = _source_receipt_state(db_path, normalized, query_id)
        if prior_state in ("FAILED_RETRYABLE", "IN_FLIGHT"):
            counts["source_uses_failed_or_unresolved"] += 1
            counts["source_uses_ambiguous_prior_dispatch"] += 1
            with _connect(db_path) as db:
                _put(db, version=version, candidate=candidate, purpose=purpose,
                     request=normalized, query_id=query_id,
                     status="SOURCE_RECONCILIATION_REQUIRED", source_sha=None)
            notify("source_blocked", status="SOURCE_RECONCILIATION_REQUIRED",
                   error="AMBIGUOUS_PREVIOUS_DISPATCH_NO_SAME_QUERY_RETRY")
            if not continue_on_error:
                raise StrategySourceRuntimeError(
                    "AMBIGUOUS_PREVIOUS_DISPATCH_NO_SAME_QUERY_RETRY"
                )
            continue
        # Persist source intent before the first read-through provider call.
        # Cached rows are reused; new source requests still dispatch normally.
        with _connect(db_path) as db:
            _put(db, version=version, candidate=candidate, purpose=purpose,
                 request=normalized, query_id=query_id,
                 status="SOURCE_CACHE_OR_FIRST_DISPATCH_PENDING", source_sha=None)
        attempts_before = counts["provider_dispatch_attempts"]
        try:
            source = read_through_historical_options(
                settings, item["method"], item["kwargs"],
                provider_call=counted_provider_call,
            )
            status = source["status"]
            if status not in OUTCOMES or source["query_id"] != query_id:
                raise StrategySourceRuntimeError("SOURCE_RECEIPT_QUERY_OR_STATUS_DRIFT")
            with _connect(db_path) as db:
                _put(db, version=version, candidate=candidate, purpose=purpose,
                     request=normalized, query_id=query_id, status=status,
                     source_sha=source["source_sha256"])
            if on_source is not None:
                on_source(dict(item), source)
            counts["source_uses_resolved"] += status in SUCCESS
            counts["source_uses_explicit_no_data"] += status in NO_DATA
            counts["provider_fetch_successes"] += status.startswith("FETCHED_")
            counts["persisted_cache_hits"] += status.startswith("CACHE")
            notify("source_done", status=status)
        except Exception as exc:
            counts["source_uses_failed_or_unresolved"] += 1
            was_dispatched = counts["provider_dispatch_attempts"] > attempts_before
            failure_status = (
                "SOURCE_DISPATCH_OUTCOME_UNKNOWN" if was_dispatched
                else "SOURCE_ACQUISITION_REVIEW_REQUIRED"
            )
            if was_dispatched:
                counts["source_uses_ambiguous_current_dispatch"] += 1
            with _connect(db_path) as db:
                _put(db, version=version, candidate=candidate, purpose=purpose,
                     request=normalized, query_id=query_id,
                     status=failure_status, source_sha=None)
            # Never print raw provider exception text (may contain secrets).
            notify("source_failed", status=failure_status,
                   error=type(exc).__name__)
            if not continue_on_error:
                raise
    return {
        "contract": CONTRACT, "strategy_version": version,
        "status": (
            "NO_STRATEGY_SOURCE_DEMANDS_YET"
            if not counts["source_uses_requested"]
            else "ALL_REQUESTED_SOURCES_PRESENT"
            if counts["source_uses_requested"] == counts["source_uses_resolved"]
            else "SOURCE_REQUIREMENTS_UNRESOLVED_OR_NO_DATA"
        ),
        "source_uses_requested": counts["source_uses_requested"],
        "source_uses_resolved": counts["source_uses_resolved"],
        "source_uses_explicit_no_data": counts["source_uses_explicit_no_data"],
        "source_uses_failed_or_unresolved": counts["source_uses_failed_or_unresolved"],
        "source_uses_ambiguous_prior_dispatch": counts["source_uses_ambiguous_prior_dispatch"],
        "source_uses_ambiguous_current_dispatch": counts["source_uses_ambiguous_current_dispatch"],
        "provider_dispatch_attempts": counts["provider_dispatch_attempts"],
        "provider_fetch_successes": counts["provider_fetch_successes"],
        "persisted_cache_hits": counts["persisted_cache_hits"],
        "exact_query_store": str(db_path),
        "unlimited_candidate_roster_and_total_source_requests": True,
        "historical_execution_proven": False,
        "point_in_time_feature_availability_proven": False,
        "historical_strategy_profitability_proven": False,
    }
