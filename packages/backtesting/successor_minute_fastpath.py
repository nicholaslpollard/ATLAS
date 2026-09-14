from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from statistics import median
from typing import Sequence

import pandas as pd

from packages.core.enums import (
    DataProvider,
    DatasetType,
    SessionSegment,
    Timeframe,
)
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
REGULAR_START = time(9, 30)
ORB_ENTRY_CUTOFF = time(11, 30)
ORB_RETEST_BREAKOUT_CUTOFF = time(11, 0)
PREMARKET_START = time(4, 0)
PREMARKET_END = time(9, 30)
PREMARKET_CONSOLIDATION_START = time(9, 0)
PREMARKET_CONSOLIDATION_END = time(9, 30)


@dataclass(frozen=True, slots=True)
class SuccessorMinuteSessionView:
    """One immutable partition/sort of a source-validated minute session."""

    session_date: date
    regular: tuple[CanonicalBar, ...]
    regular_times: tuple[time, ...]
    premarket: tuple[CanonicalBar, ...]
    premarket_times: tuple[time, ...]


_CACHED_BARS: Sequence[CanonicalBar] | None = None
_CACHED_VIEW: SuccessorMinuteSessionView | None = None
_ENGINE_FASTPATH_INSTALLED = False
_RUNNER_FASTPATH_INSTALLED = False


def _local_time(bar: CanonicalBar) -> time:
    return bar.timestamp_utc.astimezone(MARKET_TZ).time()


def _assert_unique(values: Sequence[CanonicalBar]) -> None:
    stamps = [bar.timestamp_utc for bar in values]
    if len(stamps) != len(set(stamps)):
        raise ValueError("duplicate closed one-minute timestamps are not permitted")


def prepare_successor_minute_session(
    bars: Sequence[CanonicalBar], *, session_date: date
) -> SuccessorMinuteSessionView:
    regular = tuple(
        sorted(
            (
                bar
                for bar in bars
                if bar.timeframe == Timeframe.MINUTE_1
                and bar.session_date == session_date
                and bar.session_segment == SessionSegment.REGULAR
            ),
            key=lambda item: item.timestamp_utc,
        )
    )
    premarket = tuple(
        sorted(
            (
                bar
                for bar in bars
                if bar.timeframe == Timeframe.MINUTE_1
                and bar.session_date == session_date
                and bar.session_segment == SessionSegment.PREMARKET
            ),
            key=lambda item: item.timestamp_utc,
        )
    )
    _assert_unique(regular)
    _assert_unique(premarket)
    return SuccessorMinuteSessionView(
        session_date=session_date,
        regular=regular,
        regular_times=tuple(_local_time(bar) for bar in regular),
        premarket=premarket,
        premarket_times=tuple(_local_time(bar) for bar in premarket),
    )


def _view_from_bars(
    bars: Sequence[CanonicalBar], session_date: date
) -> SuccessorMinuteSessionView:
    global _CACHED_BARS, _CACHED_VIEW
    if (
        _CACHED_BARS is bars
        and _CACHED_VIEW is not None
        and _CACHED_VIEW.session_date == session_date
    ):
        return _CACHED_VIEW
    view = prepare_successor_minute_session(bars, session_date=session_date)
    _CACHED_BARS = bars
    _CACHED_VIEW = view
    _install_runtime_fastpaths()
    return view


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
    bars: Sequence[CanonicalBar] | None = None,
    *,
    session_date: date,
    view: SuccessorMinuteSessionView | None = None,
) -> SuccessorIntradaySignal | None:
    """Return the first frozen VWAP reclaim/reject fire in one regular-session scan."""

    session = view or _view_from_bars(tuple(bars or ()) if bars is None else bars, session_date)
    weighted = 0.0
    cumulative_volume = 0.0
    previous: CanonicalBar | None = None
    previous_vwap: float | None = None
    observed_regular_bars = 0

    for current, current_local in zip(
        session.regular, session.regular_times, strict=True
    ):
        if current_local < REGULAR_START or current_local > VWAP_LATEST:
            continue
        observed_regular_bars += 1
        if current.volume > 0.0:
            typical = (current.high + current.low + current.close) / 3.0
            weighted += typical * current.volume
            cumulative_volume += current.volume
        current_vwap = (
            None if cumulative_volume <= 0.0 else weighted / cumulative_volume
        )

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
                        "observed_regular_bars": observed_regular_bars,
                    },
                )

        previous = current
        previous_vwap = current_vwap
    return None


