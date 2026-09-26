from __future__ import annotations

"""Frozen 2025 candidate CALL quote-series acquisition; source observations only.

New work after the completed chain, shortlist, and historical-reference gates.
Original reference receipts are consumed once as lineage; they are not reacquired.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint
from packages.data.marketdata_candidate_2025_exact_reference_v1 import (
    FROZEN_SYMBOLS, FROZEN_SHORTLIST, PLAN_REL as REFERENCE_PLAN_REL,
    _assert_intact as assert_reference_intact,
    _paths as reference_paths, build_exact_reference_plan, read_accepted_shortlist,
)
from packages.data.research_storage import assert_category_acquisition_allowed
from packages.providers.marketdata_app import MarketDataError, array_rows, rate_limit_snapshot

CONTRACT = "atlas-marketdata-2025-selected-eod-quote-source-v1"
REFERENCE_PLAN_FINGERPRINT = "261812136e0ce8d947aece094ba60a45e69429db0093072e21f7457420361fd4"
REFERENCE_STATUS = "PIT_REFERENCE_TERMS_CONSISTENT_DELIVERABLE_UNVERIFIED"
QUOTE_REL = "data/options/candidate_cache/quotes/marketdata_2025_v1"
PLAN_REL = "data/options/manifests/marketdata_candidate_2025_selected_quote_plan_v1_d6c924cf5006d295.json"
MAX_NEW_REQUESTS = 11
MAX_RAW_BYTES = 4 * 1024 * 1024
MAX_QUOTE_ROWS = 500
MIN_REMAINING_CREDITS = 200
MAX_OBSERVED_CREDITS = 25
EASTERN = ZoneInfo("America/New_York")
REQUIRED_COLUMNS = frozenset({
    "optionSymbol", "updated", "bid", "ask", "last", "volume",
    "openInterest", "underlyingPrice",
})


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a price or quantity")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("nonfinite value")
    return number


def read_accepted_inputs(settings: AtlasSettings) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the two accepted manifests and eleven original receipts, never the provider."""
    shortlist = read_accepted_shortlist(settings)
    reference_plan = build_exact_reference_plan(shortlist)
    if reference_plan["plan_fingerprint"] != REFERENCE_PLAN_FINGERPRINT:
        raise CandidateChainCacheError("reference plan no longer matches frozen operator result")
    path = settings.resolved_path(REFERENCE_PLAN_REL)
    if not path.is_file() or path.is_symlink():
        raise CandidateChainCacheError("accepted historical reference plan is missing or linked")
    if json.loads(path.read_text(encoding="utf-8")) != reference_plan:
        raise CandidateChainCacheError("accepted historical reference plan differs from frozen input")
    return shortlist, reference_plan


