from __future__ import annotations

import math
from datetime import date
from typing import Any

from packages.portfolio.phase13_policy import (
    PHASE13_OPTION_MAX_ABS_DELTA,
    PHASE13_OPTION_MAX_ALTERNATIVES,
    PHASE13_OPTION_MAX_DTE,
    PHASE13_OPTION_MAX_SPREAD_TO_MID,
    PHASE13_OPTION_MIN_ABS_DELTA,
    PHASE13_OPTION_MIN_DTE,
    PHASE13_OPTION_MIN_OPEN_INTEREST,
    PHASE13_OPTION_TARGET_ABS_DELTA,
    PHASE13_OPTION_TARGET_DTE,
)
from packages.schemas.case_file import OptionCandidateEvidence
from packages.schemas.discovery_score import DiscoveryDirection


class Phase13OptionError(ValueError):
    pass


def normalize_option_snapshot(
    item: dict[str, Any],
    *,
    as_of_date: date,
    direction: DiscoveryDirection,
) -> OptionCandidateEvidence | None:
    details = item.get("details")
    quote = item.get("last_quote")
    if not isinstance(details, dict) or not isinstance(quote, dict):
        return None
    try:
        contract_ticker = str(details["ticker"]).strip()
        contract_type = str(details["contract_type"]).strip().lower()
        expiration = date.fromisoformat(str(details["expiration_date"]))
        strike = float(details["strike_price"])
        bid = float(quote["bid"])
        ask = float(quote["ask"])
    except (KeyError, TypeError, ValueError):
        return None
    if not contract_ticker or contract_type not in {"call", "put"}:
        return None
    if not all(math.isfinite(value) for value in (strike, bid, ask)):
        return None
    if strike <= 0.0 or bid < 0.0 or ask < bid:
        return None
    mid = (bid + ask) / 2.0
    if mid <= 0.0:
        return None
    spread_to_mid = (ask - bid) / mid
    dte = (expiration - as_of_date).days

    open_interest_raw = item.get("open_interest", 0)
    try:
        open_interest = max(0, int(open_interest_raw or 0))
    except (TypeError, ValueError):
        open_interest = 0
    day = item.get("day") if isinstance(item.get("day"), dict) else {}
    volume_raw = day.get("volume") if isinstance(day, dict) else None
    try:
        volume = None if volume_raw is None else max(0, int(volume_raw))
    except (TypeError, ValueError):
        volume = None
    greeks = item.get("greeks") if isinstance(item.get("greeks"), dict) else {}
    delta_raw = greeks.get("delta") if isinstance(greeks, dict) else None
    try:
        delta = None if delta_raw is None else float(delta_raw)
    except (TypeError, ValueError):
        delta = None
    if delta is not None and (not math.isfinite(delta) or not -1.0 <= delta <= 1.0):
        delta = None
    iv_raw = item.get("implied_volatility")
    try:
        iv = None if iv_raw is None else float(iv_raw)
    except (TypeError, ValueError):
        iv = None
    if iv is not None and (not math.isfinite(iv) or iv < 0.0):
        iv = None

    desired_type = "call" if direction == DiscoveryDirection.BULLISH else "put"
    checks = {
        "direction_alignment": direction in {DiscoveryDirection.BULLISH, DiscoveryDirection.BEARISH}
        and contract_type == desired_type,
        "dte": PHASE13_OPTION_MIN_DTE <= dte <= PHASE13_OPTION_MAX_DTE,
        "open_interest": open_interest >= PHASE13_OPTION_MIN_OPEN_INTEREST,
        "spread": spread_to_mid <= PHASE13_OPTION_MAX_SPREAD_TO_MID,
        "delta": delta is not None
        and PHASE13_OPTION_MIN_ABS_DELTA <= abs(delta) <= PHASE13_OPTION_MAX_ABS_DELTA,
    }
    reasons = tuple(
        f"{name.upper()}_{'PASS' if passed else 'FAIL'}" for name, passed in checks.items()
    )
    return OptionCandidateEvidence(
        contract_ticker=contract_ticker,
        contract_type=contract_type,
        expiration_date=expiration,
        dte=max(0, dte),
        strike=strike,
        bid=bid,
        ask=ask,
        mid=mid,
        spread_to_mid=spread_to_mid,
        open_interest=open_interest,
        volume=volume,
        delta=delta,
        implied_volatility=iv,
        eligible=all(checks.values()),
        reason_codes=reasons,
    )


def rank_option_alternatives(
    items: list[dict[str, Any]],
    *,
    as_of_date: date,
    direction: DiscoveryDirection,
) -> tuple[OptionCandidateEvidence, ...]:
    normalized = [
        candidate
        for item in items
        if (candidate := normalize_option_snapshot(item, as_of_date=as_of_date, direction=direction))
        is not None
    ]
    eligible = [item for item in normalized if item.eligible]
    eligible.sort(
        key=lambda item: (
            item.spread_to_mid,
            -item.open_interest,
            abs(abs(float(item.delta)) - PHASE13_OPTION_TARGET_ABS_DELTA)
            if item.delta is not None
            else float("inf"),
            abs(item.dte - PHASE13_OPTION_TARGET_DTE),
            item.contract_ticker,
        )
    )
    return tuple(eligible[:PHASE13_OPTION_MAX_ALTERNATIVES])
