from __future__ import annotations

"""Frozen pilot geometry and decision-time quote gates for invented fixtures.

Identity selection precedes liquidity/availability filters. The result is an
exact pair candidate, never a fill, a historical source adapter or a trade signal.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.multiyear_offline_account_replay_v1 import _money
from packages.strategies.options_native_pilot_v1_contract import (
    AUTHORITY, END_DATE, MAX_DTE, MAX_HOLD_SESSIONS, MIN_DTE, SPECIFICATION_FINGERPRINT, START_DATE,
)

ORIGIN = "SYNTHETIC_FIXTURE_ONLY"
EASTERN = ZoneInfo("America/New_York")
OCC = re.compile(r"^O:SPY(\d{6})([CP])(\d{8})$")


class NativePairError(ValueError):
    pass


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise NativePairError("aware clock required")
    return value.astimezone(UTC)


def decimal(value: str, *, zero: bool = False) -> Decimal:
    if not isinstance(value, str) or not value or len(value) > 64 or value.strip() != value:
        raise NativePairError("bounded exact decimal string required")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise NativePairError("invalid decimal") from exc
    if (not number.is_finite() or number < 0 or (not zero and number == 0)
            or number > 1000000 or not -24 <= number.as_tuple().exponent <= 6):
        raise NativePairError("decimal outside finite bounds")
    return number


def identity(symbol: str) -> tuple[date, str, Decimal]:
    match = OCC.fullmatch(symbol) if isinstance(symbol, str) else None
    if match is None:
        raise NativePairError("exact SPY OCC identity required")
    try:
        expiry = datetime.strptime(match.group(1), "%y%m%d").date()
    except ValueError as exc:
        raise NativePairError("invalid OCC expiry") from exc
    strike = Decimal(match.group(3)) / 1000
    if strike <= 0:
        raise NativePairError("invalid OCC strike")
    return expiry, match.group(2), strike


def pilot_entry_clock(cutoff: datetime) -> datetime:
    """Validate the frozen weekly feature clock, not option trading hours."""
    cutoff = utc(cutoff)
    local = cutoff.astimezone(EASTERN)
    calendar = get_market_calendar("XNYS")
    if (not START_DATE <= local.date().isoformat() <= END_DATE
            or local.date() + timedelta(days=MAX_DTE) > date.fromisoformat(END_DATE)
            or (local.hour, local.minute, local.second, local.microsecond) != (10, 0, 0, 0)
            or not calendar.is_session(local.date())):
        raise NativePairError("pilot decision scope or cutoff invalid")
    week = local.date() - timedelta(days=local.weekday())
    if calendar.sessions_in_range(week, local.date())[0] != local.date():
        raise NativePairError("entry must be first session of its ISO week")
    return cutoff + timedelta(minutes=1)


def payload(value: Any) -> Any:
    if isinstance(value, datetime):
        return utc(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: payload(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [payload(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class SyntheticPairQuoteV1:
    option_symbol: str
    observed_at_utc: datetime | None
    available_at_utc: datetime | None
    bid: str | None
    ask: str | None
    bid_size: int | None
    ask_size: int | None
    open_interest: int | None
    oi_state_session: date | None
    oi_available_at_utc: datetime | None
    source_qualified: bool
    option_hours_qualified: bool
    standard_deliverable_verified: bool
    multiplier: int = 100
    reported_volume: int | None = None


@dataclass(frozen=True, slots=True)
class SyntheticPairSurfaceV1:
    case_id: str
    feature_cutoff_utc: datetime
    spot: str
    spot_observed_at_utc: datetime
    spot_available_at_utc: datetime
    roster_available_at_utc: datetime
    source_fingerprint: str
    complete_identity_roster_qualified: bool
    spot_source_qualified: bool
    quotes: tuple[SyntheticPairQuoteV1, ...]
    origin: str = ORIGIN


def construct_synthetic_pilot_pair(surface: SyntheticPairSurfaceV1) -> dict[str, Any]:
    if not isinstance(surface, SyntheticPairSurfaceV1) or surface.origin != ORIGIN:
        raise NativePairError("synthetic surface required; historical source adapter unavailable")
    if (not isinstance(surface.case_id, str) or not surface.case_id
            or not isinstance(surface.source_fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", surface.source_fingerprint) is None):
        raise NativePairError("case and source identity required")
    cutoff = utc(surface.feature_cutoff_utc)
    ready = pilot_entry_clock(cutoff)
    local = cutoff.astimezone(EASTERN)
    calendar = get_market_calendar("XNYS")
    spot = decimal(surface.spot)
    spot_at, spot_known = utc(surface.spot_observed_at_utc), utc(surface.spot_available_at_utc)
    roster_known = utc(surface.roster_available_at_utc)
    if not isinstance(surface.quotes, tuple) or not 1 <= len(surface.quotes) <= 5000:
        raise NativePairError("bounded nonempty identity/quote tuple required")
    identities = {}
    for quote in surface.quotes:
        if not isinstance(quote, SyntheticPairQuoteV1):
            raise NativePairError("typed pair quote required")
        info = identity(quote.option_symbol)
        if quote.option_symbol in identities:
            raise NativePairError("duplicate contract identity")
        for flag in (quote.source_qualified, quote.option_hours_qualified,
                     quote.standard_deliverable_verified):
            if type(flag) is not bool:
                raise NativePairError("quote qualification must be boolean")
        identities[quote.option_symbol] = (info, quote)
    for flag in (surface.complete_identity_roster_qualified, surface.spot_source_qualified):
        if type(flag) is not bool:
            raise NativePairError("surface qualification must be boolean")
    reasons = []
    if not surface.complete_identity_roster_qualified or roster_known > ready:
        reasons.append("IDENTITY_ROSTER_UNQUALIFIED_OR_LATE")
    if (not surface.spot_source_qualified or not cutoff - timedelta(seconds=60) <= spot_at <= cutoff
            or not spot_at <= spot_known <= ready):
        reasons.append("SPOT_SOURCE_OR_CLOCK_UNQUALIFIED")
    chosen: list[SyntheticPairQuoteV1] = []
    expiry = strike = None
    if not reasons:
        expiries = sorted({info[0] for info, _ in identities.values()
                           if MIN_DTE <= (info[0] - local.date()).days <= MAX_DTE})
        if not expiries:
            reasons.append("NO_EXPIRATION_IN_FROZEN_DTE_BAND")
        else:
            expiry = expiries[0]
            call = {info[2]: quote for info, quote in identities.values() if info[0] == expiry and info[1] == "C"}
            put = {info[2]: quote for info, quote in identities.values() if info[0] == expiry and info[1] == "P"}
            common = call.keys() & put.keys()
            if not common:
                reasons.append("EARLIEST_EXPIRATION_HAS_NO_COMMON_STRIKE")
            else:
                strike = min(common, key=lambda candidate: (abs(candidate - spot), candidate))
                chosen = [call[strike], put[strike]]
    previous_session = calendar.sessions_in_range(local.date() - timedelta(days=10), local.date())[-2]
    for quote in chosen:
        prefix = identity(quote.option_symbol)[1] + ":"
        if not quote.source_qualified or not quote.option_hours_qualified:
            reasons.append(prefix + "SOURCE_OR_OPTION_HOURS_UNQUALIFIED")
        if type(quote.multiplier) is not int or quote.multiplier != 100 or not quote.standard_deliverable_verified:
            reasons.append(prefix + "DELIVERABLE_UNQUALIFIED")
        if quote.observed_at_utc is None or quote.available_at_utc is None:
            reasons.append(prefix + "QUOTE_CLOCK_UNKNOWN")
        else:
            observed, available = utc(quote.observed_at_utc), utc(quote.available_at_utc)
            if not cutoff - timedelta(seconds=30) <= observed <= cutoff or not observed <= available <= ready:
                reasons.append(prefix + "QUOTE_FUTURE_STALE_OR_LATE")
        if quote.bid is None or quote.ask is None:
            reasons.append(prefix + "MISSING_QUOTE_SIDE")
        else:
            bid, ask = decimal(quote.bid, zero=True), decimal(quote.ask, zero=True)
            if bid <= 0 or ask <= 0 or bid > ask:
                reasons.append(prefix + "NONPOSITIVE_OR_CROSSED_QUOTE")
            elif (ask - bid) / ((ask + bid) / 2) > Decimal("0.15"):
                reasons.append(prefix + "SPREAD_EXCEEDS_FROZEN_LIMIT")
        if any(type(size) is not int or size < 1 for size in (quote.bid_size, quote.ask_size)):
            reasons.append(prefix + "INSUFFICIENT_DISPLAYED_SIZE")
        if (type(quote.open_interest) is not int or quote.open_interest < 100
                or quote.oi_state_session != previous_session or quote.oi_available_at_utc is None
                or not calendar.regular_open_close(previous_session)[1] <= utc(quote.oi_available_at_utc) <= ready):
            reasons.append(prefix + "OPEN_INTEREST_STATE_OR_AVAILABILITY_UNQUALIFIED")
    if (len(chosen) == 2 and all(quote.observed_at_utc is not None for quote in chosen)
            and abs((utc(chosen[0].observed_at_utc) - utc(chosen[1].observed_at_utc)).total_seconds()) > 1):
        reasons.append("PAIR_QUOTE_OBSERVATION_SKEW")
    result = {
        "contract": "atlas-options-native-synthetic-pair-construction-v1",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "case_id": surface.case_id, "origin": ORIGIN,
        "source_fingerprint": surface.source_fingerprint,
        "input_fingerprint": _fingerprint(payload(asdict(surface))),
        "feature_cutoff_utc": cutoff.isoformat(), "order_eligible_utc": ready.isoformat(),
        "status": "FIXTURE_PAIR_CANDIDATE" if not reasons else "FIXTURE_ABSTAIN",
        "reasons": reasons, "expiration": expiry.isoformat() if expiry else None,
        "strike": str(strike) if strike is not None else None,
        "selected_exact_symbols": [quote.option_symbol for quote in chosen],
        "selected_quotes": [payload(asdict(quote)) for quote in chosen],
        "reference_ask_debit_before_fees": str(_money(sum((decimal(q.ask) * 100 for q in chosen), Decimal(0)))) if not reasons else None,
        "variance_signal_bound": False, "historical_performance_evidence": False,
        "authority": dict(AUTHORITY),
    }
    result["pair_fingerprint"] = _fingerprint(result)
    return result


@dataclass(frozen=True, slots=True)
class SyntheticPairExitReviewV1:
    entry_order_eligible_utc: datetime
    feature_cutoff_utc: datetime
    call_symbol: str
    put_symbol: str
    variance_gap: str | None
    variance_inputs_qualified: bool
    origin: str = ORIGIN


def review_synthetic_pilot_exit(review: SyntheticPairExitReviewV1) -> dict[str, Any]:
    """Evaluate a fixture's original pair; an exit request never releases capital."""
    if (not isinstance(review, SyntheticPairExitReviewV1) or review.origin != ORIGIN
            or type(review.variance_inputs_qualified) is not bool):
        raise NativePairError("typed synthetic exit review required")
    entry, cutoff = utc(review.entry_order_eligible_utc), utc(review.feature_cutoff_utc)
    pilot_entry_clock(entry - timedelta(minutes=1))
    call, put = identity(review.call_symbol), identity(review.put_symbol)
    if call[1] != "C" or put[1] != "P" or (call[0], call[2]) != (put[0], put[2]):
        raise NativePairError("management must retain the original same-strike/expiry pair")
    entry_day, day = entry.astimezone(EASTERN).date(), cutoff.astimezone(EASTERN).date()
    if not MIN_DTE <= (call[0] - entry_day).days <= MAX_DTE:
        raise NativePairError("original pair outside frozen DTE band")
    local = cutoff.astimezone(EASTERN)
    calendar = get_market_calendar("XNYS")
    if (day <= entry_day or not calendar.is_session(day)
            or (local.hour, local.minute, local.second, local.microsecond) != (10, 0, 0, 0)
            or day > date.fromisoformat(END_DATE)):
        raise NativePairError("review must be a subsequent development-session 10:00 clock")
    elapsed = len(calendar.sessions_in_range(entry_day + timedelta(days=1), day))
    reasons = []
    if elapsed >= MAX_HOLD_SESSIONS:
        reasons.append("MAXIMUM_HOLDING_SESSIONS_REACHED")
    if (call[0] - day).days <= 14:
        reasons.append("DTE_GUARD_REACHED")
    feature_known = review.variance_inputs_qualified and review.variance_gap is not None
    if feature_known:
        value = review.variance_gap
        if not isinstance(value, str) or not value or len(value) > 64 or value.strip() != value:
            raise NativePairError("bounded signed fixture variance gap required")
        try:
            gap = Decimal(value)
        except InvalidOperation as exc:
            raise NativePairError("invalid fixture variance gap") from exc
        if not gap.is_finite() or abs(gap) > 1000000 or not -24 <= gap.as_tuple().exponent <= 6:
            raise NativePairError("fixture variance gap outside finite bounds")
        if gap <= 0:
            reasons.append("VARIANCE_THESIS_NO_LONGER_POSITIVE")
    result = {
        "contract": "atlas-options-native-synthetic-pair-exit-review-v1",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "origin": ORIGIN, "feature_cutoff_utc": cutoff.isoformat(),
        "order_eligible_utc": (cutoff + timedelta(minutes=1)).isoformat(),
        "original_exact_symbols": [review.call_symbol, review.put_symbol],
        "subsequent_sessions": elapsed, "calendar_dte": (call[0] - day).days,
        "variance_feature_state": "KNOWN_FIXTURE_GAP" if feature_known else "MISSING_OR_UNQUALIFIED",
        "action": "REQUEST_EXIT" if reasons else "HOLD", "reasons": reasons,
        "cash_released": "0.00", "historical_performance_evidence": False,
        "authority": dict(AUTHORITY),
    }
    result["review_fingerprint"] = _fingerprint(result)
    return result