def build_quote_plan(
    settings: AtlasSettings, shortlist: dict[str, Any], reference_plan: dict[str, Any],
) -> dict[str, Any]:
    """Source-only path plan, reusing original reference receipts without a new study."""
    if (shortlist.get("shortlist_fingerprint") != FROZEN_SHORTLIST
            or reference_plan.get("plan_fingerprint") != REFERENCE_PLAN_FINGERPRINT
            or len(reference_plan.get("requests", [])) != MAX_NEW_REQUESTS):
        raise CandidateChainCacheError("quote plan does not bind accepted source cohort")
    choices = {x["ticker"]: x for x in shortlist["opportunities"]}
    if len(choices) != 12 or choices["FSLY"]["provisional_nearest_atm_call"] is not None:
        raise CandidateChainCacheError("FSLY and accepted 12-opportunity cohort changed")
    requests: list[dict[str, Any]] = []
    for reference in reference_plan["requests"]:
        receipt = assert_reference_intact(
            reference, reference_paths(settings, reference),
            plan_fingerprint=REFERENCE_PLAN_FINGERPRINT,
        )
        if (receipt is None or receipt.get("status") != "COMPLETE_REFERENCE_RECEIPT"
                or receipt.get("classification") != REFERENCE_STATUS):
            raise CandidateChainCacheError(
                "exact reference receipt is missing, quarantined or terms-ambiguous; no quote request"
            )
        row = choices[reference["ticker"]]
        horizon = row["quote_horizon_planning_only"]
        first = date.fromisoformat(horizon["from_inclusive"])
        end = date.fromisoformat(horizon["to_exclusive"])
        snapshot = date.fromisoformat(reference["as_of"])
        expiry = date.fromisoformat(reference["expiration"])
        decision = datetime.fromisoformat(row["stock_decision_at_utc"].replace("Z", "+00:00"))
        if (decision.tzinfo is None or decision.utcoffset() != timedelta(0)
                or decision.astimezone(EASTERN).date() != first
                or snapshot >= first or end != expiry + timedelta(days=1)
                or (expiry - snapshot).days > 76 or first > expiry
                or not horizon["decision_is_intraday_0935_no_same_day_eod_entry_price"]
                or row["provisional_nearest_atm_call"] != reference["option_symbol"]
                or row["source_chain_body_sha256"] != reference["source_chain_sha256"]
                or row["final_executable_option_contract_selected"] is not False
                or row["historical_quote_or_fill_price_validated"] is not False
                or receipt["safe_terms"]["historical_standard_deliverable_verified"] is not False
                or receipt["safe_terms"]["option_quote_or_fill_verified"] is not False):
            raise CandidateChainCacheError("quote horizon or historical source/authority binding differs")
        request: dict[str, Any] = {
            "ticker": reference["ticker"],
            "option_symbol": reference["option_symbol"],
            "opportunity_id": row["opportunity_id"],
            "source_chain_sha256": reference["source_chain_sha256"],
            "source_reference_receipt_fingerprint": receipt["receipt_fingerprint"],
            "source_reference_body_sha256": receipt["body_sha256"],
            "historical_reference_as_of": reference["as_of"],
            "stock_decision_at_utc": row["stock_decision_at_utc"],
            "from_inclusive": first.isoformat(),
            "to_exclusive": end.isoformat(),
            "expiration": reference["expiration"],
            "observation_role": "AS_TRADED_HISTORICAL_EOD_SOURCE_ONLY",
            "not_an_intraday_or_executable_price": True,
        }
        request["request_identity"] = _fingerprint(request)
        requests.append(request)
    requests.sort(key=lambda item: item["ticker"])
    if len({x["option_symbol"] for x in requests}) != 11 or len({x["request_identity"] for x in requests}) != 11:
        raise CandidateChainCacheError("quote series cannot duplicate contracts")
    plan = {
        "contract": CONTRACT,
        "status": "FROZEN_SELECTED_EOD_QUOTE_SOURCE_PLAN",
        "shortlist_fingerprint": FROZEN_SHORTLIST,
        "reference_plan_fingerprint": REFERENCE_PLAN_FINGERPRINT,
        "requests": requests,
        "source_gap_excluded": "FSLY",
        "request_count": len(requests),
        "bounded_exact_contract_series_only": True,
        "max_new_requests_per_run": MAX_NEW_REQUESTS,
        "max_raw_bytes_per_request": MAX_RAW_BYTES,
        "provider_retry_allowed": False,
        "provider_license_retention_required": True,
        "historical_deliverables_remain_unverified": True,
        "no_intraday_fill_option_pnl_strategy_paper_live_or_broker_authority": True,
    }
    plan["plan_fingerprint"] = _fingerprint(plan)
    return plan


