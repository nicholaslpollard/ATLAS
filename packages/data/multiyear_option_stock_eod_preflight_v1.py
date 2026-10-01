from __future__ import annotations

"""One offline option->native-stock EOD demand and legacy-quote overlap gate.

This does not reinterpret option vendor timestamps as XNYS close, claim a
standard deliverable, silently fill missing observations or issue provider GETs.
"""

from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.marketdata_candidate_2025_selected_quote_source_v1 import (
    CONTRACT as PILOT_CONTRACT, PLAN_REL as PILOT_PLAN_REL,
    _intact as pilot_receipt, _paths as pilot_paths,
)
from packages.data.multiyear_observed_option_quote_timeline_v1 import (
    CONTRACT as TIMELINE_CONTRACT,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.multiyear_demand_quote_cache_v1 import _write_new
from packages.data.multiyear_option_quote_bridge_v1 import NATIVE_FP, NATIVE_REL

CONTRACT = "atlas-multiyear-option-stock-eod-source-needs-v1"
OUTPUT_REL = "data/options/derived/multiyear_option_stock_eod_source_needs_v1"
EASTERN = ZoneInfo("America/New_York")
PILOT_COUNT = 11
NEEDS = "QUOTE_SOURCE_AVAILABLE_NATIVE_RAW_EOD_CLOSE_NOT_YET_VERIFIED"
PROTECTED_2026 = "OPTION_SOURCE_PAIR_REQUIRES_PROTECTED_2026_NATIVE_CLOSE_WITHHELD"
NO_TWO = "NO_LATER_TWO_SIDED_SOURCE_PAIR"


class OptionStockEodNeedsError(ValueError):
    pass


def _day(value: object) -> date:
    if not isinstance(value, str):
        raise OptionStockEodNeedsError("source date is not text")
    return date.fromisoformat(value)


def _stamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise OptionStockEodNeedsError("option update time is not ISO text")
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise OptionStockEodNeedsError("option update must carry UTC offset")
    return stamp.astimezone(UTC)


def build_native_eod_needs(
    native: dict[str, Any], selection: dict[str, Any],
    timeline: dict[str, Any], *,
    expected_original_cases: int = 14902,
) -> dict[str, Any]:
    """Freeze exact (instrument,ticker,session) native CLOSE requests; no raw scan."""
    for doc, field in ((native, "source_fingerprint"),
                       (selection, "selection_fingerprint"),
                       (timeline, "timeline_fingerprint")):
        if not isinstance(doc, dict):
            raise OptionStockEodNeedsError("source is not an object")
        _check_signature(doc, field)
    if (native.get("source_fingerprint") != NATIVE_FP
        or native.get("case_denominator") != expected_original_cases
        or native.get("provider_requests") != 0
        or native.get("protected_outcomes_read") != 0
        or selection.get("original_case_denominator") != expected_original_cases
        or selection.get("right_policy") != "both"
        or timeline.get("contract") != TIMELINE_CONTRACT
        or timeline.get("status") != "OFFLINE_OBSERVED_QUOTE_SOURCE_TIMELINES_ONLY"
        or timeline.get("selection_fingerprint") != selection["selection_fingerprint"]
        or timeline.get("original_case_denominator") != expected_original_cases
        or timeline.get("original_right_memberships") != expected_original_cases * 2
        or timeline.get("selected_case_right_memberships") != len(selection.get("cases", []))
        or timeline.get("provider_requests") != 0
        or timeline.get("account_pnl_authority") is not False
        or timeline.get("protected_2026_outcomes_read") != 0):
        raise OptionStockEodNeedsError("accepted native/option denominator or authority differs")
    stocks = {r["case_id"]: r for r in native["rows"]}
    selected = {r["case_id"]: r for r in selection["cases"]}
    if len(stocks) != expected_original_cases or len(selected) != len(selection["cases"]):
        raise OptionStockEodNeedsError("duplicate native or selected case identity")
    requests: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    yearly: dict[str, Counter[str]] = defaultdict(Counter)
    seen = set()
    for item in timeline["rows"]:
        case_right = item["case_right_id"]
        original = item["original_case_id"]
        year = item["year"]
        if case_right in seen or original not in stocks or year not in ("2021","2022","2023","2024","2025"):
            raise OptionStockEodNeedsError("duplicate case/right or unknown native case")
        seen.add(case_right)
        stock = stocks[original]
        picked = selected.get(case_right)
        if (stock["signal_session"][:4] != year
            or stock["case_id"] != original
            or item["option_symbol"] != (picked["option_symbol"] if picked else None)):
            raise OptionStockEodNeedsError("original native/option identity mismatch")
        observations = [
            ("entry", item["first_later_observed_quote"]),
            ("next", item["next_later_observed_quote"]),
        ]
        marks = {}
        protected_roles = {"entry": False, "next": False}
        for role, quote in observations:
            if quote is None:
                marks[role] = None
                continue
            if picked is None or item["timeline_status"] not in (
                "FIRST_LATER_TWO_SIDED_SOURCE_ONLY",
                "TWO_OR_MORE_LATER_TWO_SIDED_SOURCE_DATES",
            ):
                raise OptionStockEodNeedsError("unselected contract has observed quote")
            day = _day(quote["session_et"])
            clock = _stamp(quote["provider_updated_at_utc"])
            decision = _stamp(picked["decision_at_utc"])
            if (clock.astimezone(EASTERN).date() != day
                or day <= decision.astimezone(EASTERN).date()
                or day > _day(picked["expiration"])
                or day < _day(stock["entry_session"])
                or quote["two_sided_source"] is not True):
                raise OptionStockEodNeedsError("future/PIT/EOD quote chronology changed")
            query = {
                "instrument_id": stock["instrument_id"],
                "ticker": stock["ticker"],
                "session_et": day.isoformat(),
            }
            identity = _fingerprint({"contract": CONTRACT, "native_query": query})
            protected = day.year == 2026
            protected_roles[role] = protected
            request = requests.setdefault(identity, {
                "request_identity": identity,
                **query,
                "case_right_ids": [],
                "option_source_updates_utc": [],
                "required_native_field": "RAW_AS_TRADED_1DAY_REGULAR_CLOSE",
                "stock_close_has_not_been_read": True,
                "protected_2026_native_read_forbidden": protected,
            })
            if request["protected_2026_native_read_forbidden"] is not protected:
                raise OptionStockEodNeedsError("same native request crossed protected boundary")
            if case_right not in request["case_right_ids"]:
                request["case_right_ids"].append(case_right)
            stamp_text = clock.isoformat()
            if stamp_text not in request["option_source_updates_utc"]:
                request["option_source_updates_utc"].append(stamp_text)
            marks[role] = identity
        if (marks["next"] is not None and marks["entry"] is None):
            raise OptionStockEodNeedsError("next quote without earlier entry source")
        status = (
            PROTECTED_2026
            if marks["entry"] and marks["next"] and any(protected_roles.values())
            else NEEDS if marks["entry"] and marks["next"]
            else NO_TWO
        )
        yearly[year][status] += 1
        rows.append({
            "case_right_id": case_right, "original_case_id": original,
            "year": year, "ticker": stock["ticker"],
            "instrument_id": stock["instrument_id"],
            "option_symbol": item["option_symbol"],
            "observed_quote_timeline_status": item["timeline_status"],
            "native_entry_close_request_identity": marks["entry"],
            "native_next_close_request_identity": marks["next"],
            "protected_2026_native_entry_withheld": protected_roles["entry"],
            "protected_2026_native_next_withheld": protected_roles["next"],
            "native_close_verified": False,
            "matched_option_stock_clock_verified": False,
            "hypothetical_fill_or_option_pnl_authority": False,
            "status": status,
        })
    if len(seen) != expected_original_cases * 2:
        raise OptionStockEodNeedsError("full original case/right population changed")
    for req in requests.values():
        req["case_right_ids"].sort()
        req["option_source_updates_utc"].sort()
    result = {
        "contract": CONTRACT,
        "status": "OFFLINE_NATIVE_STOCK_EOD_DEMAND_NOT_SOURCE_PROOF",
        "accepted_native_fingerprint": native["source_fingerprint"],
        "accepted_selection_fingerprint": selection["selection_fingerprint"],
        "accepted_option_timeline_fingerprint": timeline["timeline_fingerprint"],
        "original_case_denominator": expected_original_cases,
        "original_right_memberships": expected_original_cases * 2,
        "selected_case_right_memberships": len(selected),
        "case_rights_with_two_later_option_quote_dates": sum(
            x["status"] in {NEEDS, PROTECTED_2026} for x in rows
        ),
        "case_rights_with_protected_2026_native_close_withheld": sum(
            x["status"] == PROTECTED_2026 for x in rows
        ),
        "unique_native_raw_eod_close_requests": len(requests),
        "by_year": {k: dict(sorted(v.items())) for k,v in sorted(yearly.items())},
        "requests": sorted(requests.values(), key=lambda x: x["request_identity"]),
        "rows": sorted(rows, key=lambda x: x["case_right_id"]),
        "provider_requests": 0, "native_raw_closes_read": 0,
        "protected_2026_outcomes_read": 0, "same_clock_pairs_proven": 0,
        "portfolio_pnl_authority": False,
    }
    result["demand_fingerprint"] = _fingerprint(result)
    return result


def preview_pilot_quote_overlap(
    settings: AtlasSettings, quote_plan: dict[str, Any], handoff: dict[str, Any],
    *,
    read_verified_pilot: Callable[[dict[str, Any], str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Inspect original 2025 pilot ONLY for matching pending exact OCC symbols.

    Covering histories and partial overlaps are separate. A partial history is
    NEVER called a complete full-demand source or substituted by an option fill.
    """
    _check_signature(quote_plan, "plan_fingerprint")
    _check_signature(handoff, "handoff_fingerprint")
    if handoff["quote_plan_fingerprint"] != quote_plan["plan_fingerprint"]:
        raise OptionStockEodNeedsError("pilot overlap source plan changed")
    targets = {
        x["quote_request_identity"]: x for x in handoff["rows"]
        if x["quote_history_status"] == "QUOTE_HISTORY_NOT_ACQUIRED"
    }
    pending = {k for k in targets if k is not None}
    by_request = {x["request_identity"]: x for x in quote_plan["requests"]}
    if not pending.issubset(by_request):
        raise OptionStockEodNeedsError("pending quote query is not in exact frozen plan")
    source = settings.resolved_path(PILOT_PLAN_REL)
    rows = []
    counts: Counter[str] = Counter()
    if not source.exists() and not source.is_symlink():
        return {
            "contract": CONTRACT, "status": "NO_LOCAL_PILOT_PLAN_NO_REUSE_CLAIM",
            "quote_plan_fingerprint": quote_plan["plan_fingerprint"],
            "source_handoff_fingerprint": handoff["handoff_fingerprint"],
            "pending_unique_exact_requests": len(pending),
            "pilot_plan_fingerprint": None,
            "candidate_full_coverage_sources": 0,
            "candidate_partial_overlap_sources": 0,
            "by_status": {}, "rows": [], "provider_requests": 0,
            "paid_provider_reads_authorized": False,
        }
    pilot = _read_object(source)
    _check_signature(pilot, "plan_fingerprint")
    if (pilot.get("contract") != PILOT_CONTRACT
        or pilot.get("status") != "FROZEN_SELECTED_EOD_QUOTE_SOURCE_PLAN"
        or pilot.get("request_count") != PILOT_COUNT
        or len(pilot.get("requests", [])) != PILOT_COUNT
        or len({x["option_symbol"] for x in pilot["requests"]}) != PILOT_COUNT):
        raise OptionStockEodNeedsError("original 2025 pilot quote plan is not accepted")
    old_by_symbol = {x["option_symbol"]: x for x in pilot["requests"]}
    if read_verified_pilot is None:
        read_verified_pilot = lambda original, fingerprint: pilot_receipt(
            original, pilot_paths(settings, original), fingerprint,
        )
    for identity in sorted(pending):
        demand = by_request[identity]
        old = old_by_symbol.get(demand["option_symbol"])
        if old is None:
            continue
        before = max(_day(old["from_inclusive"]), _day(demand["from_inclusive"]))
        after = min(_day(old["to_exclusive"]), _day(demand["to_exclusive"]))
        if before >= after:
            continue
        receipt = read_verified_pilot(old, pilot["plan_fingerprint"])
        if receipt is None:
            status = "PILOT_QUOTE_SOURCE_UNAVAILABLE_NO_REUSE"
        elif receipt["status"] == "EXACT_QUERY_SOURCE_GAP":
            status = "PILOT_EXACT_SOURCE_GAP_ONLY_NO_CROSS_QUERY_INFERENCE"
        elif receipt["status"] == "COMPLETE_SOURCE_ONLY":
            full = (old["from_inclusive"] <= demand["from_inclusive"]
                    and old["to_exclusive"] >= demand["to_exclusive"])
            status = ("VERIFIED_PILOT_COVERS_FULL_DEMAND"
                      if full else "VERIFIED_PILOT_PARTIAL_WINDOW_ONLY")
        else:
            raise OptionStockEodNeedsError("original pilot source quarantined")
        counts[status] += 1
        rows.append({
            "quote_request_identity": identity,
            "option_symbol": demand["option_symbol"],
            "original_pilot_request_identity": old["request_identity"],
            "original_pilot_plan_fingerprint": pilot["plan_fingerprint"],
            "original_pilot_body_sha256": (
                receipt["body_sha256"] if receipt else None
            ),
            "original_pilot_observed_rows": (
                receipt["safe_summary"]["observed_rows"] if receipt else None
            ),
            "pilot_from_inclusive": old["from_inclusive"],
            "pilot_to_exclusive": old["to_exclusive"],
            "demand_from_inclusive": demand["from_inclusive"],
            "demand_to_exclusive": demand["to_exclusive"],
            "status": status,
            "not_a_historical_fill_or_full_reuse_if_partial": True,
        })
    result = {
        "contract": CONTRACT,
        "status": "LOCAL_ORIGINAL_PILOT_QUOTE_OVERLAP_CENSUS_ONLY",
        "quote_plan_fingerprint": quote_plan["plan_fingerprint"],
        "source_handoff_fingerprint": handoff["handoff_fingerprint"],
        "pending_unique_exact_requests": len(pending),
        "pilot_plan_fingerprint": pilot["plan_fingerprint"],
        "candidate_full_coverage_sources": counts["VERIFIED_PILOT_COVERS_FULL_DEMAND"],
        "candidate_partial_overlap_sources": counts["VERIFIED_PILOT_PARTIAL_WINDOW_ONLY"],
        "by_status": dict(sorted(counts.items())),
        "rows": rows,
        "provider_requests": 0,
        "paid_provider_reads_authorized": False,
    }
    result["overlap_fingerprint"] = _fingerprint(result)
    return result


def persist_source_needs(settings: AtlasSettings, result: dict[str, Any]) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(result, "demand_fingerprint")
    path = settings.resolved_path(f"{OUTPUT_REL}_{result['demand_fingerprint'][:16]}.json")
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != result:
            raise OptionStockEodNeedsError("previous immutable native EOD demand differs")
        return path, "REUSED_IDENTICAL_STOCK_EOD_SOURCE_DEMAND"
    _write_new(path, result)
    return path, "WRITTEN_IMMUTABLE_STOCK_EOD_SOURCE_DEMAND"


def persist_pilot_overlap(settings: AtlasSettings, result: dict[str, Any]) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    if result["status"] == "NO_LOCAL_PILOT_PLAN_NO_REUSE_CLAIM":
        result = dict(result)
        result["overlap_fingerprint"] = _fingerprint(result)
    _check_signature(result, "overlap_fingerprint")
    path = settings.resolved_path(
        "data/options/manifests/multiyear_2025_pilot_quote_overlap_v1_"
        + result["overlap_fingerprint"][:16] + ".json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != result:
            raise OptionStockEodNeedsError("previous immutable pilot overlap differs")
        return path, "REUSED_IDENTICAL_PILOT_QUOTE_OVERLAP"
    _write_new(path, result)
    return path, "WRITTEN_IMMUTABLE_PILOT_QUOTE_OVERLAP"
