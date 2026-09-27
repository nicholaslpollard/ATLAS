from __future__ import annotations

"""PIT-frozen 2022 CALL candidate EOD quote histories, source-only.

This new additive cache does not change the original 2025 eleven-symbol pilot.
Its global exact-symbol/year-start/expiration request identity allows reuse
across partially overlapping 2022 shard campaigns.
"""

import hashlib
import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_additive_2022_shards_v1 import (
    YEAR, prepare_additive_shard,
)
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, _fingerprint, _paths as chain_paths,
    _valid_receipt as intact_chain_receipt,
)
from packages.data.marketdata_candidate_expansion_v1 import (
    _exclusive, _read_object, _require_external, _sha,
)
from packages.data.marketdata_candidate_2025_selected_quote_source_v1 import (
    _classify as classify_quote, _transport as quote_transport,
    MAX_RAW_BYTES, MIN_REMAINING_CREDITS,
)
from packages.data.research_storage import assert_category_acquisition_allowed
from packages.providers.marketdata_app.client import array_rows, rate_limit_snapshot

CONTRACT = "atlas-marketdata-2022-additive-selected-call-eod-quote-v1"
PLAN_REL = "data/options/manifests/marketdata_2022_additive_quote_plans_v1"
CACHE_REL = "data/options/candidate_cache/quotes/marketdata_2022_additive_v1"
MAX_SHARDS = 71
MAX_WORKERS = 4
MAX_NEW_QUOTE_REQUESTS = 3000
MAX_OBSERVED_CREDITS = 3500
MAX_SOURCE_ROWS = 500
HISTORICAL_FROM = date(2022, 1, 1)
POLICY = "NEAREST_PIT_RAW_OPEN_CALL_AND_UP_TO_TWO_NEAREST_DISTINCT_ALTERNATES_NO_EOD_LIQUIDITY_SELECTION"


def _clean_call_candidates(
    rows: tuple[dict[str, Any], ...], raw_open: object,
) -> tuple[dict[str, Any], ...]:
    """Select a bounded CALL candidate set from *prior-session* identities only."""
    try:
        price = Decimal(str(raw_open))
        if not price.is_finite() or price <= 0:
            raise ValueError("invalid raw-open price")
        calls = []
        seen = set()
        for row in rows:
            if row.get("side") != "call":
                continue
            symbol = row.get("optionSymbol")
            strike = Decimal(str(row.get("strike")))
            if (not isinstance(symbol, str) or not strike.is_finite()
                    or strike <= 0 or symbol in seen):
                raise ValueError("invalid or duplicate CALL identity")
            seen.add(symbol)
            calls.append({"option_symbol": symbol, "strike": str(strike)})
        if not calls:
            return ()
        calls.sort(key=lambda x: (
            abs(Decimal(x["strike"]) - price),
            Decimal(x["strike"]) < price,  # out-of-the-money wins exact tie
            Decimal(x["strike"]), x["option_symbol"],
        ))
        return tuple(calls[:3])
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CandidateChainCacheError("PIT raw-open CALL selection malformed") from exc


