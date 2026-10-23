from __future__ import annotations

"""Pure local hybrid option-data requirement versus source-presence planner.

One immutable batch of explicitly declared quote requirements becomes a
deterministic, deduplicated missing-source worklist. Existing V1 catalog
entries are source diagnostics, never simulator-ready evidence. No provider,
broker, protected outcomes, DB writes, price scans, or API fallbacks.
"""

from collections import defaultdict
from datetime import date, time
import json
from pathlib import Path
import re
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.hybrid_options_coverage_catalog_v1 import CATALOG_REL
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-hybrid-options-source-requirement-gap-planner-v1"
BATCH_CONTRACT = "atlas-hybrid-options-source-requirement-batch-v1"
MAX_BATCH_BYTES = 128 * 1024
MAX_REQUIREMENTS = 64
MAX_SOURCES_PER_SESSION = 100
SYMBOL_PATTERN = re.compile(r"[A-Z][A-Z0-9.\\-]{0,15}")
NAME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_\\-]{0,63}")
QUERY_FIELDS = frozenset((
    "symbol", "date_et", "expiration", "right", "interval",
    "start_time", "end_time", "max_dte", "strike_range",
))
PURPOSES = frozenset(("discovery", "entry", "management", "exit", "research"))
INTERVALS = frozenset(("1h", "1m", "1s"))


class HybridGapPlannerError(ValueError):
    pass


