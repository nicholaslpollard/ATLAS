from __future__ import annotations

"""PIT-causal, source-only premarket context for B34's accepted raw SIP bars.

This is a distinct descriptive research contract, NOT a modification of the
frozen B34 opening pack or the 09:35 options strategy. No outcomes, signals,
order sizing, quote fills, news/earnings assumptions, or provider requests.
"""

from datetime import UTC, date, datetime, time, timedelta
import hashlib
import json
import math
from typing import Iterable
from zoneinfo import ZoneInfo

from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar

CONTRACT = "atlas-b34-causal-premarket-context-v1-source-only"
EASTERN = ZoneInfo("America/New_York")
B34_LAST_SAFE_SESSION = date(2026, 4, 30)
ALPACA_V2_SOURCE_PREFIX = "alpaca:sip:1Min:raw:asof=-:v2:unit="
ALLOWED_DECISIONS_ET = (time(9, 20), time(9, 30), time(9, 35))
PM_START = time(4, 0)
PM_END = time(9, 30)
MAX_ELIGIBLE_BARS = 335  # exactly 330 PM + 5 opening regular minutes


class PremarketContextError(ValueError):
    pass


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        .encode("utf-8")
    ).hexdigest()


def _close_before(stamp: datetime, decision: datetime) -> bool:
    return stamp + timedelta(minutes=1) <= decision


def _time_window(stamp_et: datetime, segment: SessionSegment) -> bool:
    if segment == SessionSegment.PREMARKET:
        return PM_START <= stamp_et.time() < PM_END
    if segment == SessionSegment.REGULAR:
        return PM_END <= stamp_et.time() < time(9, 35)
    return False


