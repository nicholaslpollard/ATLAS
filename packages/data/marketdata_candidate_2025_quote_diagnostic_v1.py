from __future__ import annotations

"""Offline, source-bound descriptive audit of the already acquired 2025 CALL EOD series.

No external/provider reads. Original source receipts are rehashed for lineage, not
reacquired. No fill model, P&L, selector revision or scientific promotion.
"""

import json
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint
from packages.data import marketdata_candidate_2025_selected_quote_source_v1 as quote
from packages.providers.marketdata_app import array_rows

CONTRACT = "atlas-marketdata-2025-selected-eod-quote-offline-diagnostic-v1"
FROZEN_QUOTE_PLAN = "b15feb274a00e911a233572856254c5b1bc77b5a8930832b94d76659a16d6589"
ACCEPTED_SOURCE_RUN = "5912e0a4b9467a7dacf35044cfa4bc10791735e3ace3e7b50fa2ad3f38c743ea"
OUTPUT_REL = "data/options/manifests/marketdata_candidate_2025_eod_quote_diagnostic_v1_d6c924cf5006d295.json"
EASTERN = ZoneInfo("America/New_York")

# Frozen from the operator's complete 2026-09-26 acquisition output, not an
# independent scientific threshold or an inferred execution-quality verdict.
EXPECTED_SOURCE = {
    "AGIO": (36, 22, 9988),
    "AMGN": (31, 31, 9987),
    "ATRC": (26, 0, 9986),
    "BANF": (32, 0, 9985),
    "DAKT": (38, 3, 9984),
    "ISRG": (27, 25, 9983),
    "LNT": (26, 20, 9982),
    "OLLI": (21, 17, 9981),
    "SRRK": (27, 16, 9980),
    "TEM": (22, 22, 9979),
    "TSLA": (34, 34, 9978),
}


def _read_exact_plan(settings: AtlasSettings, rebuilt: dict[str, Any]) -> None:
    path = settings.resolved_path(quote.PLAN_REL)
    if not path.is_file() or path.is_symlink():
        raise CandidateChainCacheError("original quote plan is missing or linked")
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, TypeError, OSError) as exc:
        raise CandidateChainCacheError("original quote plan cannot be read") from exc
    if saved != rebuilt:
        raise CandidateChainCacheError("original quote plan differs from frozen saved plan")


