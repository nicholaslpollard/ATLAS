from __future__ import annotations

"""Frozen, bounded option-exit retries for offline synthetic account mechanics.

The planning window is XNYS regular hours, capped strictly before expiration day.
It is a conservative fixture window, not certification of an option's trading
hours, liquidity, deliverable or execution. No provider/broker client is used.
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.market_calendar import MarketCalendar, get_market_calendar

PLAN_CONTRACT = "atlas-offline-option-exit-retry-plan-v1"
CURSOR_CONTRACT = "atlas-offline-option-exit-retry-cursor-v1"
ORIGIN = "SYNTHETIC_FIXTURE_ONLY"
EASTERN = ZoneInfo("America/New_York")
MAX_ATTEMPTS = 64
MAX_WINDOW_DAYS = 31
MAX_CHECKPOINT_BYTES = 256 * 1024
OCC = re.compile(r"^O:([A-Z0-9.]{1,6})(\d{6})([CP])(\d{8})$")


class OptionExitRetryError(ValueError):
    pass


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise OptionExitRetryError(f"{label} requires an aware datetime")
    return value.astimezone(UTC)


def _integer(value: int, low: int, high: int, label: str) -> None:
    if type(value) is not int or not low <= value <= high:
        raise OptionExitRetryError(f"{label} out of bounds")


def _decimal(value: str) -> Decimal:
    if not isinstance(value, str) or not value or len(value) > 128 or value.strip() != value:
        raise OptionExitRetryError("price requires a bounded exact decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise OptionExitRetryError("invalid price") from exc
    if not number.is_finite() or not 0 <= number <= Decimal("1e12"):
        raise OptionExitRetryError("invalid price")
    return number


def _payload(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _payload(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_payload(item) for item in value]
    return value


def _fingerprint(value: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    total = 0
    try:
        encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), allow_nan=False)
        for chunk in encoder.iterencode(value):
            raw = chunk.encode()
            total += len(raw)
            if total > MAX_CHECKPOINT_BYTES:
                raise OptionExitRetryError("retry checkpoint exceeds safe byte bound")
            digest.update(raw)
    except (TypeError, ValueError, RecursionError) as exc:
        raise OptionExitRetryError(f"invalid retry checkpoint encoding: {exc}") from exc
    return digest.hexdigest()


def _schedule(
    requested: datetime, deadline: datetime, interval: int, maximum: int,
    windows: tuple[tuple[datetime, datetime], ...],
) -> tuple[datetime, ...]:
    candidate = requested
    attempts: list[datetime] = []
    for opened, closed in windows:
        candidate = max(candidate, opened)
        while candidate < closed and candidate <= deadline:
            attempts.append(candidate)
            if len(attempts) == maximum:
                return tuple(attempts)
            candidate += timedelta(seconds=interval)
    return tuple(attempts)


@dataclass(frozen=True, slots=True)
class OptionExitRetryPlanV1:
    option_symbol: str
    expiration: date
    opened_at_utc: datetime
    requested_exit_at_utc: datetime
    deadline_at_utc: datetime
    retry_interval_seconds: int
    maximum_attempts: int
    maximum_quote_age_seconds: int
    session_windows_utc: tuple[tuple[datetime, datetime], ...]
    attempt_times_utc: tuple[datetime, ...]

    def __post_init__(self) -> None:
        match = OCC.fullmatch(self.option_symbol) if isinstance(self.option_symbol, str) else None
        if (not match or type(self.expiration) is not date
                or int(match.group(4)) <= 0):
            raise OptionExitRetryError("exact option identity required")
        try:
            expiry = datetime.strptime(match.group(2), "%y%m%d").date()
        except ValueError as exc:
            raise OptionExitRetryError("invalid OCC expiry") from exc
        if expiry != self.expiration:
            raise OptionExitRetryError("OCC expiry mismatch")
        opened = _utc(self.opened_at_utc, "position open")
        requested = _utc(self.requested_exit_at_utc, "exit request")
        deadline = _utc(self.deadline_at_utc, "exit deadline")
        if not opened < requested <= deadline:
            raise OptionExitRetryError("exit request/deadline chronology invalid")
        if deadline - requested > timedelta(days=MAX_WINDOW_DAYS):
            raise OptionExitRetryError("retry window exceeds safe bound")
        # Do not infer an option-specific expiration-day exercise/trading cutoff.
        if deadline.astimezone(EASTERN).date() >= expiry:
            raise OptionExitRetryError("retry deadline must precede expiration day")
        _integer(self.retry_interval_seconds, 1, 7 * 86400, "retry interval")
        _integer(self.maximum_attempts, 1, MAX_ATTEMPTS, "maximum attempts")
        _integer(self.maximum_quote_age_seconds, 0, 3600, "quote age")
        if (type(self.session_windows_utc) is not tuple
                or len(self.session_windows_utc) > MAX_WINDOW_DAYS + 2
                or type(self.attempt_times_utc) is not tuple):
            raise OptionExitRetryError("immutable bounded session/attempt tuples required")
        previous: datetime | None = None
        for window in self.session_windows_utc:
            if type(window) is not tuple or len(window) != 2:
                raise OptionExitRetryError("invalid session window")
            start, end = (_utc(window[0], "session open"), _utc(window[1], "session close"))
            day = start.astimezone(EASTERN).date()
            if (start >= end or day != end.astimezone(EASTERN).date()
                    or not requested.astimezone(EASTERN).date() <= day <= deadline.astimezone(EASTERN).date()
                    or (previous is not None and start <= previous)):
                raise OptionExitRetryError("session windows are not chronological/in range")
            previous = end
        expected = _schedule(requested, deadline, self.retry_interval_seconds,
                             self.maximum_attempts, self.session_windows_utc)
        if self.attempt_times_utc != expected:
            raise OptionExitRetryError("attempt schedule differs from frozen session windows")

    def payload(self) -> dict[str, Any]:
        return {"contract": PLAN_CONTRACT, "origin": ORIGIN,
                "calendar": "XNYS_REGULAR_CONSERVATIVE_WINDOW", **_payload(asdict(self))}

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.payload())


def build_option_exit_retry_plan(
    *, option_symbol: str, expiration: date, opened_at_utc: datetime,
    requested_exit_at_utc: datetime, deadline_at_utc: datetime,
    retry_interval_seconds: int, maximum_attempts: int,
    maximum_quote_age_seconds: int, calendar: MarketCalendar | None = None,
) -> OptionExitRetryPlanV1:
    requested = _utc(requested_exit_at_utc, "exit request")
    deadline = _utc(deadline_at_utc, "exit deadline")
    # Validate bounds before any calendar access or schedule construction.
    OptionExitRetryPlanV1(option_symbol, expiration, _utc(opened_at_utc, "position open"),
                         requested, deadline, retry_interval_seconds, maximum_attempts,
                         maximum_quote_age_seconds, (), ())
    calendar = calendar or get_market_calendar()
    if calendar.exchange != "XNYS":
        raise OptionExitRetryError("XNYS conservative planning window required")
    try:
        days = calendar.sessions_in_range(requested.astimezone(EASTERN).date(),
                                          deadline.astimezone(EASTERN).date())
        windows = tuple(calendar.regular_open_close(day) for day in days)
    except (ValueError, OverflowError) as exc:
        raise OptionExitRetryError("calendar does not cover the retry window") from exc
    return OptionExitRetryPlanV1(
        option_symbol, expiration, _utc(opened_at_utc, "position open"), requested, deadline,
        retry_interval_seconds, maximum_attempts, maximum_quote_age_seconds, windows,
        _schedule(requested, deadline, retry_interval_seconds, maximum_attempts, windows),
    )


@dataclass(frozen=True, slots=True)
class SyntheticExitQuoteV1:
    option_symbol: str
    observed_at_utc: datetime
    available_at_utc: datetime
    bid_per_share: str | None
    ask_per_share: str | None
    bid_size_contracts: int | None
    source_integrity_qualified: bool
    observation_clock_qualified: bool
    origin: str = ORIGIN

    def __post_init__(self) -> None:
        if self.origin != ORIGIN:
            raise OptionExitRetryError("historical/provider observations cannot impersonate fixtures")
        if not isinstance(self.option_symbol, str) or not 1 <= len(self.option_symbol) <= 64:
            raise OptionExitRetryError("bounded quote instrument required")
        _utc(self.observed_at_utc, "quote observation")
        _utc(self.available_at_utc, "quote availability")
        if any(price is not None and (not isinstance(price, str) or len(price) > 128)
               for price in (self.bid_per_share, self.ask_per_share)):
            raise OptionExitRetryError("bounded decimal quote fields required")
        if any(type(flag) is not bool for flag in (
            self.source_integrity_qualified, self.observation_clock_qualified,
        )):
            raise OptionExitRetryError("quote qualification flags must be boolean")
        if self.bid_size_contracts is not None:
            _integer(self.bid_size_contracts, 0, 10**9, "quote bid size")


def _quote_result(
    plan: OptionExitRetryPlanV1, at: datetime, quote: SyntheticExitQuoteV1 | None,
    required_contracts: int, slippage_per_share: str,
) -> str:
    if quote is None:
        return "NO_QUOTE"
    if not isinstance(quote, SyntheticExitQuoteV1):
        raise OptionExitRetryError("typed synthetic quote or explicit absence required")
    if quote.option_symbol != plan.option_symbol:
        return "QUOTE_CONTRACT_MISMATCH"
    if not quote.source_integrity_qualified:
        return "UNQUALIFIED_QUOTE_SOURCE"
    if not quote.observation_clock_qualified:
        return "UNQUALIFIED_QUOTE_CLOCK"
    observed = _utc(quote.observed_at_utc, "quote observation")
    available = _utc(quote.available_at_utc, "quote availability")
    if observed > at:
        return "FUTURE_QUOTE"
    if available < observed:
        return "INVALID_QUOTE_AVAILABILITY_CLOCK"
    if available > at:
        return "QUOTE_NOT_AVAILABLE_BY_ATTEMPT"
    if at - observed > timedelta(seconds=plan.maximum_quote_age_seconds):
        return "STALE_QUOTE"
    if not any(start <= observed < end for start, end in plan.session_windows_utc):
        return "QUOTE_OUTSIDE_PLANNED_SESSION"
    if quote.bid_per_share is None or quote.ask_per_share is None:
        return "ONE_SIDED_QUOTE"
    try:
        bid, ask = _decimal(quote.bid_per_share), _decimal(quote.ask_per_share)
    except OptionExitRetryError:
        return "INVALID_QUOTE_PRICE"
    if bid <= 0:
        return "NO_EXECUTABLE_BID"
    if ask < bid:
        return "CROSSED_QUOTE"
    if quote.bid_size_contracts is None or quote.bid_size_contracts < required_contracts:
        return "INSUFFICIENT_DISPLAYED_BID_SIZE"
    net_bid = bid - _decimal(slippage_per_share)
    if net_bid <= 0:
        return "SLIPPAGE_CONSUMES_BID"
    if (net_bid * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) <= 0:
        return "NO_POSITIVE_MODELED_EXIT_CREDIT"
    return "EXIT_QUOTE_READY"


@dataclass(frozen=True, slots=True)
class ExitRetryAttemptV1:
    attempted_at_utc: datetime
    result: str
    quote: SyntheticExitQuoteV1 | None


@dataclass(frozen=True, slots=True)
class OptionExitRetryCursorV1:
    plan: OptionExitRetryPlanV1
    required_contracts: int
    slippage_per_share: str
    as_of_utc: datetime
    attempts: tuple[ExitRetryAttemptV1, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.plan, OptionExitRetryPlanV1):
            raise OptionExitRetryError("typed retry plan required")
        _integer(self.required_contracts, 1, 100000, "required contracts")
        _decimal(self.slippage_per_share)
        horizon = _utc(self.as_of_utc, "cursor as-of")
        if horizon < self.plan.opened_at_utc:
            raise OptionExitRetryError("cursor predates position open")
        if type(self.attempts) is not tuple or len(self.attempts) > len(self.plan.attempt_times_utc):
            raise OptionExitRetryError("immutable bounded attempt prefix required")
        for index, attempt in enumerate(self.attempts):
            if (not isinstance(attempt, ExitRetryAttemptV1)
                    or attempt.attempted_at_utc != self.plan.attempt_times_utc[index]
                    or attempt.attempted_at_utc > horizon):
                raise OptionExitRetryError("cursor attempts differ from reached schedule prefix")
            expected = _quote_result(self.plan, attempt.attempted_at_utc, attempt.quote,
                                     self.required_contracts, self.slippage_per_share)
            if attempt.result != expected or (expected == "EXIT_QUOTE_READY" and index != len(self.attempts) - 1):
                raise OptionExitRetryError("cursor result changed or continued after a close quote")
        if (self.ready_quote is None and len(self.attempts) < len(self.plan.attempt_times_utc)
                and self.plan.attempt_times_utc[len(self.attempts)] <= horizon):
            raise OptionExitRetryError("cursor omitted a reached attempt")

    @property
    def ready_quote(self) -> SyntheticExitQuoteV1 | None:
        return self.attempts[-1].quote if self.attempts and self.attempts[-1].result == "EXIT_QUOTE_READY" else None

    @property
    def status(self) -> str:
        if self.ready_quote is not None:
            return "EXIT_QUOTE_READY"
        if self.as_of_utc < self.plan.requested_exit_at_utc:
            return "OPEN_EXIT_NOT_REQUESTED_YET"
        if len(self.attempts) == self.plan.maximum_attempts:
            return "OPEN_UNRESOLVED_EXIT_RETRY_LIMIT"
        if self.as_of_utc >= self.plan.deadline_at_utc:
            return "OPEN_UNRESOLVED_EXIT_RETRY_DEADLINE"
        return "OPEN_AWAITING_EXIT_RETRY"

    def payload(self) -> dict[str, Any]:
        return {"contract": CURSOR_CONTRACT, "origin": ORIGIN,
                "plan": self.plan.payload(), "plan_fingerprint": self.plan.fingerprint,
                "required_contracts": self.required_contracts,
                "slippage_per_share": self.slippage_per_share,
                "as_of_utc": self.as_of_utc.isoformat(),
                "attempts": _payload([asdict(item) for item in self.attempts])}

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.payload())


def advance_option_exit_retry(
    cursor: OptionExitRetryCursorV1, *, as_of_utc: datetime,
    read_quote: Callable[[str, datetime], SyntheticExitQuoteV1 | None],
) -> OptionExitRetryCursorV1:
    """Only reached attempts are read; a restored prefix is never read again."""
    horizon = _utc(as_of_utc, "retry as-of")
    if horizon < cursor.as_of_utc:
        raise OptionExitRetryError("retry cursor cannot move backwards")
    attempts = list(cursor.attempts)
    if cursor.ready_quote is None:
        for at in cursor.plan.attempt_times_utc[len(attempts):]:
            if at > horizon:
                break
            quote = read_quote(cursor.plan.option_symbol, at)
            result = _quote_result(cursor.plan, at, quote, cursor.required_contracts,
                                   cursor.slippage_per_share)
            attempts.append(ExitRetryAttemptV1(at, result, quote))
            if result == "EXIT_QUOTE_READY":
                break
    return replace(cursor, as_of_utc=horizon, attempts=tuple(attempts))


def restore_option_exit_retry_cursor(
    payload: dict[str, Any], *, expected_fingerprint: str,
    expected_plan_fingerprint: str,
) -> OptionExitRetryCursorV1:
    """Restore against caller-retained identities; do not trust re-signed JSON."""
    if (not isinstance(payload, dict) or _fingerprint(payload) != expected_fingerprint
            or payload.get("contract") != CURSOR_CONTRACT or payload.get("origin") != ORIGIN
            or payload.get("plan_fingerprint") != expected_plan_fingerprint):
        raise OptionExitRetryError("retry checkpoint fingerprint/contract mismatch")
    try:
        original_plan = payload["plan"]
        fields = {key: value for key, value in original_plan.items()
                  if key not in {"contract", "origin", "calendar"}}
        fields["expiration"] = date.fromisoformat(fields["expiration"])
        for key in ("opened_at_utc", "requested_exit_at_utc", "deadline_at_utc"):
            fields[key] = datetime.fromisoformat(fields[key])
        fields["session_windows_utc"] = tuple(tuple(datetime.fromisoformat(item) for item in window)
                                             for window in fields["session_windows_utc"])
        fields["attempt_times_utc"] = tuple(datetime.fromisoformat(item) for item in fields["attempt_times_utc"])
        plan = OptionExitRetryPlanV1(**fields)
        if plan.fingerprint != expected_plan_fingerprint or plan.payload() != original_plan:
            raise OptionExitRetryError("retry plan fingerprint/contract mismatch")
        attempts = []
        for item in payload["attempts"]:
            quote_fields = dict(item["quote"]) if item["quote"] is not None else None
            if quote_fields is not None:
                for key in ("observed_at_utc", "available_at_utc"):
                    quote_fields[key] = datetime.fromisoformat(quote_fields[key])
                quote = SyntheticExitQuoteV1(**quote_fields)
            else:
                quote = None
            attempts.append(ExitRetryAttemptV1(datetime.fromisoformat(item["attempted_at_utc"]),
                                                item["result"], quote))
        cursor = OptionExitRetryCursorV1(plan, payload["required_contracts"], payload["slippage_per_share"],
                                         datetime.fromisoformat(payload["as_of_utc"]), tuple(attempts))
        if cursor.payload() != payload:
            raise OptionExitRetryError("retry checkpoint fields changed")
        return cursor
    except (KeyError, TypeError, ValueError) as exc:
        raise OptionExitRetryError(f"invalid retry checkpoint: {exc}") from exc
