from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Any
from zoneinfo import ZoneInfo


CONTRACT = "atlas-marketdata-candidate-chain-batch-plan-v1"
EASTERN = ZoneInfo("America/New_York")
TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,12}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CENT = Decimal("0.01")
STRIKE_WINDOW_FRACTION = Decimal("0.08")
MAX_UNION_SPAN_FRACTION = Decimal("0.25")
MAX_OPPORTUNITIES = 10_000
MAX_CHAIN_GROUPS = 250
# This is a bound on *local planned groups*, not a provider request-per-minute cap.
# Provider concurrency and actual response-row/credit budgets belong to the future executor.
MIN_DTE = 7
MAX_DTE = 75


class CandidateBatchPlanError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CandidateOpportunity:
    opportunity_id: str
    ticker: str
    snapshot_date: date
    decision_at_utc: datetime
    raw_underlying_price: Decimal
    expiration: date
    side: str
    stock_source_sha256: str
    lower_strike: Decimal
    upper_strike: Decimal


@dataclass(frozen=True, slots=True)
class _MutableBatch:
    ticker: str
    snapshot_date: date
    expiration: date
    lower_strike: Decimal
    upper_strike: Decimal
    minimum_pit_price: Decimal
    opportunity_ids: tuple[str, ...]
    sides: tuple[str, ...]


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_date(value: object, name: str) -> date:
    if not isinstance(value, str):
        raise CandidateBatchPlanError(f"{name} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise CandidateBatchPlanError(f"{name} is not a valid ISO date") from exc
    if parsed.isoformat() != value:
        raise CandidateBatchPlanError(f"{name} must use YYYY-MM-DD")
    return parsed


def _parse_decision(value: object) -> datetime:
    if not isinstance(value, str):
        raise CandidateBatchPlanError("decision_at_utc must be an ISO timestamp")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CandidateBatchPlanError("decision_at_utc is malformed") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise CandidateBatchPlanError("decision_at_utc must have a timezone")
    if timestamp.utcoffset().total_seconds() != 0:
        raise CandidateBatchPlanError("decision_at_utc must explicitly be UTC")
    return timestamp.astimezone(UTC)


def _parse_opportunity(row: object) -> CandidateOpportunity:
    if not isinstance(row, dict):
        raise CandidateBatchPlanError("every opportunity must be an object")
    expected = {
        "opportunity_id", "ticker", "snapshot_date", "decision_at_utc",
        "raw_underlying_price", "underlying_price_basis", "expiration",
        "side", "stock_source_sha256",
    }
    if set(row) != expected:
        raise CandidateBatchPlanError(
            f"opportunity fields differ: missing={sorted(expected - set(row))}, "
            f"extra={sorted(set(row) - expected)}"
        )

    opportunity_id = row["opportunity_id"]
    if (
        not isinstance(opportunity_id, str)
        or not opportunity_id.strip()
        or len(opportunity_id) > 200
    ):
        raise CandidateBatchPlanError("opportunity_id must be a nonempty bounded string")

    ticker = row["ticker"]
    if not isinstance(ticker, str) or not TICKER_PATTERN.fullmatch(ticker):
        raise CandidateBatchPlanError(f"{opportunity_id}: invalid canonical ticker")

    source_sha = row["stock_source_sha256"]
    if not isinstance(source_sha, str) or not SHA256_PATTERN.fullmatch(source_sha):
        raise CandidateBatchPlanError(f"{opportunity_id}: missing stock-source SHA256")

    if row["underlying_price_basis"] != "RAW_AS_TRADED":
        raise CandidateBatchPlanError(
            f"{opportunity_id}: incompatible stock price adjustment basis"
        )

    if row["side"] not in {"call", "put"}:
        raise CandidateBatchPlanError(f"{opportunity_id}: side must be call or put")

    snapshot_date = _parse_date(row["snapshot_date"], "snapshot_date")
    decision_at_utc = _parse_decision(row["decision_at_utc"])
    if decision_at_utc.astimezone(EASTERN).date() <= snapshot_date:
        raise CandidateBatchPlanError(
            f"{opportunity_id}: source EOD snapshot must precede local decision date"
        )
    if snapshot_date > datetime.now(EASTERN).date():
        raise CandidateBatchPlanError(f"{opportunity_id}: future snapshot not allowed")

    expiration = _parse_date(row["expiration"], "expiration")
    dte = (expiration - snapshot_date).days
    if not MIN_DTE <= dte <= MAX_DTE:
        raise CandidateBatchPlanError(
            f"{opportunity_id}: expiration DTE outside {MIN_DTE}..{MAX_DTE}"
        )

    raw_price = row["raw_underlying_price"]
    if isinstance(raw_price, bool):
        raise CandidateBatchPlanError(f"{opportunity_id}: invalid stock price")
    try:
        price = Decimal(str(raw_price))
    except (ArithmeticError, ValueError) as exc:
        raise CandidateBatchPlanError(f"{opportunity_id}: invalid stock price") from exc
    if not price.is_finite() or not Decimal("0.01") <= price <= Decimal("1000000"):
        raise CandidateBatchPlanError(f"{opportunity_id}: invalid stock price")

    lower = (price * (Decimal(1) - STRIKE_WINDOW_FRACTION)).quantize(
        CENT, rounding=ROUND_FLOOR,
    )
    upper = (price * (Decimal(1) + STRIKE_WINDOW_FRACTION)).quantize(
        CENT, rounding=ROUND_CEILING,
    )
    lower = max(CENT, lower)
    if lower >= upper:
        raise CandidateBatchPlanError(f"{opportunity_id}: invalid strike interval")
    return CandidateOpportunity(
        opportunity_id=opportunity_id,
        ticker=ticker,
        snapshot_date=snapshot_date,
        decision_at_utc=decision_at_utc,
        raw_underlying_price=price,
        expiration=expiration,
        side=row["side"],
        stock_source_sha256=source_sha,
        lower_strike=lower,
        upper_strike=upper,
    )


def _join(left: _MutableBatch, item: CandidateOpportunity) -> _MutableBatch | None:
    # Do not bridge non-overlapping strike windows merely to save an API credit.
    if item.lower_strike > left.upper_strike or item.upper_strike < left.lower_strike:
        return None
    lo = min(left.lower_strike, item.lower_strike)
    hi = max(left.upper_strike, item.upper_strike)
    minimum_price = min(left.minimum_pit_price, item.raw_underlying_price)
    if (hi - lo) / minimum_price > MAX_UNION_SPAN_FRACTION:
        return None
    return _MutableBatch(
        ticker=left.ticker,
        snapshot_date=left.snapshot_date,
        expiration=left.expiration,
        lower_strike=lo,
        upper_strike=hi,
        minimum_pit_price=minimum_price,
        opportunity_ids=left.opportunity_ids + (item.opportunity_id,),
        sides=tuple(sorted(set(left.sides) | {item.side})),
    )


def plan_candidate_chain_batches(payload: object) -> dict[str, Any]:
    """Pure offline planning: zero network, zero filesystem and zero provider reads.

    Returned shared-chain requests are exploratory source-acquisition requests only;
    they cannot select an executable option or create historical option P&L.
    """
    if not isinstance(payload, dict) or set(payload) != {"opportunities", "purpose"}:
        raise CandidateBatchPlanError(
            "input must contain exactly 'purpose' and 'opportunities'"
        )
    if payload["purpose"] != "SOURCE_ACQUISITION_ONLY":
        raise CandidateBatchPlanError("purpose must be SOURCE_ACQUISITION_ONLY")
    raw = payload["opportunities"]
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_OPPORTUNITIES:
        raise CandidateBatchPlanError(
            f"opportunities must contain 1..{MAX_OPPORTUNITIES} rows"
        )

    records = [_parse_opportunity(row) for row in raw]
    identifiers = [item.opportunity_id for item in records]
    if len(set(identifiers)) != len(identifiers):
        raise CandidateBatchPlanError("duplicate opportunity_id is not allowed")
    records.sort(
        key=lambda item: (
            item.ticker, item.snapshot_date, item.expiration,
            item.lower_strike, item.upper_strike, item.opportunity_id,
        )
    )

    grouped: dict[tuple[str, date, date], list[_MutableBatch]] = {}
    for item in records:
        key = (item.ticker, item.snapshot_date, item.expiration)
        groups = grouped.setdefault(key, [])
        # Multiple opportunities share one chain even if the opportunity sides differ:
        # side=None returns calls and puts within the bounded explicit strike interval.
        for index, group in enumerate(groups):
            combined = _join(group, item)
            if combined is not None:
                groups[index] = combined
                break
        else:
            groups.append(
                _MutableBatch(
                    ticker=item.ticker,
                    snapshot_date=item.snapshot_date,
                    expiration=item.expiration,
                    lower_strike=item.lower_strike,
                    upper_strike=item.upper_strike,
                    minimum_pit_price=item.raw_underlying_price,
                    opportunity_ids=(item.opportunity_id,),
                    sides=(item.side,),
                )
            )

    # Repeated overlaps can connect previously separate groups. Merge to a stable
    # fixed point, independent of input order and without widening beyond the cap.
    for groups in grouped.values():
        changed = True
        while changed:
            changed = False
            groups.sort(key=lambda x: (x.lower_strike, x.upper_strike))
            for i in range(len(groups)):
                if changed:
                    break
                for j in range(i + 1, len(groups)):
                    right = groups[j]
                    temp_item = CandidateOpportunity(
                        opportunity_id="", ticker=right.ticker,
                        snapshot_date=right.snapshot_date,
                        decision_at_utc=datetime.now(UTC),
                        raw_underlying_price=right.minimum_pit_price,
                        expiration=right.expiration, side=right.sides[0],
                        stock_source_sha256="", lower_strike=right.lower_strike,
                        upper_strike=right.upper_strike,
                    )
                    merged = _join(groups[i], temp_item)
                    if merged is not None:
                        groups[i] = _MutableBatch(
                            ticker=merged.ticker,
                            snapshot_date=merged.snapshot_date,
                            expiration=merged.expiration,
                            lower_strike=merged.lower_strike,
                            upper_strike=merged.upper_strike,
                            minimum_pit_price=merged.minimum_pit_price,
                            opportunity_ids=tuple(sorted(
                                set(groups[i].opportunity_ids) | set(right.opportunity_ids)
                            )),
                            sides=tuple(sorted(set(groups[i].sides) | set(right.sides))),
                        )
                        groups.pop(j)
                        changed = True
                        break

    requests: list[dict[str, Any]] = []
    for key in sorted(grouped):
        for group in sorted(grouped[key], key=lambda x: (x.lower_strike, x.upper_strike)):
            params = {
                "date": group.snapshot_date.isoformat(),
                "expiration": group.expiration.isoformat(),
                "strike": f"{group.lower_strike:.2f}-{group.upper_strike:.2f}",
            }
            request = {
                "ticker": group.ticker,
                "endpoint": f"options/chain/{group.ticker}/",
                "params": params,
                "requested_sides": list(group.sides),
                "opportunity_ids": sorted(set(group.opportunity_ids)),
                "bounded_query": True,
                "request_identity": _digest({
                    "ticker": group.ticker, "params": params, "mode": "HISTORICAL_EOD",
                }),
            }
            requests.append(request)
    if len(requests) > MAX_CHAIN_GROUPS:
        raise CandidateBatchPlanError(
            f"plan would exceed the {MAX_CHAIN_GROUPS}-group budget"
        )
    plan = {
        "contract": CONTRACT,
        "purpose": "SOURCE_ACQUISITION_ONLY",
        "provider_calls_performed": 0,
        "broker_calls_performed": 0,
        "opportunities": len(records),
        "shared_chain_requests": len(requests),
        "minimum_historical_chain_credits": len(requests),
        "credit_estimate_is_only_a_lower_bound": True,
        "maximum_returned_contracts_per_request_for_future_executor": 1000,
        "requests": requests,
        "source_bindings": {
            item.opportunity_id: {
                "stock_source_sha256": item.stock_source_sha256,
                "decision_at_utc": item.decision_at_utc.isoformat(),
                "raw_underlying_price": str(item.raw_underlying_price),
                "snapshot_date": item.snapshot_date.isoformat(),
                "expiration": item.expiration.isoformat(),
                "side": item.side,
            }
            for item in records
        },
        "limitations": {
            "no_historical_option_fill_or_pnl_authority": True,
            "no_same_day_eod_lookahead": True,
            "no_automatic_contract_selection": True,
            "no_historical_quote_paths_requested": True,
            "no_provider_entitlement_proven_by_plan": True,
        },
    }
    plan["plan_fingerprint"] = _digest(plan)
    return plan
