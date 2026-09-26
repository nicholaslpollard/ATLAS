from __future__ import annotations

"""Offline, outcome-blind structural CALL shortlist for the frozen 2025 pilot.

This is NOT an executable option selector. It uses original previous-session
historical chain identities and the accepted next-session raw stock OPEN known
at the 09:35 ET decision. It never ranks by same-day option quote/last/volume,
future returns, news, realized outcomes or historical Greeks.
"""

import json
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, _fingerprint, _paths, _valid_receipt,
    verify_candidate_plan,
)
from packages.data.marketdata_candidate_2025_source_closeout_v1 import (
    CONTRACT as CLOSEOUT_CONTRACT, FROZEN_FSLY, FROZEN_FSLY_BODY,
    FROZEN_FSLY_PROOF, FROZEN_PLAN, OUTPUT_REL as CLOSEOUT_REL,
)
from packages.providers.marketdata_app import array_rows

CONTRACT = "atlas-marketdata-2025-pit-structural-call-shortlist-v1"
FROZEN_CLOSEOUT = "98b47179a2e563fb9d97ed16fec02d9a962f8f8788e88952f64c022f34a49daa"
OUTPUT_REL = (
    "data/options/manifests/"
    "marketdata_candidate_2025_structural_call_shortlist_v1_d6c924cf5006d295.json"
)
EASTERN = ZoneInfo("America/New_York")
POLICY = "NEAREST_ATM_TO_PIT_RAW_OPEN_TIE_PREFER_CALL_OTM"
MAX_PLAN_REQUESTS = 12


def read_frozen_source_closeout(settings: AtlasSettings) -> dict[str, Any]:
    """Read the existing accepted closeout exactly once; no repeated closeout run."""
    path = settings.resolved_path(CLOSEOUT_REL)
    if not path.is_file() or path.is_symlink():
        raise CandidateChainCacheError("accepted local closeout missing or is a file link")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        payload = dict(result)
        signature = payload.pop("closeout_fingerprint")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise CandidateChainCacheError("accepted closeout is unreadable") from exc
    if (
        signature != _fingerprint(payload)
        or signature != FROZEN_CLOSEOUT
        or result.get("contract") != CLOSEOUT_CONTRACT
        or result.get("status") != "COMPLETE_WITH_SOURCE_GAPS"
        or result.get("plan_fingerprint") != FROZEN_PLAN
        or result.get("verified_complete_chains") != 11
        or result.get("exact_query_no_data") != 1
        or result.get("pending") != 0
        or result.get("verified_opportunities") != 12
        or not isinstance(result.get("requests"), list)
        or not isinstance(result.get("opportunities"), list)
        or len(result["requests"]) != 12
        or len(result["opportunities"]) != 12
    ):
        raise CandidateChainCacheError("accepted closeout identity/status does not match frozen evidence")
    return result


def _positive_decimal(value: object, *, label: str) -> Decimal:
    if isinstance(value, bool):
        raise CandidateChainCacheError(f"{label} invalid numeric value")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CandidateChainCacheError(f"{label} invalid numeric value") from exc
    if not number.is_finite() or number <= 0:
        raise CandidateChainCacheError(f"{label} must be finite and positive")
    return number


def rank_structural_calls(
    rows: tuple[dict[str, Any], ...],
    raw_stock_open: Decimal,
) -> list[dict[str, Any]]:
    """Pure structural ranking: no quote, Greeks, OI, liquidity or outcome fields."""
    options: list[tuple[tuple[Decimal, int, Decimal, str], dict[str, Any]]] = []
    seen: set[str] = set()
    for row in rows:
        if row["side"] != "call":
            continue
        symbol = row["optionSymbol"]
        strike = _positive_decimal(row["strike"], label="option strike")
        if not isinstance(symbol, str) or symbol in seen:
            raise CandidateChainCacheError("duplicate/invalid structural CALL identity")
        seen.add(symbol)
        # Equal ATM distance prefers the out-of-the-money CALL. No same-session
        # option quote or later stock price is involved.
        key = (abs(strike - raw_stock_open), 0 if strike >= raw_stock_open else 1, strike, symbol)
        options.append((key, {
            "option_symbol": symbol,
            "strike": str(strike),
            "distance_from_raw_open": str(abs(strike - raw_stock_open)),
            "call_moneyness_at_raw_open": (
                "OTM" if strike > raw_stock_open else "ATM" if strike == raw_stock_open else "ITM"
            ),
            "structural_identity_only": True,
            "standard_deliverable_independently_validated": False,
            "historical_entry_quote_verified": False,
        }))
    options.sort(key=lambda item: item[0])
    return [dict(rank=index, **record) for index, (_key, record) in enumerate(options, 1)]