def freeze_quote_plan(
    settings: AtlasSettings, *, last_shard_inclusive: int,
    preparer: Callable[..., Any] = prepare_additive_shard,
) -> dict[str, Any]:
    """Needs already-complete source shards only. ZERO provider requests."""
    if type(last_shard_inclusive) is not int or not 0 <= last_shard_inclusive < MAX_SHARDS:
        raise CandidateChainCacheError("quote source shard range out of bounds")
    requests_by_symbol: dict[str, dict[str, Any]] = {}
    source_plans = []
    source_gaps = []
    total_memberships = 0
    cohort_census: str | None = None
    for index in range(last_shard_inclusive + 1):
        plan, source_path, binding, action = preparer(
            settings, shard_index=index, duckdb_threads=4,
        )
        source = _read_object(source_path)
        census = source.get("all_additive_query_keys_fingerprint")
        if (source.get("year") != YEAR or source.get("shard_index") != index
                or source.get("protected_master_return_rows_read") != 0
                or source.get("original_prior_plan_fingerprint") is None
                or not isinstance(census, str)
                or (cohort_census is not None and census != cohort_census)
                or binding["source_sha256"] != _sha(source_path)
                or len(source.get("rows", [])) != plan["opportunities"]):
            raise CandidateChainCacheError("selected quote source shard immutable lineage changed")
        cohort_census = census
        source_by_id = {x["opportunity_id"]: x for x in source["rows"]}
        if len(source_by_id) != len(source["rows"]):
            raise CandidateChainCacheError("duplicate source opportunity IDs")
        source_plans.append({
            "shard_index": index, "source_sha256": binding["source_sha256"],
            "chain_plan_fingerprint": plan["plan_fingerprint"],
            "source_action": action,
        })
        for request in plan["requests"]:
            receipt = intact_chain_receipt(
                chain_paths(settings, request["request_identity"]), request,
                expected_plan_fingerprint=plan["plan_fingerprint"],
            )
            if receipt is None:
                raise CandidateChainCacheError(
                    f"shard {index} contains pending original chain source; complete it before quote history"
                )
            if receipt["status"] == "VERIFIED_NO_DATA":
                source_gaps.append({
                    "shard_index": index, "chain_request_identity": request["request_identity"],
                    "exact_no_data_proof": receipt["no_data_proof"],
                })
                continue
            raw = chain_paths(settings, request["request_identity"]).body.read_bytes()
            rows = array_rows(json.loads(raw.decode("utf-8")))
            for oid in request["opportunity_ids"]:
                original = source_by_id.get(oid)
                member = plan["source_bindings"].get(oid)
                if (original is None or member is None
                        or member["stock_source_sha256"] != binding["source_sha256"]
                        or str(member["raw_underlying_price"]) != str(original["raw_underlying_price"])
                        or original["snapshot_date"] != request["params"]["date"]
                        or original["expiration"] != request["params"]["expiration"]
                        or original["ticker"] != request["ticker"]
                        or member["side"] != "call"):
                    raise CandidateChainCacheError("original stock/PIT source mapping changed")
                candidates = _clean_call_candidates(rows, original["raw_underlying_price"])
                if not candidates:
                    source_gaps.append({
                        "shard_index": index, "chain_request_identity": request["request_identity"],
                        "opportunity_id": oid, "classification": "NO_CALL_IN_COMPLETED_CHAIN",
                    })
                    continue
                for rank, candidate in enumerate(candidates):
                    symbol = candidate["option_symbol"]
                    expiry = date.fromisoformat(original["expiration"])
                    match = re.fullmatch(r"([A-Z0-9.]+)(\d{6})C(\d{8})", symbol)
                    if match is None or "20" + match[2][:2] + "-" + match[2][2:4] + "-" + match[2][4:] != expiry.isoformat():
                        raise CandidateChainCacheError("CALL symbol not aligned with source expiry")
                    until = (expiry + timedelta(days=1)).isoformat()
                    immutable_query = {
                        "option_symbol": symbol,
                        "from_inclusive": HISTORICAL_FROM.isoformat(),
                        "to_exclusive": until,
                    }
                    identity = _fingerprint({"contract": CONTRACT, "query": immutable_query})
                    row = requests_by_symbol.get(symbol)
                    if row is None:
                        row = {
                            **immutable_query, "request_identity": identity,
                            "source_shard_memberships": [],
                            "historical_eod_only": True,
                            "historical_deliverable_not_verified": True,
                        }
                        requests_by_symbol[symbol] = row
                    if row["request_identity"] != identity or row["to_exclusive"] != until:
                        raise CandidateChainCacheError("same OCC symbol has conflicting exact quote range")
                    row["source_shard_memberships"].append({
                        "shard_index": index, "opportunity_id": oid, "rank": rank,
                        "raw_underlying_open": str(original["raw_underlying_price"]),
                        "selected_call_strike": candidate["strike"],
                        "chain_request_identity": request["request_identity"],
                        "chain_body_sha256": receipt["body_sha256"],
                    })
                    total_memberships += 1
    requests = []
    for symbol, row in sorted(requests_by_symbol.items()):
        row["source_shard_memberships"].sort(
            key=lambda m: (m["shard_index"], m["opportunity_id"], m["rank"])
        )
        requests.append(row)
    if not requests:
        raise CandidateChainCacheError("no source-supported CALL quote requests")
    plan = {
        "contract": CONTRACT,
        "status": "SOURCE_ONLY_SELECTED_CALL_QUOTE_HISTORIES_FROZEN",
        "year": YEAR,
        "first_shard": 0, "last_shard_inclusive": last_shard_inclusive,
        "global_2022_query_keys_fingerprint": cohort_census,
        "selection_policy": POLICY,
        "historical_quote_from": HISTORICAL_FROM.isoformat(),
        "source_plans": source_plans,
        "source_gaps": source_gaps,
        "selected_candidate_memberships": total_memberships,
        "unique_exact_quote_series": len(requests),
        "requests": requests,
        "deduplicated_by_option_symbol_and_exact_full_year_to_expiry_range": True,
        "historical_eod_only_no_0935_fill_or_option_pnl_authority": True,
        "provider_reads_in_planning": 0,
    }
    plan["plan_fingerprint"] = _fingerprint(plan)
    return plan


