from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from statistics import median
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

from packages.core.enums import SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.schemas.strategy import StrategyDirection
from packages.schemas.strategy_lab import (
    ResearchStrategyFamily,
    StrategyAuthority,
    StrategyEvidenceSource,
    StrategySpecification,
)


B34_INTRADAY_PACK_CONTRACT = "atlas-b34-opening-premarket-pack-v1-pre-outcome"
MARKET_TZ = ZoneInfo("America/New_York")

OPENING_RANGE_MINUTES = 15
OPENING_RANGE_START = time(9, 30)
OPENING_RANGE_END = time(9, 45)
OPENING_RANGE_ENTRY_CUTOFF = time(11, 30)

PREMARKET_START = time(4, 0)
PREMARKET_END = time(9, 30)
PREMARKET_CONSOLIDATION_START = time(9, 0)
PREMARKET_CONSOLIDATION_END = time(9, 30)
PREMARKET_LOOKBACK_SESSIONS = 20
PREMARKET_RELVOL_MIN = 2.0
PREMARKET_CONSOLIDATION_MAX_RANGE_PCT = 0.03
PREMARKET_MIN_CONSOLIDATION_BARS = 5
PREMARKET_BREAKOUT_CUTOFF = time(11, 30)

HVD_DAILY_LOOKBACK_SESSIONS = 252
GAP_MIN_ABS_PCT = 0.02


@dataclass(frozen=True, slots=True)
class IntradaySetupResult:
    contract: str
    strategy_id: str
    session_date: str
    ready: bool
    fired: bool
    direction: str | None
    reason_codes: tuple[str, ...]
    evidence: dict[str, object]


@dataclass(frozen=True, slots=True)
class PremarketSnapshot:
    session_date: str
    observed_bar_count: int
    cumulative_volume: float
    high: float
    low: float
    last_price: float
    consolidation_bar_count: int
    consolidation_high: float
    consolidation_low: float
    consolidation_range_pct: float


