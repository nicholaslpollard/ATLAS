from __future__ import annotations

"""Historical point-in-time reference dossiers for the frozen 2025 CALL shortlist.

This is a NEW exact-contract reference source, not a re-run of the chain pilot.
Every potentially billable request receives an exclusive durable intent marker
before transport; neither missing receipts nor quarantines are retried. A 200
reference row may provide structural terms, but never alone proves a historical
standard deliverable, liquid quote, fill or P&L.
"""

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, _fingerprint,
)
from packages.data.marketdata_candidate_2025_structural_call_shortlist_v1 import (
    CONTRACT as SHORTLIST_CONTRACT, FROZEN_CLOSEOUT,
    FROZEN_PLAN, OUTPUT_REL as SHORTLIST_REL,
)

CONTRACT = "atlas-marketdata-2025-exact-contract-reference-dossier-v1"
FROZEN_SHORTLIST = "e5a8347fa346934d908d925b9fdbf667d7a458d010bf51ce8e27324fbbc01268"
CACHE_REL = "data/options/candidate_cache/reference/massive_exact_2025_v1"
PLAN_REL = "data/options/manifests/marketdata_candidate_2025_exact_reference_plan_v1_d6c924cf5006d295.json"
MIN_REQUEST_INTERVAL_SECONDS = 13.0  # <=5 reference GET starts/min, single worker
MAX_NEW_REQUESTS = 11
MAX_BODY_BYTES = 256 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
OPTION_RE = re.compile(r"^([A-Z][A-Z0-9.]*)?(\d{6})([CP])(\d{8})$")

