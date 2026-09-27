from __future__ import annotations

"""2022 rank-zero CALL later-session EOD bid/ask reference paths.

This is a retrospective per-share SOURCE REFERENCE, not an at-09:35 fill,
executable quote, verified OCC deliverable, cash P&L or strategy result.
Selection and reporting denominator come from the independently accepted
structural rank-zero readiness manifest, NEVER from future observed liquidity.
"""

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from statistics import median
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_2022_ranked_eod_readiness_v1 import (
    AUTHORITY as READINESS_AUTHORITY, CONTRACT as READINESS_CONTRACT,
    EXPECTED_PLAN, OUTPUT_REL as READINESS_REL,
)
from packages.data.marketdata_2022_broad_quote_campaign_v2 import PLAN_REL
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    _cache_paths, _read_intact_quote,
)
from packages.data.marketdata_candidate_2025_selected_quote_source_v1 import EASTERN, _decimal
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object
from packages.providers.marketdata_app.client import array_rows

CONTRACT = "atlas-marketdata-2022-rank0-later-eod-spread-reference-v1"
EXPECTED_READINESS = "8f561664c6ee0bc11aed44bfe4a84606701e93a9aa8a3cbd7f4b53a102452efc"
DERIVED_REL = "data/options/derived/marketdata_2022_rank0_later_eod_reference_v1"
EXPECTED_OPPORTUNITIES = 2643
EXPECTED_UNIQUE_RANK_ZERO = 2227
EXPECTED_FULL_QUOTE_CORPUS = 6398
QUANT = Decimal("0.000001")
AUTHORITY = {
    "provider_reads": False,
    "original_0935_option_fill": False,
    "executable_eod_fill": False,
    "verified_historical_deliverable": False,
    "option_cash_pnl": False,
    "portfolio_return": False,
    "paper": False,
    "live": False,
    "broker": False,
    "strategy_promotion": False,
}


def _num(value: Any) -> Decimal | None:
    try:
        return _decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CandidateChainCacheError("original EOD numeric field malformed") from exc


def _rounded(value: Decimal) -> str:
    if not value.is_finite():
        raise CandidateChainCacheError("nonfinite EOD price reference")
    return str(value.quantize(QUANT, rounding=ROUND_HALF_EVEN))


def _original_observations(raw: bytes, ticket: dict[str, Any],
                           expected_rows: int) -> list[dict[str, Any]]:
    try:
        items = array_rows(json.loads(raw.decode("utf-8")))
    except (ValueError, TypeError, KeyError) as exc:
        raise CandidateChainCacheError("exact original EOD body cannot be decoded") from exc
    if len(items) != expected_rows:
        raise CandidateChainCacheError("original quote body row count differs from receipt")
    rows: list[dict[str, Any]] = []
    seen: set[date] = set()
    for item in items:
        if item.get("optionSymbol") != ticket["option_symbol"]:
            raise CandidateChainCacheError("original OCC quote symbol changed")
        ts = _num(item.get("updated"))
        if ts is None or ts != ts.to_integral_value():
            raise CandidateChainCacheError("original quote timestamp malformed")
        timestamp = datetime.fromtimestamp(int(ts), UTC)
        day = timestamp.astimezone(EASTERN).date()
        if (not date.fromisoformat(ticket["from_inclusive"]) <= day
                < date.fromisoformat(ticket["to_exclusive"]) or day in seen):
            raise CandidateChainCacheError("original quote date or duplicate differs")
        seen.add(day)
        bid, ask, volume = (_num(item.get(field)) for field in ("bid", "ask", "volume"))
        if (bid is not None and bid < 0 or ask is not None and ask < 0
                or volume is not None and volume < 0):
            raise CandidateChainCacheError("original quote contains negative price/volume")
        valid = bid is not None and ask is not None and bid > 0 and ask >= bid
        rows.append({
            "day": day, "updated_at_utc": timestamp.isoformat(),
            "bid": bid, "ask": ask, "two_sided": valid,
            "positive_volume": volume is not None and volume > 0,
        })
    rows.sort(key=lambda x: x["day"])
    return rows


