from __future__ import annotations

"""Source-only full-cohort join of verified original option and native daily data.

This is not a trade construction: a vendor quote update timestamp does not
establish a publication time or the stock daily-close observation clock.
"""

import math
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import _write_new
from packages.data.multiyear_native_eod_close_source_v1 import CONTRACT as CLOSE_CONTRACT
from packages.data.multiyear_observed_option_quote_timeline_v1 import CONTRACT as TIMELINE_CONTRACT
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    CONTRACT as HANDOFF_CONTRACT, _check_signature,
)
from packages.data.multiyear_option_stock_eod_preflight_v1 import CONTRACT as NEEDS_CONTRACT

CONTRACT = "atlas-multiyear-verified-stock-option-source-casebook-v1"
OUTPUT_REL = "data/options/derived/multiyear_verified_stock_option_source_casebook_v1"
NO_PAIR = "NO_TWO_LATER_TWO_SIDED_OPTION_SOURCE_DATES"
STOCK_GAP = "ONE_OR_MORE_EXACT_NATIVE_DAILY_CLOSE_GAPS"
SOURCE_PAIR = "PAIRED_DATED_SOURCE_ONLY_UNSYNCHRONIZED"


class SourceCasebookError(ValueError):
    pass


def _unique_rows(document: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    records = document.get("rows")
    if not isinstance(records, list):
        raise SourceCasebookError("source rows are not an array")
    indexed = {row[key]: row for row in records}
    if len(indexed) != len(records) or any(not isinstance(k, str) or not k for k in indexed):
        raise SourceCasebookError("duplicate or invalid source row identity")
    return indexed


def _verified_price(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SourceCasebookError(f"{label} is not a source price string")
    try:
        amount = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SourceCasebookError(f"{label} cannot be represented") from exc
    if not math.isfinite(amount) or amount <= 0:
        raise SourceCasebookError(f"{label} must be positive and finite")
    return value


def _source_quote(observation: dict[str, Any] | None) -> dict[str, Any] | None:
    if observation is None:
        return None
    if not isinstance(observation, dict) or observation.get("two_sided_source") is not True:
        raise SourceCasebookError("source quote is not two-sided")
    session = date.fromisoformat(observation["session_et"])
    stamp = datetime.fromisoformat(observation["provider_updated_at_utc"])
    if stamp.tzinfo is None:
        raise SourceCasebookError("source option update timestamp is naive")
    bid = _verified_price(observation["observed_bid_per_share"], "source bid")
    ask = _verified_price(observation["observed_ask_per_share"], "source ask")
    if float(ask) < float(bid):
        raise SourceCasebookError("crossed quote cannot enter source casebook")
    if observation.get("provider_update_not_proven_publication_or_1600_et_mark") is not True:
        raise SourceCasebookError("option timestamp uncertainty was removed")
    return {
        "session_et": session.isoformat(),
        "provider_updated_at_utc": stamp.isoformat(),
        "observed_bid_per_share": bid,
        "observed_ask_per_share": ask,
        "two_sided_source": True,
        "publication_and_stock_close_clock_unproven": True,
    }


def _native_close(
    identity: str | None, query_by_id: dict[str, dict[str, Any]],
    native_by_id: dict[str, dict[str, Any]], expected_ticker: str,
    expected_instrument: str, option_quote: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if identity is None:
        if option_quote is not None:
            raise SourceCasebookError("observed quote has no frozen native close query")
        return None
    if option_quote is None or identity not in query_by_id or identity not in native_by_id:
        raise SourceCasebookError("native source lacks a frozen observation/query identity")
    query, close = query_by_id[identity], native_by_id[identity]
    if (
        query["instrument_id"] != expected_instrument
        or query["ticker"] != expected_ticker
        or query["session_et"] != option_quote["session_et"]
        or close["instrument_id"] != query["instrument_id"]
        or close["ticker"] != query["ticker"]
        or close["session_et"] != query["session_et"]
        or close["request_identity"] != identity
        or close.get("option_clock_match_proven") is not False
        or close.get("historical_fill_proven") is not False
    ):
        raise SourceCasebookError("native-close identity, date or clock authority changed")
    state = close["status"]
    if state not in {"VERIFIED_NATIVE_RAW_EOD_CLOSE", "NO_RAW_NATIVE_DAILY_BAR_FOR_EXACT_SESSION"}:
        raise SourceCasebookError("unknown native raw daily close status")
    raw = close.get("raw_as_traded_close")
    if state == "VERIFIED_NATIVE_RAW_EOD_CLOSE":
        _verified_price(close.get("raw_as_traded_open"), "native raw open")
        _verified_price(raw, "native raw close")
        digest = close.get("native_canonical_sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(
            c not in "0123456789abcdef" for c in digest
        ):
            raise SourceCasebookError("verified native canonical source SHA missing")
        if not close.get("native_unit_id"):
            raise SourceCasebookError("verified native unit identity missing")
    elif raw is not None or close.get("raw_as_traded_open") is not None:
        raise SourceCasebookError("missing native source contains a claimed price")
    return {
        "request_identity": identity,
        "session_et": query["session_et"],
        "status": state,
        "raw_as_traded_close": raw if state == "VERIFIED_NATIVE_RAW_EOD_CLOSE" else None,
        "native_unit_id": close.get("native_unit_id"),
        "native_canonical_sha256": close.get("native_canonical_sha256"),
        "actual_close_observation_timestamp_unavailable": True,
    }


def build_verified_source_casebook(
    handoff: dict[str, Any], timeline: dict[str, Any],
    needs: dict[str, Any], closes: dict[str, Any],
    *, expected_original_cases: int = 14902,
) -> dict[str, Any]:
    """Join immutable source reports with complete 2-right denominator; never price P&L."""
    for document, field in (
        (handoff, "handoff_fingerprint"),
        (timeline, "timeline_fingerprint"),
        (needs, "demand_fingerprint"),
        (closes, "source_fingerprint"),
    ):
        if not isinstance(document, dict):
            raise SourceCasebookError("signed source is not an object")
        _check_signature(document, field)
    right_count = expected_original_cases * 2
    if (
        handoff.get("contract") != HANDOFF_CONTRACT
        or timeline.get("contract") != TIMELINE_CONTRACT
        or needs.get("contract") != NEEDS_CONTRACT
        or closes.get("contract") != CLOSE_CONTRACT
        or timeline.get("source_handoff_fingerprint") != handoff["handoff_fingerprint"]
        or needs.get("accepted_option_timeline_fingerprint") != timeline["timeline_fingerprint"]
        or closes.get("original_stock_close_demand_fingerprint") != needs["demand_fingerprint"]
        or closes.get("original_native_fingerprint") != needs.get("accepted_native_fingerprint")
        or handoff.get("original_case_denominator") != expected_original_cases
        or timeline.get("original_case_denominator") != expected_original_cases
        or needs.get("original_case_denominator") != expected_original_cases
        or any(doc.get("original_right_memberships") != right_count
               for doc in (handoff, timeline, needs))
        or closes.get("unique_requested_native_closes") != len(needs.get("requests", []))
        or any(doc.get("provider_requests") != 0 for doc in (handoff, timeline, needs, closes))
        or any(doc.get("protected_2026_outcomes_read") != 0 for doc in (handoff, timeline, needs, closes))
        or handoff.get("portfolio_pnl_authority") is not False
        or timeline.get("account_pnl_authority") is not False
        or needs.get("portfolio_pnl_authority") is not False
        or closes.get("option_fill_or_portfolio_pnl_authority") is not False
        or closes.get("provider_option_update_is_not_verified_stock_close_clock") is not True
    ):
        raise SourceCasebookError("full-population lineage or source-only authority changed")
    historical = _unique_rows(handoff, "case_right_id")
    observations = _unique_rows(timeline, "case_right_id")
    demand = _unique_rows(needs, "case_right_id")
    native = _unique_rows(closes, "request_identity")
    query_list = needs["requests"]
    query_by_id = {x["request_identity"]: x for x in query_list}
    if (
        len(historical) != right_count or set(historical) != set(observations) or set(historical) != set(demand)
        or len(native) != len(query_list) or len(query_by_id) != len(query_list)
        or set(native) != set(query_by_id)
    ):
        raise SourceCasebookError("case/right or exact native query partition changed")
    rows = []
    by_year: dict[str, Counter[str]] = defaultdict(Counter)
    unique_originals = set()
    for key in sorted(historical):
        original, quote, need = historical[key], observations[key], demand[key]
        year = original["year"]
        if (
            year not in {"2021", "2022", "2023", "2024", "2025"}
            or quote["year"] != year or need["year"] != year
            or quote["original_case_id"] != original["original_case_id"]
            or need["original_case_id"] != original["original_case_id"]
            or quote["right"] != original["right"]
            or quote["option_symbol"] != original["option_symbol"]
            or need["option_symbol"] != original["option_symbol"]
            or quote["quote_request_identity"] != original["quote_request_identity"]
            or quote["original_quote_history_status"] != original["quote_history_status"]
            or quote.get("actual_execution_or_portfolio_pnl_authority") is not False
            or need.get("native_close_verified") is not False
            or need.get("matched_option_stock_clock_verified") is not False
            or need.get("hypothetical_fill_or_option_pnl_authority") is not False
        ):
            raise SourceCasebookError("original selected contract or authority changed")
        unique_originals.add(original["original_case_id"])
        entry = _source_quote(quote["first_later_observed_quote"])
        later = _source_quote(quote["next_later_observed_quote"])
        stock_entry = _native_close(
            need["native_entry_close_request_identity"], query_by_id, native,
            need["ticker"], need["instrument_id"], entry,
        )
        stock_later = _native_close(
            need["native_next_close_request_identity"], query_by_id, native,
            need["ticker"], need["instrument_id"], later,
        )
        if later is not None and (entry is None or later["session_et"] <= entry["session_et"]):
            raise SourceCasebookError("option observation chronology changed")
        if entry and later and stock_entry and stock_later:
            status = SOURCE_PAIR if (
                stock_entry["status"] == stock_later["status"] == "VERIFIED_NATIVE_RAW_EOD_CLOSE"
            ) else STOCK_GAP
        else:
            status = NO_PAIR
        if (status == SOURCE_PAIR) != (
            need["status"] == "QUOTE_SOURCE_AVAILABLE_NATIVE_RAW_EOD_CLOSE_NOT_YET_VERIFIED"
            and stock_entry is not None and stock_later is not None
            and stock_entry["status"] == stock_later["status"] == "VERIFIED_NATIVE_RAW_EOD_CLOSE"
        ):
            raise SourceCasebookError("frozen quote/native source classification changed")
        by_year[year][status] += 1
        rows.append({
            "case_right_id": key,
            "original_case_id": original["original_case_id"],
            "year": year, "right": original["right"],
            "ticker": need["ticker"], "instrument_id": need["instrument_id"],
            "option_symbol": original["option_symbol"],
            "quote_request_identity": original["quote_request_identity"],
            "original_quote_history_status": original["quote_history_status"],
            "observed_quote_timeline_status": quote["timeline_status"],
            "original_quote_body_sha256": original.get("quote_body_sha256"),
            "first_later_option_source": entry,
            "next_later_option_source": later,
            "entry_session_native_source": stock_entry,
            "next_session_native_source": stock_later,
            "source_join_status": status,
            "same_session_evidence_is_not_same_clock_evidence": True,
            "deliverable_and_multiplier_verified": False,
            "executable_fill_or_account_pnl_authority": False,
        })
    if len(unique_originals) != expected_original_cases:
        raise SourceCasebookError("original signal population changed")
    counts = Counter(r["source_join_status"] for r in rows)
    report = {
        "contract": CONTRACT,
        "status": "FULL_COHORT_DATED_SOURCE_CASEBOOK_NOT_TRADE_REPLAY",
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "option_timeline_fingerprint": timeline["timeline_fingerprint"],
        "native_close_demand_fingerprint": needs["demand_fingerprint"],
        "native_close_source_fingerprint": closes["source_fingerprint"],
        "original_case_denominator": expected_original_cases,
        "original_right_memberships": right_count,
        "selected_case_right_memberships": handoff["selected_case_right_memberships"],
        "two_later_option_source_rights": counts[SOURCE_PAIR] + counts[STOCK_GAP],
        "dated_option_and_stock_source_rights": counts[SOURCE_PAIR],
        "by_status": dict(sorted(counts.items())),
        "by_year": {
            str(year): dict(sorted(by_year[str(year)].items()))
            for year in range(2021, 2027)
        },
        "rows": rows,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "synchronized_clock_pairs_proven": 0,
        "option_fills_verified": 0,
        "account_pnl_authority": False,
    }
    report["casebook_fingerprint"] = _fingerprint(report)
    return report


def persist_source_casebook(
    settings: AtlasSettings, report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "casebook_fingerprint")
    path = settings.resolved_path(
        f"{OUTPUT_REL}_{report['casebook_fingerprint'][:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != report:
            raise SourceCasebookError("previous immutable source casebook differs")
        return path, "REUSED_IDENTICAL_SOURCE_CASEBOOK"
    _write_new(path, report)
    return path, "WRITTEN_IMMUTABLE_SOURCE_CASEBOOK"