# These freeze the operator's actual output, not fabricated provider inventory.
FROZEN_SYMBOLS = {
    "AGIO": "AGIO251017C00040000",
    "AMGN": "AMGN251219C00320000",
    "ATRC": "ATRC251017C00035000",
    "BANF": "BANF250815C00130000",
    "DAKT": "DAKT250815C00015000",
    "FSLY": None,
    "ISRG": "ISRG260116C00565000",
    "LNT": "LNT251121C00067500",
    "OLLI": "OLLI250417C00105000",
    "SRRK": "SRRK250221C00045000",
    "TEM": "TEM250620C00064000",
    "TSLA": "TSLA250417C00300000",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean is not a contract quantity")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("nonfinite contract quantity")
    return number


def _symbol_terms(symbol: str) -> tuple[str, str, str]:
    match = OPTION_RE.fullmatch(symbol)
    if not match:
        raise CandidateChainCacheError("frozen provisional symbol has invalid OCC structure")
    root, compact, side, numeric_strike = match.groups()
    expiry = date.fromisoformat("20" + compact[:2] + "-" + compact[2:4] + "-" + compact[4:]).isoformat()
    if side != "C":
        raise CandidateChainCacheError("reference gate only accepts frozen CALL symbols")
    return root, expiry, str(Decimal(numeric_strike) / Decimal(1000))


def read_accepted_shortlist(settings: AtlasSettings) -> dict[str, Any]:
    path = settings.resolved_path(SHORTLIST_REL)
    if not path.is_file() or path.is_symlink():
        raise CandidateChainCacheError("accepted private PIT shortlist is missing or linked")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        base = dict(value)
        signature = base.pop("shortlist_fingerprint")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise CandidateChainCacheError("accepted PIT shortlist unreadable") from exc
    if (signature != _fingerprint(base) or signature != FROZEN_SHORTLIST
            or value.get("contract") != SHORTLIST_CONTRACT
            or value.get("status") != "PROVISIONAL_STRUCTURAL_SHORTLIST_ONLY"
            or value.get("source_plan_fingerprint") != FROZEN_PLAN
            or value.get("source_closeout_fingerprint") != FROZEN_CLOSEOUT
            or value.get("provisional_structural_symbols") != 11
            or value.get("exact_query_no_data") != 1
            or value.get("stock_opportunities") != 12
            or not isinstance(value.get("opportunities"), list)
            or len(value["opportunities"]) != 12):
        raise CandidateChainCacheError("private PIT shortlist fingerprint/cohort mismatch")
    return value


def build_exact_reference_plan(shortlist: dict[str, Any]) -> dict[str, Any]:
    """No files, provider requests, current reference or realized outcomes."""
    if shortlist.get("shortlist_fingerprint") != FROZEN_SHORTLIST:
        raise CandidateChainCacheError("reference plan requires accepted shortlist fingerprint")
    opportunities = shortlist["opportunities"]
    observed: set[str] = set()
    tickets: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in opportunities:
        symbol = FROZEN_SYMBOLS.get(row["ticker"], "UNEXPECTED")
        if row["ticker"] in observed or symbol == "UNEXPECTED":
            raise CandidateChainCacheError("duplicate/unrecognized frozen shortlist ticker")
        observed.add(row["ticker"])
        if symbol is None:
            if (row["ticker"] != "FSLY"
                    or row["source_status"] != "EXACT_QUERY_NO_DATA"
                    or row["provisional_nearest_atm_call"] is not None
                    or row["structural_call_count"] != 0):
                raise CandidateChainCacheError("FSLY source gap differs from frozen result")
            excluded.append({
                "ticker": "FSLY", "opportunity_id": row["opportunity_id"],
                "status": "EXACT_QUERY_SOURCE_GAP_NO_REFERENCE_TICKET",
            })
            continue
        if (row["source_status"] != "COMPLETE_ORIGINAL_CHAIN"
                or row["provisional_nearest_atm_call"] != symbol
                or not row["ranked_structural_calls"]
                or row["ranked_structural_calls"][0]["option_symbol"] != symbol
                or row["final_executable_option_contract_selected"] is not False
                or row["historical_quote_or_fill_price_validated"] is not False):
            raise CandidateChainCacheError("frozen provisional contract selection differs")
        root, expiry, strike = _symbol_terms(symbol)
        if root != row["ticker"] or expiry != row["expiration"] or _decimal(strike) != _decimal(row["provisional_strike"]):
            raise CandidateChainCacheError("OCC identity not bound to exact frozen strike/expiration")
        snapshot = date.fromisoformat(row["chain_snapshot_date"]).isoformat()
        if date.fromisoformat(snapshot) >= date.fromisoformat(expiry):
            raise CandidateChainCacheError("reference as-of must precede expiration")
        # Never query present-day reference for a historical contract and call it PIT.
        ticket: dict[str, Any] = {
            "opportunity_id": row["opportunity_id"],
            "ticker": root,
            "option_symbol": symbol,
            "massive_ticker": "O:" + symbol,
            "as_of": snapshot,
            "expiration": expiry,
            "strike": strike,
            "contract_type": "call",
            "source_chain_sha256": row["source_chain_body_sha256"],
            "source_shortlist_fingerprint": FROZEN_SHORTLIST,
            "source_role": "PIT_STRUCTURAL_TERMS_ONLY",
        }
        ticket["request_identity"] = _fingerprint(ticket)
        tickets.append(ticket)
    if observed != set(FROZEN_SYMBOLS) or len(tickets) != 11 or len(excluded) != 1:
        raise CandidateChainCacheError("frozen 11 plus FSLY exact-gap cohort differs")
    tickets.sort(key=lambda x: (x["ticker"], x["option_symbol"]))
    result: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "EXACT_HISTORICAL_REFERENCE_PLAN",
        "authority": "DEVELOPMENT_REFERENCE_ONLY_NO_OPTION_PRICE",
        "shortlist_fingerprint": FROZEN_SHORTLIST,
        "frozen_stock_plan_fingerprint": FROZEN_PLAN,
        "historical_as_of_basis": "PREVIOUS_SESSION_CHAIN_SNAPSHOT_DATE",
        "requests": tickets,
        "source_gap_exclusions": excluded,
        "max_new_requests_per_authorized_run": MAX_NEW_REQUESTS,
        "minimum_seconds_between_provider_request_starts": MIN_REQUEST_INTERVAL_SECONDS,
        "automatic_retries_allowed": False,
        "no_current_reference_substitution": True,
        "no_independent_historical_deliverable_or_fill_pnl_authority": True,
    }
    result["plan_fingerprint"] = _fingerprint(result)
    return result


