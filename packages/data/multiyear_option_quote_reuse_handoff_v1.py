from __future__ import annotations

"""Immutable source-to-account-replay handoff; no quote inference or paid GET."""

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import (
    CONTRACT as QUOTE_CONTRACT, _write_new,
)

CONTRACT = "atlas-multiyear-option-quote-reuse-handoff-v1"
OUTPUT_REL = "data/options/manifests/multiyear_option_quote_reuse_handoff_v1"
AVAILABLE = {
    "REUSED_ACCEPTED_2022_FULL_SERIES": "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY",
    "COMPLETE_SOURCE_ONLY": "VERIFIED_DEMAND_CACHE_QUOTE_HISTORY",
    "EXACT_QUERY_SOURCE_GAP": "EXACT_QUOTE_QUERY_NO_DATA",
}
RECOVERY_COMPLETE = "VERIFIED_CLIPPED_DEMAND_CACHE_QUOTE_HISTORY"
RECOVERY_GAP = "CLIPPED_RECOVERY_QUERY_NO_DATA"
INELIGIBLE_DISPOSITIONS = {
    "ORIGINAL_DECISION_OUTSIDE_STARTER_FIVE_YEAR_WINDOW":
        "QUOTE_HISTORY_OUTSIDE_CURRENT_PROVIDER_WINDOW",
    "ORIGINAL_DECISION_AFTER_LAST_COMPLETED_SESSION":
        "QUOTE_HISTORY_AFTER_LAST_COMPLETED_SESSION",
    "NO_CLOSED_SOURCE_PERIOD":
        "QUOTE_HISTORY_NO_CLOSED_SOURCE_PERIOD",
}


class QuoteReuseHandoffError(ValueError):
    pass


def _check_signature(value: dict[str, Any], key: str) -> None:
    unsigned = dict(value)
    signature = unsigned.pop(key, None)
    if signature != _fingerprint(unsigned):
        raise QuoteReuseHandoffError(f"{key} source fingerprint mismatch")


