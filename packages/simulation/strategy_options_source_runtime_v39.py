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


def resolve_strategy_source_demands(
    settings: AtlasSettings,
    strategy_version: str,
    demands: Iterable[dict[str, Any]],
    *,
    provider_call: Callable | None = None,
    on_source: Callable[[dict, dict], None] | None = None,
    continue_on_error: bool = False,
) -> dict:
    """Consume arbitrarily many dynamic requirements one at a time.

    Producer yields one current-strategy source need (even for candidates
    discovered during simulation). A missing exact query automatically calls
    ThetaData; it is archived/indexed before the source callback runs. The
    strategy may request additional sources after inspecting qualifying
    *causal* observations. The coordinator does not itself grant that gate.

    Rerun/resume simply replays needs: completed source queries are cache hits,
    failures can be retried; all use/candidate associations persist in SQLite.
    """
    version = _name(strategy_version, "STRATEGY_VERSION")
    if type(continue_on_error) is not bool:
        raise StrategySourceRuntimeError("INVALID_CONTINUE_ON_ERROR")
    db_path = _database(settings)
    with _connect(db_path) as db:
        _journal(db)
    counts = Counter()

    def counted_provider_call(method: str, kwargs: dict):
        # Count *attempts* at runtime, including a provider failure; neither
        # cache hits nor a printed preflight can predict this number.
        counts["provider_dispatch_attempts"] += 1
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
            counts["source_uses_resolved"] += status in SUCCESS
            counts["source_uses_explicit_no_data"] += status in NO_DATA
            counts["provider_fetch_successes"] += status.startswith("FETCHED_")
            counts["persisted_cache_hits"] += status.startswith("CACHE")
            if on_source is not None:
                on_source(dict(item), source)
        except Exception:
            counts["source_uses_failed_or_unresolved"] += 1
            with _connect(db_path) as db:
                _put(db, version=version, candidate=candidate, purpose=purpose,
                     request=normalized, query_id=query_id,
                     status="SOURCE_RETRY_REQUIRED", source_sha=None)
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
        "provider_dispatch_attempts": counts["provider_dispatch_attempts"],
        "provider_fetch_successes": counts["provider_fetch_successes"],
        "persisted_cache_hits": counts["persisted_cache_hits"],
        "exact_query_store": str(db_path),
        "unlimited_candidate_roster_and_total_source_requests": True,
        "historical_execution_proven": False,
        "point_in_time_feature_availability_proven": False,
        "historical_strategy_profitability_proven": False,
    }
