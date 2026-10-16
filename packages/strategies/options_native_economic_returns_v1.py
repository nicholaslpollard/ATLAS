from __future__ import annotations

"""Synthetic economic-return arithmetic; no historical adjustment adapter.

For one share at the preceding close, end wealth is split_new_per_old times
the new raw close plus ex-date cash entitlement per ORIGINAL share. The cash
term is an analytical feature, not a broker cash payment or option settlement.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from re import fullmatch
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.strategies.options_native_pair_v1 import ORIGIN, NativePairError, decimal, payload, utc
from packages.strategies.options_native_pilot_v1 import PriorEconomicLogReturnV1
from packages.strategies.options_native_pilot_v1_contract import (
    AUTHORITY, END_DATE, LOOKBACK_RETURNS, SPECIFICATION_FINGERPRINT, START_DATE,
)


@dataclass(frozen=True, slots=True)
class SyntheticEconomicIntervalV1:
    interval_start_utc: datetime
    interval_end_utc: datetime
    inputs_available_at_utc: datetime
    prior_raw_close: str
    current_raw_close: str
    split_new_shares_per_old: str | None
    ex_date_cash_per_original_share: str | None
    source_fingerprint: str
    complete_action_coverage_qualified: bool
    publication_and_revision_clocks_qualified: bool
    unsupported_action_present: bool = False
    cash_basis: str = "PER_ORIGINAL_SHARE_AT_PRIOR_CLOSE"
    origin: str = ORIGIN


def build_synthetic_pilot_economic_returns(
    intervals: tuple[SyntheticEconomicIntervalV1, ...], *, feature_cutoff_utc: datetime,
) -> dict[str, Any]:
    cutoff = utc(feature_cutoff_utc)
    ready = cutoff + timedelta(minutes=1)
    calendar = get_market_calendar("XNYS")
    local = cutoff.astimezone(ZoneInfo("America/New_York"))
    if (not START_DATE <= local.date().isoformat() <= END_DATE
            or (local.hour, local.minute, local.second, local.microsecond) != (10, 0, 0, 0)
            or not calendar.is_session(local.date()) or not isinstance(intervals, tuple) or len(intervals) != LOOKBACK_RETURNS
            or any(not isinstance(row, SyntheticEconomicIntervalV1) for row in intervals)):
        raise NativePairError("exact pre-2026 pilot clock and twenty typed fixture intervals required")
    days = calendar.sessions_in_range((cutoff - timedelta(days=75)).date(), local.date())
    closes = [calendar.regular_open_close(day)[1] for day in days]
    closes = [stamp for stamp in closes if stamp < cutoff][-(LOOKBACK_RETURNS + 1):]
    ordered = sorted(intervals, key=lambda row: utc(row.interval_end_utc))
    if [(utc(row.interval_start_utc), utc(row.interval_end_utc)) for row in ordered] != list(zip(closes, closes[1:])):
        raise NativePairError("economic fixture must retain the exact contiguous prior-close window")
    if any(decimal(left.current_raw_close) != decimal(right.prior_raw_close)
           for left, right in zip(ordered, ordered[1:])):
        raise NativePairError("adjacent fixture intervals disagree on their shared raw close")
    reasons, rows, outputs = [], [], []
    for index, row in enumerate(ordered):
        if (not isinstance(row, SyntheticEconomicIntervalV1) or row.origin != ORIGIN
                or not isinstance(row.source_fingerprint, str) or fullmatch(r"[0-9a-f]{64}", row.source_fingerprint) is None
                or any(type(flag) is not bool for flag in (row.complete_action_coverage_qualified,
                       row.publication_and_revision_clocks_qualified, row.unsupported_action_present))):
            raise NativePairError("typed synthetic return source and qualification flags required")
        start, end, known = utc(row.interval_start_utc), utc(row.interval_end_utc), utc(row.inputs_available_at_utc)
        before, after = decimal(row.prior_raw_close), decimal(row.current_raw_close)
        if known < end:
            raise NativePairError("completed economic return cannot be available before its ending close")
        failures = []
        if known > ready or not row.publication_and_revision_clocks_qualified:
            failures.append("PUBLICATION_OR_REVISION_CLOCK_UNQUALIFIED_OR_LATE")
        if not row.complete_action_coverage_qualified:
            failures.append("ACTION_COVERAGE_UNQUALIFIED_NO_ZERO_DEFAULT")
        if row.unsupported_action_present:
            failures.append("UNSUPPORTED_NONCASH_OR_IDENTITY_ACTION")
        if row.cash_basis != "PER_ORIGINAL_SHARE_AT_PRIOR_CLOSE":
            failures.append("AMBIGUOUS_CASH_SHARE_BASIS")
        if row.split_new_shares_per_old is None or row.ex_date_cash_per_original_share is None:
            failures.append("MISSING_SPLIT_OR_CASH_INPUT_NO_DEFAULT")
        log_return = None
        if not failures:
            factor = decimal(row.split_new_shares_per_old)
            cash = decimal(row.ex_date_cash_per_original_share, zero=True)
            with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
                gross = (factor * after + cash) / before
                rounded = gross.ln().quantize(Decimal("1e-24"))
                log_return = str(rounded) if rounded else "0"
                if abs(Decimal(log_return)) > 10:
                    raise NativePairError("economic return exceeds the existing variance-input bounds")
            source = _fingerprint(payload(asdict(row)))
            outputs.append(PriorEconomicLogReturnV1(start, end, known, log_return, source))
        reasons.extend(f"{index}:{reason}" for reason in failures)
        rows.append({"interval_start_utc": start.isoformat(), "interval_end_utc": end.isoformat(),
                     "inputs_available_at_utc": known.isoformat(), "log_return": log_return, "reasons": failures})
    # A missing or unqualified interval invalidates the whole fixed lookback;
    # never shrink the window or feed a convenient partial subset to screening.
    if reasons:
        outputs = []
    result = {"contract": "atlas-options-native-synthetic-economic-return-window-v1",
              "specification_fingerprint": SPECIFICATION_FINGERPRINT, "origin": ORIGIN,
              "status": "FIXTURE_ECONOMIC_WINDOW_READY" if not reasons else "FIXTURE_ABSTAIN",
              "feature_cutoff_utc": cutoff.isoformat(), "intervals": rows, "reasons": reasons,
              "prior_returns": outputs, "formula": "ln((split_new_per_old * current_raw_close + ex_date_cash_per_original_share) / prior_raw_close)",
              "account_cash_credited": "0.00", "historical_adjustment_adapter": False,
              "historical_performance_evidence": False, "authority": dict(AUTHORITY)}
    result["window_fingerprint"] = _fingerprint(payload({**result, "prior_returns": [asdict(r) for r in outputs]}))
    return result