def build_rank0_later_eod_reference(
    settings: AtlasSettings, *,
    quote_reader: Callable[..., Any] = _read_intact_quote,
    raw_reader: Callable[..., bytes] | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Consume accepted readiness and exact raw quote receipts, ZERO paid GETs."""
    settings.assert_external_storage_binding("options")
    rp = settings.resolved_path(f"{READINESS_REL}_{EXPECTED_PLAN[:16]}.json")
    readiness = _read_object(rp)
    unsigned = dict(readiness)
    readiness_fp = unsigned.pop("readiness_fingerprint", None)
    if (readiness_fp != EXPECTED_READINESS or readiness_fp != _fingerprint(unsigned)
            or readiness.get("contract") != READINESS_CONTRACT
            or readiness.get("accepted_original_quote_plan") != EXPECTED_PLAN
            or readiness.get("status") != "RANKED_EOD_SCENARIO_READINESS_ONLY"
            or readiness.get("provider_requests") != 0
            or readiness.get("authority") != READINESS_AUTHORITY
            or readiness.get("rank_zero_opportunity_memberships") != EXPECTED_OPPORTUNITIES
            or readiness.get("unique_rank_zero_quote_histories") != EXPECTED_UNIQUE_RANK_ZERO
            or not readiness.get("context_only_no_fills_usable_quote_timestamp_or_pnl")):
        raise CandidateChainCacheError("accepted original ranked readiness changed")
    rows = readiness["rows"]
    if (not isinstance(rows, list) or len(rows) != EXPECTED_OPPORTUNITIES
            or len({(x["shard_index"], x["opportunity_id"]) for x in rows}) != len(rows)
            or any(x["structural_rank"] != 0 or not x["future_eod_never_used_for_structural_selection"]
                   for x in rows)):
        raise CandidateChainCacheError("structural rank-zero denominator changed")

    quote_plan = _read_object(settings.resolved_path(f"{PLAN_REL}/through_shard_070.json"))
    unsigned_plan = dict(quote_plan)
    plan_fp = unsigned_plan.pop("plan_fingerprint", None)
    tickets = quote_plan.get("requests")
    if (plan_fp != EXPECTED_PLAN or plan_fp != _fingerprint(unsigned_plan)
            or not isinstance(tickets, list) or len(tickets) != EXPECTED_FULL_QUOTE_CORPUS):
        raise CandidateChainCacheError("original full 2022 quote plan differs")
    ticket_by_id = {x["request_identity"]: x for x in tickets}
    if len(ticket_by_id) != EXPECTED_FULL_QUOTE_CORPUS:
        raise CandidateChainCacheError("duplicate full source physical history identity")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        identity = row["original_exact_quote_request_identity"]
        ticket = ticket_by_id.get(identity)
        if (ticket is None or row["option_symbol"] != ticket["option_symbol"]
                or row["classification"] not in (
                    "NO_LATER_EOD_OBSERVATION", "LATER_EOD_NO_TWO_SIDED_CONTEXT",
                    "LATER_TWO_SIDED_CONTEXT_ONLY",
                )):
            raise CandidateChainCacheError("rank-zero source/quote mapping changed")
        member = (row["shard_index"], row["opportunity_id"])
        if not any(m["rank"] == 0 and (m["shard_index"], m["opportunity_id"]) == member
                   for m in ticket["source_shard_memberships"]):
            raise CandidateChainCacheError("rank-zero membership no longer matches original plan")
        groups.setdefault(identity, []).append(row)
    if len(groups) != EXPECTED_UNIQUE_RANK_ZERO:
        raise CandidateChainCacheError("unique original rank-zero quote census differs")
    if raw_reader is None:
        def raw_reader(s: AtlasSettings, ticket: dict[str, Any]) -> bytes:
            return _cache_paths(s, ticket)[0].read_bytes()
    out: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    observed_positive_volume_at_entry = 0
    observed_positive_volume_at_exit = 0
    pct: list[Decimal] = []
    for index, identity in enumerate(sorted(groups), 1):
        ticket = ticket_by_id[identity]
        receipt = quote_reader(settings, ticket)
        if receipt is None or receipt.get("status") != "COMPLETE_SOURCE_ONLY":
            raise CandidateChainCacheError("original rank-zero receipt missing or quarantined")
        raw = raw_reader(settings, ticket)
        if hashlib.sha256(raw).hexdigest() != receipt["body_sha256"]:
            raise CandidateChainCacheError("rank-zero original raw body SHA differs from accepted receipt")
        events = _original_observations(
            raw, ticket, receipt["safe_summary"]["observed_rows"]
        )
        for ready in groups[identity]:
            decision = date.fromisoformat(ready["stock_decision_session_et"])
            expiry = date.fromisoformat(ready["expiration"])
            if (not date.fromisoformat(ready["source_signal_session"]) < decision < expiry
                    or (expiry - date.fromisoformat(ticket["to_exclusive"])).days != -1):
                raise CandidateChainCacheError("original stock decision/expiry chronology changed")
            # Strictly later session. Same-day EOD does not exist at 09:35.
            later = [event for event in events if decision < event["day"] <= expiry]
            valid = [event for event in later if event["two_sided"]]
            if len(valid) == 0:
                code = "NO_LATER_TWO_SIDED_REFERENCE"
            elif len(valid) == 1:
                code = "ENTRY_REFERENCE_ONLY_NO_SUBSEQUENT_REFERENCE"
            else:
                code = "ENTRY_AND_NEXT_REFERENCE_AVAILABLE"
            if ((not later and ready["classification"] != "NO_LATER_EOD_OBSERVATION")
                    or (later and not valid and ready["classification"] != "LATER_EOD_NO_TWO_SIDED_CONTEXT")
                    or (valid and ready["classification"] != "LATER_TWO_SIDED_CONTEXT_ONLY")
                    or len(valid) != ready["later_two_sided_eod_context_sessions"]):
                raise CandidateChainCacheError("new original source disagrees with accepted readiness")
            entry = valid[0] if valid else None
            subsequent = valid[1] if len(valid) >= 2 else None
            if (entry is not None and
                    entry["day"].isoformat() != ready["first_later_two_sided_eod_context_session"]):
                raise CandidateChainCacheError("first later source date differs from accepted readiness")
            entry_ask = entry["ask"] if entry else None
            exit_bid = subsequent["bid"] if subsequent else None
            diff = exit_bid-entry_ask if entry_ask is not None and exit_bid is not None else None
            fraction = diff/entry_ask if diff is not None else None
            counts[code] += 1
            if entry and entry["positive_volume"]:
                observed_positive_volume_at_entry += 1
            if subsequent and subsequent["positive_volume"]:
                observed_positive_volume_at_exit += 1
            if fraction is not None:
                pct.append(fraction)
            out.append({
                "opportunity_id": ready["opportunity_id"],
                "shard_index": ready["shard_index"],
                "ticker": ready["ticker"], "option_symbol": ready["option_symbol"],
                "original_quote_request_identity": identity,
                "stock_decision_session_et": decision.isoformat(),
                "source_signal_session": ready["source_signal_session"],
                "expiration": expiry.isoformat(), "structural_rank": 0,
                "selection_never_uses_later_liquidity": True,
                "reference_status": code,
                "first_later_two_sided_session": entry["day"].isoformat() if entry else None,
                "first_later_quote_updated_at_utc": entry["updated_at_utc"] if entry else None,
                "first_later_eod_ask_reference_per_share": _rounded(entry_ask) if entry_ask is not None else None,
                "first_later_eod_bid_reference_per_share": _rounded(entry["bid"]) if entry else None,
                "first_later_reported_positive_volume": entry["positive_volume"] if entry else None,
                "subsequent_two_sided_session": subsequent["day"].isoformat() if subsequent else None,
                "subsequent_quote_updated_at_utc": subsequent["updated_at_utc"] if subsequent else None,
                "subsequent_eod_bid_reference_per_share": _rounded(exit_bid) if exit_bid is not None else None,
                "subsequent_reported_positive_volume": subsequent["positive_volume"] if subsequent else None,
                "calendar_days_between_observed_reference_sessions": (
                    (subsequent["day"]-entry["day"]).days if subsequent and entry else None
                ),
                "hypothetical_ask_to_next_bid_reference_change_per_share": (
                    _rounded(diff) if diff is not None else None
                ),
                "hypothetical_ask_to_next_bid_reference_fraction": (
                    _rounded(fraction) if fraction is not None else None
                ),
                "retrospective_not_executable_or_original_0935_fill": True,
            })
        if progress and (index % 250 == 0 or index == len(groups)):
            progress({"stage": "LATER_EOD_REFERENCE_PROGRESS",
                      "unique_original_rank0_histories": index,
                      "total_original_rank0_histories": len(groups),
                      "opportunities_processed": len(out),
                      "provider_requests": 0})
    out.sort(key=lambda x: (x["stock_decision_session_et"], x["opportunity_id"],
                            x["shard_index"], x["option_symbol"]))
    result = {
        "contract": CONTRACT, "status": "DESCRIPTIVE_LATER_EOD_REFERENCE_ONLY",
        "original_rank_zero_readiness_fingerprint": readiness_fp,
        "original_2022_quote_plan_fingerprint": plan_fp,
        "structural_rank_zero_opportunities": len(rows),
        "unique_original_rank_zero_histories": len(groups),
        "no_later_two_sided_reference": counts["NO_LATER_TWO_SIDED_REFERENCE"],
        "entry_reference_only_no_subsequent_reference": counts["ENTRY_REFERENCE_ONLY_NO_SUBSEQUENT_REFERENCE"],
        "entry_and_next_reference_available": counts["ENTRY_AND_NEXT_REFERENCE_AVAILABLE"],
        "entry_reference_with_positive_reported_volume": observed_positive_volume_at_entry,
        "next_reference_with_positive_reported_volume": observed_positive_volume_at_exit,
        "median_hypothetical_ask_to_next_bid_reference_fraction": (
            _rounded(median(pct)) if pct else None
        ),
        "denominator_includes_all_structurally_chosen_rank0_opportunities": True,
        "first_reference_rule": "FIRST_VALID_TWO_SIDED_OBSERVATION_STRICTLY_LATER_THAN_0935_DECISION_DATE",
        "next_reference_rule": "NEXT_VALID_TWO_SIDED_OBSERVATION_ON_A_STRICTLY_LATER_SESSION",
        "reported_bid_ask_source_times_are_not_ASSUMED_TO_BE_1600_ET": True,
        "reference_price_change_not_cash_pnl_or_proven_fill": True,
        "original_receipts_modified": 0, "provider_requests": 0,
        "authority": AUTHORITY, "rows": out,
    }
    if (len(out) != EXPECTED_OPPORTUNITIES or
            sum(counts.values()) != EXPECTED_OPPORTUNITIES or
            len(pct) != counts["ENTRY_AND_NEXT_REFERENCE_AVAILABLE"]
            or counts["NO_LATER_TWO_SIDED_REFERENCE"] != (
                readiness["no_later_eod_observation"] + readiness["later_eod_without_two_sided_context"]
            )
            or counts["ENTRY_AND_NEXT_REFERENCE_AVAILABLE"] != (
                readiness["opportunities_with_two_or_more_later_two_sided_context_dates"]
            )
            or counts["ENTRY_REFERENCE_ONLY_NO_SUBSEQUENT_REFERENCE"] != (
                readiness["later_two_sided_eod_context_only"]
                - readiness["opportunities_with_two_or_more_later_two_sided_context_dates"]
            )):
        raise CandidateChainCacheError("rank-zero reference accounting changed")
    result["reference_fingerprint"] = _fingerprint(result)
    return result


def write_rank0_later_eod_reference(
    settings: AtlasSettings, result: dict[str, Any],
) -> tuple[Path, str]:
    if (result.get("contract") != CONTRACT or result.get("authority") != AUTHORITY
            or result.get("provider_requests") != 0
            or result.get("original_receipts_modified") != 0
            or result.get("reference_fingerprint") != _fingerprint({
                k: v for k, v in result.items() if k != "reference_fingerprint"
            })):
        raise CandidateChainCacheError("rank-zero EOD reference output invalid")
    path = settings.resolved_path(
        f"{DERIVED_REL}_{EXPECTED_READINESS[:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if _read_object(path) != result:
            raise CandidateChainCacheError("existing later-EOD reference differs, no overwrite")
        return path, "REUSED_IDENTICAL_DERIVED_REFERENCE"
    _exclusive(path, result)
    if _read_object(path) != result:
        raise CandidateChainCacheError("later-EOD derived reference readback differs")
    return path, "WRITTEN_NEW_DERIVED_REFERENCE"
