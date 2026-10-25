from __future__ import annotations

"""V9 immutable exact at-time historical option-research demand inventory.

Consumes the deterministic weekly SPY source plan and, when explicitly
provided, the existing frozen 9,455 CALL candidate-surface plan. Preserves
09:35 / 10:00, exact call/put rights, wildcard strikes, max DTE and native
provider query parameters. It NEVER manufactures hourly substitutes, V7
reservations, V8 authority, provider requests or accepted quote coverage.

An operator may explicitly snapshot both real branches in a bounded,
content-addressed manifest on external options storage. The default is a
read-only summary and does not require opening the 9,455-surface artifact.
"""

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.hybrid_options_lossless_archive_v1 import _write_immutable
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_plan_v1 import (
    build_options_native_pilot_plan, verify_options_native_pilot_plan,
)
from packages.data.thetadata_candidate_surface_enrichment_plan_v1 import (
    _validate_source_plan,
)
from packages.data.thetadata_candidate_surface_plan_v1 import (
    EXPECTED_MAX_DTE, EXPECTED_UNIQUE_SURFACES, _normalize_surface,
    _provider_query,
)
from packages.data.research_storage import GIB

CONTRACT = "atlas-hybrid-option-exact-legacy-research-demand-manifest-v1"
OUTPUT_REL = "data/options/manifests/hybrid_exact_at_time_research_demand_v1"
ALLOWED_CANDIDATE_PREFIX = "thetadata_candidate_surface_source_plan_v1_"
MAX_CANDIDATE_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
MIN_FREE_BYTES = 40 * GIB
SHA = re.compile(r"[a-f0-9]{64}")
EXPECTED_PROVIDER_ENDPOINT = "/v3/option/at_time/quote"
EXPECTED_CANDIDATE_PARAMS = {
    "symbol", "expiration", "strike", "right", "start_date",
    "end_date", "time_of_day", "max_dte", "strike_range", "format",
}
ROW_KEY_FIELDS = {
    "origin", "original_source_fingerprint", "origin_query_fingerprint",
    "symbol", "date_et", "decision_clock_et", "right", "endpoint",
    "params", "source_role", "qualification_anchor", "query_id",
    "exact_adapter", "provider_requests", "simulator_ready",
}


class HybridFrozenDemandError(ValueError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ) + "\n").encode("utf-8")


def load_candidate_source_plan(
    settings: AtlasSettings, requested: Path,
) -> dict[str, Any]:
    """One bounded *explicit* immutable file in the options manifest binding."""
    settings.assert_external_storage_binding("options")
    root = settings.resolved_path("data/options/manifests")
    path = requested if requested.is_absolute() else settings.resolved_path(requested)
    if (path.is_symlink() or not path.is_file()
            or not path.resolve().is_relative_to(root.resolve())
            or not path.name.startswith(ALLOWED_CANDIDATE_PREFIX)
            or not path.name.endswith(".json")
            or not 0 < path.stat().st_size <= MAX_CANDIDATE_BYTES):
        raise HybridFrozenDemandError("EXACT_CANDIDATE_SOURCE_PLAN_NOT_AVAILABLE")
    try:
        plan = json.loads(path.read_bytes())
    except (UnicodeError, ValueError) as exc:
        raise HybridFrozenDemandError("CANDIDATE_SOURCE_PLAN_JSON_INVALID") from exc
    if not isinstance(plan, dict):
        raise HybridFrozenDemandError("CANDIDATE_SOURCE_PLAN_NOT_OBJECT")
    fp = plan.get("plan_fingerprint")
    if (not isinstance(fp, str) or not SHA.fullmatch(fp)
            or path.name != f"{ALLOWED_CANDIDATE_PREFIX}{fp[:16]}.json"):
        raise HybridFrozenDemandError("CANDIDATE_SOURCE_FILE_FINGERPRINT_DRIFT")
    # Source bytes have already been independently signed by the original
    # plan's exact fingerprint; V9 independently validates every quote shape.
    _validate_source_plan(plan)
    return plan