def _scope(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != QUERY_FIELDS:
        raise HybridGapPlannerError("EXACT_QUERY_FIELDS_REQUIRED")
    symbol = raw["symbol"]
    if not isinstance(symbol, str) or not SYMBOL_PATTERN.fullmatch(symbol):
        raise HybridGapPlannerError("INVALID_UNDERLYING_SYMBOL")
    try:
        day = date.fromisoformat(raw["date_et"])
        if not (2016 <= day.year <= 2035):
            raise ValueError("unsupported date")
        start = time.fromisoformat(raw["start_time"])
        end = time.fromisoformat(raw["end_time"])
    except (TypeError, ValueError) as exc:
        raise HybridGapPlannerError("INVALID_SESSION_OR_CLOCK") from exc
    if (start >= end or start.hour < 9 or end.hour > 16
            or start.minute != 30 and start.hour == 9 and start.minute < 30):
        raise HybridGapPlannerError("INVALID_REGULAR_SESSION_WINDOW")
    if (raw["expiration"] != "*" or raw["right"] not in ("call", "put", "both")
            or raw["interval"] not in INTERVALS
            or not isinstance(raw["max_dte"], int)
            or isinstance(raw["max_dte"], bool)
            or not (1 <= raw["max_dte"] <= 365)
            or not isinstance(raw["strike_range"], int)
            or isinstance(raw["strike_range"], bool)
            or not (0 <= raw["strike_range"] <= 16)):
        raise HybridGapPlannerError("UNSUPPORTED_SOURCE_QUERY_SHAPE")
    return dict(raw)


def demo_batch() -> dict[str, Any]:
    """Five independent uses of four unique historical requests.

    One exact observed local SPY source gets reused by two strategy contexts.
    A minute SPY source, a QQQ source and older SPY year remain NOT_INDEXED.
    """
    base = {
        "symbol": "SPY", "date_et": "2025-06-09", "expiration": "*",
        "right": "both", "interval": "1h", "start_time": "09:30:00",
        "end_time": "16:00:00", "max_dte": 45, "strike_range": 2,
    }
    return {
        "contract": BATCH_CONTRACT,
        "requests": [
            {"strategy_key": "SPY_NATIVE_HOURLY", "purpose": "discovery",
             "query": dict(base)},
            {"strategy_key": "SPY_DIFFERENT_HOURLY", "purpose": "research",
             "query": dict(base)},
            {"strategy_key": "SPY_DYNAMIC_EXIT", "purpose": "management",
             "query": {**base, "interval": "1m"}},
            {"strategy_key": "QQQ_HOURLY", "purpose": "discovery",
             "query": {**base, "symbol": "QQQ"}},
            {"strategy_key": "SPY_2018_RESEARCH", "purpose": "discovery",
             "query": {**base, "date_et": "2018-06-11"}},
        ],
    }


def load_batch_file(path: Path) -> dict[str, Any]:
    if (path.is_symlink() or not path.is_file()
            or not (0 < path.stat().st_size <= MAX_BATCH_BYTES)):
        raise HybridGapPlannerError("BATCH_FILE_MISSING_OR_OUTSIDE_SIZE_CAP")
    try:
        value = json.loads(path.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise HybridGapPlannerError("BATCH_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise HybridGapPlannerError("BATCH_JSON_NOT_OBJECT")
    return value


def normalize_batch(batch: dict[str, Any]) -> list[dict[str, Any]]:
    if (not isinstance(batch, dict) or set(batch) != {"contract", "requests"}
            or batch["contract"] != BATCH_CONTRACT
            or not isinstance(batch["requests"], list)
            or not (1 <= len(batch["requests"]) <= MAX_REQUIREMENTS)):
        raise HybridGapPlannerError("BATCH_CONTRACT_OR_BOUNDS_INVALID")
    normalized: list[dict[str, Any]] = []
    for item in batch["requests"]:
        if not isinstance(item, dict) or set(item) != {
            "strategy_key", "purpose", "query",
        }:
            raise HybridGapPlannerError("REQUEST_FIELDS_INVALID")
        key, purpose = item["strategy_key"], item["purpose"]
        if (not isinstance(key, str) or not NAME_PATTERN.fullmatch(key)
                or purpose not in PURPOSES):
            raise HybridGapPlannerError("STRATEGY_OR_PURPOSE_INVALID")
        normalized.append({
            "strategy_key": key, "purpose": purpose,
            "query": _scope(item["query"]),
        })
    return normalized


def plan_missing_sources(
    settings: AtlasSettings,
    batch: dict[str, Any],
) -> dict[str, Any]:
    """Read exact-query matches; never infer quote coverage from nearby data."""
    requirements = normalize_batch(batch)
    settings.assert_external_storage_binding("options")
    root = settings.resolved_path("data/options")
    if not root.is_dir():
        raise HybridGapPlannerError("OPTIONS_STORAGE_BINDING_UNAVAILABLE")
    db_path = settings.resolved_path(CATALOG_REL)
    by_query: dict[str, dict[str, Any]] = {}
    for request in requirements:
        query = request["query"]
        identity = _fingerprint({"source_type": "option_history_quote", "query": query})
        if identity not in by_query:
            by_query[identity] = {
                "query_id": identity, "query": query, "uses": [],
            }
        use = (request["strategy_key"], request["purpose"])
        if use not in by_query[identity]["uses"]:
            by_query[identity]["uses"].append(use)

    existing: dict[tuple[str, str], list[tuple[Any, ...]]] = defaultdict(list)
    if db_path.is_file() and not db_path.is_symlink():
        con = connect_utc(db_path, read_only=True)
        try:
            sessions = {(r["query"]["symbol"], r["query"]["date_et"])
                        for r in by_query.values()}
            for symbol, day in sorted(sessions):
                records = con.execute(
                    "SELECT source_id, query_json, source_status, "
                    "query_coverage_proven, simulator_ready, source_rows, "
                    "source_type FROM source_units "
                    "WHERE symbol=? AND session_et=? "
                    "ORDER BY source_id LIMIT ?",
                    [symbol, day, MAX_SOURCES_PER_SESSION + 1],
                ).fetchall()
                if len(records) > MAX_SOURCES_PER_SESSION:
                    raise HybridGapPlannerError("CATALOG_SOURCE_COUNT_CAP")
                existing[(symbol, day)] = records
        finally:
            con.close()
    elif db_path.exists() or db_path.is_symlink():
        raise HybridGapPlannerError("CATALOG_DB_PATH_INVALID")

    results = []
    for query_id, entry in sorted(by_query.items()):
        query = entry["query"]
        candidates = existing.get((query["symbol"], query["date_et"]), ())
        exact_sources = []
        for src in candidates:
            try:
                stored = json.loads(src[1])
            except (ValueError, TypeError) as exc:
                raise HybridGapPlannerError("CATALOG_QUERY_JSON_INVALID") from exc
            if not isinstance(stored, dict):
                raise HybridGapPlannerError("CATALOG_QUERY_NOT_OBJECT")
            if stored == query and src[6] == "THETADATA_OPTION_HISTORY_QUOTE":
                if (src[2] != "RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED"
                        or src[3] is not False or src[4] is not False):
                    raise HybridGapPlannerError("UNEXPECTED_CATALOG_ACCEPTANCE_STATE")
                exact_sources.append({
                    "source_id": src[0],
                    "source_status": src[2],
                    "observed_rows": int(src[5]),
                    "simulator_ready": False,
                })
        exact = bool(exact_sources)
        results.append({
            "query_id": query_id,
            "query": query,
            "uses": [{"strategy_key": name, "purpose": purpose}
                     for name, purpose in sorted(entry["uses"])],
            "source_state": "EXACT_SOURCE_OBSERVED_UNQUALIFIED" if exact
                            else "MISSING_EXACT_LOCAL_SOURCE",
            "source_present": exact,
            "same_symbol_day_other_scopes": max(0, len(candidates) - len(exact_sources)),
            "exact_sources": exact_sources,
            "simulator_ready": False,
            "acquisition_status": "NO_REQUEST_AUTHORIZED",
        })

    body = {
        "contract": CONTRACT,
        "status": "OFFLINE_GAP_DIAGNOSTIC_NOT_A_PROVIDER_WORKLIST",
        "batch_contract": BATCH_CONTRACT,
        "total_requirement_uses": len(requirements),
        "unique_exact_queries": len(results),
        "deduplicated_uses": len(requirements) - len(results),
        "exact_sources_observed_not_qualified":
            sum(r["source_present"] for r in results),
        "queries_missing_exact_local_source":
            sum(not r["source_present"] for r in results),
        "qualified_for_simulator": 0,
        "catalog_present": db_path.is_file(),
        "queries": results,
        "provider_requests": 0,
        "broker_requests": 0,
        "source_files_scanned": 0,
        "simulations_run": 0,
        "automatic_acquisition_authorized": False,
        "missing_does_not_prove_provider_unavailability": True,
    }
    body["report_fingerprint"] = _fingerprint(body)
    return body
