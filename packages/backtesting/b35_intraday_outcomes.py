from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

from packages.core.enums import SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.schemas.strategy import StrategyDirection
from packages.strategies.b35_conditional_evidence_contract import (
    ALL_IN_ROUND_TRIP_COST_GRID_BPS,
    B35_PREOUTCOME_FINGERPRINT,
    DEVELOPMENT_LAST_SCORING_SESSION,
    MAX_ENTRY_DELAY_MINUTES,
    TARGET_R_MULTIPLE,
    TIME_EXIT_END_ET,
    TIME_EXIT_START_ET,
    RowUse,
    validate_row_use,
)
from packages.strategies.intraday_opening_pack import IntradaySetupResult


B35_INTRADAY_OUTCOME_CONTRACT = (
    "atlas-b35-development-intraday-outcome-v2-entry-notional-unresolved-preserved"
)
MARKET_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class B35IntradayOutcome:
    contract: str
    b35_preoutcome_fingerprint: str
    strategy_id: str
    symbol: str
    session_date: str
    direction: str
    comparable: bool
    status: str
    reason_codes: tuple[str, ...]
    signal_bar_timestamp_utc: str | None
    entry_bar_timestamp_utc: str | None
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    exit_bar_timestamp_utc: str | None
    exit_price: float | None
    exit_reason: str | None
    same_bar_collision_adverse_first: bool
    gross_directional_return: float | None
    net_directional_returns_by_cost_bps: dict[str, float]
    primary_50bps_net_directional_return: float | None
    risk_multiple: float | None
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    bars_observed_after_entry: int
    outcome_fingerprint: str


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _regular_session_bars(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
) -> tuple[CanonicalBar, ...]:
    selected = tuple(
        sorted(
            (
                bar
                for bar in bars
                if bar.timeframe == Timeframe.MINUTE_1
                and bar.session_segment == SessionSegment.REGULAR
                and bar.session_date == session_date
            ),
            key=lambda bar: bar.timestamp_utc,
        )
    )
    previous = None
    for bar in selected:
        if previous is not None and bar.timestamp_utc <= previous:
            raise ValueError("B35 outcome bars must be strictly increasing")
        previous = bar.timestamp_utc
    return selected


def _signal_stamp(
    setup: IntradaySetupResult, regular: Sequence[CanonicalBar]
) -> datetime | None:
    raw = setup.evidence.get("breakout_bar_timestamp_utc")
    if isinstance(raw, str) and raw:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("B35 breakout timestamp must be timezone-aware")
        return stamp
    if setup.strategy_id == "b34_gap_continuation_v1" and regular:
        # Sparse opens use the first observed regular bar. The entry can only be
        # attempted on a later observed bar after this one closes.
        return regular[0].timestamp_utc
    return None


def _stop_anchor(setup: IntradaySetupResult, direction: StrategyDirection) -> float | None:
    evidence = setup.evidence
    if setup.strategy_id == "b34_gap_continuation_v1":
        value = evidence.get("prior_regular_close")
    elif setup.strategy_id == "b34_opening_range_breakout_15m_v1":
        value = (
            evidence.get("opening_range_low")
            if direction == StrategyDirection.LONG
            else evidence.get("opening_range_high")
        )
    elif setup.strategy_id in {
        "b34_premarket_relvol_consolidation_v1",
        "b34_highest_volume_day_style_v1",
    }:
        value = evidence.get("consolidation_low")
    else:
        value = None
    try:
        numeric = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    if numeric is None or not math.isfinite(numeric) or numeric <= 0:
        return None
    return numeric


def _gross_return(
    *, direction: StrategyDirection, entry: float, exit_price: float
) -> float:
    if direction == StrategyDirection.LONG:
        return (exit_price - entry) / entry
    return (entry - exit_price) / entry


def _net_return_with_cost(
    *,
    direction: StrategyDirection,
    entry: float,
    exit_price: float,
    round_trip_cost_bps: float,
) -> float:
    """Apply half the frozen cost adversely at each side and normalize to entry capital."""

    half = round_trip_cost_bps / 20_000.0
    if direction == StrategyDirection.LONG:
        adverse_entry = entry * (1.0 + half)
        adverse_exit = exit_price * (1.0 - half)
        return (adverse_exit - adverse_entry) / adverse_entry
    adverse_entry_proceeds = entry * (1.0 - half)
    adverse_cover = exit_price * (1.0 + half)
    return (adverse_entry_proceeds - adverse_cover) / adverse_entry_proceeds


def _excursion(
    *, direction: StrategyDirection, entry: float, bar: CanonicalBar
) -> tuple[float, float]:
    if direction == StrategyDirection.LONG:
        return (float(bar.high) - entry) / entry, (float(bar.low) - entry) / entry
    return (entry - float(bar.low)) / entry, (entry - float(bar.high)) / entry