def _entry(origin: str, original_fingerprint: str,
           origin_query_fingerprint: str,
           query: dict[str, Any], *,
           role: str, anchor: bool) -> dict[str, Any]:
    params = query["params"]
    date_compact = params["start_date"]
    try:
        day = datetime.strptime(date_compact, "%Y%m%d").date().isoformat()
    except (ValueError, TypeError) as exc:
        raise HybridFrozenDemandError("ORIGINAL_DATE_NOT_EXACT") from exc
    if (not isinstance(original_fingerprint, str)
            or not SHA.fullmatch(original_fingerprint)
            or not isinstance(origin_query_fingerprint, str)
            or not SHA.fullmatch(origin_query_fingerprint)
            or set(params) != EXPECTED_CANDIDATE_PARAMS
            or query["endpoint"] != EXPECTED_PROVIDER_ENDPOINT
            or params["end_date"] != date_compact
            or params["expiration"] != "*"
            or params["strike"] != "*"
            or params["format"] != "json"
            or params["symbol"] != params["symbol"].upper()
            or params["time_of_day"] not in ("09:35:00.000", "10:00:00.000")):
        raise HybridFrozenDemandError("ORIGINAL_AT_TIME_REQUEST_SHAPE_DRIFT")
    row = {
        "origin": origin,
        "original_source_fingerprint": original_fingerprint,
        "origin_query_fingerprint": origin_query_fingerprint,
        "symbol": params["symbol"],
        "date_et": day,
        "decision_clock_et": params["time_of_day"],
        "right": params["right"],
        "endpoint": query["endpoint"],
        "params": dict(params),
        "source_role": role,
        "qualification_anchor": bool(anchor),
        # V8's hourly identity is intentionally NOT reused for at-time data.
        "query_id": _fingerprint({
            "provider": "thetadata",
            "endpoint": query["endpoint"], "params": params,
        }),
        "exact_adapter": "AT_TIME_ADAPTER_NOT_IMPLEMENTED_NO_PROVIDER_AUTHORITY",
        "provider_requests": 0,
        "simulator_ready": False,
    }
    if set(row) != ROW_KEY_FIELDS:
        raise HybridFrozenDemandError("V9_ROW_SCHEMA_DRIFT")
    return row


