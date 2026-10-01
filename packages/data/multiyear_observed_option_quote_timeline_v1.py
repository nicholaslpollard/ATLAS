from __future__ import annotations

"""Observed selected-option quote timelines; no synthetic fills or paid provider GETs.

Every original case/right remains in the denominator. Physical quote bodies are
decoded only once per unique exact query and only after existing receipt checks.
"""

import hashlib
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.marketdata_2022_rank0_later_eod_reference_v1 import _original_observations
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    _cache_paths as old_2022_paths, _read_intact_quote as old_2022_receipt,
)
from packages.data.multiyear_demand_quote_cache_v1 import (
    _intact as demand_receipt, _path as demand_paths, _write_new,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    CONTRACT as HANDOFF_CONTRACT, _check_signature,
)
from packages.data.offline_option_history_v1 import OfflineOptionHistoryStore

CONTRACT = "atlas-multiyear-observed-option-quote-timeline-v1"
OUTPUT_REL = "data/options/derived/multiyear_observed_option_quote_timeline_v1"
EASTERN = ZoneInfo("America/New_York")
VERIFIED = {
    "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY",
    "VERIFIED_DEMAND_CACHE_QUOTE_HISTORY",
    "VERIFIED_CLIPPED_DEMAND_CACHE_QUOTE_HISTORY",
}
ABSENT = {
    "NO_PIT_SELECTED_CONTRACT",
    "QUOTE_HISTORY_NOT_ACQUIRED",
    "EXACT_QUOTE_QUERY_NO_DATA",
    "CLIPPED_RECOVERY_QUERY_NO_DATA",
    "QUOTE_HISTORY_OUTSIDE_CURRENT_PROVIDER_WINDOW",
    "QUOTE_HISTORY_AFTER_LAST_COMPLETED_SESSION",
    "QUOTE_HISTORY_NO_CLOSED_SOURCE_PERIOD",
}


class ObservedOptionTimelineError(ValueError):
    pass


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ObservedOptionTimelineError("source timestamp must be ISO text")
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ObservedOptionTimelineError("invalid original timestamp") from exc
    if stamp.tzinfo is None:
        raise ObservedOptionTimelineError("source timestamp must be aware")
    return stamp.astimezone(UTC)


def _observation(row: dict[str, Any]) -> dict[str, Any]:
    """Check a fully receipt-verified physical EOD row, not a simulated fill.

    A covering original source can begin before the narrower selected request.
    Check every original row first; restrict the view to the selected frozen
    window only after original full-source receipt/body validation.
    """
    day = row["day"]
    if not isinstance(day, date) or isinstance(day, datetime):
        raise ObservedOptionTimelineError("option observation session missing")
    stamp = _utc(row["updated_at_utc"])
    bid, ask = row["bid"], row["ask"]
    valid = bid is not None and ask is not None and bid > 0 and ask >= bid
    if stamp.astimezone(EASTERN).date() != day:
        raise ObservedOptionTimelineError(
            f"source quote timing/Eastern session mismatch on {day.isoformat()}"
        )
    if row["two_sided"] is not valid:
        raise ObservedOptionTimelineError(
            f"source quote bid/ask spread classification mismatch on {day.isoformat()}"
        )
    if type(row["positive_volume"]) is not bool:
        raise ObservedOptionTimelineError(
            f"source quote reported volume flag invalid on {day.isoformat()}"
        )
    return {
        "session_et": day.isoformat(),
        "provider_updated_at_utc": stamp.isoformat(),
        "observed_bid_per_share": str(bid) if bid is not None else None,
        "observed_ask_per_share": str(ask) if ask is not None else None,
        "two_sided_source": valid,
        "reported_positive_volume": row["positive_volume"],
        "provider_update_not_proven_publication_or_1600_et_mark": True,
    }