def _noncomparable(
    *,
    setup: IntradaySetupResult,
    symbol: str,
    session_date: date,
    direction: StrategyDirection,
    status: str,
    reasons: tuple[str, ...],
    signal_stamp: datetime | None = None,
    entry_bar: CanonicalBar | None = None,
    entry_price: float | None = None,
    stop_price: float | None = None,
    target_price: float | None = None,
    mfe: float | None = None,
    mae: float | None = None,
    observed: int = 0,
) -> B35IntradayOutcome:
    fields = {
        "contract": B35_INTRADAY_OUTCOME_CONTRACT,
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "strategy_id": setup.strategy_id,
        "symbol": symbol,
        "session_date": session_date.isoformat(),
        "direction": direction.value,
        "comparable": False,
        "status": status,
        "reason_codes": reasons,
        "signal_bar_timestamp_utc": signal_stamp.isoformat() if signal_stamp else None,
        "entry_bar_timestamp_utc": entry_bar.timestamp_utc.isoformat() if entry_bar else None,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "exit_bar_timestamp_utc": None,
        "exit_price": None,
        "exit_reason": None,
        "same_bar_collision_adverse_first": False,
        "gross_directional_return": None,
        "net_directional_returns_by_cost_bps": {},
        "primary_50bps_net_directional_return": None,
        "risk_multiple": None,
        "maximum_favorable_excursion": mfe,
        "maximum_adverse_excursion": mae,
        "bars_observed_after_entry": observed,
    }
    fingerprint = _stable_hash(fields)
    return B35IntradayOutcome(**fields, outcome_fingerprint=fingerprint)