def assemble_quote_reuse_handoff(
    selection: dict[str, Any],
    plan: dict[str, Any],
    census: dict[str, Any],
    *,
    recovery_overlay: dict[str, Any] | None = None,
    expected_original_cases: int = 14902,
) -> dict[str, Any]:
    """Join every frozen case/right to an audited quote pointer or explicit gap.

    The caller must obtain the census from run_demand_cache in preview mode:
    it verifies each accepted 2022 receipt and each exact cache body before
    reporting a source. This function never constructs prices, trades or fills.
    """
    for value, key in (
        (selection, "selection_fingerprint"),
        (plan, "plan_fingerprint"),
        (census, "report_fingerprint"),
    ):
        if not isinstance(value, dict):
            raise QuoteReuseHandoffError("signed input must be an object")
        _check_signature(value, key)
    coverage = selection.get("coverage")
    selected = selection.get("cases")
    memberships = plan.get("memberships")
    requests = plan.get("requests")
    entries = census.get("source_entries")
    if (
        selection.get("original_case_denominator") != expected_original_cases
        or selection.get("right_policy") != "both"
        or selection.get("original_right_memberships") != expected_original_cases * 2
        or selection.get("selected_case_right_memberships") != len(selected or [])
        or not isinstance(coverage, list)
        or len(coverage) != expected_original_cases * 2
        or not isinstance(selected, list)
        or not isinstance(memberships, list)
        or not isinstance(requests, list)
        or not isinstance(entries, list)
        or plan.get("contract") != QUOTE_CONTRACT
        or plan.get("requested_case_denominator") != len(selected)
        or plan.get("unique_physical_quote_queries") != len(requests)
        or len(memberships) != len(selected)
        or census.get("plan_fingerprint") != plan.get("plan_fingerprint")
        or census.get("original_requested_case_denominator") != len(selected)
        or census.get("unique_physical_quote_queries") != len(requests)
        or census.get("new_provider_attempts") != 0
        or census.get("observed_credits") != 0
        or census.get("status") not in (
            "PREVIEW_ONLY_NO_PROVIDER_GETS", "ALL_ELIGIBLE_SOURCE_QUERIES_ACCOUNTED"
        )
    ):
        raise QuoteReuseHandoffError("frozen population, provenance or zero-GET census mismatch")
    by_selected = {x["case_id"]: x for x in selected}
    by_member = {x["case_id"]: x for x in memberships}
    by_request = {x["request_identity"]: x for x in requests}
    by_entry = {x["request_identity"]: x for x in entries}
    recovery_by_original: dict[str, dict[str, Any]] = {}
    recovery_overlay_fp = None
    recovery_complete_queries = recovery_gap_queries = 0
    recovered_original_queries = 0
    if recovery_overlay is not None:
        from packages.data.multiyear_quote_tail_recovery_v1 import (
            OVERLAY_CONTRACT,
        )
        try:
            _check_signature(recovery_overlay, "overlay_fingerprint")
        except (QuoteReuseHandoffError, ValueError) as exc:
            raise QuoteReuseHandoffError("recovery overlay fingerprint mismatch") from exc
        overlay_rows = recovery_overlay.get("rows")
        if (
            recovery_overlay.get("contract") != OVERLAY_CONTRACT
            or recovery_overlay.get("original_plan_fingerprint") != plan["plan_fingerprint"]
            or recovery_overlay.get("provider_requests") != 0
            or recovery_overlay.get("historical_fill_or_pnl_authority") is not False
            or recovery_overlay.get("original_window_fully_reconstructed") is not False
            or not isinstance(overlay_rows, list)
        ):
            raise QuoteReuseHandoffError("recovery overlay lineage or authority changed")
        recovery_by_original = {
            x["original_request_identity"]: x for x in overlay_rows
        }
        if len(recovery_by_original) != len(overlay_rows):
            raise QuoteReuseHandoffError("duplicate original recovery request")
        if not set(recovery_by_original).issubset(by_request):
            raise QuoteReuseHandoffError("recovery overlay references unknown original request")
        if set(recovery_by_original) & set(by_entry):
            raise QuoteReuseHandoffError(
                "recovery overlay may only augment still-missing original requests"
            )
        recovery_overlay_fp = recovery_overlay["overlay_fingerprint"]
        recovery_complete_queries = recovery_overlay.get("complete_recovery_queries", 0)
        recovery_gap_queries = recovery_overlay.get("recovery_query_gaps", 0)
        recovered_original_queries = sum(
            row.get("status") == RECOVERY_COMPLETE
            for row in overlay_rows
        )
    if (
        len(by_selected) != len(selected)
        or len(by_member) != len(memberships)
        or len(by_request) != len(requests)
        or len(by_entry) != len(entries)
        or set(by_selected) != set(by_member)
        or not set(by_entry).issubset(by_request)
        or len(entries) + census.get("pending", -1) != len(requests)
        or census.get("reused_original_2022") != sum(
            x["status"] == "REUSED_ACCEPTED_2022_FULL_SERIES" for x in entries
        )
        or census.get("new_cache_complete") != sum(
            x["status"] == "COMPLETE_SOURCE_ONLY" for x in entries
        )
        or census.get("exact_source_gaps") != sum(
            x["status"] == "EXACT_QUERY_SOURCE_GAP" for x in entries
        )
        or any(x["status"] not in AVAILABLE for x in entries)
    ):
        raise QuoteReuseHandoffError("quote request / census partition changed")
    for m in memberships:
        chosen = by_selected[m["case_id"]]
        if (
            chosen.get("option_symbol") != m.get("option_symbol")
            or chosen.get("ticker") != m.get("ticker")
            or chosen.get("original_case_id") is None
            or chosen.get("right") not in ("call", "put")
        ):
            raise QuoteReuseHandoffError("PIT OCC selected identity/membership differs")
        disposition = m.get("disposition")
        if disposition == "SOURCE_DEMAND_READY":
            if m.get("request_identity") not in by_request:
                raise QuoteReuseHandoffError("selected case has no exact quote request")
            req = by_request[m["request_identity"]]
            if (
                m.get("option_symbol") != req["option_symbol"]
                or m["case_id"] not in req["member_case_ids"]
            ):
                raise QuoteReuseHandoffError("case-to-request membership changed")
        elif disposition in INELIGIBLE_DISPOSITIONS:
            if m.get("request_identity") is not None:
                raise QuoteReuseHandoffError(
                    "ineligible selected case unexpectedly gained exact request"
                )
        else:
            raise QuoteReuseHandoffError("unknown selected quote-demand disposition")

    by_status: Counter[str] = Counter()
    by_year: dict[str, Counter[str]] = defaultdict(Counter)
    rows: list[dict[str, Any]] = []
    seen_original: set[str] = set()
    seen_slot: set[str] = set()
    for item in coverage:
        original_id = item["case_id"]
        right = item["right"]
        year = item["signal_year"]
        slot_id = original_id + (":C" if right == "call" else ":P")
        if (
            right not in ("call", "put") or slot_id in seen_slot
            or not isinstance(year, str) or year not in (
                "2021", "2022", "2023", "2024", "2025"
            )
        ):
            raise QuoteReuseHandoffError("original case/right coverage changed")
        seen_slot.add(slot_id)
        seen_original.add(original_id)
        chosen = by_selected.get(slot_id)
        recovered = None
        if chosen is None:
            if item.get("option_symbol") is not None or item.get("status", "").startswith("SELECTED_"):
                raise QuoteReuseHandoffError("selected source missing from quote demand")
            status = "NO_PIT_SELECTED_CONTRACT"
            entry = None
            membership = None
        else:
            membership = by_member[slot_id]
            if (chosen["original_case_id"] != original_id
                or chosen["right"] != right
                or chosen["option_symbol"] != item.get("option_symbol")
                or chosen["source_selection_status"] != item.get("status")):
                raise QuoteReuseHandoffError("original source/selected case mismatch")
            disposition = membership["disposition"]
            if disposition != "SOURCE_DEMAND_READY":
                entry = None
                recovered = None
                status = INELIGIBLE_DISPOSITIONS[disposition]
            else:
                entry = by_entry.get(membership["request_identity"])
                recovered = None if entry is not None else recovery_by_original.get(
                    membership["request_identity"]
                )
                if entry is not None:
                    status = AVAILABLE[entry["status"]]
                elif recovered is not None:
                    if recovered["option_symbol"] != chosen["option_symbol"]:
                        raise QuoteReuseHandoffError("recovery source option identity changed")
                    if recovered["status"] not in (
                        RECOVERY_COMPLETE, RECOVERY_GAP, "TAIL_RECOVERY_NOT_ACQUIRED"
                    ):
                        raise QuoteReuseHandoffError("unknown clipped recovery source status")
                    status = (
                        recovered["status"]
                        if recovered["status"] != "TAIL_RECOVERY_NOT_ACQUIRED"
                        else "QUOTE_HISTORY_NOT_ACQUIRED"
                    )
                else:
                    status = "QUOTE_HISTORY_NOT_ACQUIRED"
        by_status[status] += 1
        by_year[year][status] += 1
        rows.append({
            "original_case_id": original_id,
            "case_right_id": slot_id,
            "year": year,
            "right": right,
            "source_selection_status": item["status"],
            "quote_history_status": status,
            "option_symbol": item.get("option_symbol"),
            "quote_request_identity": (
                membership.get("request_identity") if membership else None
            ),
            "quote_body_sha256": (
                entry.get("body_sha256") if entry else
                recovered.get("quote_body_sha256") if recovered and status == RECOVERY_COMPLETE
                else None
            ),
            "quote_source_request_identity": (
                entry.get("source_request_identity", membership["request_identity"])
                if entry and membership else
                recovered.get("recovery_request_identity")
                if recovered and status == RECOVERY_COMPLETE else None
            ),
            "quote_source_from_inclusive": (
                by_request[membership["request_identity"]]["from_inclusive"]
                if entry and membership else
                recovered.get("source_from_inclusive")
                if recovered and status == RECOVERY_COMPLETE else None
            ),
            "quote_source_to_exclusive": (
                by_request[membership["request_identity"]]["to_exclusive"]
                if entry and membership else
                recovered.get("source_to_exclusive")
                if recovered and status == RECOVERY_COMPLETE else None
            ),
            "quote_source_is_clipped_recovery": bool(
                recovered is not None and status == RECOVERY_COMPLETE
            ),
            "original_quote_window_fully_reconstructed": bool(
                entry is not None and status in (
                    "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY",
                    "VERIFIED_DEMAND_CACHE_QUOTE_HISTORY",
                    "EXACT_QUOTE_QUERY_NO_DATA",
                )
            ),
            "observed_quote_rows": (
                entry.get("cached_observed_rows") if entry else
                recovered.get("observed_quote_rows") if recovered and status == RECOVERY_COMPLETE
                else None
            ),
        })
    expected_reused = sum(
        len(by_request[e["request_identity"]]["member_case_ids"])
        for e in entries if e["status"] in (
            "REUSED_ACCEPTED_2022_FULL_SERIES", "COMPLETE_SOURCE_ONLY"
        )
    )
    expected_reused += sum(
        len(by_request[oid]["member_case_ids"])
        for oid, recovered in recovery_by_original.items()
        if recovered.get("status") == RECOVERY_COMPLETE
    )
    if (
        len(seen_original) != expected_original_cases
        or len(seen_slot) != expected_original_cases * 2
        or sum(by_status[k] for k in (
            "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY",
            "VERIFIED_DEMAND_CACHE_QUOTE_HISTORY",
            RECOVERY_COMPLETE,
        )) != expected_reused
    ):
        raise QuoteReuseHandoffError("full-case or reused-membership accounting mismatch")
    report = {
        "contract": CONTRACT,
        "status": "OFFLINE_SOURCE_REUSE_HANDOFF_NO_TRADE_AUTHORITY",
        "selection_fingerprint": selection["selection_fingerprint"],
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "source_census_fingerprint": census["report_fingerprint"],
        "original_case_denominator": expected_original_cases,
        "original_right_memberships": expected_original_cases * 2,
        "selected_case_right_memberships": len(selected),
        "unique_quote_queries": len(requests),
        "reused_original_2022_queries": census["reused_original_2022"],
        "verified_demand_cache_queries": census["new_cache_complete"],
        "recovery_overlay_fingerprint": recovery_overlay_fp,
        "verified_clipped_recovery_queries": recovery_complete_queries,
        "clipped_recovery_gap_queries": recovery_gap_queries,
        "recovered_original_quote_queries": recovered_original_queries,
        "ineligible_selected_case_right_memberships": sum(
            m.get("disposition") != "SOURCE_DEMAND_READY" for m in memberships
        ),
        "pending_unique_quote_queries": (
            census["pending"] - len(recovery_by_original)
            + sum(x.get("status") == "TAIL_RECOVERY_NOT_ACQUIRED"
                  for x in recovery_by_original.values())
            + sum(x.get("status") == RECOVERY_GAP
                  for x in recovery_by_original.values())
        ),
        "by_status": dict(sorted(by_status.items())),
        "by_year": {y: dict(sorted(c.items())) for y, c in sorted(by_year.items())},
        "rows": sorted(rows, key=lambda x: x["case_right_id"]),
        "provider_requests": 0,
        "option_fills_verified": 0,
        "portfolio_pnl_authority": False,
        "protected_2026_outcomes_read": 0,
    }
    report["handoff_fingerprint"] = _fingerprint(report)
    return report


def persist_quote_reuse_handoff(
    settings: AtlasSettings, report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "handoff_fingerprint")
    path = settings.resolved_path(
        f"{OUTPUT_REL}_{report['handoff_fingerprint'][:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != report:
            raise QuoteReuseHandoffError("immutable prior reuse handoff changed")
        return path, "REUSED_IDENTICAL_SOURCE_REUSE_HANDOFF"
    _write_new(path, report)
    return path, "WRITTEN_IMMUTABLE_SOURCE_REUSE_HANDOFF"