def _paths(settings: AtlasSettings, ticket: dict[str, Any]) -> tuple[Path, Path, Path]:
    digest = ticket["request_identity"]
    if not SHA_RE.fullmatch(digest):
        raise CandidateChainCacheError("invalid exact-reference request identity")
    parent = settings.resolved_path(CACHE_REL) / digest[:2]
    return tuple(parent / (digest + suffix) for suffix in (".json", ".receipt.json", ".attempt.json"))


def _assert_intact(ticket: dict[str, Any], paths: tuple[Path, Path, Path],
                   *, plan_fingerprint: str) -> dict[str, Any] | None:
    body, receipt_path, intent_path = paths
    exists = [x.exists() or x.is_symlink() for x in paths]
    if not any(exists):
        return None
    if not all(exists) or any(x.is_symlink() or not x.is_file() for x in paths):
        raise CandidateChainCacheError("unresolved original reference attempt; do not re-request")
    try:
        raw = body.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
        receipt_copy = dict(receipt)
        receipt_sig = receipt_copy.pop("receipt_fingerprint")
        intent_copy = dict(intent)
        intent_sig = intent_copy.pop("intent_fingerprint")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise CandidateChainCacheError("historical reference evidence unreadable; preserve") from exc
    if (receipt_sig != _fingerprint(receipt_copy) or intent_sig != _fingerprint(intent_copy)
            or receipt.get("contract") != CONTRACT or intent.get("contract") != CONTRACT
            or intent.get("plan_fingerprint") != plan_fingerprint
            or receipt.get("request_identity") != ticket["request_identity"]
            or intent.get("request_identity") != ticket["request_identity"]
            or receipt.get("body_sha256") != _sha(raw)
            or receipt.get("body_bytes") != len(raw)
            or intent.get("automatic_retry_permitted") is not False):
        raise CandidateChainCacheError("reference evidence/plan hash mismatch; preserve originals")
    return receipt


def _classify_reference(ticket: dict[str, Any], raw: bytes, status: int) -> tuple[str, dict[str, Any]]:
    """Never promote a reference response to independent deliverable authority."""
    safe: dict[str, Any] = {
        "exact_identity_match": False,
        "shares_per_contract": None,
        "exercise_style": None,
        "additional_underlyings": "UNKNOWN",
        "cfi": None,
        "historical_standard_deliverable_verified": False,
        "option_quote_or_fill_verified": False,
    }
    if status != 200:
        return "HTTP_NON_200_REVIEW_REQUIRED", safe
    try:
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("status") not in (None, "OK"):
            return "PROVIDER_SCHEMA_REVIEW_REQUIRED", safe
        row = payload.get("results", payload.get("result"))
        if isinstance(row, list):
            if len(row) != 1: return "PROVIDER_SCHEMA_REVIEW_REQUIRED", safe
            row = row[0]
        if not isinstance(row, dict):
            return "PROVIDER_SCHEMA_REVIEW_REQUIRED", safe
        match = (
            row.get("ticker") == ticket["massive_ticker"]
            and row.get("underlying_ticker") == ticket["ticker"]
            and row.get("contract_type") == "call"
            and row.get("expiration_date") == ticket["expiration"]
            and _decimal(row.get("strike_price")) == _decimal(ticket["strike"])
        )
        safe["exact_identity_match"] = bool(match)
        if not match:
            return "PIT_REFERENCE_IDENTITY_CONFLICT", safe
        shares = _decimal(row.get("shares_per_contract"))
        safe["shares_per_contract"] = str(shares)
        style = row.get("exercise_style")
        safe["exercise_style"] = style if style in ("american", "european", "bermudan") else "OTHER_OR_UNKNOWN"
        extra = row.get("additional_underlyings", "NOT_REPORTED")
        safe["additional_underlyings"] = (
            "NOT_REPORTED" if extra == "NOT_REPORTED" else
            "NONE_REPORTED" if extra in (None, [], {}) else "PRESENT_OR_AMBIGUOUS"
        )
        cfi = row.get("cfi")
        safe["cfi"] = cfi if isinstance(cfi, str) and len(cfi) <= 12 else None
        if (shares != Decimal(100)
                or safe["exercise_style"] != "american"
                or safe["additional_underlyings"] == "PRESENT_OR_AMBIGUOUS"):
            return "HISTORICAL_TERMS_ADJUSTED_OR_AMBIGUOUS", safe
        # A bare 100-share attribute and absent additional_underlyings are not
        # a complete corporate-action / OCC deliverable proof.
        return "PIT_REFERENCE_TERMS_CONSISTENT_DELIVERABLE_UNVERIFIED", safe
    except (ValueError, InvalidOperation, TypeError, KeyError, OverflowError):
        return "PROVIDER_SCHEMA_REVIEW_REQUIRED", safe