def build_structural_call_shortlist(
    settings: AtlasSettings,
    plan: dict[str, Any],
    closeout: dict[str, Any],
) -> dict[str, Any]:
    verified = verify_candidate_plan(plan)
    if verified["plan_fingerprint"] != FROZEN_PLAN or len(verified["requests"]) != MAX_PLAN_REQUESTS:
        raise CandidateChainCacheError("frozen candidate plan differs")
    if (closeout.get("closeout_fingerprint") != FROZEN_CLOSEOUT
            or closeout.get("plan_fingerprint") != FROZEN_PLAN):
        raise CandidateChainCacheError("selector requires the accepted original source closeout")
    closeout_rows = closeout["requests"]
    original_opportunities = {x["opportunity_id"]: x for x in closeout["opportunities"]}
    if len(original_opportunities) != 12:
        raise CandidateChainCacheError("accepted closeout opportunities are missing/duplicated")

    decisions: list[dict[str, Any]] = []
    complete = 0
    source_gaps = 0
    calls_seen = 0
    for index, request in enumerate(verified["requests"]):
        prior = closeout_rows[index]
        if (prior["request_identity"] != request["request_identity"]
                or prior["ticker"] != request["ticker"]
                or prior["snapshot_date"] != request["params"]["date"]
                or prior["expiration"] != request["params"]["expiration"]
                or prior["strike_window"] != request["params"]["strike"]
                or prior["opportunity_ids"] != request["opportunity_ids"]):
            raise CandidateChainCacheError("original closeout request lineage differs from plan")
        paths = _paths(settings, request["request_identity"])
        receipt = _valid_receipt(
            paths, request, expected_plan_fingerprint=FROZEN_PLAN,
        )
        if receipt is None or receipt["body_sha256"] != prior["raw_body_sha256"]:
            raise CandidateChainCacheError("original chain receipt differs from accepted closeout")
        gap = receipt["status"] == "VERIFIED_NO_DATA"
        if gap:
            if (request["request_identity"] != FROZEN_FSLY
                    or receipt["body_sha256"] != FROZEN_FSLY_BODY
                    or receipt["no_data_proof"] != FROZEN_FSLY_PROOF
                    or prior["status"] != "SOURCE_NO_DATA_VERIFIED"):
                raise CandidateChainCacheError("unaccepted exact-query no-data evidence")
            rows: tuple[dict[str, Any], ...] = ()
            source_gaps += 1
        else:
            if (receipt["status"] != "COMPLETE"
                    or prior["status"] != "REUSED_VERIFIED"
                    or prior["row_count"] != receipt["row_count"]):
                raise CandidateChainCacheError("unexpected non-complete chain source")
            try:
                payload = json.loads(paths.body.read_bytes().decode("utf-8"))
                rows = array_rows(payload)
            except (OSError, ValueError, TypeError) as exc:
                raise CandidateChainCacheError("verified chain could not be locally decoded") from exc
            if len(rows) != receipt["row_count"]:
                raise CandidateChainCacheError("chain row count differs from original verified receipt")
            complete += 1

        for opportunity_id in request["opportunity_ids"]:
            source = verified["source_bindings"][opportunity_id]
            original = original_opportunities.get(opportunity_id)
            if (original is None or original["request_identity"] != request["request_identity"]
                    or original["requested_side"] != source["side"]
                    or original["decision_at_utc"] != source["decision_at_utc"]):
                raise CandidateChainCacheError("stock opportunity changed since accepted closeout")
            if source["side"] != "call":
                raise CandidateChainCacheError("frozen LONG-stock CALL cohort only")
            decision = datetime.fromisoformat(source["decision_at_utc"].replace("Z", "+00:00"))
            if decision.tzinfo is None or decision.utcoffset() != timedelta(0):
                raise CandidateChainCacheError("decision clock must be explicit UTC")
            snapshot = date.fromisoformat(request["params"]["date"])
            expiry = date.fromisoformat(request["params"]["expiration"])
            decision_local = decision.astimezone(EASTERN)
            decision_day = decision_local.date()
            if (decision_local.hour, decision_local.minute, decision_local.second, decision_local.microsecond) != (9, 35, 0, 0):
                raise CandidateChainCacheError("frozen decision must be 09:35 Eastern after raw stock OPEN")
            if not snapshot < decision_day <= expiry:
                raise CandidateChainCacheError("chain EOD must predate decision and expiry")
            raw_open = _positive_decimal(source["raw_underlying_price"], label="accepted raw stock OPEN")
            ranked = rank_structural_calls(rows, raw_open)
            calls_seen += len(ranked)
            if gap and ranked:
                raise CandidateChainCacheError("source gap cannot generate a structural option")
            if len(ranked) != (original["observed_same_side_rows"] or 0):
                raise CandidateChainCacheError("CALL row count differs from accepted source closeout")
            preferred = ranked[0] if ranked else None
            decisions.append({
                "opportunity_id": opportunity_id,
                "request_identity": request["request_identity"],
                "ticker": request["ticker"],
                "stock_decision_at_utc": source["decision_at_utc"],
                "accepted_raw_stock_open": str(raw_open),
                "stock_price_basis": "RAW_AS_TRADED",
                "chain_snapshot_date": request["params"]["date"],
                "expiration": request["params"]["expiration"],
                "source_chain_body_sha256": receipt["body_sha256"],
                "source_status": "EXACT_QUERY_NO_DATA" if gap else "COMPLETE_ORIGINAL_CHAIN",
                "structural_call_count": len(ranked),
                "policy": POLICY,
                "provisional_nearest_atm_call": (
                    preferred["option_symbol"] if preferred is not None else None
                ),
                "provisional_strike": preferred["strike"] if preferred is not None else None,
                "ranked_structural_calls": ranked,
                "abstention_reason": "FSLY_EXACT_QUERY_NO_DATA" if gap else (
                    "NO_CALL_IN_COMPLETED_EXACT_CHAIN" if not ranked else None
                ),
                "quote_horizon_planning_only": {
                    "from_inclusive": decision_day.isoformat(),
                    "to_exclusive": (expiry + timedelta(days=1)).isoformat(),
                    "decision_is_intraday_0935_no_same_day_eod_entry_price": True,
                } if preferred is not None else None,
                "deliverable_and_corporate_action_status": "UNVERIFIED",
                "final_executable_option_contract_selected": False,
                "historical_quote_or_fill_price_validated": False,
                "option_pnl_authority": False,
            })
    if complete != 11 or source_gaps != 1 or len(decisions) != 12:
        raise CandidateChainCacheError("structural shortlist requires exact closed 11+1 cohort")
    result: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "PROVISIONAL_STRUCTURAL_SHORTLIST_ONLY",
        "authority": "DEVELOPMENT_SOURCE_ONLY_NO_OPTION_PRICE",
        "source_plan_fingerprint": FROZEN_PLAN,
        "source_closeout_fingerprint": FROZEN_CLOSEOUT,
        "ranking_policy": POLICY,
        "outcome_blind": True,
        "uses_only_original_prior_session_option_identity_and_pit_raw_stock_open": True,
        "excludes_quote_volume_oi_greeks_news_and_realized_outcomes_from_ranking": True,
        "complete_source_chains": complete,
        "exact_query_no_data": source_gaps,
        "stock_opportunities": len(decisions),
        "provisional_structural_symbols": sum(x["provisional_nearest_atm_call"] is not None for x in decisions),
        "source_call_rows_examined": calls_seen,
        "provider_reads": 0,
        "credits_consumed": 0,
        "independent_standard_deliverable_validation_required": True,
        "no_option_execution_price_pnl_strategy_paper_live_or_broker_authority": True,
        "opportunities": sorted(decisions, key=lambda item: item["opportunity_id"]),
    }
    result["shortlist_fingerprint"] = _fingerprint(result)
    return result


def write_local_shortlist(
    settings: AtlasSettings,
    result: dict[str, Any],
    *,
    authorize_local_write: bool = False,
) -> tuple[str, Path]:
    """Exclusive, idempotent private D:-bound write; original raw cache untouched."""
    path = settings.resolved_path(OUTPUT_REL)
    content = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists() or path.is_symlink():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != content:
            raise CandidateChainCacheError("existing structural shortlist differs; preserve original")
        return "REUSED_EXACT_STRUCTURAL_SHORTLIST", path
    if not authorize_local_write:
        return "PREVIEW_NO_WRITES", path
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise CandidateChainCacheError("concurrent shortlist appeared; inspect before continuing") from exc
    if path.read_bytes() != content:
        raise CandidateChainCacheError("shortlist write read-back failed; preserve file")
    return "WRITTEN_AND_REVERIFIED", path