def _observations(ticket: dict[str, Any], body: bytes) -> dict[str, Any]:
    """Only descriptive session activity; never turn an EOD price into an entry fill."""
    payload = json.loads(body.decode("utf-8"))
    rows = array_rows(payload)
    decision = datetime.fromisoformat(ticket["stock_decision_at_utc"].replace("Z", "+00:00"))
    if decision.tzinfo is None or decision.utcoffset() != UTC.utcoffset(None):
        raise CandidateChainCacheError("original decision timestamp is not UTC")
    local = decision.astimezone(EASTERN)
    if (local.hour, local.minute, local.second, local.microsecond) != (9, 35, 0, 0):
        raise CandidateChainCacheError("original decision is no longer 09:35 ET")
    day = local.date()

    positive: list[date] = []
    later_positive: list[date] = []
    both_sides = 0
    positive_both_sides = 0
    null_last = 0
    zero_volume_with_last = 0
    entry_day_rows = entry_day_positive = 0
    first = last = None
    for row in rows:
        session = datetime.fromtimestamp(int(Decimal(str(row["updated"]))), UTC).astimezone(EASTERN).date()
        first = min(first, session) if first is not None else session
        last = max(last, session) if last is not None else session
        vol = quote._decimal(row["volume"])
        if vol is None:
            raise CandidateChainCacheError("accepted source output unexpectedly has null volume")
        is_positive = vol > 0
        if is_positive:
            positive.append(session)
            if session > day:
                later_positive.append(session)
        if session == day:
            entry_day_rows += 1
            entry_day_positive += int(is_positive)
        bid, ask, last_price = (quote._decimal(row[field]) for field in ("bid", "ask", "last"))
        has_two_sided = bid is not None and ask is not None and bid > 0 and ask >= bid
        both_sides += int(has_two_sided)
        positive_both_sides += int(has_two_sided and is_positive)
        null_last += int(last_price is None or last_price <= 0)
        zero_volume_with_last += int(not is_positive and last_price is not None and last_price > 0)

    count = len(rows)
    if not count or count != len({datetime.fromtimestamp(int(Decimal(str(row["updated"]))), UTC).astimezone(EASTERN).date() for row in rows}):
        raise CandidateChainCacheError("accepted quote body has duplicate or missing source sessions")
    return {
        "total_eod_source_rows": count,
        "positive_volume_rows": len(positive),
        "zero_volume_rows": count - len(positive),
        "first_observed_session": first.isoformat(),
        "last_observed_session": last.isoformat(),
        "decision_session": day.isoformat(),
        "same_decision_day_eod_rows_unavailable_at_0935": entry_day_rows,
        "same_decision_day_positive_volume_eod_unavailable_at_0935": entry_day_positive,
        "first_positive_volume_source_session": min(positive).isoformat() if positive else None,
        "first_post_decision_positive_volume_source_session": min(later_positive).isoformat() if later_positive else None,
        "post_decision_positive_volume_source_sessions": len(later_positive),
        "observed_two_sided_eod_quote_geometry_rows": both_sides,
        "positive_volume_and_two_sided_eod_quote_context_rows": positive_both_sides,
        "null_or_nonpositive_last_rows": null_last,
        "zero_volume_with_positive_last_not_a_same_session_trade": zero_volume_with_last,
        "observation_classification": (
            "NO_POSITIVE_VOLUME_IN_SELECTED_SERIES"
            if not positive else
            "NO_LATER_POSITIVE_VOLUME_AFTER_0935_DECISION_SESSION"
            if not later_positive else "LATER_POSITIVE_VOLUME_OBSERVATIONS_ONLY"
        ),
        "historical_deliverable_certified": False,
        "intraday_quote_or_fill_verified": False,
        "eod_bid_ask_is_executable_fill": False,
        "option_pnl_authority": False,
    }


