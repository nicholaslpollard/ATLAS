from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

from packages.core.enums import SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar


SUCCESSOR_INTRADAY_RULE_CONTRACT = (
    "successor-intraday-rules-v1-closed-bar-pit-objective-quality-and-retest"
)
MARKET_TZ = ZoneInfo("America/New_York")
REGULAR_START = time(9, 30)
VWAP_ENTRY_CUTOFF = time(15, 30)
ORB_ENTRY_CUTOFF = time(11, 30)
ORB_RETEST_BREAKOUT_CUTOFF = time(11, 0)
PREMARKET_START = time(4, 0)
PREMARKET_END = time(9, 30)
PREMARKET_CONSOLIDATION_START = time(9, 0)
PREMARKET_CONSOLIDATION_END = time(9, 30)


@dataclass(frozen=True, slots=True)
class SuccessorIntradaySignal:
    contract: str
    policy_id: str
    session_date: str
    ready: bool
    fired: bool
    direction: str | None
    signal_available_at_utc: str | None
    reason_codes: tuple[str, ...]
    evidence: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def successor_intraday_rule_fingerprint() -> str:
    return _stable_hash(
        {
            "contract": SUCCESSOR_INTRADAY_RULE_CONTRACT,
            "information_clock": "1m left-edge bar is usable only at timestamp+1 minute",
            "missing_bar_policy": "absence remains absence; required complete ranges fail closed",
            "vwap": "observed regular HLC3*volume cumulative VWAP",
            "failed_break_levels": "prior regular high/low plus observed premarket high/low",
            "gap_quality": {"gap_min": 0.02, "price_min": 5.0, "prior_median_dollar_volume_20_min": 20_000_000.0, "natr_14_min": 0.01, "natr_14_max": 0.08, "premarket_relvol_20_min": 1.5},
            "orb_5m": {"required_bars": 5, "same_time_relvol_min": 2.0, "prior_median_dollar_volume_20_min": 20_000_000.0, "price_min": 5.0, "cutoff": "11:30"},
            "orb_15m_retest": {"required_bars": 15, "retest_bars": 5, "retest_atr_fraction": 0.25, "confirmation_atr_fraction": 0.10, "breakout_cutoff": "11:00"},
            "premarket_quality": {"premarket_relvol_min": 2.0, "consolidation_max_fraction": 0.03, "consolidation_min_bars": 5, "prior_median_dollar_volume_20_min": 20_000_000.0, "price_min": 5.0, "premarket_dollar_volume_min": 2_000_000.0, "breakout_same_time_relvol_min": 1.5, "cutoff": "11:30"},
            "authority": "RESEARCH_ONLY_NO_OUTCOME_NO_PAPER_NO_LIVE",
        }
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("decision time must be timezone-aware")
    return value.astimezone(UTC)


def _local_time(bar: CanonicalBar) -> time:
    return bar.timestamp_utc.astimezone(MARKET_TZ).time()


def _closed(bar: CanonicalBar, decision_utc: datetime) -> bool:
    return bar.timestamp_utc + timedelta(minutes=1) <= decision_utc


def _closed_session_bars(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
    decision_time_utc: datetime,
    segment: SessionSegment | None = None,
) -> list[CanonicalBar]:
    decision = _aware_utc(decision_time_utc)
    selected = [
        bar
        for bar in bars
        if bar.timeframe == Timeframe.MINUTE_1
        and bar.session_date == session_date
        and _closed(bar, decision)
        and (segment is None or bar.session_segment == segment)
    ]
    ordered = sorted(selected, key=lambda item: item.timestamp_utc)
    stamps = [bar.timestamp_utc for bar in ordered]
    if len(stamps) != len(set(stamps)):
        raise ValueError("duplicate closed one-minute timestamps are not permitted")
    return ordered


def _signal(
    *,
    policy_id: str,
    session_date: date,
    ready: bool,
    fired: bool,
    direction: str | None,
    signal_bar: CanonicalBar | None,
    reasons: Sequence[str],
    evidence: dict[str, object],
) -> SuccessorIntradaySignal:
    if fired and not ready:
        raise ValueError("fired signal cannot be not-ready")
    available = None if signal_bar is None else (signal_bar.timestamp_utc + timedelta(minutes=1)).astimezone(UTC).isoformat()
    return SuccessorIntradaySignal(
        contract=SUCCESSOR_INTRADAY_RULE_CONTRACT,
        policy_id=policy_id,
        session_date=session_date.isoformat(),
        ready=ready,
        fired=fired,
        direction=direction,
        signal_available_at_utc=available,
        reason_codes=tuple(reasons),
        evidence=evidence,
    )


def _regular_through(bars: Sequence[CanonicalBar], *, start: time, cutoff: time) -> list[CanonicalBar]:
    return [bar for bar in bars if bar.session_segment == SessionSegment.REGULAR and start <= _local_time(bar) <= cutoff]


def _cumulative_vwap(bars: Sequence[CanonicalBar]) -> list[float | None]:
    weighted = 0.0
    volume = 0.0
    values: list[float | None] = []
    for bar in bars:
        if bar.volume > 0.0:
            typical = (bar.high + bar.low + bar.close) / 3.0
            weighted += typical * bar.volume
            volume += bar.volume
        values.append(None if volume <= 0.0 else weighted / volume)
    return values


def evaluate_vwap_reclaim_reject(
    bars: Iterable[CanonicalBar], *, session_date: date, decision_time_utc: datetime
) -> SuccessorIntradaySignal:
    closed = _closed_session_bars(bars, session_date=session_date, decision_time_utc=decision_time_utc, segment=SessionSegment.REGULAR)
    eligible = [bar for bar in closed if REGULAR_START <= _local_time(bar) <= VWAP_ENTRY_CUTOFF]
    if len(eligible) < 2:
        return _signal(policy_id="pract_vwap_reclaim_reject_v1", session_date=session_date, ready=False, fired=False, direction=None, signal_bar=None, reasons=("NEED_TWO_CLOSED_REGULAR_BARS",), evidence={"observed_regular_bars": len(eligible)})
    vwaps = _cumulative_vwap(eligible)
    prior_vwap, current_vwap = vwaps[-2], vwaps[-1]
    current, previous = eligible[-1], eligible[-2]
    if prior_vwap is None or current_vwap is None:
        return _signal(policy_id="pract_vwap_reclaim_reject_v1", session_date=session_date, ready=False, fired=False, direction=None, signal_bar=current, reasons=("CUMULATIVE_VWAP_UNAVAILABLE_ZERO_VOLUME",), evidence={})
    long_fire = previous.close <= prior_vwap and current.close > current_vwap
    short_fire = previous.close >= prior_vwap and current.close < current_vwap
    direction = "LONG" if long_fire else "SHORT" if short_fire else None
    return _signal(
        policy_id="pract_vwap_reclaim_reject_v1", session_date=session_date, ready=True, fired=direction is not None, direction=direction, signal_bar=current,
        reasons=(("VWAP_RECLAIM" if long_fire else "VWAP_REJECT" if short_fire else "NO_VWAP_CROSS"),),
        evidence={"prior_close": previous.close, "prior_cumulative_vwap": prior_vwap, "current_close": current.close, "current_cumulative_vwap": current_vwap, "observed_regular_bars": len(eligible)},
    )


def evaluate_session_failed_break_reclaim(
    bars: Iterable[CanonicalBar], *, session_date: date, decision_time_utc: datetime,
    prior_regular_high: float, prior_regular_low: float, premarket_high: float | None, premarket_low: float | None,
) -> SuccessorIntradaySignal:
    if not (math.isfinite(prior_regular_high) and math.isfinite(prior_regular_low) and prior_regular_high > prior_regular_low > 0.0):
        raise ValueError("prior regular high/low must be finite positive geometry")
    closed = _closed_session_bars(bars, session_date=session_date, decision_time_utc=decision_time_utc, segment=SessionSegment.REGULAR)
    eligible = [bar for bar in closed if REGULAR_START <= _local_time(bar) <= VWAP_ENTRY_CUTOFF]
    if not eligible:
        return _signal(policy_id="pract_session_failed_break_reclaim_v1", session_date=session_date, ready=False, fired=False, direction=None, signal_bar=None, reasons=("NO_CLOSED_REGULAR_BAR",), evidence={})
    current = eligible[-1]
    supports = [("PRIOR_REGULAR_LOW", prior_regular_low)]
    resistances = [("PRIOR_REGULAR_HIGH", prior_regular_high)]
    if premarket_low is not None and math.isfinite(premarket_low) and premarket_low > 0.0:
        supports.append(("PREMARKET_LOW", float(premarket_low)))
    if premarket_high is not None and math.isfinite(premarket_high) and premarket_high > 0.0:
        resistances.append(("PREMARKET_HIGH", float(premarket_high)))
    failed_supports = [(name, level) for name, level in supports if current.low < level and current.close > level]
    failed_resistances = [(name, level) for name, level in resistances if current.high > level and current.close < level]
    if failed_supports and failed_resistances:
        return _signal(policy_id="pract_session_failed_break_reclaim_v1", session_date=session_date, ready=True, fired=False, direction=None, signal_bar=current, reasons=("AMBIGUOUS_TWO_SIDED_FAILED_BREAK",), evidence={"failed_supports": failed_supports, "failed_resistances": failed_resistances})
    direction = "LONG" if failed_supports else "SHORT" if failed_resistances else None
    reason = "FAILED_SUPPORT_BREAK_RECLAIMED" if failed_supports else "FAILED_RESISTANCE_BREAK_REJECTED" if failed_resistances else "NO_FAILED_BREAK_RECLAIM"
    return _signal(policy_id="pract_session_failed_break_reclaim_v1", session_date=session_date, ready=True, fired=direction is not None, direction=direction, signal_bar=current, reasons=(reason,), evidence={"failed_supports": failed_supports, "failed_resistances": failed_resistances, "bar_low": current.low, "bar_high": current.high, "bar_close": current.close})


def evaluate_gap_quality_condition_long(
    *, session_date: date, decision_time_utc: datetime, prior_regular_close: float, current_regular_open: float,
    current_price: float, prior_median_dollar_volume_20: float, natr_14: float, premarket_relvol_20: float, split_crossed: bool,
) -> SuccessorIntradaySignal:
    decision = _aware_utc(decision_time_utc).astimezone(MARKET_TZ)
    earliest = datetime.combine(session_date, time(9, 31), tzinfo=MARKET_TZ)
    if decision < earliest:
        return _signal(policy_id="gap_quality_condition_long_v2", session_date=session_date, ready=False, fired=False, direction=None, signal_bar=None, reasons=("INFORMATION_CLOCK_NOT_READY",), evidence={"earliest_decision_et": earliest.isoformat()})
    if split_crossed:
        return _signal(policy_id="gap_quality_condition_long_v2", session_date=session_date, ready=False, fired=False, direction=None, signal_bar=None, reasons=("SPLIT_CROSSES_PRICE_COMPARISON",), evidence={})
    values = (prior_regular_close, current_regular_open, current_price, prior_median_dollar_volume_20, natr_14, premarket_relvol_20)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("gap quality inputs must be finite")
    if prior_regular_close <= 0.0 or current_regular_open <= 0.0 or current_price <= 0.0:
        raise ValueError("gap quality prices must be positive")
    gap = current_regular_open / prior_regular_close - 1.0
    checks = {"gap_ge_2pct": gap >= 0.02, "price_ge_5": current_price >= 5.0, "prior_median_dollar_volume_20_ge_20m": prior_median_dollar_volume_20 >= 20_000_000.0, "natr_14_ge_1pct": natr_14 >= 0.01, "natr_14_le_8pct": natr_14 <= 0.08, "premarket_relvol_20_ge_1_5": premarket_relvol_20 >= 1.5}
    fired = all(checks.values())
    return _signal(policy_id="gap_quality_condition_long_v2", session_date=session_date, ready=True, fired=fired, direction="LONG" if fired else None, signal_bar=None, reasons=(("QUALITY_GATE_PASS",) if fired else ("QUALITY_GATE_FAIL",)), evidence={"gap_fraction": gap, "checks": checks})


def evaluate_orb_stocks_in_play_5m(
    bars: Iterable[CanonicalBar], *, session_date: date, decision_time_utc: datetime,
    same_time_opening_relvol: float, prior_median_dollar_volume_20: float, current_price: float,
) -> SuccessorIntradaySignal:
    if not all(math.isfinite(value) for value in (same_time_opening_relvol, prior_median_dollar_volume_20, current_price)):
        raise ValueError("ORB stocks-in-play scalar inputs must be finite")
    closed = _closed_session_bars(bars, session_date=session_date, decision_time_utc=decision_time_utc, segment=SessionSegment.REGULAR)
    opening = [bar for bar in closed if time(9, 30) <= _local_time(bar) < time(9, 35)]
    if len(opening) < 5:
        return _signal(policy_id="orb_stocks_in_play_5m_v1", session_date=session_date, ready=False, fired=False, direction=None, signal_bar=None, reasons=("INCOMPLETE_FIVE_MINUTE_OPENING_RANGE",), evidence={"observed_range_bars": len(opening)})
    range_high, range_low = max(bar.high for bar in opening), min(bar.low for bar in opening)
    quality = {"same_time_opening_relvol_ge_2": same_time_opening_relvol >= 2.0, "prior_median_dollar_volume_20_ge_20m": prior_median_dollar_volume_20 >= 20_000_000.0, "price_ge_5": current_price >= 5.0}
    if not all(quality.values()):
        return _signal(policy_id="orb_stocks_in_play_5m_v1", session_date=session_date, ready=True, fired=False, direction=None, signal_bar=opening[-1], reasons=("STOCKS_IN_PLAY_GATE_FAIL",), evidence={"checks": quality, "range_high": range_high, "range_low": range_low})
    breakout_bars = _regular_through(closed, start=time(9, 35), cutoff=ORB_ENTRY_CUTOFF)
    for bar in breakout_bars:
        if bar.close > range_high:
            return _signal(policy_id="orb_stocks_in_play_5m_v1", session_date=session_date, ready=True, fired=True, direction="LONG", signal_bar=bar, reasons=("FIVE_MINUTE_ORB_BREAKOUT", "STOCKS_IN_PLAY_GATE_PASS"), evidence={"range_high": range_high, "range_low": range_low, "checks": quality})
        if bar.close < range_low:
            return _signal(policy_id="orb_stocks_in_play_5m_v1", session_date=session_date, ready=True, fired=True, direction="SHORT", signal_bar=bar, reasons=("FIVE_MINUTE_ORB_BREAKDOWN", "STOCKS_IN_PLAY_GATE_PASS"), evidence={"range_high": range_high, "range_low": range_low, "checks": quality})
    return _signal(policy_id="orb_stocks_in_play_5m_v1", session_date=session_date, ready=True, fired=False, direction=None, signal_bar=breakout_bars[-1] if breakout_bars else opening[-1], reasons=("NO_FIVE_MINUTE_RANGE_BREAK",), evidence={"range_high": range_high, "range_low": range_low, "checks": quality})


def evaluate_orb_15m_close_retest(
    bars: Iterable[CanonicalBar], *, session_date: date, decision_time_utc: datetime, atr_reference: float,
) -> SuccessorIntradaySignal:
    if not math.isfinite(atr_reference) or atr_reference <= 0.0:
        raise ValueError("ATR reference must be finite and positive")
    closed = _closed_session_bars(bars, session_date=session_date, decision_time_utc=decision_time_utc, segment=SessionSegment.REGULAR)
    opening = [bar for bar in closed if time(9, 30) <= _local_time(bar) < time(9, 45)]
    if len(opening) < 15:
        return _signal(policy_id="orb_15m_close_retest_v2", session_date=session_date, ready=False, fired=False, direction=None, signal_bar=None, reasons=("INCOMPLETE_FIFTEEN_MINUTE_OPENING_RANGE",), evidence={"observed_range_bars": len(opening)})
    range_high, range_low = max(bar.high for bar in opening), min(bar.low for bar in opening)
    post = _regular_through(closed, start=time(9, 45), cutoff=VWAP_ENTRY_CUTOFF)
    breakout_index: int | None = None
    breakout_direction: str | None = None
    boundary: float | None = None
    for index, bar in enumerate(post):
        if _local_time(bar) > ORB_RETEST_BREAKOUT_CUTOFF:
            break
        if bar.close > range_high:
            breakout_index, breakout_direction, boundary = index, "LONG", range_high
            break
        if bar.close < range_low:
            breakout_index, breakout_direction, boundary = index, "SHORT", range_low
            break
    if breakout_index is None or breakout_direction is None or boundary is None:
        return _signal(policy_id="orb_15m_close_retest_v2", session_date=session_date, ready=True, fired=False, direction=None, signal_bar=post[-1] if post else opening[-1], reasons=("NO_15M_CLOSE_BREAKOUT_BEFORE_1100",), evidence={"range_high": range_high, "range_low": range_low})
    breakout = post[breakout_index]
    retest_limit = min(len(post), breakout_index + 6)
    for retest_index in range(breakout_index + 1, retest_limit):
        retest = post[retest_index]
        touches = retest.low <= boundary + 0.25 * atr_reference if breakout_direction == "LONG" else retest.high >= boundary - 0.25 * atr_reference
        holds = retest.close >= boundary if breakout_direction == "LONG" else retest.close <= boundary
        if not (touches and holds):
            continue
        confirmation_index = retest_index + 1
        if confirmation_index >= len(post):
            return _signal(policy_id="orb_15m_close_retest_v2", session_date=session_date, ready=False, fired=False, direction=None, signal_bar=retest, reasons=("RETEST_SEEN_CONFIRMATION_BAR_NOT_CLOSED",), evidence={"direction": breakout_direction, "boundary": boundary, "breakout_stamp_utc": breakout.timestamp_utc.isoformat(), "retest_stamp_utc": retest.timestamp_utc.isoformat()})
        confirmation = post[confirmation_index]
        confirmed = confirmation.close >= boundary + 0.10 * atr_reference if breakout_direction == "LONG" else confirmation.close <= boundary - 0.10 * atr_reference
        if confirmed:
            return _signal(policy_id="orb_15m_close_retest_v2", session_date=session_date, ready=True, fired=True, direction=breakout_direction, signal_bar=confirmation, reasons=("BREAKOUT_RETEST_HOLD_CONFIRMED",), evidence={"range_high": range_high, "range_low": range_low, "boundary": boundary, "atr_reference": atr_reference, "breakout_stamp_utc": breakout.timestamp_utc.isoformat(), "retest_stamp_utc": retest.timestamp_utc.isoformat(), "confirmation_stamp_utc": confirmation.timestamp_utc.isoformat()})
    return _signal(policy_id="orb_15m_close_retest_v2", session_date=session_date, ready=True, fired=False, direction=None, signal_bar=post[-1] if post else breakout, reasons=("BREAKOUT_WITHOUT_VALID_RETEST_CONFIRMATION",), evidence={"range_high": range_high, "range_low": range_low, "direction": breakout_direction, "boundary": boundary})


def evaluate_premarket_relvol_quality(
    bars: Iterable[CanonicalBar], *, session_date: date, decision_time_utc: datetime,
    prior_premarket_median_volume_20: float, prior_median_dollar_volume_20: float, current_price: float, breakout_same_time_relvol: float,
) -> SuccessorIntradaySignal:
    scalar_values = (prior_premarket_median_volume_20, prior_median_dollar_volume_20, current_price, breakout_same_time_relvol)
    if not all(math.isfinite(value) for value in scalar_values):
        raise ValueError("premarket quality scalar inputs must be finite")
    if prior_premarket_median_volume_20 <= 0.0:
        return _signal(policy_id="premarket_relvol_quality_v2", session_date=session_date, ready=False, fired=False, direction=None, signal_bar=None, reasons=("PRIOR_PREMARKET_MEDIAN_VOLUME_UNAVAILABLE",), evidence={})
    closed = _closed_session_bars(bars, session_date=session_date, decision_time_utc=decision_time_utc)
    premarket = [bar for bar in closed if bar.session_segment == SessionSegment.PREMARKET and PREMARKET_START <= _local_time(bar) < PREMARKET_END]
    consolidation = [bar for bar in premarket if PREMARKET_CONSOLIDATION_START <= _local_time(bar) < PREMARKET_CONSOLIDATION_END]
    if len(consolidation) < 5:
        return _signal(policy_id="premarket_relvol_quality_v2", session_date=session_date, ready=False, fired=False, direction=None, signal_bar=None, reasons=("INSUFFICIENT_PREMARKET_CONSOLIDATION_BARS",), evidence={"consolidation_bars": len(consolidation)})
    pm_volume = sum(bar.volume for bar in premarket)
    pm_dollar_volume = sum(((bar.high + bar.low + bar.close) / 3.0) * bar.volume for bar in premarket)
    relvol = pm_volume / prior_premarket_median_volume_20
    consolidation_high, consolidation_low = max(bar.high for bar in consolidation), min(bar.low for bar in consolidation)
    last_price = consolidation[-1].close
    consolidation_range = (consolidation_high - consolidation_low) / last_price if last_price > 0.0 else math.inf
    quality = {"premarket_relvol_ge_2": relvol >= 2.0, "consolidation_range_le_3pct": consolidation_range <= 0.03, "prior_median_dollar_volume_20_ge_20m": prior_median_dollar_volume_20 >= 20_000_000.0, "price_ge_5": current_price >= 5.0, "premarket_dollar_volume_ge_2m": pm_dollar_volume >= 2_000_000.0, "breakout_same_time_relvol_ge_1_5": breakout_same_time_relvol >= 1.5}
    regular = [bar for bar in closed if bar.session_segment == SessionSegment.REGULAR and REGULAR_START <= _local_time(bar) <= ORB_ENTRY_CUTOFF]
    if all(quality.values()):
        for bar in regular:
            if bar.close > consolidation_high:
                return _signal(policy_id="premarket_relvol_quality_v2", session_date=session_date, ready=True, fired=True, direction="LONG", signal_bar=bar, reasons=("PREMARKET_QUALITY_PASS", "CONSOLIDATION_BREAKOUT"), evidence={"premarket_relvol": relvol, "premarket_dollar_volume": pm_dollar_volume, "consolidation_high": consolidation_high, "consolidation_low": consolidation_low, "consolidation_range_fraction": consolidation_range, "checks": quality})
    return _signal(policy_id="premarket_relvol_quality_v2", session_date=session_date, ready=True, fired=False, direction=None, signal_bar=regular[-1] if regular else None, reasons=(("NO_PREMARKET_QUALITY_BREAKOUT",) if all(quality.values()) else ("PREMARKET_QUALITY_GATE_FAIL",)), evidence={"premarket_relvol": relvol, "premarket_dollar_volume": pm_dollar_volume, "consolidation_range_fraction": consolidation_range, "checks": quality})


SUCCESSOR_INTRADAY_RULE_FINGERPRINT = successor_intraday_rule_fingerprint()