def _url(settings: AtlasSettings, ticket: dict[str, Any]) -> str:
    root = settings.massive.provider.rest_base_url.rstrip("/")
    parts = urllib.parse.urlsplit(root)
    if parts.scheme != "https" or parts.username or parts.password or not parts.netloc:
        raise CandidateChainCacheError("historical reference requires configured HTTPS API base")
    endpoint = settings.data.research.options.reference_endpoint_path
    return root + endpoint + "/" + urllib.parse.quote(ticket["massive_ticker"], safe="") + "?" + urllib.parse.urlencode({"as_of": ticket["as_of"]})


def _transport(url: str, api_key: str, *, timeout: float = 25.0) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + api_key, "Accept": "application/json",
                      "User-Agent": "ATLAS-exact-2025-reference-dossier/1"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_BODY_BYTES + 1)
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read(MAX_BODY_BYTES + 1)
        status = int(exc.code)
    if len(raw) > MAX_BODY_BYTES:
        raise CandidateChainCacheError("oversized provider response; preserve intent, no retry")
    return status, raw


def _exclusive_write(path: Path, value: dict[str, Any] | bytes) -> None:
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8") if isinstance(value, dict) else value
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def run_reference_dossiers(
    settings: AtlasSettings, plan: dict[str, Any], *,
    authorize_provider_reads: bool = False,
    confirm_reference_only: bool = False,
    max_new_requests: int = 0,
    transport: Callable[[str, str], tuple[int, bytes]] | None = None,
    api_key: str | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Read-only default; one new durable reference attempt per frozen symbol."""
    base = dict(plan)
    signature = base.pop("plan_fingerprint", None)
    expected = build_exact_reference_plan({"shortlist_fingerprint": FROZEN_SHORTLIST, "opportunities": [
        # Reconstructing from the current plan's own tickets is not authority.
    ]}) if False else None
    if signature != _fingerprint(base) or plan.get("contract") != CONTRACT or len(plan.get("requests", [])) != 11:
        raise CandidateChainCacheError("exact frozen reference plan is malformed")
    if not 0 <= max_new_requests <= MAX_NEW_REQUESTS:
        raise CandidateChainCacheError("new reference request budget outside 0..11")
    if max_new_requests and not (authorize_provider_reads and confirm_reference_only):
        raise CandidateChainCacheError("historical reference reads require explicit authorization")
    if not max_new_requests and authorize_provider_reads:
        raise CandidateChainCacheError("authorization requires positive bounded request count")
    if max_new_requests and (not api_key or not api_key.strip()):
        raise CandidateChainCacheError("Massive credential missing; no attempt recorded")

    items: list[dict[str, Any]] = []
    new = 0
    last_start: float | None = None
    getter = transport or _transport
    for ticket in plan["requests"]:
        paths = _paths(settings, ticket)
        result = _assert_intact(ticket, paths, plan_fingerprint=signature)
        if result is not None:
            if result["status"] != "COMPLETE_REFERENCE_RECEIPT":
                raise CandidateChainCacheError("stored reference quarantine; do not retry")
            items.append({"ticker": ticket["ticker"], "option_symbol": ticket["option_symbol"],
                          "status": result["classification"],
                          "receipt_fingerprint": result["receipt_fingerprint"],
                          "new_provider_attempt": False})
            continue
        if new >= max_new_requests:
            items.append({"ticker": ticket["ticker"], "option_symbol": ticket["option_symbol"],
                          "status": "PENDING_NEVER_ATTEMPTED", "new_provider_attempt": False})
            continue
        url = _url(settings, ticket)
        body, receipt_path, intent_path = paths
        intent = {
            "contract": CONTRACT, "plan_fingerprint": signature,
            "request_identity": ticket["request_identity"],
            "option_symbol": ticket["option_symbol"], "as_of": ticket["as_of"],
            "automatic_retry_permitted": False, "request_method": "GET",
        }
        intent["intent_fingerprint"] = _fingerprint(intent)
        _exclusive_write(intent_path, intent)
        # The durable marker is written BEFORE pacing and transport.
        if last_start is not None:
            sleeper(max(0.0, MIN_REQUEST_INTERVAL_SECONDS - (monotonic() - last_start)))
        last_start = monotonic()
        try:
            status, raw = getter(url, api_key)
        except Exception as exc:
            raise CandidateChainCacheError(
                "reference transport failed after attempt marker; preserve and review, no automatic retry"
            ) from exc
        if not isinstance(raw, bytes) or len(raw) > MAX_BODY_BYTES or not (100 <= status <= 599):
            raise CandidateChainCacheError("unbounded/invalid provider response after attempt; preserve")
        classification, safe = _classify_reference(ticket, raw, status)
        _exclusive_write(body, raw)
        receipt: dict[str, Any] = {
            "contract": CONTRACT,
            "plan_fingerprint": signature,
            "request_identity": ticket["request_identity"],
            "option_symbol": ticket["option_symbol"],
            "as_of": ticket["as_of"],
            "status": "COMPLETE_REFERENCE_RECEIPT" if status == 200 and classification in (
                "PIT_REFERENCE_TERMS_CONSISTENT_DELIVERABLE_UNVERIFIED",
                "HISTORICAL_TERMS_ADJUSTED_OR_AMBIGUOUS",
            ) else "QUARANTINED_REVIEW_REQUIRED",
            "http_status": status, "classification": classification,
            "raw_http_body_exact": True, "body_sha256": _sha(raw),
            "body_bytes": len(raw), "safe_terms": safe,
            "no_independent_historical_deliverable_or_price_authority": True,
        }
        receipt["receipt_fingerprint"] = _fingerprint(receipt)
        _exclusive_write(receipt_path, receipt)
        new += 1
        items.append({
            "ticker": ticket["ticker"], "option_symbol": ticket["option_symbol"],
            "status": classification, "receipt_fingerprint": receipt["receipt_fingerprint"],
            "new_provider_attempt": True,
        })
        if receipt["status"] != "COMPLETE_REFERENCE_RECEIPT":
            raise CandidateChainCacheError(
                "reference response quarantined: " + classification + "; no automatic retry"
            )

    report = {
        "contract": CONTRACT, "plan_fingerprint": signature,
        "status": "SOURCE_REFERENCE_RECEIPTS_COMPLETE" if all(x["status"] != "PENDING_NEVER_ATTEMPTED" for x in items) else "PARTIAL_NEW_SOURCE",
        "new_provider_attempts_this_run": new,
        "previous_receipts_reused": sum(x.get("new_provider_attempt") is False and x["status"] != "PENDING_NEVER_ATTEMPTED" for x in items),
        "pending": sum(x["status"] == "PENDING_NEVER_ATTEMPTED" for x in items),
        "independent_deliverable_verified": 0, "final_executable_contracts": 0,
        "provider_billing_not_inferred_from_request_count": True,
        "no_quote_or_option_pnl_authority": True, "results": items,
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report


def write_reference_plan(settings: AtlasSettings, plan: dict[str, Any]) -> tuple[str, Path]:
    path = settings.resolved_path(PLAN_REL)
    raw = (json.dumps(plan, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists() or path.is_symlink():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != raw:
            raise CandidateChainCacheError("original exact-reference plan differs; never overwrite")
        return "REUSED_EXACT_REFERENCE_PLAN", path
    _exclusive_write(path, raw)
    if path.read_bytes() != raw:
        raise CandidateChainCacheError("reference plan write read-back mismatch")
    return "WRITTEN_NEW_REFERENCE_PLAN", path