def _cache_paths(settings: AtlasSettings, ticket: dict[str, Any]) -> tuple[Path, Path, Path]:
    stem = ticket["request_identity"]
    root = settings.resolved_path(CACHE_REL) / stem[:2]
    return root / (stem + ".json"), root / (stem + ".receipt.json"), root / (stem + ".attempt.json")


def _read_intact_quote(settings: AtlasSettings, ticket: dict[str, Any]) -> dict[str, Any] | None:
    body, receipt_path, intent_path = _cache_paths(settings, ticket)
    exists = [x.exists() or x.is_symlink() for x in (body, receipt_path, intent_path)]
    if not any(exists):
        return None
    if not all(exists) or any(x.is_symlink() or not x.is_file() for x in (body, receipt_path, intent_path)):
        raise CandidateChainCacheError("unresolved quote request or orphan source; preserve all originals")
    try:
        raw = body.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
        ro, io = dict(receipt), dict(intent)
        rf, af = ro.pop("receipt_fingerprint"), io.pop("intent_fingerprint")
        classification, safe = classify_quote(ticket, receipt["http_status"], raw)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CandidateChainCacheError("historical quote receipt/source unreadable") from exc
    status = ("COMPLETE_SOURCE_ONLY" if classification == "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY"
              else "EXACT_QUERY_SOURCE_GAP" if classification == "EXACT_QUERY_NO_DATA"
              else "QUARANTINED_REVIEW_REQUIRED")
    rate = receipt.get("rate_limit") or {}
    if (rf != _fingerprint(ro) or af != _fingerprint(io)
            or receipt.get("contract") != CONTRACT or intent.get("contract") != CONTRACT
            or receipt.get("request_identity") != ticket["request_identity"]
            or intent.get("request_identity") != ticket["request_identity"]
            or receipt.get("query") != {k: ticket[k] for k in ("option_symbol", "from_inclusive", "to_exclusive")}
            or intent.get("query") != receipt["query"]
            or receipt.get("body_sha256") != hashlib.sha256(raw).hexdigest()
            or receipt.get("body_bytes") != len(raw)
            or receipt.get("classification") != classification
            or receipt.get("safe_summary") != safe
            or receipt.get("status") != status
            or intent.get("automatic_retry_permitted") is not False
            or type(rate.get("consumed")) is not int or rate["consumed"] < 0
            or type(rate.get("remaining")) is not int or rate["remaining"] < 0
            or (status == "EXACT_QUERY_SOURCE_GAP" and rate["consumed"] != 0)):
        raise CandidateChainCacheError("selected quote original lineage or rate-limit headers differ")
    if status == "QUARANTINED_REVIEW_REQUIRED":
        raise CandidateChainCacheError("existing original quote quarantine; no second API request")
    return receipt