B34_INTRADAY_SPECIFICATIONS: tuple[StrategySpecification, ...] = (
    StrategySpecification(
        strategy_id="b34_gap_continuation_v1",
        version="1.0.0",
        family=ResearchStrategyFamily.GAP,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        authority=StrategyAuthority.RESEARCH,
        directions=(StrategyDirection.LONG, StrategyDirection.SHORT),
        native_timeframe="1m",
        universe_contract="accepted V2 equity universe; exact provider symbol; no PIT market-cap filter",
        signal_contract=(
            "At the first information-safe post-open decision, compare current regular-session "
            "open with the prior regular-session close. Long gap >= +2%; short gap <= -2%. "
            "Any split effective between the two prices blocks the setup."
        ),
        entry_contract=(
            "Reference setup only; no B34 order. Earliest historical decision is 09:31 ET "
            "because the 09:30 one-minute bar is usable only after it closes."
        ),
        exit_contract="Not defined in B34; any later replay package must preregister exits before outcomes.",
        risk_contract="No position sizing or execution authority in B34.",
        cost_contract="No performance evaluation in B34; later replay must model accepted transaction costs.",
        evaluation_contract="Pre-outcome syntax/fixture validation only; protected and performance outcomes unavailable.",
        required_features=("prior_regular_close", "current_regular_open", "split_crossed"),
        outcome_access_permitted=False,
        governed_performance_accessed=False,
    ),
    StrategySpecification(
        strategy_id="b34_opening_range_breakout_15m_v1",
        version="1.0.0",
        family=ResearchStrategyFamily.OPENING_RANGE,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        authority=StrategyAuthority.RESEARCH,
        directions=(StrategyDirection.LONG, StrategyDirection.SHORT),
        native_timeframe="1m",
        universe_contract="accepted V2 equity universe; exact provider symbol",
        signal_contract=(
            "Opening range is the observed high/low from regular-session bars stamped 09:30..09:44 ET. "
            "Range becomes information-safe at 09:45 ET. A later closed 1m bar through 11:30 ET "
            "fires long only when its close is above the range high or short only when below the range low."
        ),
        entry_contract="Reference signal only; no B34 order. Breakout bar must be fully closed before decision.",
        exit_contract="Not defined in B34; any replay must preregister exit/risk geometry before outcomes.",
        risk_contract="No position sizing or execution authority in B34.",
        cost_contract="No performance evaluation in B34; later replay must model accepted transaction costs.",
        evaluation_contract="Pre-outcome syntax/fixture validation only; no historical returns opened.",
        required_features=("opening_range_high", "opening_range_low", "closed_breakout_bar"),
        outcome_access_permitted=False,
        governed_performance_accessed=False,
    ),
    StrategySpecification(
        strategy_id="b34_premarket_relvol_consolidation_v1",
        version="1.0.0",
        family=ResearchStrategyFamily.PREMARKET,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        authority=StrategyAuthority.RESEARCH,
        directions=(StrategyDirection.LONG,),
        native_timeframe="1m",
        universe_contract="accepted V2 equity universe; exact provider symbol",
        signal_contract=(
            "Use observed SIP premarket bars from 04:00..09:29 ET. Premarket relative volume equals "
            "current observed premarket volume divided by the median observed premarket volume of exactly "
            "20 prior eligible sessions. Require relvol >= 2.0 and a 09:00..09:29 consolidation with at "
            "least 5 observed bars and high-low range <= 3% of its last price. Fire only after a closed "
            "regular-session 1m bar through 11:30 ET closes above the consolidation high."
        ),
        entry_contract="Reference signal only; no B34 order. Premarket state freezes at 09:30 ET.",
        exit_contract="Not defined in B34; later replay must preregister exits before outcome access.",
        risk_contract="No position sizing or execution authority in B34.",
        cost_contract="No performance evaluation in B34; later replay must model accepted transaction costs.",
        evaluation_contract="Pre-outcome syntax/fixture validation only; no performance claim.",
        required_features=(
            "premarket_volume",
            "premarket_relvol_20_median",
            "premarket_consolidation_high",
            "premarket_consolidation_low",
            "closed_regular_breakout_bar",
        ),
        outcome_access_permitted=False,
        governed_performance_accessed=False,
    ),
    StrategySpecification(
        strategy_id="b34_highest_volume_day_style_v1",
        version="1.0.0",
        family=ResearchStrategyFamily.PREMARKET,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        authority=StrategyAuthority.RESEARCH,
        directions=(StrategyDirection.LONG,),
        native_timeframe="1m",
        universe_contract=(
            "accepted V2 equity universe; exact provider symbol. This reference variant intentionally "
            "omits a small-cap market-cap filter until an accepted PIT market-cap source exists."
        ),
        signal_contract=(
            "Quantified HVD-style reference: observed 04:00..09:29 ET premarket volume must be >= the "
            "maximum regular daily volume across exactly 252 prior eligible sessions; 09:00..09:29 ET "
            "must form the same <=3% consolidation with >=5 observed bars; a closed regular 1m bar through "
            "11:30 ET must then close above the full premarket high."
        ),
        entry_contract="Reference signal only; no B34 order. Premarket state freezes at 09:30 ET.",
        exit_contract="Not defined in B34; later replay must preregister exits before outcome access.",
        risk_contract="No position sizing or execution authority in B34.",
        cost_contract="No performance evaluation in B34; later replay must model accepted transaction costs.",
        evaluation_contract="Pre-outcome syntax/fixture validation only; practitioner performance claims are not imported.",
        required_features=(
            "premarket_volume",
            "prior_252_max_daily_volume",
            "premarket_high",
            "premarket_consolidation_high",
            "premarket_consolidation_low",
            "closed_regular_breakout_bar",
        ),
        outcome_access_permitted=False,
        governed_performance_accessed=False,
    ),
)