def simulate_intraday_outcome(
    setup: IntradaySetupResult,
    bars: Iterable[CanonicalBar],
    *,
    symbol: str,
    session_date: date,
) -> B35IntradayOutcome:
    """Apply the frozen B35 DEVELOPMENT entry/stop/2R/time-exit mechanics."""

    validate_row_use(session_date, RowUse.DEVELOPMENT_OUTCOME)
    if session_date > DEVELOPMENT_LAST_SCORING_SESSION:
        raise ValueError("B35 DEVELOPMENT outcome is after the frozen scoring boundary")
    if not setup.ready or not setup.fired or setup.direction is None:
        raise ValueError("B35 outcome simulation requires a ready fired B34 setup")
    if setup.session_date != session_date.isoformat():
        raise ValueError("B35 setup/session mismatch")

    direction = StrategyDirection(setup.direction)
    regular = _regular_session_bars(bars, session_date=session_date)
    if not regular:
        return _noncomparable(
            setup=setup,
            symbol=symbol,
            session_date=session_date,
            direction=direction,
            status="NONCOMPARABLE_NO_REGULAR_BARS",
            reasons=("NO_REGULAR_SESSION_BARS",),
        )

    signal_stamp = _signal_stamp(setup, regular)
    if signal_stamp is None:
        return _noncomparable(
            setup=setup,
            symbol=symbol,
            session_date=session_date,
            direction=direction,
            status="NONCOMPARABLE_NO_SIGNAL_BAR",
            reasons=("SIGNAL_BAR_TIMESTAMP_UNAVAILABLE",),
        )
    if signal_stamp.astimezone(MARKET_TZ).date() != session_date:
        return _noncomparable(
            setup=setup,
            symbol=symbol,
            session_date=session_date,
            direction=direction,
            status="NONCOMPARABLE_SIGNAL_DATE_MISMATCH",
            reasons=("SIGNAL_BAR_OUTSIDE_SESSION",),
            signal_stamp=signal_stamp,
        )

    decision_stamp = signal_stamp + timedelta(minutes=1)
    entry_candidates = [bar for bar in regular if bar.timestamp_utc >= decision_stamp]
    if not entry_candidates:
        return _noncomparable(
            setup=setup,
            symbol=symbol,
            session_date=session_date,
            direction=direction,
            status="NONCOMPARABLE_NO_NEXT_ENTRY_BAR",
            reasons=("NO_NEXT_REGULAR_MINUTE_BAR",),
            signal_stamp=signal_stamp,
        )
    entry_bar = entry_candidates[0]
    delay = (entry_bar.timestamp_utc - decision_stamp).total_seconds() / 60.0
    if delay > MAX_ENTRY_DELAY_MINUTES:
        return _noncomparable(
            setup=setup,
            symbol=symbol,
            session_date=session_date,
            direction=direction,
            status="NONCOMPARABLE_ENTRY_DELAY",
            reasons=("NEXT_ENTRY_BAR_EXCEEDS_MAX_DELAY",),
            signal_stamp=signal_stamp,
        )

    entry = float(entry_bar.open)
    stop = _stop_anchor(setup, direction)
    if stop is None:
        return _noncomparable(
            setup=setup,
            symbol=symbol,
            session_date=session_date,
            direction=direction,
            status="NONCOMPARABLE_STOP_UNAVAILABLE",
            reasons=("FROZEN_STOP_ANCHOR_UNAVAILABLE",),
            signal_stamp=signal_stamp,
        )
    if direction == StrategyDirection.LONG:
        risk_per_share = entry - stop
        geometry_valid = stop < entry
        target = entry + TARGET_R_MULTIPLE * risk_per_share
    else:
        risk_per_share = stop - entry
        geometry_valid = stop > entry
        target = entry - TARGET_R_MULTIPLE * risk_per_share
    if not geometry_valid or risk_per_share <= 0 or target <= 0:
        return _noncomparable(
            setup=setup,
            symbol=symbol,
            session_date=session_date,
            direction=direction,
            status="NONCOMPARABLE_INVALID_STOP_GEOMETRY",
            reasons=("STOP_ENTRY_TARGET_GEOMETRY_INVALID",),
            signal_stamp=signal_stamp,
        )

    mfe = 0.0
    mae = 0.0
    exit_bar: CanonicalBar | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    collision = False
    observed = 0

    for bar in entry_candidates:
        observed += 1
        local_time = bar.timestamp_utc.astimezone(MARKET_TZ).time()
        if TIME_EXIT_START_ET <= local_time <= TIME_EXIT_END_ET:
            exit_bar = bar
            exit_price = float(bar.open)
            exit_reason = "TIME_EXIT"
            break

        # Resolve price gaps at the bar open before intrabar range ambiguity.
        if direction == StrategyDirection.LONG:
            stop_gap = float(bar.open) < stop
            target_gap = float(bar.open) >= target
        else:
            stop_gap = float(bar.open) > stop
            target_gap = float(bar.open) <= target
        if stop_gap:
            exit_bar = bar
            exit_price = float(bar.open)
            exit_reason = "STOP_GAP_WORSE_OPEN"
            break
        if target_gap:
            exit_bar = bar
            exit_price = target
            exit_reason = "TARGET_GAP_NO_BETTER_THAN_TARGET"
            break

        if direction == StrategyDirection.LONG:
            stop_hit = float(bar.low) <= stop
            target_hit = float(bar.high) >= target
        else:
            stop_hit = float(bar.high) >= stop
            target_hit = float(bar.low) <= target
        if stop_hit and target_hit:
            exit_bar = bar
            exit_price = stop
            exit_reason = "STOP_AND_TARGET_SAME_BAR_ADVERSE_FIRST"
            collision = True
            break
        if stop_hit:
            exit_bar = bar
            exit_price = stop
            exit_reason = "STOP"
            break
        if target_hit:
            exit_bar = bar
            exit_price = target
            exit_reason = "TARGET_2R"
            break

        favorable, adverse = _excursion(direction=direction, entry=entry, bar=bar)
        mfe = max(mfe, favorable)
        mae = min(mae, adverse)

    if exit_bar is None or exit_price is None or exit_reason is None:
        return _noncomparable(
            setup=setup,
            symbol=symbol,
            session_date=session_date,
            direction=direction,
            status="NONCOMPARABLE_UNRESOLVED_EXIT_AFTER_ENTRY",
            reasons=("NO_STOP_TARGET_OR_OBSERVED_TIME_EXIT",),
            signal_stamp=signal_stamp,
            entry_bar=entry_bar,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            mfe=mfe,
            mae=mae,
            observed=observed,
        )

    gross = _gross_return(direction=direction, entry=entry, exit_price=exit_price)
    if direction == StrategyDirection.LONG:
        r_multiple = (exit_price - entry) / risk_per_share
    else:
        r_multiple = (entry - exit_price) / risk_per_share
    mfe = max(mfe, gross)
    mae = min(mae, gross)
    net = {
        str(cost_bps): _net_return_with_cost(
            direction=direction,
            entry=entry,
            exit_price=exit_price,
            round_trip_cost_bps=float(cost_bps),
        )
        for cost_bps in ALL_IN_ROUND_TRIP_COST_GRID_BPS
    }
    fields = {
        "contract": B35_INTRADAY_OUTCOME_CONTRACT,
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "strategy_id": setup.strategy_id,
        "symbol": symbol,
        "session_date": session_date.isoformat(),
        "direction": direction.value,
        "comparable": True,
        "status": "EXITED",
        "reason_codes": ("FROZEN_B35_OUTCOME_RESOLVED",),
        "signal_bar_timestamp_utc": signal_stamp.isoformat(),
        "entry_bar_timestamp_utc": entry_bar.timestamp_utc.isoformat(),
        "entry_price": entry,
        "stop_price": stop,
        "target_price": target,
        "exit_bar_timestamp_utc": exit_bar.timestamp_utc.isoformat(),
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "same_bar_collision_adverse_first": collision,
        "gross_directional_return": gross,
        "net_directional_returns_by_cost_bps": net,
        "primary_50bps_net_directional_return": net["50"],
        "risk_multiple": r_multiple,
        "maximum_favorable_excursion": mfe,
        "maximum_adverse_excursion": mae,
        "bars_observed_after_entry": observed,
    }
    fingerprint = _stable_hash(fields)
    return B35IntradayOutcome(**fields, outcome_fingerprint=fingerprint)


def outcome_to_dict(outcome: B35IntradayOutcome) -> dict[str, object]:
    return asdict(outcome)