def first_session_failed_break_reclaim(
    bars: Sequence[CanonicalBar] | None = None,
    *,
    session_date: date,
    prior_regular_high: float,
    prior_regular_low: float,
    premarket_high: float | None,
    premarket_low: float | None,
    view: SuccessorMinuteSessionView | None = None,
) -> SuccessorIntradaySignal | None:
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

    session = view or _view_from_bars(tuple(bars or ()) if bars is None else bars, session_date)
    for current, current_local in zip(
        session.regular, session.regular_times, strict=True
    ):
        if current_local < FAILED_BREAK_EARLIEST or current_local > FAILED_BREAK_LATEST:
            continue
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


def first_gap_quality_condition_long(
    *,
    session_date: date,
    view: SuccessorMinuteSessionView,
    prior_regular_close: float,
    prior_median_dollar_volume_20: float,
    natr_14: float,
    premarket_relvol_20: float,
    split_crossed: bool,
) -> SuccessorIntradaySignal | None:
    if split_crossed:
        return None
    opening_bar = next(
        (
            bar
            for bar, stamp in zip(view.regular, view.regular_times, strict=True)
            if stamp == time(9, 30)
        ),
        None,
    )
    if opening_bar is None:
        return None
    current_regular_open = float(opening_bar.open)
    quality_price = float(opening_bar.close)
    values = (
        prior_regular_close,
        current_regular_open,
        quality_price,
        prior_median_dollar_volume_20,
        natr_14,
        premarket_relvol_20,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("gap quality inputs must be finite")
    if prior_regular_close <= 0.0 or current_regular_open <= 0.0 or quality_price <= 0.0:
        raise ValueError("gap quality prices must be positive")
    gap = current_regular_open / prior_regular_close - 1.0
    checks = {
        "gap_ge_2pct": gap >= 0.02,
        "price_ge_5": quality_price >= 5.0,
        "prior_median_dollar_volume_20_ge_20m": prior_median_dollar_volume_20
        >= 20_000_000.0,
        "natr_14_ge_1pct": natr_14 >= 0.01,
        "natr_14_le_8pct": natr_14 <= 0.08,
        "premarket_relvol_20_ge_1_5": premarket_relvol_20 >= 1.5,
    }
    if not all(checks.values()):
        return None
    return _signal(
        policy_id="gap_quality_condition_long_v2",
        session_date=session_date,
        direction="LONG",
        signal_bar=opening_bar,
        reasons=("QUALITY_GATE_PASS",),
        evidence={
            "gap_fraction": gap,
            "quality_price_0930_close": quality_price,
            "checks": checks,
        },
    )


def first_orb_stocks_in_play_5m(
    *,
    session_date: date,
    view: SuccessorMinuteSessionView,
    same_time_opening_relvol: float,
    prior_median_dollar_volume_20: float,
) -> SuccessorIntradaySignal | None:
    if not all(
        math.isfinite(value)
        for value in (same_time_opening_relvol, prior_median_dollar_volume_20)
    ):
        raise ValueError("ORB stocks-in-play scalar inputs must be finite")
    opening = [
        bar
        for bar, stamp in zip(view.regular, view.regular_times, strict=True)
        if time(9, 30) <= stamp < time(9, 35)
    ]
    if len(opening) < 5:
        return None
    range_high = max(bar.high for bar in opening)
    range_low = min(bar.low for bar in opening)
    opening_quality_price = float(opening[-1].close)
    quality = {
        "same_time_opening_relvol_ge_2": same_time_opening_relvol >= 2.0,
        "prior_median_dollar_volume_20_ge_20m": prior_median_dollar_volume_20
        >= 20_000_000.0,
        "price_ge_5": opening_quality_price >= 5.0,
    }
    if not all(quality.values()):
        return None
    evidence = {
        "checks": quality,
        "range_high": range_high,
        "range_low": range_low,
        "opening_quality_price_0934_close": opening_quality_price,
    }
    for bar, stamp in zip(view.regular, view.regular_times, strict=True):
        if stamp < time(9, 35) or stamp > ORB_ENTRY_CUTOFF:
            continue
        if bar.close > range_high:
            return _signal(
                policy_id="orb_stocks_in_play_5m_v1",
                session_date=session_date,
                direction="LONG",
                signal_bar=bar,
                reasons=("FIVE_MINUTE_ORB_BREAKOUT", "STOCKS_IN_PLAY_GATE_PASS"),
                evidence=evidence,
            )
        if bar.close < range_low:
            return _signal(
                policy_id="orb_stocks_in_play_5m_v1",
                session_date=session_date,
                direction="SHORT",
                signal_bar=bar,
                reasons=("FIVE_MINUTE_ORB_BREAKDOWN", "STOCKS_IN_PLAY_GATE_PASS"),
                evidence=evidence,
            )
    return None


def first_orb_15m_close_retest(
    *,
    session_date: date,
    view: SuccessorMinuteSessionView,
    atr_reference: float,
) -> SuccessorIntradaySignal | None:
    if not math.isfinite(atr_reference) or atr_reference <= 0.0:
        raise ValueError("ATR reference must be finite and positive")
    opening = [
        bar
        for bar, stamp in zip(view.regular, view.regular_times, strict=True)
        if time(9, 30) <= stamp < time(9, 45)
    ]
    if len(opening) < 15:
        return None
    range_high = max(bar.high for bar in opening)
    range_low = min(bar.low for bar in opening)
    post = [
        (bar, stamp)
        for bar, stamp in zip(view.regular, view.regular_times, strict=True)
        if time(9, 45) <= stamp <= VWAP_LATEST
    ]
    breakout_index: int | None = None
    breakout_direction: str | None = None
    boundary: float | None = None
    for index, (bar, stamp) in enumerate(post):
        if stamp > ORB_RETEST_BREAKOUT_CUTOFF:
            break
        if bar.close > range_high:
            breakout_index, breakout_direction, boundary = index, "LONG", range_high
            break
        if bar.close < range_low:
            breakout_index, breakout_direction, boundary = index, "SHORT", range_low
            break
    if breakout_index is None or breakout_direction is None or boundary is None:
        return None
    breakout = post[breakout_index][0]
    retest_limit = min(len(post), breakout_index + 6)
    for retest_index in range(breakout_index + 1, retest_limit):
        retest = post[retest_index][0]
        touches = (
            retest.low <= boundary + 0.25 * atr_reference
            if breakout_direction == "LONG"
            else retest.high >= boundary - 0.25 * atr_reference
        )
        holds = (
            retest.close >= boundary
            if breakout_direction == "LONG"
            else retest.close <= boundary
        )
        if not (touches and holds):
            continue
        confirmation_index = retest_index + 1
        if confirmation_index >= len(post):
            return None
        confirmation = post[confirmation_index][0]
        confirmed = (
            confirmation.close >= boundary + 0.10 * atr_reference
            if breakout_direction == "LONG"
            else confirmation.close <= boundary - 0.10 * atr_reference
        )
        if confirmed:
            return _signal(
                policy_id="orb_15m_close_retest_v2",
                session_date=session_date,
                direction=breakout_direction,
                signal_bar=confirmation,
                reasons=("BREAKOUT_RETEST_HOLD_CONFIRMED",),
                evidence={
                    "range_high": range_high,
                    "range_low": range_low,
                    "boundary": boundary,
                    "atr_reference": atr_reference,
                    "breakout_stamp_utc": breakout.timestamp_utc.isoformat(),
                    "retest_stamp_utc": retest.timestamp_utc.isoformat(),
                    "confirmation_stamp_utc": confirmation.timestamp_utc.isoformat(),
                },
            )
    return None


def first_premarket_relvol_quality(
    *,
    session_date: date,
    view: SuccessorMinuteSessionView,
    prior_premarket_median_volume_20: float,
    prior_median_dollar_volume_20: float,
    breakout_same_time_relvol_by_timestamp: dict[datetime, float],
) -> SuccessorIntradaySignal | None:
    scalar_values = (prior_premarket_median_volume_20, prior_median_dollar_volume_20)
    if not all(math.isfinite(value) for value in scalar_values):
        raise ValueError("premarket quality scalar inputs must be finite")
    if prior_premarket_median_volume_20 <= 0.0:
        return None
    premarket = [
        bar
        for bar, stamp in zip(view.premarket, view.premarket_times, strict=True)
        if PREMARKET_START <= stamp < PREMARKET_END
    ]
    consolidation = [
        bar
        for bar, stamp in zip(view.premarket, view.premarket_times, strict=True)
        if PREMARKET_CONSOLIDATION_START <= stamp < PREMARKET_CONSOLIDATION_END
    ]
    if len(consolidation) < 5:
        return None
    pm_volume = sum(bar.volume for bar in premarket)
    pm_dollar_volume = sum(
        ((bar.high + bar.low + bar.close) / 3.0) * bar.volume for bar in premarket
    )
    relvol = pm_volume / prior_premarket_median_volume_20
    consolidation_high = max(bar.high for bar in consolidation)
    consolidation_low = min(bar.low for bar in consolidation)
    quality_price = float(consolidation[-1].close)
    consolidation_range = (
        (consolidation_high - consolidation_low) / quality_price
        if quality_price > 0.0
        else math.inf
    )
    static_quality = {
        "premarket_relvol_ge_2": relvol >= 2.0,
        "consolidation_range_le_3pct": consolidation_range <= 0.03,
        "prior_median_dollar_volume_20_ge_20m": prior_median_dollar_volume_20
        >= 20_000_000.0,
        "price_ge_5": quality_price >= 5.0,
        "premarket_dollar_volume_ge_2m": pm_dollar_volume >= 2_000_000.0,
    }
    if not all(static_quality.values()):
        return None
    base_evidence = {
        "premarket_relvol": relvol,
        "premarket_dollar_volume": pm_dollar_volume,
        "consolidation_high": consolidation_high,
        "consolidation_low": consolidation_low,
        "consolidation_range_fraction": consolidation_range,
        "quality_price_last_consolidation_close": quality_price,
        "checks": static_quality,
    }
    first_breakout = next(
        (
            bar
            for bar, stamp in zip(view.regular, view.regular_times, strict=True)
            if REGULAR_START <= stamp <= ORB_ENTRY_CUTOFF
            and bar.close > consolidation_high
        ),
        None,
    )
    if first_breakout is None:
        return None
    breakout_relvol = breakout_same_time_relvol_by_timestamp.get(
        first_breakout.timestamp_utc
    )
    if breakout_relvol is None or not math.isfinite(float(breakout_relvol)):
        return None
    breakout_relvol = float(breakout_relvol)
    if breakout_relvol < 1.5:
        return None
    evidence = {
        **base_evidence,
        "first_breakout_stamp_utc": first_breakout.timestamp_utc.isoformat(),
        "first_breakout_same_time_relvol": breakout_relvol,
        "breakout_same_time_relvol_ge_1_5": True,
    }
    return _signal(
        policy_id="premarket_relvol_quality_v2",
        session_date=session_date,
        direction="LONG",
        signal_bar=first_breakout,
        reasons=("PREMARKET_QUALITY_PASS", "CONSOLIDATION_BREAKOUT"),
        evidence=evidence,
    )


def _opening_relvol(history: object, view: SuccessorMinuteSessionView) -> float | None:
    prior_values = getattr(history, "opening_five_minute_volumes")
    if len(prior_values) < 20:
        return None
    opening = [
        bar
        for bar, stamp in zip(view.regular, view.regular_times, strict=True)
        if time(9, 30) <= stamp < time(9, 35)
    ]
    if len(opening) != 5:
        return None
    denominator = float(median(value for _, value in prior_values[-20:]))
    if denominator <= 0.0:
        return None
    return float(sum(float(item.volume) for item in opening)) / denominator


def _premarket_volume_from_view(view: SuccessorMinuteSessionView) -> float | None:
    selected = [
        bar
        for bar, stamp in zip(view.premarket, view.premarket_times, strict=True)
        if PREMARKET_START <= stamp < PREMARKET_END
    ]
    if not selected:
        return None
    return float(sum(float(bar.volume) for bar in selected))


def _same_time_relvol_map(
    history: object, view: SuccessorMinuteSessionView
) -> dict[datetime, float]:
    result: dict[datetime, float] = {}
    prior_map = getattr(history, "same_time_regular_volumes")
    for item, local_time in zip(view.regular, view.regular_times, strict=True):
        key = local_time.replace(tzinfo=None)
        prior = prior_map.get(key, [])
        if len(prior) < 20:
            continue
        denominator = float(median(value for _, value in prior[-20:]))
        if denominator > 0.0:
            result[item.timestamp_utc] = float(item.volume) / denominator
    return result


def optimized_new_successor_minute_signals(
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    history: object,
    current_epoch: float,
) -> list[tuple[SuccessorIntradaySignal, float | None, float | None]]:
    """Execution-equivalent successor route scan using one shared session view."""

    view = _view_from_bars(bars, session_date)
    signals: list[tuple[SuccessorIntradaySignal, float | None, float | None]] = []
    daily = getattr(history, "daily")
    prior = daily[-1] if daily else None
    prior_close = None if prior is None else float(prior.close)
    prior_dv = history.prior_median_dollar_volume_20()
    prior_pm_median = history.prior_premarket_median_volume_20()
    natr14 = history.prior_natr_14(current_epoch)
    opening_relvol = _opening_relvol(history, view)
    pm_volume = _premarket_volume_from_view(view)
    pm_relvol = (
        None
        if pm_volume is None or prior_pm_median is None or prior_pm_median <= 0.0
        else pm_volume / prior_pm_median
    )

    vwap = first_vwap_reclaim_reject(session_date=session_date, view=view)
    if vwap is not None:
        signals.append((vwap, opening_relvol, pm_relvol))

    valid_prior = bool(
        prior is not None
        and math.isfinite(float(prior.high))
        and math.isfinite(float(prior.low))
        and float(prior.high) > float(prior.low) > 0.0
    )
    split_crossed = history.split_crossed_prior_close(current_epoch)
    if valid_prior and not split_crossed:
        pm_high = max((float(item.high) for item in view.premarket), default=None)
        pm_low = min((float(item.low) for item in view.premarket), default=None)
        failed_break = first_session_failed_break_reclaim(
            session_date=session_date,
            prior_regular_high=float(prior.high),
            prior_regular_low=float(prior.low),
            premarket_high=pm_high,
            premarket_low=pm_low,
            view=view,
        )
        if failed_break is not None:
            signals.append((failed_break, opening_relvol, pm_relvol))

    if (
        prior_close is not None
        and prior_dv is not None
        and natr14 is not None
        and pm_relvol is not None
    ):
        gap = first_gap_quality_condition_long(
            session_date=session_date,
            view=view,
            prior_regular_close=prior_close,
            prior_median_dollar_volume_20=prior_dv,
            natr_14=natr14,
            premarket_relvol_20=pm_relvol,
            split_crossed=split_crossed,
        )
        if gap is not None:
            signals.append((gap, opening_relvol, pm_relvol))

    if prior_dv is not None and opening_relvol is not None:
        orb5 = first_orb_stocks_in_play_5m(
            session_date=session_date,
            view=view,
            same_time_opening_relvol=opening_relvol,
            prior_median_dollar_volume_20=prior_dv,
        )
        if orb5 is not None:
            signals.append((orb5, opening_relvol, pm_relvol))

    if natr14 is not None and prior_close is not None:
        atr_reference = natr14 * prior_close
        if atr_reference > 0.0:
            orb15 = first_orb_15m_close_retest(
                session_date=session_date,
                view=view,
                atr_reference=atr_reference,
            )
            if orb15 is not None:
                signals.append((orb15, opening_relvol, pm_relvol))

    if prior_pm_median is not None and prior_dv is not None:
        pm_quality = first_premarket_relvol_quality(
            session_date=session_date,
            view=view,
            prior_premarket_median_volume_20=prior_pm_median,
            prior_median_dollar_volume_20=prior_dv,
            breakout_same_time_relvol_by_timestamp=_same_time_relvol_map(history, view),
        )
        if pm_quality is not None:
            signals.append((pm_quality, opening_relvol, pm_relvol))
    return signals


def fast_prior_natr_14(history: object, current_epoch: float) -> float | None:
    same_epoch = []
    for item in reversed(getattr(history, "daily")):
        if not math.isclose(
            float(item.split_epoch), current_epoch, rel_tol=1e-10, abs_tol=1e-12
        ):
            break
        same_epoch.append(item)
    same_epoch.reverse()
    if len(same_epoch) < 14:
        return None

    true_ranges: list[float] = []
    previous_close: float | None = None
    for item in same_epoch:
        high = float(item.high)
        low = float(item.low)
        close = float(item.close)
        if previous_close is None:
            true_range = high - low
        else:
            true_range = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        true_ranges.append(true_range)
        previous_close = close

    average = sum(true_ranges[:14]) / 14.0
    for value in true_ranges[14:]:
        average = (average * 13.0 + value) / 14.0
    latest_close = float(same_epoch[-1].close)
    if latest_close <= 0.0:
        return None
    result = average / latest_close
    return result if math.isfinite(result) else None


def fast_append_session(
    history: object,
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    split_epoch: float,
) -> None:
    view = _view_from_bars(bars, session_date)
    premarket = [
        bar
        for bar, stamp in zip(view.premarket, view.premarket_times, strict=True)
        if PREMARKET_START <= stamp < PREMARKET_END
    ]
    if premarket:
        history.premarket_volumes.append(
            (session_date, float(sum(float(item.volume) for item in premarket)))
        )
        del history.premarket_volumes[:-25]
    regular = view.regular
    if not regular:
        return

    # Import only after the engine module is fully initialized; this avoids an
    # import cycle while preserving the exact RawMinuteDailySummary type.
    engine = sys.modules.get("packages.backtesting.successor_development_engine")
    if engine is None:
        raise RuntimeError("successor engine is not loaded")
    summary_type = getattr(engine, "RawMinuteDailySummary")
    history.daily.append(
        summary_type(
            session_date=session_date,
            high=max(float(item.high) for item in regular),
            low=min(float(item.low) for item in regular),
            close=float(regular[-1].close),
            dollar_volume=float(
                sum(
                    float(item.volume)
                    * float(item.vwap if item.vwap is not None else item.close)
                    for item in regular
                )
            ),
            split_epoch=split_epoch,
        )
    )
    del history.daily[:-260]

    opening = [
        item
        for item, stamp in zip(view.regular, view.regular_times, strict=True)
        if time(9, 30) <= stamp < time(9, 35)
    ]
    if len(opening) == 5:
        history.opening_five_minute_volumes.append(
            (session_date, float(sum(float(item.volume) for item in opening)))
        )
        del history.opening_five_minute_volumes[:-25]
    for item, local_time in zip(view.regular, view.regular_times, strict=True):
        key = local_time.replace(tzinfo=None)
        prior = history.same_time_regular_volumes.setdefault(key, [])
        prior.append((session_date, float(item.volume)))
        del prior[:-25]


def fast_current_regular_open(
    bars: Sequence[CanonicalBar], session_date: date
) -> float | None:
    view = _view_from_bars(bars, session_date)
    return float(view.regular[0].open) if view.regular else None


def fast_premarket_volume(
    bars: Sequence[CanonicalBar], session_date: date
) -> float | None:
    return _premarket_volume_from_view(_view_from_bars(bars, session_date))


def _utc_datetime(value: object) -> datetime:
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("source-validated minute timestamp lost timezone awareness")
    return value.astimezone(UTC)


def trusted_canonical_bars(frame: pd.DataFrame) -> tuple[CanonicalBar, ...]:
    """Construct CanonicalBar objects after B35 physical validation has passed.

    ``B35DevelopmentMinuteSource.load_unit`` has already checked OHLC geometry,
    timestamps, provider/dataset/timeframe/source identity, session labels,
    duplicate keys, non-negative volume/transactions, and the canonical SHA-256.
    Re-running the Pydantic validation stack for every bar is therefore redundant
    execution work and does not add a new scientific check.
    """

    bars: list[CanonicalBar] = []
    isna = pd.isna
    construct = CanonicalBar.model_construct
    for row in frame.itertuples(index=False):
        timestamp = _utc_datetime(row.timestamp_utc)
        vwap = None if isna(row.vwap) else float(row.vwap)
        transaction_count = (
            None if isna(row.transaction_count) else int(row.transaction_count)
        )
        bars.append(
            construct(
                symbol=str(row.symbol),
                timestamp_utc=timestamp,
                session_date=row.session_date,
                timeframe=Timeframe.MINUTE_1,
                session_segment=SessionSegment(str(row.session_segment)),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
                vwap=vwap,
                transaction_count=transaction_count,
                provider=DataProvider.ALPACA,
                dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
                source_id=str(row.source_id),
                is_adjusted=False,
                provider_timestamp_utc=timestamp,
            )
        )
    return tuple(bars)


def _install_runtime_fastpaths() -> None:
    """Install execution-only worker accelerators after import cycles are complete."""

    global _ENGINE_FASTPATH_INSTALLED, _RUNNER_FASTPATH_INSTALLED
    engine = sys.modules.get("packages.backtesting.successor_development_engine")
    if engine is not None and not _ENGINE_FASTPATH_INSTALLED:
        engine._new_successor_minute_signals = optimized_new_successor_minute_signals
        engine._current_regular_open = fast_current_regular_open
        engine._premarket_volume = fast_premarket_volume
        engine.SuccessorMinuteHistory.prior_natr_14 = fast_prior_natr_14
        engine.SuccessorMinuteHistory.append_session = fast_append_session
        _ENGINE_FASTPATH_INSTALLED = True

    runner = sys.modules.get("packages.backtesting.successor_development_runner")
    if runner is not None and not _RUNNER_FASTPATH_INSTALLED:
        runner._canonical_bars = trusted_canonical_bars
        _RUNNER_FASTPATH_INSTALLED = True
