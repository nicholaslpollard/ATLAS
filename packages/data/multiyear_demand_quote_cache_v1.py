from __future__ import annotations

"""Source-only, on-demand historical quote cache for 2021–2026 strategy inputs.

Plan is made from preselected OCC identities, never from future EOD liquidity.
One immutable physical query body serves every later strategy iteration. No API
request runs unless explicitly enabled with separate request/credit limits.
"""

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, _fingerprint,
)
from packages.data.marketdata_candidate_2025_selected_quote_source_v1 import (
    _classify as classify_quote, _transport as quote_transport,
    MAX_RAW_BYTES,
)
from packages.data.marketdata_candidate_expansion_v1 import _require_external
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    _read_intact_quote as old_2022_receipt,
)
from packages.data.offline_option_history_v1 import OfflineOptionHistoryStore
from packages.data.research_storage import assert_category_acquisition_allowed
from packages.providers.marketdata_app.client import rate_limit_snapshot

CONTRACT = "atlas-multiyear-demand-driven-option-eod-quote-source-v1"
CACHE_REL = "data/options/candidate_cache/quotes/multiyear_demand_v1"
PLAN_REL = "data/options/manifests/multiyear_demand_quote_v1"
EASTERN = ZoneInfo("America/New_York")
MAX_REQUESTS = 250
MAX_CREDITS = 250
MIN_REMAINING = 500
MAX_WORKERS = 8
MAX_PRICE_ROWS = 500
OCC = re.compile(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$")


class MultiYearQuoteCacheError(ValueError):
    pass


def _write_new(path: Path, payload: dict[str, Any] | bytes) -> None:
    raw = (
        (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
        if isinstance(payload, dict) else payload
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _date(value: object) -> date:
    if not isinstance(value, str):
        raise MultiYearQuoteCacheError("ISO date required")
    return date.fromisoformat(value)


def _time(value: object) -> datetime:
    if not isinstance(value, str):
        raise MultiYearQuoteCacheError("ISO timestamp required")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise MultiYearQuoteCacheError("timezone-aware timestamp required")
    return parsed.astimezone(UTC)


def _floor(asof: date) -> date:
    try:
        return asof.replace(year=asof.year - 5)
    except ValueError:
        return asof.replace(year=asof.year - 5, day=28)


def freeze_quote_demand(
    selected: list[dict[str, Any]], *,
    asof_utc: datetime, last_completed_session: date,
) -> dict[str, Any]:
    """Freeze original candidate demand and a transparent full-case gap ledger.

    selected MUST be extracted from independently accepted stock decisions;
    these source claims alone do not authorize a strategy result or a GET.
    """
    if not isinstance(asof_utc, datetime) or asof_utc.tzinfo is None:
        raise MultiYearQuoteCacheError("aware planning as-of required")
    if not isinstance(last_completed_session, date):
        raise MultiYearQuoteCacheError("last completed exchange session required")
    asof_day = asof_utc.astimezone(EASTERN).date()
    if (
        not 1 <= len(selected) <= 100000 or last_completed_session > asof_day
        or last_completed_session.year != 2026
    ):
        raise MultiYearQuoteCacheError("selected cohort or completed session invalid")
    floor_day = _floor(asof_day)
    by_query: dict[str, dict[str, Any]] = {}
    memberships: list[dict[str, Any]] = []
    seen_case: set[str] = set()
    for row in selected:
        if not isinstance(row, dict):
            raise MultiYearQuoteCacheError("candidate row must be an object")
        oid = row.get("case_id")
        symbol = row.get("option_symbol")
        match = OCC.fullmatch(symbol) if isinstance(symbol, str) else None
        if not isinstance(oid, str) or not oid or oid in seen_case or match is None:
            raise MultiYearQuoteCacheError("duplicate case or invalid exact OCC symbol")
        seen_case.add(oid)
        decision = _time(row.get("decision_at_utc"))
        selection = _time(row.get("selected_at_utc"))
        signal_day = decision.astimezone(EASTERN).date()
        expiry = date(2000 + int(match.group(2)[:2]), int(match.group(2)[2:4]),
                      int(match.group(2)[4:6]))
        stock_source = row.get("accepted_stock_source_sha256")
        if (
            not isinstance(stock_source, str) or len(stock_source) != 64
            or any(c not in "0123456789abcdef" for c in stock_source)
            or not 2021 <= signal_day.year <= 2026
            or selection > decision
            or row.get("ticker") != match.group(1)
            or row.get("right") != {"C": "call", "P": "put"}[match.group(3)]
            or row.get("expiration") != expiry.isoformat()
            or not 7 <= (expiry - signal_day).days <= 75
        ):
            raise MultiYearQuoteCacheError("predecision original stock/OCC selection mismatch")
        disposition = "SOURCE_DEMAND_READY"
        if signal_day < floor_day:
            disposition = "ORIGINAL_DECISION_OUTSIDE_STARTER_FIVE_YEAR_WINDOW"
        elif signal_day > last_completed_session:
            disposition = "ORIGINAL_DECISION_AFTER_LAST_COMPLETED_SESSION"
        membership: dict[str, Any] = {
            "case_id": oid, "decision_at_utc": decision.isoformat(),
            "selected_at_utc": selection.isoformat(),
            "original_accepted_stock_source_sha256": stock_source,
            "ticker": row["ticker"], "option_symbol": symbol,
            "disposition": disposition, "request_identity": None,
        }
        if disposition == "SOURCE_DEMAND_READY":
            start = max(date(signal_day.year, 1, 1), floor_day)
            end = min(expiry + timedelta(days=1), last_completed_session + timedelta(days=1))
            if end <= start:
                membership["disposition"] = "NO_CLOSED_SOURCE_PERIOD"
            else:
                query = {
                    "option_symbol": symbol,
                    "from_inclusive": start.isoformat(),
                    "to_exclusive": end.isoformat(),
                }
                identity = _fingerprint({"contract": CONTRACT, "query": query})
                item = by_query.setdefault(identity, {
                    **query, "request_identity": identity,
                    "member_case_ids": [], "source_only_not_validated_trade": True,
                })
                item["member_case_ids"].append(oid)
                membership["request_identity"] = identity
        memberships.append(membership)
    requests = sorted(by_query.values(), key=lambda x: x["request_identity"])
    for item in requests:
        item["member_case_ids"].sort()
    report = {
        "contract": CONTRACT,
        "status": "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS",
        "asof_utc": asof_utc.astimezone(UTC).isoformat(),
        "rolling_five_year_floor": floor_day.isoformat(),
        "last_completed_session": last_completed_session.isoformat(),
        "requested_case_denominator": len(memberships),
        "unique_physical_quote_queries": len(requests),
        "memberships": sorted(memberships, key=lambda x: x["case_id"]),
        "requests": requests,
        "provider_requests": 0, "strategy_authority": False,
        "no_future_liquidity_contract_selection": True,
    }
    report["plan_fingerprint"] = _fingerprint(report)
    return report


def _path(settings: AtlasSettings, ticket: dict[str, Any]) -> tuple[Path, Path, Path]:
    stem = ticket["request_identity"]
    root = settings.resolved_path(CACHE_REL) / stem[:2]
    return (
        root / (stem + ".json"), root / (stem + ".receipt.json"),
        root / (stem + ".attempt.json"),
    )


def _intact(settings: AtlasSettings, ticket: dict[str, Any]) -> dict[str, Any] | None:
    paths = _path(settings, ticket)
    exists = [p.exists() or p.is_symlink() for p in paths]
    if not any(exists):
        return None
    if not all(exists) or any(p.is_symlink() or not p.is_file() for p in paths):
        raise MultiYearQuoteCacheError("unresolved paid quote attempt, preserve originals")
    try:
        raw = paths[0].read_bytes()
        receipt = json.loads(paths[1].read_text(encoding="utf-8"))
        intent = json.loads(paths[2].read_text(encoding="utf-8"))
        rr, ii = dict(receipt), dict(intent)
        rf = rr.pop("receipt_fingerprint")
        af = ii.pop("intent_fingerprint")
        classification, safe = classify_quote(ticket, receipt["http_status"], raw)
        expected = (
            "COMPLETE_SOURCE_ONLY" if classification == "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY"
            else "EXACT_QUERY_SOURCE_GAP" if classification == "EXACT_QUERY_NO_DATA"
            else "QUARANTINED_REVIEW_REQUIRED"
        )
        rate = receipt["rate_limit"]
        if (
            rf != _fingerprint(rr) or af != _fingerprint(ii)
            or receipt["contract"] != CONTRACT or intent["contract"] != CONTRACT
            or receipt["query"] != {k: ticket[k] for k in (
                "option_symbol", "from_inclusive", "to_exclusive"
            )}
            or intent["query"] != receipt["query"]
            or receipt["request_identity"] != ticket["request_identity"]
            or intent["request_identity"] != ticket["request_identity"]
            or intent["automatic_retry_permitted"] is not False
            or receipt["body_sha256"] != hashlib.sha256(raw).hexdigest()
            or receipt["body_bytes"] != len(raw)
            or receipt["classification"] != classification
            or receipt["safe_summary"] != safe
            or receipt["status"] != expected
            or type(rate.get("consumed")) is not int or rate["consumed"] < 0
            or type(rate.get("remaining")) is not int or rate["remaining"] < 0
        ):
            raise MultiYearQuoteCacheError("original multiyear quote cache lineage changed")
        if receipt["status"] == "QUARANTINED_REVIEW_REQUIRED":
            raise MultiYearQuoteCacheError("stored original quarantine, no retry")
        return receipt
    except MultiYearQuoteCacheError:
        raise
    except (OSError, ValueError, TypeError, KeyError, CandidateChainCacheError) as exc:
        raise MultiYearQuoteCacheError("original quote receipt/body unreadable") from exc


def _reuse_2022(
    ticket: dict[str, Any], store: OfflineOptionHistoryStore | None,
) -> dict[str, Any] | None:
    if store is None:
        return None
    old = store._tickets.get(ticket["option_symbol"])
    if old is None or not (
        old["from_inclusive"] <= ticket["from_inclusive"]
        and old["to_exclusive"] >= ticket["to_exclusive"]
    ):
        return None
    receipt = old_2022_receipt(store.settings, old)
    if receipt is None or receipt["status"] != "COMPLETE_SOURCE_ONLY":
        raise MultiYearQuoteCacheError("original 2022 covering source unavailable/quarantined")
    return {
        "status": "REUSED_ACCEPTED_2022_FULL_SERIES",
        "body_sha256": receipt["body_sha256"],
        "source_request_identity": old["request_identity"],
        "physical_original_2022_quote_plan": store.plan_fingerprint,
        "cached_observed_rows": receipt["safe_summary"]["observed_rows"],
    }


def _one_get(
    settings: AtlasSettings, ticket: dict[str, Any], token: str,
    transport: Callable[[dict[str, Any], str], tuple[int, bytes, dict[str, str]]],
) -> dict[str, Any]:
    body, receipt_path, attempt_path = _path(settings, ticket)
    query = {k: ticket[k] for k in ("option_symbol", "from_inclusive", "to_exclusive")}
    attempt = {
        "contract": CONTRACT, "query": query,
        "request_identity": ticket["request_identity"],
        "automatic_retry_permitted": False,
    }
    attempt["intent_fingerprint"] = _fingerprint(attempt)
    _write_new(attempt_path, attempt)  # durable before paid provider access
    try:
        status, raw, headers = transport(ticket, token)
    except Exception as exc:
        raise MultiYearQuoteCacheError(
            "paid transport uncertain, preserve original intent; NO retry"
        ) from exc
    if (
        type(status) is not int or not 100 <= status <= 599
        or not isinstance(raw, bytes) or len(raw) > MAX_RAW_BYTES
        or not isinstance(headers, dict)
    ):
        raise MultiYearQuoteCacheError("unbounded/malformed paid response; preserve intent")
    classification, safe = classify_quote(ticket, status, raw)
    rate = rate_limit_snapshot(headers)
    expected = (
        "COMPLETE_SOURCE_ONLY" if classification == "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY"
        else "EXACT_QUERY_SOURCE_GAP" if classification == "EXACT_QUERY_NO_DATA"
        else "QUARANTINED_REVIEW_REQUIRED"
    )
    if (
        type(rate["consumed"]) is not int or rate["consumed"] < 0
        or type(rate["remaining"]) is not int or rate["remaining"] < 0
        or (expected == "EXACT_QUERY_SOURCE_GAP" and rate["consumed"] != 0)
    ):
        expected = "QUARANTINED_REVIEW_REQUIRED"
    _write_new(body, raw)
    receipt = {
        "contract": CONTRACT, "request_identity": ticket["request_identity"],
        "query": query, "status": expected, "http_status": status,
        "classification": classification,
        "body_sha256": hashlib.sha256(raw).hexdigest(), "body_bytes": len(raw),
        "safe_summary": safe, "rate_limit": rate,
        "subscription_data_retention_required": True,
        "source_only_not_fill_or_trade_pnl": True,
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    _write_new(receipt_path, receipt)
    if expected == "QUARANTINED_REVIEW_REQUIRED":
        raise MultiYearQuoteCacheError(
            "original paid response quarantined; preserve and review, no automatic retry"
        )
    return receipt


def run_demand_cache(
    settings: AtlasSettings, plan: dict[str, Any], *,
    max_new_requests: int = 0, max_observed_credits: int = 0,
    user_asserted_remaining: int | None = None,
    authorize_provider: bool = False, confirm_paid_starter: bool = False,
    confirm_private_internal_use: bool = False,
    token: str | None = None,
    workers: int = 4,
    transport: Callable[[dict[str, Any], str], tuple[int, bytes, dict[str, str]]] = quote_transport,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Safe preview by default. Paid worker uses bounded, SHA-bound exact GETs."""
    unsigned = dict(plan)
    signature = unsigned.pop("plan_fingerprint", None)
    requests = plan.get("requests")
    if (
        signature != _fingerprint(unsigned)
        or plan.get("contract") != CONTRACT
        or plan.get("status") != "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS"
        or plan.get("strategy_authority") is not False
        or plan.get("provider_requests") != 0
        or not isinstance(requests, list)
        or plan.get("unique_physical_quote_queries") != len(requests)
        or len({r["request_identity"] for r in requests}) != len(requests)
        or len(plan.get("memberships", [])) != plan.get("requested_case_denominator")
        or any(r.get("request_identity") != _fingerprint({
            "contract": CONTRACT,
            "query": {k: r[k] for k in ("option_symbol", "from_inclusive", "to_exclusive")}
        }) for r in requests)
    ):
        raise MultiYearQuoteCacheError("demand plan integrity/source identity changed")
    if (
        type(max_new_requests) is not int or type(max_observed_credits) is not int
        or not 0 <= max_new_requests <= MAX_REQUESTS
        or not 0 <= max_observed_credits <= MAX_CREDITS
        or (max_new_requests == 0) != (max_observed_credits == 0)
        or type(workers) is not int or not 1 <= workers <= MAX_WORKERS
    ):
        raise MultiYearQuoteCacheError("request, credit or concurrency cap invalid")
    paid = max_new_requests > 0
    if paid and not (
        authorize_provider and confirm_paid_starter and confirm_private_internal_use
        and isinstance(token, str) and token.strip()
        and type(user_asserted_remaining) is int
        and user_asserted_remaining >= max_observed_credits + MIN_REMAINING
    ):
        raise MultiYearQuoteCacheError(
            "paid authorization, token, user-asserted credits and 500-credit reserve required"
        )
    if not paid and (authorize_provider or confirm_paid_starter or confirm_private_internal_use):
        raise MultiYearQuoteCacheError("paid flags without positive bounded budget")
    if paid:
        _require_external(settings)
    settings.assert_external_storage_binding("options")
    # Existing original 2022 plan is looked up ONCE; never rescan/reacquire 6,398 bodies.
    store = (
        OfflineOptionHistoryStore(settings)
        if any(r["from_inclusive"].startswith("2022-") for r in requests) else None
    )
    reused_original = completed = gap = 0
    pending: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for ticket in requests:
        previous = _reuse_2022(ticket, store)
        if previous is not None:
            reused_original += 1
            rows.append({"request_identity": ticket["request_identity"], **previous})
            continue
        receipt = _intact(settings, ticket)
        if receipt is None:
            pending.append(ticket)
            continue
        completed += receipt["status"] == "COMPLETE_SOURCE_ONLY"
        gap += receipt["status"] == "EXACT_QUERY_SOURCE_GAP"
        rows.append({
            "request_identity": ticket["request_identity"],
            "status": receipt["status"],
            "body_sha256": receipt["body_sha256"],
            "cached_observed_rows": receipt["safe_summary"]["observed_rows"],
        })
    if progress:
        progress({
            "stage": "OFFLINE_CACHE_CENSUS", "original_2022_reused": reused_original,
            "new_cache_complete": completed, "exact_gaps": gap,
            "pending_new_queries": len(pending), "provider_requests": 0,
        })
    attempts = credits = 0
    latest_remaining: int | None = None
    started = time.monotonic()
    if paid and pending:
        # No second paid ATLAS process may share this session: other existing
        # scripts do not participate in this lock, so operator must keep them off.
        lock = settings.resolved_path("data/options/manifests/.multiyear_paid_get.lock")
        _write_new(lock, {
            "contract": CONTRACT, "plan_fingerprint": signature,
            "started_at_utc": datetime.now(UTC).isoformat(),
            "manual_review_required_if_aborted": True,
        })
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                while pending and attempts < max_new_requests and credits < max_observed_credits:
                    reserve_remaining = (
                        user_asserted_remaining if latest_remaining is None
                        else min(user_asserted_remaining, latest_remaining)
                    )
                    # First actual GET establishes authoritative provider headers.
                    batch_size = min(
                        1 if latest_remaining is None else workers,
                        len(pending), max_new_requests - attempts,
                        max_observed_credits - credits,
                        max(0, reserve_remaining - MIN_REMAINING),
                    )
                    if batch_size < 1:
                        break
                    assert_category_acquisition_allowed(
                        settings, category="options_candidate_cache",
                        projected_additional_bytes=batch_size * (MAX_RAW_BYTES + 8192),
                    )
                    batch, pending = pending[:batch_size], pending[batch_size:]
                    started_batch = time.monotonic()
                    futures = [
                        pool.submit(_one_get, settings, ticket, token.strip(), transport)
                        for ticket in batch
                    ]
                    first_error: Exception | None = None
                    for future, ticket in zip(futures, batch):
                        attempts += 1
                        try:
                            receipt = future.result()
                        except Exception as exc:
                            first_error = first_error or exc
                            continue
                        rate = receipt["rate_limit"]
                        credits += rate["consumed"]
                        latest_remaining = (
                            rate["remaining"] if latest_remaining is None
                            else min(latest_remaining, rate["remaining"])
                        )
                        completed += receipt["status"] == "COMPLETE_SOURCE_ONLY"
                        gap += receipt["status"] == "EXACT_QUERY_SOURCE_GAP"
                        rows.append({
                            "request_identity": ticket["request_identity"],
                            "status": receipt["status"],
                            "body_sha256": receipt["body_sha256"],
                            "cached_observed_rows": receipt["safe_summary"]["observed_rows"],
                        })
                    if progress:
                        progress({
                            "stage": "BOUNDED_EXACT_HISTORY_GETS",
                            "new_attempts": attempts, "observed_credits": credits,
                            "provider_remaining_min_observed": latest_remaining,
                            "inflight_wave": batch_size,
                            "new_cache_complete": completed, "exact_gaps": gap,
                            "pending_new_queries": len(pending),
                            "batch_seconds": round(time.monotonic() - started_batch, 3),
                            "total_seconds": round(time.monotonic() - started, 3),
                        })
                    if first_error is not None:
                        raise MultiYearQuoteCacheError(
                            "paid source uncertain/quarantined; preserved original bytes and "
                            "intent; no automatic replay"
                        ) from first_error
                    if (
                        credits > max_observed_credits
                        or latest_remaining is None
                        or latest_remaining < MIN_REMAINING
                    ):
                        raise MultiYearQuoteCacheError(
                            "observed provider credit bound/floor violated; STOP paid acquisition"
                        )
        finally:
            # A clean/handled final path has persisted all reported source
            # receipts. If process terminates abruptly, lock survives for review.
            lock.unlink(missing_ok=True)
    report = {
        "contract": CONTRACT, "plan_fingerprint": signature,
        "status": (
            "ALL_DEMAND_SOURCES_ACCOUNTED" if not pending
            else "PREVIEW_ONLY_NO_PROVIDER_GETS" if not paid else "PARTIAL_HARD_BUDGET"
        ),
        "original_requested_case_denominator": plan["requested_case_denominator"],
        "unique_physical_quote_queries": len(requests),
        "reused_original_2022": reused_original,
        "new_cache_complete": completed, "exact_source_gaps": gap,
        "pending": len(pending), "new_provider_attempts": attempts,
        "observed_credits": credits, "last_observed_provider_remaining": latest_remaining,
        "provider_read_authority_only_not_strategy_or_pnl": True,
        "source_entries": sorted(rows, key=lambda r: r["request_identity"]),
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