def build_frozen_research_demand(
    candidate_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create exact source demand; never reinterpret it as hourly quotes."""
    pilot = verify_options_native_pilot_plan(
        build_options_native_pilot_plan()
    )
    pilot_fp = pilot["plan_fingerprint"]
    pilot_anchors = {
        a["query_fingerprint"] for a in
        pilot["qualification_design"]["anchors"]
    }
    rows = []
    for original in pilot["entry_quote_surface_requests"]:
        if (set(original) != {
                "endpoint", "params", "role", "source_qualified",
                "query_fingerprint",
            } or original["source_qualified"] is not False
                or original["role"] != "DECISION_INPUT"
                or original["query_fingerprint"] != _fingerprint({
                    k: v for k, v in original.items()
                    if k != "query_fingerprint"
                })):
            raise HybridFrozenDemandError("PILOT_ORIGINAL_REQUEST_DRIFT")
        query = {"endpoint": original["endpoint"], "params": original["params"]}
        params = query["params"]
        if (params["symbol"] != "SPY"
                or params["time_of_day"] != "10:00:00.000"
                or params["right"] != "both"
                or params["strike_range"] != 2):
            raise HybridFrozenDemandError("PILOT_1000_DECISION_SHAPE_CHANGED")
        rows.append(_entry(
            "FROZEN_SPY_WEEKLY_OPTIONS_NATIVE", pilot_fp,
            original["query_fingerprint"], query,
            role="WEEKLY_ENTRY_DECISION", anchor=(
                original["query_fingerprint"] in pilot_anchors
            ),
        ))
    if len(rows) != pilot["entry_quote_surface_count"]:
        raise HybridFrozenDemandError("PILOT_QUOTE_COUNT_DRIFT")

    candidate_fp = None
    anchors = 0
    candidate_count = 0
    if candidate_plan is not None:
        original_quotes = _validate_source_plan(candidate_plan)
        candidate_fp = candidate_plan["plan_fingerprint"]
        original_anchors = candidate_plan["qualification"]["anchors"]
        anchor_ids = {
            item["decision_spot_query_fingerprint"] for item in original_anchors
        }
        if (candidate_plan["qualification"]["anchor_query_count"]
                != len(original_anchors)
                or len(anchor_ids) != len(original_anchors)):
            raise HybridFrozenDemandError("CANDIDATE_QUALIFICATION_ANCHOR_DRIFT")
        seen_source_fp = set()
        for request in original_quotes:
            if not isinstance(request, dict) or set(request) != {
                "endpoint", "params", "source_query_fingerprint",
                "member_case_ids", "member_case_count",
            }:
                raise HybridFrozenDemandError("CANDIDATE_REQUEST_SCHEMA_CHANGED")
            params = request["params"]
            surface = _normalize_surface({
                "request_type": "OPTION_CALL_CANDIDATE_SURFACE_AT_DECISION_CLOCK",
                "symbol": params["symbol"], "date_et":
                    datetime.strptime(params["start_date"], "%Y%m%d").date().isoformat(),
                "time_of_day_et": params["time_of_day"],
                "right": "call",
                "max_dte_calendar_days": EXPECTED_MAX_DTE,
                "expiration_policy": "ALL_EXPIRATIONS_WITHIN_PROVIDER_MAX_DTE",
                "strike_policy": "CANDIDATE_SURFACE_NOT_PRESELECTED_STRIKE",
                "query_fingerprint": request["source_query_fingerprint"],
                "member_case_ids": request["member_case_ids"],
                "member_case_count": request["member_case_count"],
            })
            if (_provider_query(surface) != request
                    or surface["query_fingerprint"] in seen_source_fp
                    or params["time_of_day"] != "09:35:00.000"
                    or params["right"] != "call"
                    or params["strike_range"] is not None
                    or params["max_dte"] != EXPECTED_MAX_DTE):
                raise HybridFrozenDemandError("CANDIDATE_SOURCE_QUERY_DRIFT")
            seen_source_fp.add(surface["query_fingerprint"])
            rows.append(_entry(
                "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES", candidate_fp,
                surface["query_fingerprint"],
                {"endpoint": request["endpoint"], "params": params},
                role="0935_CALL_ENTRY_DISCOVERY", anchor=(
                    surface["query_fingerprint"] in anchor_ids
                ),
            ))
        if not anchor_ids.issubset(seen_source_fp):
            raise HybridFrozenDemandError("CANDIDATE_ANCHOR_OUTSIDE_SOURCE_DEMAND")
        candidate_count = len(original_quotes)
        anchors = len(anchor_ids)
        if candidate_count != EXPECTED_UNIQUE_SURFACES:
            raise HybridFrozenDemandError("CANDIDATE_FULL_SCOPE_COUNT_DRIFT")
    ids = [x["query_id"] for x in rows]
    if len(ids) != len(set(ids)):
        raise HybridFrozenDemandError("CROSS_BRANCH_OR_WITHIN_BRANCH_QUERY_COLLISION")
    # Qualification anchors are prioritized before the broad sweep; inside
    # each tier, chronological oldest first, then reproducible symbol/clock.
    rows.sort(key=lambda r: (
        0 if r["qualification_anchor"] else 1,
        r["date_et"], r["symbol"], r["decision_clock_et"], r["query_id"],
    ))
    all_years = Counter(r["date_et"][:4] for r in rows)
    origin_counts = Counter(r["origin"] for r in rows)
    for i, row in enumerate(rows, 1):
        row["priority"] = i
    if candidate_plan is None:
        stage = "PARTIAL_PILOT_ONLY_CANDIDATE_PLAN_NOT_READ"
    else:
        stage = "BOTH_FROZEN_SOURCE_BRANCHES_PRESERVED_EXACTLY"
    body = {
        "contract": CONTRACT,
        "status": stage,
        "pilot_source_fingerprint": pilot_fp,
        "candidate_source_fingerprint": candidate_fp,
        "candidate_source_supplied_and_verified": candidate_plan is not None,
        "frozen_pilot_quote_queries": pilot["entry_quote_surface_count"],
        "frozen_candidate_quote_queries": candidate_count,
        "frozen_candidate_qualification_anchors": anchors,
        "source_request_count": len(rows),
        "priority_mode": "QUALIFICATION_ANCHORS_THEN_CHRONOLOGICAL",
        "year_counts": dict(sorted(all_years.items())),
        "origin_counts": dict(sorted(origin_counts.items())),
        "request_ids_unique": True,
        "v8_hourly_reservations_created": 0,
        "v8_hourly_query_ids_reused": 0,
        "at_time_provider_adapter_ready": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_read": 0,
        "simulations_run": 0,
        "paid_provider_authority": False,
        "simulator_ready": False,
        "requests": rows,
    }
    body["manifest_fingerprint"] = _fingerprint(body)
    return body


def write_frozen_demand_manifest(
    settings: AtlasSettings, manifest: dict[str, Any],
) -> tuple[Path, bool]:
    """Immutable user-opt-in copy of the verified TWO-branch plan only."""
    settings.assert_external_storage_binding("options")
    if (manifest.get("contract") != CONTRACT
            or manifest.get("candidate_source_supplied_and_verified") is not True
            or manifest.get("status") != "BOTH_FROZEN_SOURCE_BRANCHES_PRESERVED_EXACTLY"
            or manifest.get("source_request_count") !=
                manifest.get("frozen_pilot_quote_queries", 0) +
                manifest.get("frozen_candidate_quote_queries", 0)
            or manifest.get("paid_provider_authority") is not False
            or manifest.get("at_time_provider_adapter_ready") is not False
            or manifest.get("manifest_fingerprint") != _fingerprint({
                k: v for k, v in manifest.items() if k != "manifest_fingerprint"
            })):
        raise HybridFrozenDemandError("MANIFEST_NOT_VERIFIED_FULL_SOURCE_DEMAND")
    raw = (json.dumps(
        manifest, sort_keys=True, indent=2,
        allow_nan=False, ensure_ascii=False,
    ) + "\n").encode("utf-8")
    if len(raw) > MAX_MANIFEST_BYTES:
        raise HybridFrozenDemandError("OUTPUT_MANIFEST_EXCEEDS_SIZE_CAP")
    root = settings.resolved_path("data/options/manifests")
    if not root.is_dir() or root.is_symlink():
        raise HybridFrozenDemandError("EXTERNAL_MANIFEST_DIRECTORY_UNAVAILABLE")
    if shutil.disk_usage(root).free < MIN_FREE_BYTES + len(raw):
        raise HybridFrozenDemandError("EXTERNAL_STORAGE_WARNING_HEADROOM")
    fp = manifest["manifest_fingerprint"]
    path = root / f"hybrid_exact_at_time_research_demand_v1_{fp[:16]}.json"
    if path.is_symlink():
        raise HybridFrozenDemandError("MANIFEST_LINK_FORBIDDEN")
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise HybridFrozenDemandError("IMMUTABLE_MANIFEST_CONFLICT")
        return path, False
    _write_immutable(path, raw)
    if path.read_bytes() != raw:
        raise HybridFrozenDemandError("MANIFEST_POSTWRITE_BYTES_CHANGED")
    return path, True