def _policy_payload() -> dict[str, object]:
    return {
        "contract": B34_INTRADAY_PACK_CONTRACT,
        "parameters": {
            "opening_range_minutes": OPENING_RANGE_MINUTES,
            "opening_range_entry_cutoff": OPENING_RANGE_ENTRY_CUTOFF.isoformat(),
            "premarket_start": PREMARKET_START.isoformat(),
            "premarket_end": PREMARKET_END.isoformat(),
            "premarket_lookback_sessions": PREMARKET_LOOKBACK_SESSIONS,
            "premarket_relvol_min": PREMARKET_RELVOL_MIN,
            "premarket_consolidation_start": PREMARKET_CONSOLIDATION_START.isoformat(),
            "premarket_consolidation_end": PREMARKET_CONSOLIDATION_END.isoformat(),
            "premarket_consolidation_max_range_pct": PREMARKET_CONSOLIDATION_MAX_RANGE_PCT,
            "premarket_min_consolidation_bars": PREMARKET_MIN_CONSOLIDATION_BARS,
            "premarket_breakout_cutoff": PREMARKET_BREAKOUT_CUTOFF.isoformat(),
            "hvd_daily_lookback_sessions": HVD_DAILY_LOOKBACK_SESSIONS,
            "gap_min_abs_pct": GAP_MIN_ABS_PCT,
        },
        "specifications": [spec.model_dump(mode="json") for spec in B34_INTRADAY_SPECIFICATIONS],
        "information_clock": {
            "bar_timestamp_semantics": "left_edge_start",
            "bar_available_at": "timestamp_plus_one_minute",
            "premarket_feature_cutoff": "09:30:00 America/New_York; latest eligible stamp 09:29",
            "opening_range_cutoff": "09:45:00 America/New_York; latest range stamp 09:44",
        },
        "missing_bar_policy": (
            "Never synthesize a canonical minute. Aggregates use observed provider bars only; absence is "
            "preserved and is not relabeled as a zero-volume bar or a halt. A range requiring at least one "
            "trade bar is unavailable when no eligible bar exists."
        ),
        "split_policy": (
            "V2 minute bars are raw/unadjusted. Any price/volume comparison spanning a split effective "
            "between compared observations is ineligible; no adjusted-minute series is fabricated."
        ),
        "authority": "RESEARCH_ONLY_NO_OUTCOME_NO_PAPER_NO_LIVE",
    }