def build_observed_option_timeline(
    selection: dict[str, Any], plan: dict[str, Any], handoff: dict[str, Any],
    *,
    read_verified_observations: Callable[[dict[str, Any], dict[str, Any]], list[dict[str, Any]]],
    expected_original_cases: int = 14902,
) -> dict[str, Any]:
    for value, field in (
        (selection, "selection_fingerprint"), (plan, "plan_fingerprint"),
        (handoff, "handoff_fingerprint"),
    ):
        if not isinstance(value, dict):
            raise ObservedOptionTimelineError("frozen input must be an object")
        _check_signature(value, field)
    source_rows = handoff.get("rows")
    requests = plan.get("requests")
    memberships = plan.get("memberships")
    candidates = selection.get("cases")
    if (
        handoff.get("contract") != HANDOFF_CONTRACT
        or handoff.get("status") != "OFFLINE_SOURCE_REUSE_HANDOFF_NO_TRADE_AUTHORITY"
        or handoff.get("selection_fingerprint") != selection["selection_fingerprint"]
        or handoff.get("quote_plan_fingerprint") != plan["plan_fingerprint"]
        or handoff.get("original_case_denominator") != expected_original_cases
        or handoff.get("original_right_memberships") != expected_original_cases * 2
        or selection.get("original_case_denominator") != expected_original_cases
        or selection.get("right_policy") != "both"
        or not isinstance(source_rows, list) or len(source_rows) != expected_original_cases * 2
        or not isinstance(requests, list)
        or handoff.get("unique_quote_queries") != len(requests)
        or not isinstance(memberships, list)
        or not isinstance(candidates, list)
        or len(memberships) != len(candidates)
        or handoff.get("selected_case_right_memberships") != len(candidates)
        or handoff.get("provider_requests") != 0
        or handoff.get("portfolio_pnl_authority") is not False
        or handoff.get("protected_2026_outcomes_read") != 0
    ):
        raise ObservedOptionTimelineError("original full-denominator source lineage changed")
    req = {x["request_identity"]: x for x in requests}
    chosen = {x["case_id"]: x for x in candidates}
    member = {x["case_id"]: x for x in memberships}
    if (
        len(req) != len(requests)
        or len(chosen) != len(candidates)
        or len(member) != len(memberships)
        or set(member) != set(chosen)
    ):
        raise ObservedOptionTimelineError(
            "duplicate exact query/selected identity or plan membership"
        )
    source_by_request: dict[str, tuple[str, str, str]] = {}
    observed: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    counts: Counter[str] = Counter()
    years: dict[str, Counter[str]] = defaultdict(Counter)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for slot in source_rows:
        slot_id = slot["case_right_id"]
        year = slot["year"]
        state = slot["quote_history_status"]
        if (
            slot_id in seen or year not in {"2021", "2022", "2023", "2024", "2025"}
            or state not in VERIFIED | ABSENT
        ):
            raise ObservedOptionTimelineError("duplicate slot or unexpected source state")
        seen.add(slot_id)
        picked = chosen.get(slot_id)
        source_id = slot.get("quote_request_identity")
        result: dict[str, Any] = {
            "case_right_id": slot_id, "original_case_id": slot["original_case_id"],
            "year": year, "right": slot["right"],
            "source_selection_status": slot["source_selection_status"],
            "option_symbol": slot["option_symbol"],
            "quote_request_identity": source_id,
            "original_quote_history_status": state,
            "timeline_status": state,
            "later_two_sided_session_count": 0,
            "first_later_observed_quote": None,
            "next_later_observed_quote": None,
            "historical_option_deliverable_verified": False,
            "actual_execution_or_portfolio_pnl_authority": False,
        }
        if state in VERIFIED:
            if picked is None or source_id not in req:
                raise ObservedOptionTimelineError("verified quote has no selected OCC/query")
            request = req[source_id]
            if (
                request["option_symbol"] != slot["option_symbol"]
                or slot_id not in request["member_case_ids"]
                or picked["original_case_id"] != slot["original_case_id"]
                or picked["option_symbol"] != slot["option_symbol"]
                or picked["right"] != slot["right"]
                or picked["source_selection_status"] != slot["source_selection_status"]
            ):
                raise ObservedOptionTimelineError("source selection or quote identity changed")
            source_from = slot.get("quote_source_from_inclusive") or request["from_inclusive"]
            source_to = slot.get("quote_source_to_exclusive") or request["to_exclusive"]
            source_identity = slot["quote_source_request_identity"]
            if state == "VERIFIED_CLIPPED_DEMAND_CACHE_QUOTE_HISTORY":
                if (
                    slot.get("quote_source_is_clipped_recovery") is not True
                    or not isinstance(source_identity, str) or not source_identity
                    or not (
                        date.fromisoformat(request["from_inclusive"])
                        < date.fromisoformat(source_from)
                        < date.fromisoformat(source_to)
                        <= date.fromisoformat(request["to_exclusive"])
                    )
                    or slot.get("original_quote_window_fully_reconstructed") is not False
                ):
                    raise ObservedOptionTimelineError("clipped recovery window or authority changed")
            elif (
                source_from != request["from_inclusive"]
                or source_to != request["to_exclusive"]
                or slot.get("quote_source_is_clipped_recovery") is True
            ):
                raise ObservedOptionTimelineError("non-recovery quote source window changed")
            signature = (
                state, source_identity, slot["quote_body_sha256"]
            )
            if source_id in source_by_request and source_by_request[source_id] != signature:
                raise ObservedOptionTimelineError("shared quote points to different original bytes")
            source_by_request[source_id] = signature
            observed_key = (
                state, source_identity, source_from, source_to
            )
            if observed_key not in observed:
                original = read_verified_observations(request, slot)
                if not isinstance(original, list) or len(original) != slot["observed_quote_rows"]:
                    raise ObservedOptionTimelineError("raw quote observations differ from receipt")
                # The receipt protects the complete original source (including
                # any prior-year dates); validate every row, not merely the
                # subset exposed by the narrower immutable demand request.
                normalized = [_observation(o) for o in original]
                sessions = [x["session_et"] for x in normalized]
                if len(set(sessions)) != len(sessions):
                    raise ObservedOptionTimelineError("duplicate historical option session")
                first = date.fromisoformat(source_from)
                end = date.fromisoformat(source_to)
                if first >= end:
                    raise ObservedOptionTimelineError("frozen quote window invalid")
                observed[observed_key] = [
                    x for x in sorted(normalized, key=lambda x: x["session_et"])
                    if first <= date.fromisoformat(x["session_et"]) < end
                ]
            signal = _utc(picked["decision_at_utc"]).astimezone(EASTERN).date()
            expiry = date.fromisoformat(picked["expiration"])
            later = [
                o for o in observed[observed_key]
                if signal < date.fromisoformat(o["session_et"]) <= expiry
                and o["two_sided_source"]
            ]
            result["later_two_sided_session_count"] = len(later)
            if later:
                result["first_later_observed_quote"] = later[0]
                result["timeline_status"] = (
                    "TWO_OR_MORE_LATER_TWO_SIDED_SOURCE_DATES" if len(later) > 1
                    else "FIRST_LATER_TWO_SIDED_SOURCE_ONLY"
                )
                if len(later) > 1:
                    result["next_later_observed_quote"] = later[1]
            else:
                result["timeline_status"] = "NO_LATER_TWO_SIDED_SOURCE_DATE"
        elif state == "NO_PIT_SELECTED_CONTRACT":
            if picked is not None or source_id is not None or slot["option_symbol"] is not None:
                raise ObservedOptionTimelineError("unselected slot acquired quote authority")
        else:
            if state in {
                "QUOTE_HISTORY_OUTSIDE_CURRENT_PROVIDER_WINDOW",
                "QUOTE_HISTORY_AFTER_LAST_COMPLETED_SESSION",
                "QUOTE_HISTORY_NO_CLOSED_SOURCE_PERIOD",
            }:
                if (
                    picked is None
                    or source_id is not None
                    or picked["option_symbol"] != slot["option_symbol"]
                ):
                    raise ObservedOptionTimelineError(
                        "ineligible selected contract gained or changed quote request"
                    )
            elif (
                picked is None
                or source_id not in req
                or picked["option_symbol"] != slot["option_symbol"]
            ):
                raise ObservedOptionTimelineError("missing quote changed original selected OCC")
        counts[result["timeline_status"]] += 1
        years[year][result["timeline_status"]] += 1
        rows.append(result)
    if (
        len(seen) != expected_original_cases * 2
        or {x["case_right_id"] for x in rows if x["quote_request_identity"]} != {
            m["case_id"] for m in memberships
            if m.get("request_identity") is not None
        }
        or len(source_by_request) != (
            handoff["reused_original_2022_queries"]
            + handoff["verified_demand_cache_queries"]
            + handoff.get("recovered_original_quote_queries", 0)
        )
        or sum(counts.values()) != expected_original_cases * 2
    ):
        raise ObservedOptionTimelineError("unique source or full-case accounting changed")
    result = {
        "contract": CONTRACT,
        "status": "OFFLINE_OBSERVED_QUOTE_SOURCE_TIMELINES_ONLY",
        "selection_fingerprint": selection["selection_fingerprint"],
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "source_handoff_fingerprint": handoff["handoff_fingerprint"],
        "original_case_denominator": expected_original_cases,
        "original_right_memberships": expected_original_cases * 2,
        "selected_case_right_memberships": len(candidates),
        "unique_verified_physical_histories_decoded": len(observed),
        "by_status": dict(sorted(counts.items())),
        "by_year": {y: dict(sorted(x.items())) for y, x in sorted(years.items())},
        "rows": sorted(rows, key=lambda x: x["case_right_id"]),
        "provider_requests": 0, "historical_intraday_0935_quote_proof": False,
        "stock_option_same_clock_pair_count": 0, "option_fills_verified": 0,
        "account_pnl_authority": False, "protected_2026_outcomes_read": 0,
    }
    result["timeline_fingerprint"] = _fingerprint(result)
    return result