def build_context(
    bars: Iterable[CanonicalBar],
    *,
    symbol: str,
    session_date: date,
    decision_clock_et: time,
) -> dict[str, object]:
    """Compute three fixed as-of snapshots from accepted canonical SIP 1m facts.

    The caller may supply *full-day* rows. Anything not closed by the chosen
    decision clock is discarded BEFORE feature computation or content validation.
    This makes features invariant to future regular-session bars.
    """
    if (not symbol or symbol != symbol.strip()
            or session_date > B34_LAST_SAFE_SESSION
            or decision_clock_et not in ALLOWED_DECISIONS_ET):
        raise PremarketContextError("B34_CONTEXT_SCOPE_NOT_AUTHORIZED")
    decision_et = datetime.combine(session_date, decision_clock_et, EASTERN)
    decision_utc = decision_et.astimezone(UTC)

    eligible: list[tuple[datetime, CanonicalBar]] = []
    for bar in bars:
        if not isinstance(bar, CanonicalBar):
            raise PremarketContextError("NONCANONICAL_BAR")
        stamp = bar.timestamp_utc.astimezone(UTC)
        if not _close_before(stamp, decision_utc):
            continue
        local = stamp.astimezone(EASTERN)
        if not _time_window(local, bar.session_segment):
            continue
        if local.date() != session_date:
            continue
        if (bar.symbol != symbol or bar.session_date != session_date
                or bar.timeframe != Timeframe.MINUTE_1
                or bar.provider != DataProvider.ALPACA
                or bar.dataset != DatasetType.STOCK_MINUTE_AGGREGATES
                or bar.is_adjusted is not False
                or bar.provider_timestamp_utc != bar.timestamp_utc
                or not bar.source_id.startswith(ALPACA_V2_SOURCE_PREFIX)):
            raise PremarketContextError("B34_CANONICAL_SOURCE_MISMATCH")
        if stamp.second != 0 or stamp.microsecond != 0:
            raise PremarketContextError("NON_MINUTE_ALIGNED_SOURCE")
        if not all(math.isfinite(v) and v > 0 for v in
                   (bar.open, bar.high, bar.low, bar.close)):
            raise PremarketContextError("B34_INVALID_PRICES")
        if not math.isfinite(bar.volume) or bar.volume < 0:
            raise PremarketContextError("B34_INVALID_VOLUME")
        eligible.append((stamp, bar))
        if len(eligible) > MAX_ELIGIBLE_BARS:
            raise PremarketContextError("B34_PREMARKET_INPUT_BOUND_EXCEEDED")

    eligible.sort(key=lambda pair: pair[0])
    for idx in range(1, len(eligible)):
        if eligible[idx][0] <= eligible[idx - 1][0]:
            raise PremarketContextError("B34_DUPLICATE_CANONICAL_MINUTE")

    pm = [(stamp, bar) for stamp, bar in eligible
          if bar.session_segment == SessionSegment.PREMARKET]
    regular = [(stamp, bar) for stamp, bar in eligible
               if bar.session_segment == SessionSegment.REGULAR]
    if regular and decision_clock_et == time(9, 20):
        raise PremarketContextError("PREOPEN_DECISION_CONTAINS_REGULAR_BAR")

    latest_pm = pm[-1][1] if pm else None
    first_pm = pm[0][1] if pm else None
    latest_regular = regular[-1][1] if regular else None

    premarket_last_available_at = (
        (pm[-1][0] + timedelta(minutes=1)).astimezone(EASTERN).isoformat()
        if pm else None
    )
    cumulative_pm_volume = sum(bar.volume for _, bar in pm)
    if latest_pm is not None:
        pm_high = max(bar.high for _, bar in pm)
        pm_low = min(bar.low for _, bar in pm)
        pm_first_to_last = (latest_pm.close / first_pm.open) - 1.0
    else:
        pm_high = pm_low = pm_first_to_last = None

    features: dict[str, object] = {
        "premarket_observed_minutes": len(pm),
        "premarket_cumulative_volume": cumulative_pm_volume,
        "premarket_high": pm_high,
        "premarket_low": pm_low,
        "premarket_last_close": latest_pm.close if latest_pm else None,
        "premarket_first_open_to_last_close_pct": pm_first_to_last,
        "premarket_last_bar_available_et": premarket_last_available_at,
        "regular_observed_closed_minutes": len(regular),
        "regular_opening_range_high_so_far": (
            max(bar.high for _, bar in regular) if regular else None
        ),
        "regular_opening_range_low_so_far": (
            min(bar.low for _, bar in regular) if regular else None
        ),
        "regular_last_closed_price": (
            latest_regular.close if latest_regular else None
        ),
        "regular_last_vs_premarket_close_pct": (
            latest_regular.close / latest_pm.close - 1.0
            if latest_regular and latest_pm else None
        ),
        "premarket_volume_rel_20": None,  # prior-20 PIT session data absent
        "prior_regular_close_gap": None,  # PIT split/close join not performed
        "news_catalyst_score": None,  # as-of publication gate not performed
        "option_bid_ask": None,  # paid at-time quote not source-qualified
    }

    # Hash ONLY eligible, validated facts. Never hash future bars or values.
    selected = [
        {
            "timestamp_utc": stamp.isoformat(),
            "session_segment": bar.session_segment.value,
            "source_id": bar.source_id,
            "open": bar.open, "high": bar.high, "low": bar.low,
            "close": bar.close, "volume": bar.volume,
        }
        for stamp, bar in eligible
    ]
    return {
        "contract": CONTRACT,
        "symbol": symbol,
        "session_date": session_date.isoformat(),
        "decision_et": decision_et.isoformat(),
        "source_bar_available_rule": "minute_left_edge_plus_1_minute",
        "last_source_minute_utc": selected[-1]["timestamp_utc"] if selected else None,
        "eligible_source_bars_sha256": _sha(selected),
        "feature_status": (
            "OBSERVED_PREMARKET_CONTEXT" if pm
            else "NO_OBSERVED_PREMARKET_BARS"
        ),
        "features": features,
        "authority": "RESEARCH_ONLY_NO_OUTCOMES_NO_ORDERS",
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_opened": 0,
    }


def build_three_cutoffs(
    bars: Iterable[CanonicalBar], *, symbol: str, session_date: date
) -> tuple[dict[str, object], ...]:
    """Materialize exactly once; no repeated data source queries."""
    materialized = tuple(bars)
    return tuple(
        build_context(materialized, symbol=symbol, session_date=session_date,
                      decision_clock_et=clock)
        for clock in ALLOWED_DECISIONS_ET
    )