def _one_exact_request(
    settings: AtlasSettings, ticket: dict[str, Any], token: str,
    transport: Callable[[dict[str, Any], str], tuple[int, bytes, dict[str, str]]],
) -> dict[str, Any]:
    body, receipt_path, intent_path = _cache_paths(settings, ticket)
    query = {k: ticket[k] for k in ("option_symbol", "from_inclusive", "to_exclusive")}
    intent = {
        "contract": CONTRACT, "request_identity": ticket["request_identity"],
        "query": query, "automatic_retry_permitted": False,
    }
    intent["intent_fingerprint"] = _fingerprint(intent)
    _exclusive(intent_path, intent)
    # Preserve this durable intent even on any transport error. Reentry MUST stop.
    try:
        http, raw, headers = transport(ticket, token)
    except Exception as exc:
        raise CandidateChainCacheError("quote transport uncertain; original attempt preserved, no retry") from exc
    if (type(http) is not int or not 100 <= http <= 599
            or not isinstance(raw, bytes) or len(raw) > MAX_RAW_BYTES
            or not isinstance(headers, dict)):
        raise CandidateChainCacheError("unbounded/malformed quote transport after original intent")
    classification, safe = classify_quote(ticket, http, raw)
    rate = rate_limit_snapshot(headers)
    status = ("COMPLETE_SOURCE_ONLY" if classification == "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY"
              else "EXACT_QUERY_SOURCE_GAP" if classification == "EXACT_QUERY_NO_DATA"
              else "QUARANTINED_REVIEW_REQUIRED")
    if (type(rate["consumed"]) is not int or rate["consumed"] < 0
            or type(rate["remaining"]) is not int or rate["remaining"] < 0
            or (status == "EXACT_QUERY_SOURCE_GAP" and rate["consumed"] != 0)):
        status = "QUARANTINED_REVIEW_REQUIRED"
    body.parent.mkdir(parents=True, exist_ok=True)
    with body.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    receipt = {
        "contract": CONTRACT, "request_identity": ticket["request_identity"],
        "query": query, "status": status, "classification": classification,
        "http_status": http, "body_sha256": hashlib.sha256(raw).hexdigest(),
        "body_bytes": len(raw), "safe_summary": safe, "rate_limit": rate,
        "provider_license_retention_required": True,
        "no_intraday_fill_option_pnl_paper_live_or_broker_authority": True,
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    _exclusive(receipt_path, receipt)
    if status == "QUARANTINED_REVIEW_REQUIRED":
        raise CandidateChainCacheError("original quote response quarantined; no automatic retry")
    return receipt


def run_selected_quote_histories(
    settings: AtlasSettings, plan: dict[str, Any], *,
    max_new_requests: int = 0, max_observed_credits: int = 1500,
    workers: int = 4, authorize: bool = False, paid: bool = False, private: bool = False,
    token: str | None = None,
    transport: Callable[[dict[str, Any], str], tuple[int, bytes, dict[str, str]]] = quote_transport,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    unsigned = dict(plan)
    fp = unsigned.pop("plan_fingerprint", None)
    tickets = plan.get("requests")
    if (fp != _fingerprint(unsigned) or plan.get("contract") != CONTRACT
            or plan.get("status") != "SOURCE_ONLY_SELECTED_CALL_QUOTE_HISTORIES_FROZEN"
            or not isinstance(tickets, list)
            or len(tickets) != plan.get("unique_exact_quote_series")
            or len({row.get("request_identity") for row in tickets}) != len(tickets)
            or any(row.get("request_identity") != _fingerprint({
                "contract": CONTRACT,
                "query": {k: row[k] for k in ("option_symbol", "from_inclusive", "to_exclusive")},
            }) for row in tickets)):
        raise CandidateChainCacheError("frozen global selected quote plan malformed")
    if not 0 <= max_new_requests <= MAX_NEW_QUOTE_REQUESTS:
        raise CandidateChainCacheError("quote request cap outside 0..3000")
    if not 1 <= max_observed_credits <= MAX_OBSERVED_CREDITS:
        raise CandidateChainCacheError("quote observed credit target outside 1..3500")
    if not 1 <= workers <= MAX_WORKERS:
        raise CandidateChainCacheError("quote workers outside 1..4")
    if max_new_requests and not (authorize and paid and private):
        raise CandidateChainCacheError("all paid/private/provider confirmations required")
    if not max_new_requests and (authorize or paid or private):
        raise CandidateChainCacheError("authorization requires positive quote request cap")
    if max_new_requests and not (token or "").strip():
        raise CandidateChainCacheError("MarketData token missing; no provider attempts")
    if max_new_requests:
        _require_external(settings)
    pending = []
    complete = gaps = 0
    raw_bytes = 0
    for ticket in tickets:
        receipt = _read_intact_quote(settings, ticket)
        if receipt is None:
            pending.append(ticket)
        else:
            raw_bytes += receipt["body_bytes"]
            if receipt["status"] == "COMPLETE_SOURCE_ONLY":
                complete += 1
            else:
                gaps += 1
    if progress:
        progress({"stage": "SOURCE_ONLY_QUOTE_CENSUS", "unique": len(tickets),
                  "complete": complete, "exact_gaps": gaps, "pending": len(pending),
                  "verified_original_body_bytes": raw_bytes})
    attempts = credits = 0
    last_remaining = None
    if max_new_requests:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while pending and attempts < max_new_requests and credits < max_observed_credits:
                remaining_budget = max_observed_credits - credits
                if last_remaining is not None and last_remaining < MIN_REMAINING_CREDITS:
                    break
                # At most four in-flight original requests. Reserve one observed
                # credit per <=500-row quote series; extra charges are monitored
                # after the batch and stop any further dispatch.
                size = min(workers, len(pending), max_new_requests - attempts,
                           max(1, remaining_budget))
                assert_category_acquisition_allowed(
                    settings, category="options_candidate_cache",
                    projected_additional_bytes=size * (MAX_RAW_BYTES + 8192),
                )
                batch = pending[:size]
                pending = pending[size:]
                futures = [pool.submit(_one_exact_request, settings, t, token or "", transport) for t in batch]
                error = None
                for f in as_completed(futures):
                    attempts += 1
                    try:
                        receipt = f.result()
                    except Exception as exc:
                        error = exc
                        continue
                    rate = receipt["rate_limit"]
                    credits += rate["consumed"]
                    last_remaining = (
                        rate["remaining"] if last_remaining is None
                        else min(last_remaining, rate["remaining"])
                    )
                    raw_bytes += receipt["body_bytes"]
                    if receipt["status"] == "COMPLETE_SOURCE_ONLY":
                        complete += 1
                    else:
                        gaps += 1
                if progress:
                    progress({"stage": "BOUNDED_QUOTE_BATCH", "new_attempts": attempts,
                              "observed_credits": credits,
                              "complete_source_series": complete, "exact_source_gaps": gaps,
                              "remaining": last_remaining, "raw_body_bytes": raw_bytes,
                              "pending": len(pending)})
                if error is not None:
                    raise CandidateChainCacheError(
                        "one or more original quotes uncertain/quarantined; review original receipt and intent; no retry"
                    ) from error
    report = {
        "contract": CONTRACT,
        "plan_fingerprint": fp,
        "status": ("COMPLETE_SOURCE_ONLY" if not pending else
                   "PREVIEW_NO_PROVIDER_READS" if not max_new_requests else "PARTIAL_BUDGET_OR_CREDIT_FLOOR"),
        "unique_exact_quote_series": len(tickets),
        "complete_source_series": complete, "exact_source_gaps": gaps,
        "pending": len(pending), "new_provider_attempts": attempts,
        "observed_credits_this_invocation": credits,
        "last_observed_provider_remaining": last_remaining,
        "verified_and_new_raw_body_bytes": raw_bytes,
        "original_2025_pilot_untouched": True,
        "source_only_no_0935_option_fill_or_pnl_authority": True,
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
