from __future__ import annotations

import math
from datetime import UTC, date, time, timedelta
from typing import Sequence

from packages.core.enums import SessionSegment
from packages.schemas.market import CanonicalBar
from packages.strategies.successor_intraday_rules import (
    MARKET_TZ,
    SUCCESSOR_INTRADAY_RULE_CONTRACT,
    SuccessorIntradaySignal,
)


VWAP_EARLIEST = time(9, 31)
VWAP_LATEST = time(15, 30)
FAILED_BREAK_EARLIEST = time(9, 30)
FAILED_BREAK_LATEST = time(15, 30)


def _local_time(bar: CanonicalBar) -> time:
    return bar.timestamp_utc.astimezone(MARKET_TZ).time()


def _regular_window(
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    earliest: time,
    latest: time,
) -> list[CanonicalBar]:
    selected = sorted(
        (
            bar
            for bar in bars
            if bar.session_date == session_date
            and bar.session_segment == SessionSegment.REGULAR
            and earliest <= _local_time(bar) <= latest
        ),
        key=lambda item: item.timestamp_utc,
    )
    stamps = [bar.timestamp_utc for bar in selected]
    if len(stamps) != len(set(stamps)):
        raise ValueError("duplicate closed one-minute timestamps are not permitted")
    return selected


def _signal(
    *,
    policy_id: str,
    session_date: date,
    direction: str,
    signal_bar: CanonicalBar,
    reasons: tuple[str, ...],
    evidence: dict[str, object],
) -> SuccessorIntradaySignal:
    return SuccessorIntradaySignal(
        contract=SUCCESSOR_INTRADAY_RULE_CONTRACT,
        policy_id=policy_id,
        session_date=session_date.isoformat(),
        ready=True,
        fired=True,
        direction=direction,
        signal_available_at_utc=(signal_bar.timestamp_utc + timedelta(minutes=1))
        .astimezone(UTC)
        .isoformat(),
        reason_codes=reasons,
        evidence=evidence,
    )


def first_vwap_reclaim_reject(
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
) -> SuccessorIntradaySignal | None:
    """Return the first frozen VWAP reclaim/reject fire in one regular-session scan.

    This is execution-equivalent to repeatedly calling
    ``evaluate_vwap_reclaim_reject`` once per candidate minute, but computes the
    cumulative VWAP only once. Missing minutes remain missing and zero-volume
    prefixes remain unavailable exactly as in the frozen evaluator.
    """

    regular = _regular_window(
        bars,
        session_date=session_date,
        earliest=time(9, 30),
        latest=VWAP_LATEST,
    )
    weighted = 0.0
    cumulative_volume = 0.0
    previous: CanonicalBar | None = None
    previous_vwap: float | None = None

    for current in regular:
        if current.volume > 0.0:
            typical = (current.high + current.low + current.close) / 3.0
            weighted += typical * current.volume
            cumulative_volume += current.volume
        current_vwap = (
            None if cumulative_volume <= 0.0 else weighted / cumulative_volume
        )

        current_local = _local_time(current)
        if (
            current_local >= VWAP_EARLIEST
            and previous is not None
            and previous_vwap is not None
            and current_vwap is not None
        ):
            long_fire = previous.close <= previous_vwap and current.close > current_vwap
            short_fire = previous.close >= previous_vwap and current.close < current_vwap
            if long_fire or short_fire:
                return _signal(
                    policy_id="pract_vwap_reclaim_reject_v1",
                    session_date=session_date,
                    direction="LONG" if long_fire else "SHORT",
                    signal_bar=current,
                    reasons=("VWAP_RECLAIM" if long_fire else "VWAP_REJECT",),
                    evidence={
                        "prior_close": previous.close,
                        "prior_cumulative_vwap": previous_vwap,
                        "current_close": current.close,
                        "current_cumulative_vwap": current_vwap,
                        "observed_regular_bars": regular.index(current) + 1,
                    },
                )

        previous = current
        previous_vwap = current_vwap
    return None


def first_session_failed_break_reclaim(
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    prior_regular_high: float,
    prior_regular_low: float,
    premarket_high: float | None,
    premarket_low: float | None,
) -> SuccessorIntradaySignal | None:
    """Return the first frozen failed-break/reclaim fire in one session scan."""

    if not (
        math.isfinite(prior_regular_high)
        and math.isfinite(prior_regular_low)
        and prior_regular_high > prior_regular_low > 0.0
    ):
        raise ValueError("prior regular high/low must be finite positive geometry")

    supports: list[tuple[str, float]] = [("PRIOR_REGULAR_LOW", prior_regular_low)]
    resistances: list[tuple[str, float]] = [("PRIOR_REGULAR_HIGH", prior_regular_high)]
    if (
        premarket_low is not None
        and math.isfinite(premarket_low)
        and premarket_low > 0.0
    ):
        supports.append(("PREMARKET_LOW", float(premarket_low)))
    if (
        premarket_high is not None
        and math.isfinite(premarket_high)
        and premarket_high > 0.0
    ):
        resistances.append(("PREMARKET_HIGH", float(premarket_high)))

    for current in _regular_window(
        bars,
        session_date=session_date,
        earliest=FAILED_BREAK_EARLIEST,
        latest=FAILED_BREAK_LATEST,
    ):
        failed_supports = [
            (name, level)
            for name, level in supports
            if current.low < level and current.close > level
        ]
        failed_resistances = [
            (name, level)
            for name, level in resistances
            if current.high > level and current.close < level
        ]
        if failed_supports and failed_resistances:
            continue
        if failed_supports:
            return _signal(
                policy_id="pract_session_failed_break_reclaim_v1",
                session_date=session_date,
                direction="LONG",
                signal_bar=current,
                reasons=("FAILED_SUPPORT_BREAK_RECLAIMED",),
                evidence={
                    "failed_supports": failed_supports,
                    "failed_resistances": failed_resistances,
                    "bar_low": current.low,
                    "bar_high": current.high,
                    "bar_close": current.close,
                },
            )
        if failed_resistances:
            return _signal(
                policy_id="pract_session_failed_break_reclaim_v1",
                session_date=session_date,
                direction="SHORT",
                signal_bar=current,
                reasons=("FAILED_RESISTANCE_BREAK_REJECTED",),
                evidence={
                    "failed_supports": failed_supports,
                    "failed_resistances": failed_resistances,
                    "bar_low": current.low,
                    "bar_high": current.high,
                    "bar_close": current.close,
                },
            )
    return None