def build_offline_dossier(settings: AtlasSettings) -> dict[str, Any]:
    """One read-only workstation pass across 11 existing bodies/receipts."""
    shortlist, reference_plan = quote.read_accepted_inputs(settings)
    plan = quote.build_quote_plan(settings, shortlist, reference_plan)
    if plan["plan_fingerprint"] != FROZEN_QUOTE_PLAN:
        raise CandidateChainCacheError("quote plan fingerprint differs from accepted operator result")
    _read_exact_plan(settings, plan)
    outputs: list[dict[str, Any]] = []
    source_receipts: list[str] = []
    for ticket in plan["requests"]:
        body, receipt_path, intent_path = quote._paths(settings, ticket)
        receipt = quote._intact(ticket, (body, receipt_path, intent_path), FROZEN_QUOTE_PLAN)
        if (receipt is None or receipt["status"] != "COMPLETE_SOURCE_ONLY"
                or receipt["classification"] != "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY"
                or receipt["http_status"] != 203):
            raise CandidateChainCacheError("accepted exact original quote series missing or not source-complete")
        expected = EXPECTED_SOURCE[ticket["ticker"]]
        observed = receipt["safe_summary"]
        if (observed["observed_rows"] != expected[0]
                or observed["positive_volume_rows"] != expected[1]
                or observed["zero_volume_rows"] != expected[0] - expected[1]
                or receipt["rate_limit"]["consumed"] != 1
                or receipt["rate_limit"]["remaining"] != expected[2]):
            raise CandidateChainCacheError(
                "original receipt no longer matches operator-reported source counts/credits"
            )
        metrics = _observations(ticket, body.read_bytes())
        if (metrics["total_eod_source_rows"] != expected[0]
                or metrics["positive_volume_rows"] != expected[1]):
            raise CandidateChainCacheError("offline per-row observations disagree with original receipt")
        outputs.append({
            "ticker": ticket["ticker"],
            "option_symbol": ticket["option_symbol"],
            "request_identity": ticket["request_identity"],
            "source_body_sha256": receipt["body_sha256"],
            "source_receipt_fingerprint": receipt["receipt_fingerprint"],
            "reference_receipt_fingerprint": ticket["source_reference_receipt_fingerprint"],
            "metrics": metrics,
        })
        source_receipts.append(receipt["receipt_fingerprint"])
    if len(outputs) != 11 or len(set(source_receipts)) != 11:
        raise CandidateChainCacheError("frozen quote cohort missing or duplicate")
    aggregate = {
        "exact_series": len(outputs),
        "eod_rows": sum(x["metrics"]["total_eod_source_rows"] for x in outputs),
        "positive_volume_rows": sum(x["metrics"]["positive_volume_rows"] for x in outputs),
        "zero_volume_rows": sum(x["metrics"]["zero_volume_rows"] for x in outputs),
        "no_positive_volume_series": sorted(
            x["ticker"] for x in outputs
            if x["metrics"]["observation_classification"] == "NO_POSITIVE_VOLUME_IN_SELECTED_SERIES"
        ),
        "no_post_decision_positive_volume_series": sorted(
            x["ticker"] for x in outputs
            if x["metrics"]["first_post_decision_positive_volume_source_session"] is None
        ),
        "eod_two_sided_quote_geometry_rows": sum(
            x["metrics"]["observed_two_sided_eod_quote_geometry_rows"] for x in outputs
        ),
        "zero_volume_with_positive_last": sum(
            x["metrics"]["zero_volume_with_positive_last_not_a_same_session_trade"] for x in outputs
        ),
        "observed_marketdata_credits_in_original_run": 11,
        "new_provider_gets_this_diagnostic": 0,
    }
    if aggregate["eod_rows"] != 320 or aggregate["positive_volume_rows"] != 190 or aggregate["zero_volume_rows"] != 130:
        raise CandidateChainCacheError("source cohort aggregate no longer matches accepted output")
    result = {
        "contract": CONTRACT,
        "status": "OFFLINE_SOURCE_OBSERVATIONS_COMPLETE",
        "accepted_original_quote_run_fingerprint": ACCEPTED_SOURCE_RUN,
        "quote_plan_fingerprint": FROZEN_QUOTE_PLAN,
        "shortlist_fingerprint": quote.FROZEN_SHORTLIST,
        "reference_plan_fingerprint": quote.REFERENCE_PLAN_FINGERPRINT,
        "source_receipts_reused": len(outputs),
        "source_gap_excluded": "FSLY",
        "aggregate": aggregate,
        "per_contract": outputs,
        "interpretation": {
            "positive_volume": "observed EOD activity only, not intraday timing or executable fill",
            "zero_volume_last": "not evidence of a same-session trade",
            "two_sided_eod_geometry": "descriptive quote context only; no freshness or fill proof",
            "same_decision_day_eod": "not available at original 09:35 ET decision",
            "historical_reference_terms": "100-share/American structurally consistent, deliverable uncertified",
            "selection_policy": "unchanged original nearest ATM from raw stock open; no post-result reselection",
            "missing_sessions": "not independently certified zero volume or no quotes",
        },
        "historical_deliverable_certified": False,
        "option_execution_price_validated": False,
        "option_pnl_authority": False,
        "strategy_paper_live_or_broker_authority": False,
    }
    result["dossier_fingerprint"] = _fingerprint(result)
    return result


def write_local_dossier(settings: AtlasSettings, result: dict[str, Any], *, authorize: bool) -> tuple[str, Path]:
    path = settings.resolved_path(OUTPUT_REL)
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists() or path.is_symlink():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != raw:
            raise CandidateChainCacheError("original offline dossier differs; preserve original")
        return "REUSED_EXACT_OFFLINE_DOSSIER", path
    if not authorize:
        return "PREVIEW_NO_WRITES", path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != raw:
        raise CandidateChainCacheError("offline dossier write read-back failed")
    return "WRITTEN_NEW_OFFLINE_DOSSIER", path