def write_plan(settings: AtlasSettings, plan: dict[str, Any], *, authorize: bool) -> tuple[str, Path]:
    path = settings.resolved_path(PLAN_REL)
    raw = (json.dumps(plan, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists() or path.is_symlink():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != raw:
            raise CandidateChainCacheError("existing quote plan differs; never overwrite")
        return "REUSED_EXACT_QUOTE_PLAN", path
    if not authorize:
        return "PREVIEW_NO_WRITES", path
    _exclusive_write(path, raw)
    if path.read_bytes() != raw:
        raise CandidateChainCacheError("new quote plan failed read-back")
    return "WRITTEN_NEW_QUOTE_PLAN", path


def _paths(settings: AtlasSettings, ticket: dict[str, Any]) -> tuple[Path, Path, Path]:
    stem = ticket["request_identity"]
    base = settings.resolved_path(QUOTE_REL) / stem[:2]
    return base / (stem + ".json"), base / (stem + ".receipt.json"), base / (stem + ".attempt.json")


def _exclusive_write(path: Path, content: dict[str, Any] | bytes) -> None:
    raw = (json.dumps(content, sort_keys=True, indent=2) + "\n").encode("utf-8") if isinstance(content, dict) else content
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _classify(ticket: dict[str, Any], status: int, raw: bytes) -> tuple[str, dict[str, Any]]:
    safe: dict[str, Any] = {
        "observed_rows": 0, "positive_volume_rows": 0, "zero_volume_rows": 0,
        "first_session": None, "last_session": None, "historical_delivery_verified": False,
        "executable_fill_verified": False, "option_pnl_authority": False,
    }
    try:
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            return "QUARANTINED_SCHEMA", safe
        if status == 404 and payload.get("s") == "no_data":
            return "EXACT_QUERY_NO_DATA", safe
        if status not in (200, 203):
            return "QUARANTINED_HTTP", safe
        if payload.get("s") != "ok" or not REQUIRED_COLUMNS.issubset(payload):
            return "QUARANTINED_SCHEMA", safe
        rows = array_rows(payload)
        if not 1 <= len(rows) <= MAX_QUOTE_ROWS:
            return "QUARANTINED_ROWS", safe
        dates: set[date] = set()
        positive = zero = 0
        for row in rows:
            if row["optionSymbol"] != ticket["option_symbol"]:
                return "QUARANTINED_IDENTITY", safe
            ts = _decimal(row["updated"])
            if ts is None or ts != ts.to_integral_value():
                return "QUARANTINED_TIMESTAMP", safe
            session = datetime.fromtimestamp(int(ts), UTC).astimezone(EASTERN).date()
            if (not date.fromisoformat(ticket["from_inclusive"]) <= session
                    < date.fromisoformat(ticket["to_exclusive"]) or session in dates):
                return "QUARANTINED_TIMESTAMP", safe
            dates.add(session)
            for field in ("bid", "ask", "last", "volume", "openInterest", "underlyingPrice"):
                number = _decimal(row[field])
                if number is not None and number < 0:
                    return "QUARANTINED_SCHEMA", safe
            vol = _decimal(row["volume"])
            if vol is not None:
                if vol != vol.to_integral_value():
                    return "QUARANTINED_SCHEMA", safe
                if vol > 0: positive += 1
                else: zero += 1
        safe.update({
            "observed_rows": len(rows), "positive_volume_rows": positive,
            "zero_volume_rows": zero, "first_session": min(dates).isoformat(),
            "last_session": max(dates).isoformat(),
        })
        return "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY", safe
    except (ValueError, TypeError, KeyError, InvalidOperation, OverflowError, OSError, MarketDataError):
        return "QUARANTINED_SCHEMA", safe


def _intact(ticket: dict[str, Any], paths: tuple[Path, Path, Path], plan_fp: str) -> dict[str, Any] | None:
    body, receipt_path, attempt_path = paths
    exists = [p.exists() or p.is_symlink() for p in paths]
    if not any(exists):
        return None
    if not all(exists) or any(p.is_symlink() or not p.is_file() for p in paths):
        raise CandidateChainCacheError("unresolved quote attempt; preserve, never replay")
    try:
        raw = body.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
        rr, ii = dict(receipt), dict(attempt)
        rf = rr.pop("receipt_fingerprint")
        af = ii.pop("intent_fingerprint")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CandidateChainCacheError("quote evidence unreadable; preserve originals") from exc
    classification, safe = _classify(ticket, receipt.get("http_status"), raw)
    expected = "COMPLETE_SOURCE_ONLY" if classification == "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY" else (
        "EXACT_QUERY_SOURCE_GAP" if classification == "EXACT_QUERY_NO_DATA" else "QUARANTINED_REVIEW_REQUIRED"
    )
    if (rf != _fingerprint(rr) or af != _fingerprint(ii)
            or receipt.get("contract") != CONTRACT or attempt.get("contract") != CONTRACT
            or receipt.get("plan_fingerprint") != plan_fp or attempt.get("plan_fingerprint") != plan_fp
            or receipt.get("request_identity") != ticket["request_identity"]
            or attempt.get("request_identity") != ticket["request_identity"]
            or receipt.get("option_symbol") != ticket["option_symbol"]
            or attempt.get("option_symbol") != ticket["option_symbol"]
            or receipt.get("body_sha256") != _sha(raw) or receipt.get("body_bytes") != len(raw)
            or attempt.get("automatic_retry_permitted") is not False
            or receipt.get("classification") != classification or receipt.get("safe_summary") != safe
            or receipt.get("status") != expected):
        raise CandidateChainCacheError("quote receipt/attempt/raw lineage mismatch; preserve")
    if expected == "QUARANTINED_REVIEW_REQUIRED":
        raise CandidateChainCacheError("stored quote quarantine; no retry")
    return receipt


def _transport(ticket: dict[str, Any], token: str) -> tuple[int, bytes, dict[str, str]]:
    path = "https://api.marketdata.app/v1/options/quotes/" + ticket["option_symbol"] + "/"
    query = urllib.parse.urlencode({
        "from": ticket["from_inclusive"], "to": ticket["to_exclusive"],
    })
    request = urllib.request.Request(
        path + "?" + query,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                 "User-Agent": "ATLAS-selected-EOD-quote-source/1"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return int(response.status), response.read(MAX_RAW_BYTES + 1), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read(MAX_RAW_BYTES + 1), dict(exc.headers.items())


def run_quote_source(
    settings: AtlasSettings, plan: dict[str, Any], *,
    authorize: bool = False, confirm_paid: bool = False,
    confirm_private_use: bool = False, max_new_requests: int = 0,
    token: str | None = None,
    transport: Callable[[dict[str, Any], str], tuple[int, bytes, dict[str, str]]] | None = None,
    storage_guard: Callable[..., Any] = assert_category_acquisition_allowed,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    copy = dict(plan)
    signature = copy.pop("plan_fingerprint", None)
    tickets = plan.get("requests")
    if (signature != _fingerprint(copy) or plan.get("contract") != CONTRACT
            or plan.get("reference_plan_fingerprint") != REFERENCE_PLAN_FINGERPRINT
            or plan.get("shortlist_fingerprint") != FROZEN_SHORTLIST
            or plan.get("source_gap_excluded") != "FSLY"
            or plan.get("provider_retry_allowed") is not False
            or not isinstance(tickets, list) or len(tickets) != 11
            or len({x.get("option_symbol") for x in tickets}) != 11
            or {x.get("ticker"): x.get("option_symbol") for x in tickets}
               != {ticker: symbol for ticker, symbol in FROZEN_SYMBOLS.items() if symbol is not None}
            or any(x.get("request_identity") != _fingerprint({
                k: v for k, v in x.items() if k != "request_identity"
            }) for x in tickets)):
        raise CandidateChainCacheError("selected quote plan is malformed")
    if not 0 <= max_new_requests <= MAX_NEW_REQUESTS:
        raise CandidateChainCacheError("new quote request budget outside 0..11")
    if max_new_requests and not (authorize and confirm_paid and confirm_private_use):
        raise CandidateChainCacheError("all three explicit paid-source confirmations required")
    if max_new_requests and not (token or "").strip():
        raise CandidateChainCacheError("MarketData token missing; no provider attempt")
    if not max_new_requests and (authorize or confirm_paid or confirm_private_use):
        raise CandidateChainCacheError("authorization requires positive bounded request count")
    report_rows: list[dict[str, Any]] = []
    new = observed = 0
    remaining: int | None = None
    getter = transport or _transport
    for ticket in tickets:
        paths = _paths(settings, ticket)
        receipt = _intact(ticket, paths, signature)
        if receipt is None and new < max_new_requests and (
            remaining is None or remaining >= MIN_REMAINING_CREDITS
        ) and observed < MAX_OBSERVED_CREDITS:
            # Reserve the entire maximum response size, not a guessed one-credit charge.
            storage_guard(settings, category="options_candidate_cache",
                          projected_additional_bytes=MAX_RAW_BYTES + 8192)
            attempt = {
                "contract": CONTRACT, "plan_fingerprint": signature,
                "request_identity": ticket["request_identity"],
                "option_symbol": ticket["option_symbol"], "automatic_retry_permitted": False,
            }
            attempt["intent_fingerprint"] = _fingerprint(attempt)
            _exclusive_write(paths[2], attempt)
            try:
                http, raw, headers = getter(ticket, (token or "").strip())
            except Exception as exc:
                raise CandidateChainCacheError(
                    "quote transport uncertain after durable intent; preserve original, no retry"
                ) from exc
            if (type(http) is not int or not 100 <= http <= 599
                    or not isinstance(raw, bytes) or len(raw) > MAX_RAW_BYTES
                    or not isinstance(headers, dict)):
                raise CandidateChainCacheError("invalid/oversized quote response after intent; preserve")
            classification, safe = _classify(ticket, http, raw)
            credit = rate_limit_snapshot(headers)
            if (type(credit["consumed"]) is not int or credit["consumed"] < 0
                    or type(credit["remaining"]) is not int or credit["remaining"] < 0):
                classification = "QUARANTINED_CREDIT_HEADERS"
            status = "COMPLETE_SOURCE_ONLY" if classification == "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY" else (
                "EXACT_QUERY_SOURCE_GAP" if classification == "EXACT_QUERY_NO_DATA" else "QUARANTINED_REVIEW_REQUIRED"
            )
            _exclusive_write(paths[0], raw)
            receipt = {
                "contract": CONTRACT, "plan_fingerprint": signature,
                "request_identity": ticket["request_identity"], "option_symbol": ticket["option_symbol"],
                "status": status, "http_status": http, "classification": classification,
                "body_sha256": _sha(raw), "body_bytes": len(raw), "safe_summary": safe,
                "rate_limit": credit, "subscription_retention_required": True,
                "no_deliverable_fill_or_pnl_authority": True,
            }
            receipt["receipt_fingerprint"] = _fingerprint(receipt)
            _exclusive_write(paths[1], receipt)
            new += 1
            if progress:
                progress({"ticker": ticket["ticker"], "option_symbol": ticket["option_symbol"],
                          "classification": classification, "http_status": http,
                          "safe_summary": safe, "rate_limit": credit})
            if status == "QUARANTINED_REVIEW_REQUIRED":
                raise CandidateChainCacheError(
                    f"{ticket['ticker']} original quote response quarantined: HTTP={http} "
                    f"classification={classification} sha256={receipt['body_sha256']}; do not retry"
                )
            remaining = credit["remaining"]
            observed += credit["consumed"]
        if receipt is None:
            report_rows.append({"ticker": ticket["ticker"], "status": "PENDING_NEVER_ATTEMPTED"})
        else:
            report_rows.append({"ticker": ticket["ticker"], "status": receipt["classification"],
                                "rows": receipt["safe_summary"]["observed_rows"],
                                "receipt_fingerprint": receipt["receipt_fingerprint"]})
    report = {
        "contract": CONTRACT, "quote_plan_fingerprint": signature,
        "status": "COMPLETE_SOURCE_ONLY" if all(x["status"] != "PENDING_NEVER_ATTEMPTED" for x in report_rows) else "PARTIAL_SOURCE_ONLY",
        "new_provider_attempts": new, "observed_credits_consumed_this_run": observed,
        "last_provider_remaining": remaining,
        "source_series": sum(x["status"] == "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY" for x in report_rows),
        "exact_no_data_series": sum(x["status"] == "EXACT_QUERY_NO_DATA" for x in report_rows),
        "pending": sum(x["status"] == "PENDING_NEVER_ATTEMPTED" for x in report_rows),
        "historical_deliverables_verified": 0, "executable_option_prices": 0,
        "option_pnl_authority": False, "results": report_rows,
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