B34_INTRADAY_PACK_FINGERPRINT = hashlib.sha256(
    json.dumps(_policy_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def frozen_pack_manifest() -> dict[str, object]:
    payload = _policy_payload()
    payload["fingerprint"] = B34_INTRADAY_PACK_FINGERPRINT
    return payload


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("decision timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _local_stamp(bar: CanonicalBar) -> datetime:
    return bar.timestamp_utc.astimezone(MARKET_TZ)


def _bar_is_closed(bar: CanonicalBar, as_of_utc: datetime) -> bool:
    return bar.timestamp_utc + timedelta(minutes=1) <= as_of_utc


def _eligible_session_bars(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
    as_of_utc: datetime,
) -> list[CanonicalBar]:
    as_of_utc = _require_aware(as_of_utc)
    selected = [
        bar
        for bar in bars
        if bar.timeframe == Timeframe.MINUTE_1
        and bar.session_date == session_date
        and _bar_is_closed(bar, as_of_utc)
    ]
    return sorted(selected, key=lambda bar: bar.timestamp_utc)


def _window(
    bars: Sequence[CanonicalBar],
    *,
    segment: SessionSegment,
    start: time,
    end: time,
) -> list[CanonicalBar]:
    return [
        bar
        for bar in bars
        if bar.session_segment == segment and start <= _local_stamp(bar).time() < end
    ]


def _latest_regular_breakout_bar(
    bars: Sequence[CanonicalBar],
    *,
    earliest: time,
    cutoff: time,
) -> CanonicalBar | None:
    eligible = [
        bar
        for bar in bars
        if bar.session_segment == SessionSegment.REGULAR
        and earliest <= _local_stamp(bar).time() <= cutoff
    ]
    return eligible[-1] if eligible else None


def _result(
    *,
    strategy_id: str,
    session_date: date,
    ready: bool,
    fired: bool,
    direction: StrategyDirection | None,
    reason_codes: Sequence[str],
    evidence: dict[str, object],
) -> IntradaySetupResult:
    if fired and not ready:
        raise ValueError("an intraday setup cannot fire when it is not ready")
    return IntradaySetupResult(
        contract=B34_INTRADAY_PACK_CONTRACT,
        strategy_id=strategy_id,
        session_date=session_date.isoformat(),
        ready=ready,
        fired=fired,
        direction=direction.value if direction is not None else None,
        reason_codes=tuple(reason_codes),
        evidence=evidence,
    )


def evaluate_gap_continuation(
    *,
    session_date: date,
    prior_regular_close: float,
    current_regular_open: float,
    decision_time_utc: datetime,
    split_crossed: bool,
) -> IntradaySetupResult:
    decision = _require_aware(decision_time_utc).astimezone(MARKET_TZ)
    earliest = datetime.combine(session_date, time(9, 31), tzinfo=MARKET_TZ)
    if decision < earliest:
        return _result(
            strategy_id="b34_gap_continuation_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("INFORMATION_CLOCK_NOT_READY",),
            evidence={"earliest_decision_et": earliest.isoformat()},
        )
    if split_crossed:
        return _result(
            strategy_id="b34_gap_continuation_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("SPLIT_CROSSES_PRICE_COMPARISON",),
            evidence={},
        )
    if not all(math.isfinite(v) and v > 0 for v in (prior_regular_close, current_regular_open)):
        raise ValueError("gap prices must be finite and positive")
    gap_pct = current_regular_open / prior_regular_close - 1.0
    direction: StrategyDirection | None = None
    if gap_pct >= GAP_MIN_ABS_PCT:
        direction = StrategyDirection.LONG
    elif gap_pct <= -GAP_MIN_ABS_PCT:
        direction = StrategyDirection.SHORT
    fired = direction is not None
    return _result(
        strategy_id="b34_gap_continuation_v1",
        session_date=session_date,
        ready=True,
        fired=fired,
        direction=direction,
        reason_codes=(("GAP_THRESHOLD_MET",) if fired else ("GAP_BELOW_THRESHOLD",)),
        evidence={
            "prior_regular_close": prior_regular_close,
            "current_regular_open": current_regular_open,
            "gap_pct": gap_pct,
            "threshold_abs_pct": GAP_MIN_ABS_PCT,
        },
    )


def evaluate_opening_range_breakout(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
    decision_time_utc: datetime,
    split_crossed: bool = False,
) -> IntradaySetupResult:
    decision_utc = _require_aware(decision_time_utc)
    if split_crossed:
        return _result(
            strategy_id="b34_opening_range_breakout_15m_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("SPLIT_CROSSES_SESSION",),
            evidence={},
        )
    selected = _eligible_session_bars(bars, session_date=session_date, as_of_utc=decision_utc)
    local_decision = decision_utc.astimezone(MARKET_TZ)
    range_ready = datetime.combine(session_date, OPENING_RANGE_END, tzinfo=MARKET_TZ)
    if local_decision < range_ready:
        return _result(
            strategy_id="b34_opening_range_breakout_15m_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("OPENING_RANGE_NOT_CLOSED",),
            evidence={"range_ready_et": range_ready.isoformat()},
        )
    opening = _window(
        selected,
        segment=SessionSegment.REGULAR,
        start=OPENING_RANGE_START,
        end=OPENING_RANGE_END,
    )
    if not opening:
        return _result(
            strategy_id="b34_opening_range_breakout_15m_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("NO_OBSERVED_OPENING_RANGE_BARS",),
            evidence={},
        )
    range_high = max(bar.high for bar in opening)
    range_low = min(bar.low for bar in opening)
    breakout = _latest_regular_breakout_bar(
        selected,
        earliest=OPENING_RANGE_END,
        cutoff=OPENING_RANGE_ENTRY_CUTOFF,
    )
    if breakout is None:
        return _result(
            strategy_id="b34_opening_range_breakout_15m_v1",
            session_date=session_date,
            ready=True,
            fired=False,
            direction=None,
            reason_codes=("NO_CLOSED_POST_RANGE_BAR",),
            evidence={
                "opening_range_high": range_high,
                "opening_range_low": range_low,
                "opening_range_observed_bars": len(opening),
            },
        )
    direction: StrategyDirection | None = None
    if breakout.close > range_high:
        direction = StrategyDirection.LONG
    elif breakout.close < range_low:
        direction = StrategyDirection.SHORT
    fired = direction is not None
    return _result(
        strategy_id="b34_opening_range_breakout_15m_v1",
        session_date=session_date,
        ready=True,
        fired=fired,
        direction=direction,
        reason_codes=(("OPENING_RANGE_BREAKOUT",) if fired else ("INSIDE_OPENING_RANGE",)),
        evidence={
            "opening_range_high": range_high,
            "opening_range_low": range_low,
            "opening_range_observed_bars": len(opening),
            "breakout_bar_timestamp_utc": breakout.timestamp_utc.isoformat(),
            "breakout_bar_close": breakout.close,
        },
    )


def premarket_snapshot(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
    decision_time_utc: datetime,
) -> PremarketSnapshot | None:
    decision_utc = _require_aware(decision_time_utc)
    cutoff = datetime.combine(session_date, PREMARKET_END, tzinfo=MARKET_TZ)
    if decision_utc.astimezone(MARKET_TZ) < cutoff:
        return None
    # Freeze premarket information at 09:30 even if called later in the session.
    selected = _eligible_session_bars(bars, session_date=session_date, as_of_utc=cutoff.astimezone(UTC))
    premarket = _window(
        selected,
        segment=SessionSegment.PREMARKET,
        start=PREMARKET_START,
        end=PREMARKET_END,
    )
    consolidation = _window(
        selected,
        segment=SessionSegment.PREMARKET,
        start=PREMARKET_CONSOLIDATION_START,
        end=PREMARKET_CONSOLIDATION_END,
    )
    if not premarket or len(consolidation) < PREMARKET_MIN_CONSOLIDATION_BARS:
        return None
    last_price = consolidation[-1].close
    high = max(bar.high for bar in premarket)
    low = min(bar.low for bar in premarket)
    consolidation_high = max(bar.high for bar in consolidation)
    consolidation_low = min(bar.low for bar in consolidation)
    consolidation_range_pct = (consolidation_high - consolidation_low) / last_price
    return PremarketSnapshot(
        session_date=session_date.isoformat(),
        observed_bar_count=len(premarket),
        cumulative_volume=sum(float(bar.volume) for bar in premarket),
        high=high,
        low=low,
        last_price=last_price,
        consolidation_bar_count=len(consolidation),
        consolidation_high=consolidation_high,
        consolidation_low=consolidation_low,
        consolidation_range_pct=consolidation_range_pct,
    )


def evaluate_premarket_relvol_consolidation(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
    decision_time_utc: datetime,
    prior_premarket_volumes: Sequence[float],
    split_free_lookback: bool,
) -> IntradaySetupResult:
    decision_utc = _require_aware(decision_time_utc)
    bars = tuple(bars)
    if not split_free_lookback:
        return _result(
            strategy_id="b34_premarket_relvol_consolidation_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("SPLIT_CROSSES_LOOKBACK",),
            evidence={},
        )
    if len(prior_premarket_volumes) != PREMARKET_LOOKBACK_SESSIONS:
        return _result(
            strategy_id="b34_premarket_relvol_consolidation_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("INCOMPLETE_PREMARKET_LOOKBACK",),
            evidence={"required_sessions": PREMARKET_LOOKBACK_SESSIONS, "provided_sessions": len(prior_premarket_volumes)},
        )
    if not all(math.isfinite(v) and v >= 0 for v in prior_premarket_volumes):
        raise ValueError("prior premarket volumes must be finite and nonnegative")
    baseline = float(median(prior_premarket_volumes))
    if baseline <= 0:
        return _result(
            strategy_id="b34_premarket_relvol_consolidation_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("NONPOSITIVE_PREMARKET_VOLUME_BASELINE",),
            evidence={"median_prior_volume": baseline},
        )
    snapshot = premarket_snapshot(bars, session_date=session_date, decision_time_utc=decision_utc)
    if snapshot is None:
        return _result(
            strategy_id="b34_premarket_relvol_consolidation_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("PREMARKET_STATE_NOT_READY",),
            evidence={},
        )
    relvol = snapshot.cumulative_volume / baseline
    consolidated = snapshot.consolidation_range_pct <= PREMARKET_CONSOLIDATION_MAX_RANGE_PCT
    selected = _eligible_session_bars(bars, session_date=session_date, as_of_utc=decision_utc)
    breakout = _latest_regular_breakout_bar(
        selected,
        earliest=PREMARKET_END,
        cutoff=PREMARKET_BREAKOUT_CUTOFF,
    )
    breakout_confirmed = breakout is not None and breakout.close > snapshot.consolidation_high
    fired = relvol >= PREMARKET_RELVOL_MIN and consolidated and breakout_confirmed
    reasons: list[str] = []
    if relvol < PREMARKET_RELVOL_MIN:
        reasons.append("PREMARKET_RELVOL_BELOW_THRESHOLD")
    if not consolidated:
        reasons.append("PREMARKET_NOT_CONSOLIDATED")
    if not breakout_confirmed:
        reasons.append("NO_CLOSED_CONSOLIDATION_BREAKOUT")
    if fired:
        reasons.append("PREMARKET_RELVOL_CONSOLIDATION_BREAKOUT")
    return _result(
        strategy_id="b34_premarket_relvol_consolidation_v1",
        session_date=session_date,
        ready=True,
        fired=fired,
        direction=StrategyDirection.LONG if fired else None,
        reason_codes=reasons,
        evidence={
            **asdict(snapshot),
            "median_prior_20_premarket_volume": baseline,
            "premarket_relvol": relvol,
            "relvol_threshold": PREMARKET_RELVOL_MIN,
            "consolidation_max_range_pct": PREMARKET_CONSOLIDATION_MAX_RANGE_PCT,
            "breakout_bar_timestamp_utc": breakout.timestamp_utc.isoformat() if breakout else None,
            "breakout_bar_close": breakout.close if breakout else None,
        },
    )


def evaluate_highest_volume_day_style(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
    decision_time_utc: datetime,
    prior_regular_daily_volumes: Sequence[float],
    split_free_lookback: bool,
) -> IntradaySetupResult:
    decision_utc = _require_aware(decision_time_utc)
    bars = tuple(bars)
    if not split_free_lookback:
        return _result(
            strategy_id="b34_highest_volume_day_style_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("SPLIT_CROSSES_LOOKBACK",),
            evidence={},
        )
    if len(prior_regular_daily_volumes) != HVD_DAILY_LOOKBACK_SESSIONS:
        return _result(
            strategy_id="b34_highest_volume_day_style_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("INCOMPLETE_DAILY_VOLUME_LOOKBACK",),
            evidence={"required_sessions": HVD_DAILY_LOOKBACK_SESSIONS, "provided_sessions": len(prior_regular_daily_volumes)},
        )
    if not all(math.isfinite(v) and v >= 0 for v in prior_regular_daily_volumes):
        raise ValueError("prior daily volumes must be finite and nonnegative")
    highest_prior = float(max(prior_regular_daily_volumes))
    if highest_prior <= 0:
        return _result(
            strategy_id="b34_highest_volume_day_style_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("NONPOSITIVE_DAILY_VOLUME_BASELINE",),
            evidence={"highest_prior_daily_volume": highest_prior},
        )
    snapshot = premarket_snapshot(bars, session_date=session_date, decision_time_utc=decision_utc)
    if snapshot is None:
        return _result(
            strategy_id="b34_highest_volume_day_style_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            reason_codes=("PREMARKET_STATE_NOT_READY",),
            evidence={},
        )
    selected = _eligible_session_bars(bars, session_date=session_date, as_of_utc=decision_utc)
    breakout = _latest_regular_breakout_bar(
        selected,
        earliest=PREMARKET_END,
        cutoff=PREMARKET_BREAKOUT_CUTOFF,
    )
    volume_ready = snapshot.cumulative_volume >= highest_prior
    consolidated = snapshot.consolidation_range_pct <= PREMARKET_CONSOLIDATION_MAX_RANGE_PCT
    breakout_confirmed = breakout is not None and breakout.close > snapshot.high
    fired = volume_ready and consolidated and breakout_confirmed
    reasons: list[str] = []
    if not volume_ready:
        reasons.append("PREMARKET_VOLUME_BELOW_PRIOR_252_MAX")
    if not consolidated:
        reasons.append("PREMARKET_NOT_CONSOLIDATED")
    if not breakout_confirmed:
        reasons.append("NO_CLOSED_PREMARKET_HIGH_BREAKOUT")
    if fired:
        reasons.append("HVD_STYLE_PREMARKET_HIGH_BREAKOUT")
    return _result(
        strategy_id="b34_highest_volume_day_style_v1",
        session_date=session_date,
        ready=True,
        fired=fired,
        direction=StrategyDirection.LONG if fired else None,
        reason_codes=reasons,
        evidence={
            **asdict(snapshot),
            "highest_prior_252_daily_volume": highest_prior,
            "premarket_volume_ratio_to_prior_max": snapshot.cumulative_volume / highest_prior,
            "consolidation_max_range_pct": PREMARKET_CONSOLIDATION_MAX_RANGE_PCT,
            "breakout_bar_timestamp_utc": breakout.timestamp_utc.isoformat() if breakout else None,
            "breakout_bar_close": breakout.close if breakout else None,
        },
    )
