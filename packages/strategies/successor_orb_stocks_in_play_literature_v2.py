from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, time
from typing import Sequence
from zoneinfo import ZoneInfo

from packages.schemas.market import CanonicalBar
from packages.strategies.successor_orb_stocks_in_play_literature_v2_contract import (
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID,
)


MARKET_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class LiteratureOrbV2Signal:
    policy_id: str
    session_date: str
    direction: str
    opening_range_high: float
    opening_range_low: float
    opening_price: float
    opening_close: float
    opening_relvol_14: float
    daily_relvol_rank: int
    prior_average_daily_share_volume_14: float
    prior_atr_14_dollars: float
    entry_stop_price: float
    entry_price: float
    entry_timestamp_utc: str
    entry_fill_reason: str
    stop_loss_price: float


def _regular_session_bars(
    bars: Sequence[CanonicalBar], *, session_date: date
) -> list[CanonicalBar]:
    return sorted(
        (
            bar
            for bar in bars
            if bar.session_date == session_date
            and bar.session_segment.value == "regular"
        ),
        key=lambda bar: bar.timestamp_utc,
    )


def evaluate_orb_stocks_in_play_literature_v2(
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    prior_average_daily_share_volume_14: float,
    prior_atr_14_dollars: float,
    opening_relvol_14: float,
    daily_relvol_rank: int,
) -> LiteratureOrbV2Signal | None:
    """Evaluate the frozen literature-fidelity 5-minute ORB entry only.

    Cross-sectional rank and the two 14-session historical inputs are supplied by
    the future DEVELOPMENT runner so this function cannot infer them from the
    current session or use information after 09:35 ET.  Outcome/stop ordering is
    intentionally not evaluated here.
    """

    if not all(
        math.isfinite(float(value))
        for value in (
            prior_average_daily_share_volume_14,
            prior_atr_14_dollars,
            opening_relvol_14,
        )
    ):
        return None
    if prior_average_daily_share_volume_14 < 1_000_000.0:
        return None
    if prior_atr_14_dollars <= 0.50:
        return None
    if opening_relvol_14 < 1.0:
        return None
    if daily_relvol_rank < 1 or daily_relvol_rank > 20:
        return None

    regular = _regular_session_bars(bars, session_date=session_date)
    opening = [
        bar
        for bar in regular
        if time(9, 30)
        <= bar.timestamp_utc.astimezone(MARKET_TZ).time().replace(tzinfo=None)
        < time(9, 35)
    ]
    if len(opening) != 5:
        return None

    opening_price = float(opening[0].open)
    opening_close = float(opening[-1].close)
    if not math.isfinite(opening_price) or opening_price <= 5.0:
        return None
    if not math.isfinite(opening_close):
        return None
    if math.isclose(opening_close, opening_price, rel_tol=0.0, abs_tol=1e-12):
        return None

    direction = "LONG" if opening_close > opening_price else "SHORT"
    range_high = max(float(bar.high) for bar in opening)
    range_low = min(float(bar.low) for bar in opening)
    if not (math.isfinite(range_high) and math.isfinite(range_low) and range_high > range_low > 0.0):
        return None

    entry_stop = range_high if direction == "LONG" else range_low
    post_opening = [
        bar
        for bar in regular
        if bar.timestamp_utc.astimezone(MARKET_TZ).time().replace(tzinfo=None)
        >= time(9, 35)
    ]
    for bar in post_opening:
        bar_open = float(bar.open)
        bar_high = float(bar.high)
        bar_low = float(bar.low)
        if direction == "LONG":
            if bar_open >= entry_stop:
                entry_price = bar_open
                fill_reason = "GAP_THROUGH_STOP_AT_BAR_OPEN"
            elif bar_high >= entry_stop:
                entry_price = entry_stop
                fill_reason = "STOP_CROSS_AT_STOP_PRICE"
            else:
                continue
            stop_loss = entry_price - 0.10 * float(prior_atr_14_dollars)
        else:
            if bar_open <= entry_stop:
                entry_price = bar_open
                fill_reason = "GAP_THROUGH_STOP_AT_BAR_OPEN"
            elif bar_low <= entry_stop:
                entry_price = entry_stop
                fill_reason = "STOP_CROSS_AT_STOP_PRICE"
            else:
                continue
            stop_loss = entry_price + 0.10 * float(prior_atr_14_dollars)

        return LiteratureOrbV2Signal(
            policy_id=ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID,
            session_date=session_date.isoformat(),
            direction=direction,
            opening_range_high=range_high,
            opening_range_low=range_low,
            opening_price=opening_price,
            opening_close=opening_close,
            opening_relvol_14=float(opening_relvol_14),
            daily_relvol_rank=int(daily_relvol_rank),
            prior_average_daily_share_volume_14=float(
                prior_average_daily_share_volume_14
            ),
            prior_atr_14_dollars=float(prior_atr_14_dollars),
            entry_stop_price=float(entry_stop),
            entry_price=float(entry_price),
            entry_timestamp_utc=bar.timestamp_utc.isoformat().replace("+00:00", "Z"),
            entry_fill_reason=fill_reason,
            stop_loss_price=float(stop_loss),
        )

    return None