def local_verified_quote_body_reader(settings: AtlasSettings, plan: dict[str, Any]) -> Callable:
    """Recheck an accepted physical quote receipt/body and return its exact bytes.

    This is the common offline provenance gate for derived decoders. It never
    contacts a provider and does not reinterpret source rows as fills.
    """
    needs_2022 = any(
        row["from_inclusive"].startswith("2022-") for row in plan["requests"]
    )
    original_2022 = OfflineOptionHistoryStore(settings) if needs_2022 else None

    def reader(
        request: dict[str, Any], slot: dict[str, Any],
    ) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
        if slot["quote_history_status"] == "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY":
            if original_2022 is None:
                raise ObservedOptionTimelineError("accepted original 2022 index unavailable")
            old = original_2022._tickets.get(request["option_symbol"])
            if (
                old is None
                or old["request_identity"] != slot["quote_source_request_identity"]
                or old["from_inclusive"] > request["from_inclusive"]
                or old["to_exclusive"] < request["to_exclusive"]
            ):
                raise ObservedOptionTimelineError("frozen original 2022 covering source changed")
            receipt = old_2022_receipt(settings, old)
            if receipt is None or receipt["status"] != "COMPLETE_SOURCE_ONLY":
                raise ObservedOptionTimelineError("accepted 2022 quote receipt unavailable")
            source_ticket, raw_path = old, old_2022_paths(settings, old)[0]
        elif slot["quote_history_status"] in (
            "VERIFIED_DEMAND_CACHE_QUOTE_HISTORY",
            "VERIFIED_CLIPPED_DEMAND_CACHE_QUOTE_HISTORY",
        ):
            if slot["quote_history_status"] == "VERIFIED_CLIPPED_DEMAND_CACHE_QUOTE_HISTORY":
                source_ticket = {
                    "option_symbol": request["option_symbol"],
                    "from_inclusive": slot["quote_source_from_inclusive"],
                    "to_exclusive": slot["quote_source_to_exclusive"],
                    "request_identity": slot["quote_source_request_identity"],
                }
                if (
                    slot.get("quote_source_is_clipped_recovery") is not True
                    or source_ticket["request_identity"] == request["request_identity"]
                ):
                    raise ObservedOptionTimelineError("clipped recovery source identity changed")
            else:
                source_ticket = request
                if slot["quote_source_request_identity"] != request["request_identity"]:
                    raise ObservedOptionTimelineError("demand source request changed")
            receipt = demand_receipt(settings, source_ticket)
            if receipt is None or receipt["status"] != "COMPLETE_SOURCE_ONLY":
                raise ObservedOptionTimelineError("accepted exact demand quote unavailable")
            raw_path = demand_paths(settings, source_ticket)[0]
        else:
            raise ObservedOptionTimelineError("missing source cannot supply raw observations")
        if raw_path.is_symlink() or not raw_path.is_file():
            raise ObservedOptionTimelineError("missing or linked accepted quote body")
        raw = raw_path.read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != slot["quote_body_sha256"]
            or receipt["body_sha256"] != slot["quote_body_sha256"]
            or receipt["safe_summary"]["observed_rows"] != slot["observed_quote_rows"]
        ):
            raise ObservedOptionTimelineError("source receipt/body SHA or row count differs")
        return source_ticket, raw, receipt

    return reader


def local_verified_quote_reader(settings: AtlasSettings, plan: dict[str, Any]) -> Callable:
    """Recheck original receipt/body before decoding each selected unique series."""
    body_reader = local_verified_quote_body_reader(settings, plan)

    def reader(request: dict[str, Any], slot: dict[str, Any]) -> list[dict[str, Any]]:
        source_ticket, raw, _ = body_reader(request, slot)
        return _original_observations(raw, source_ticket, slot["observed_quote_rows"])

    return reader


def persist_observed_option_timeline(settings: AtlasSettings, report: dict[str, Any]) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "timeline_fingerprint")
    path = settings.resolved_path(
        f"{OUTPUT_REL}_{report['timeline_fingerprint'][:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != report:
            raise ObservedOptionTimelineError("immutable prior observed timeline differs")
        return path, "REUSED_IDENTICAL_OBSERVED_TIMELINE"
    _write_new(path, report)
    return path, "WRITTEN_IMMUTABLE_OBSERVED_TIMELINE"
