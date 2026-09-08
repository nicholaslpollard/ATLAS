from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from statistics import median, pstdev
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

from packages.core.enums import SessionSegment
from packages.schemas.market import CanonicalBar
from packages.strategies.b35_conditional_evidence_contract import (
    B35_PREOUTCOME_FINGERPRINT,
    bucket_absolute_gap_pct,
    bucket_hvd_volume_ratio,
    bucket_median_dollar_volume_20,
    bucket_opening_range_width_pct,
    bucket_premarket_dollar_volume,
    bucket_premarket_relvol_20,
    bucket_prior_close_price,
    bucket_realized_volatility_20,
    bucket_signal_time_et,
)
from packages.strategies.intraday_opening_pack import IntradaySetupResult


B35_DEVELOPMENT_CONTEXT_CONTRACT = (
    "atlas-b35-development-context-v2-prior-only-split-clock-corrected"
)
MARKET_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class DailySessionSummary:
    session_date: date
    close: float
    regular_volume: float
    dollar_volume: float
    # Equality-only split epoch token, never an adjustment ratio.
    split_factor: float | None = None


@dataclass(frozen=True, slots=True)
class B35ConditionSnapshot:
    contract: str
    b35_preoutcome_fingerprint: str
    strategy_id: str
    symbol: str
    session_date: str
    prior_market_regime: str
    prior_close_price: str
    median_dollar_volume_20: str
    realized_volatility_20: str
    prior_trend_20_50: str
    absolute_gap_pct: str
    premarket_relvol_20: str
    premarket_dollar_volume: str
    opening_range_width_pct: str
    signal_time_et: str
    hvd_volume_ratio: str
    setup_intensity_dimension: str
    setup_intensity_bucket: str
    split_crossed_prior_close: bool
    split_free_20: bool
    split_free_252: bool
    snapshot_fingerprint: str


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def summarize_regular_session(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
    split_factor: float | None = None,
) -> DailySessionSummary | None:
    regular = sorted(
        (
            bar
            for bar in bars
            if bar.session_date == session_date
            and bar.session_segment == SessionSegment.REGULAR
        ),
        key=lambda bar: bar.timestamp_utc,
    )
    if not regular:
        return None
    close = float(regular[-1].close)
    volume = sum(float(bar.volume) for bar in regular)
    dollar_volume = sum(
        float(bar.volume) * float(bar.vwap if bar.vwap is not None else bar.close)
        for bar in regular
    )
    if not math.isfinite(close) or close <= 0 or volume < 0 or dollar_volume < 0:
        raise ValueError("invalid raw-minute daily summary")
    return DailySessionSummary(
        session_date=session_date,
        close=close,
        regular_volume=volume,
        dollar_volume=dollar_volume,
        split_factor=split_factor,
    )


def split_free(
    summaries: Sequence[DailySessionSummary], *, current_factor: float | None
) -> bool:
    if current_factor is None or not math.isfinite(current_factor) or current_factor <= 0:
        return False
    factors = [item.split_factor for item in summaries]
    if any(
        value is None or not math.isfinite(float(value)) or float(value) <= 0
        for value in factors
    ):
        return False
    return all(
        math.isclose(float(value), current_factor, rel_tol=1e-10, abs_tol=1e-12)
        for value in factors
    )


def _prior_window_split_free(
    prior: Sequence[DailySessionSummary], required: int
) -> bool:
    if len(prior) < required:
        return False
    window = prior[-required:]
    return split_free(window, current_factor=window[-1].split_factor)


def split_crossed_prior_close(
    prior: DailySessionSummary | None,
    *,
    current_factor: float | None,
) -> bool:
    if prior is None or prior.split_factor is None or current_factor is None:
        return True
    if not all(
        math.isfinite(float(value)) and float(value) > 0
        for value in (prior.split_factor, current_factor)
    ):
        return True
    return not math.isclose(
        float(prior.split_factor), float(current_factor), rel_tol=1e-10, abs_tol=1e-12
    )


def _median_dollar_volume(prior: Sequence[DailySessionSummary]) -> float | None:
    if len(prior) < 20:
        return None
    return float(median(item.dollar_volume for item in prior[-20:]))


def _realized_volatility(prior: Sequence[DailySessionSummary]) -> float | None:
    # Twenty close-to-close returns require 21 already-completed closes, all in
    # one raw-price split epoch.
    if len(prior) < 21 or not _prior_window_split_free(prior, 21):
        return None
    closes = [float(item.close) for item in prior[-21:]]
    if any(value <= 0 or not math.isfinite(value) for value in closes):
        return None
    returns = [
        math.log(closes[index] / closes[index - 1]) for index in range(1, len(closes))
    ]
    if len(returns) != 20:
        return None
    return float(pstdev(returns) * math.sqrt(252.0))


def _trend(prior: Sequence[DailySessionSummary]) -> str:
    if len(prior) < 50 or not _prior_window_split_free(prior, 50):
        return "UNAVAILABLE"
    closes = [float(item.close) for item in prior[-50:]]
    sma20 = sum(closes[-20:]) / 20.0
    sma50 = sum(closes) / 50.0
    last = closes[-1]
    if last > sma20 > sma50:
        return "UP"
    if last < sma20 < sma50:
        return "DOWN"
    return "MIXED"


def _premarket_dollar_volume(
    bars: Iterable[CanonicalBar], session_date: date
) -> float | None:
    eligible = [
        bar
        for bar in bars
        if bar.session_date == session_date
        and bar.session_segment == SessionSegment.PREMARKET
        and time(4, 0)
        <= bar.timestamp_utc.astimezone(MARKET_TZ).time()
        < time(9, 30)
    ]
    if not eligible:
        return None
    return float(
        sum(
            float(bar.volume) * float(bar.vwap if bar.vwap is not None else bar.close)
            for bar in eligible
        )
    )


def _signal_time(setup: IntradaySetupResult) -> time:
    raw = setup.evidence.get("breakout_bar_timestamp_utc")
    if isinstance(raw, str) and raw:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("setup breakout timestamp must be timezone-aware")
        # B34 bar timestamps are left/start edges. A bar stamped T becomes
        # information-safe at T+1 minute, so an 11:30 bar is a valid 11:31
        # B35 decision.
        local = stamp.astimezone(MARKET_TZ)
        minute = local.minute + 1
        hour = local.hour
        if minute >= 60:
            hour += 1
            minute -= 60
        return time(hour, minute)
    if setup.strategy_id == "b34_gap_continuation_v1":
        return time(9, 31)
    raise ValueError("fired B35 setup has no information-safe signal time")


def build_condition_snapshot(
    setup: IntradaySetupResult,
    bars: Iterable[CanonicalBar],
    *,
    symbol: str,
    session_date: date,
    prior_daily: Sequence[DailySessionSummary],
    current_regular_open: float,
    current_split_factor: float | None,
    prior_market_regime: str = "UNAVAILABLE",
    signal_time_et_override: time | None = None,
) -> B35ConditionSnapshot:
    if not setup.ready or not setup.fired:
        raise ValueError("condition snapshot requires a fired B34 setup")
    if setup.session_date != session_date.isoformat():
        raise ValueError("condition snapshot setup/session mismatch")
    bars = tuple(bars)
    prior = prior_daily[-1] if prior_daily else None
    prior_close = prior.close if prior is not None else None
    if prior_close is None or prior_close <= 0:
        raise ValueError("condition snapshot requires a prior regular close")

    crossed = split_crossed_prior_close(prior, current_factor=current_split_factor)
    if setup.strategy_id == "b34_gap_continuation_v1" and crossed:
        # B34 itself is frozen to fail closed for gap continuation across a split.
        raise ValueError("gap continuation cannot be profiled across a split-crossed prior close")
    gap_pct = None if crossed else current_regular_open / prior_close - 1.0

    median_dv = _median_dollar_volume(prior_daily)
    realized = _realized_volatility(prior_daily)
    pm_relvol = setup.evidence.get("premarket_relvol")
    hvd_ratio = setup.evidence.get("premarket_volume_ratio_to_prior_max")
    range_high = setup.evidence.get("opening_range_high")
    range_low = setup.evidence.get("opening_range_low")
    opening_width: float | None = None
    if range_high is not None and range_low is not None and current_regular_open > 0:
        opening_width = (float(range_high) - float(range_low)) / current_regular_open

    signal_time_value = signal_time_et_override or _signal_time(setup)
    signal_bucket = bucket_signal_time_et(signal_time_value)
    relvol_bucket = bucket_premarket_relvol_20(
        float(pm_relvol) if pm_relvol is not None else None
    )
    hvd_bucket = bucket_hvd_volume_ratio(
        float(hvd_ratio) if hvd_ratio is not None else None
    )
    opening_bucket = bucket_opening_range_width_pct(opening_width)
    gap_bucket = bucket_absolute_gap_pct(gap_pct)

    intensity_by_strategy = {
        "b34_gap_continuation_v1": ("absolute_gap_pct", gap_bucket),
        "b34_opening_range_breakout_15m_v1": (
            "opening_range_width_pct",
            opening_bucket,
        ),
        "b34_premarket_relvol_consolidation_v1": (
            "premarket_relvol_20",
            relvol_bucket,
        ),
        "b34_highest_volume_day_style_v1": ("hvd_volume_ratio", hvd_bucket),
    }
    if setup.strategy_id not in intensity_by_strategy:
        raise ValueError(f"unsupported B35 strategy: {setup.strategy_id}")
    intensity_dimension, intensity_bucket = intensity_by_strategy[setup.strategy_id]

    # `split_free_20` is the audit flag for the 20-return realized-volatility
    # feature, which correctly requires 21 completed closes.
    split20 = _prior_window_split_free(prior_daily, 21)
    split252 = _prior_window_split_free(prior_daily, 252)
    values = {
        "contract": B35_DEVELOPMENT_CONTEXT_CONTRACT,
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "strategy_id": setup.strategy_id,
        "symbol": symbol,
        "session_date": session_date.isoformat(),
        "prior_market_regime": prior_market_regime or "UNAVAILABLE",
        "prior_close_price": bucket_prior_close_price(prior_close),
        "median_dollar_volume_20": bucket_median_dollar_volume_20(median_dv),
        "realized_volatility_20": bucket_realized_volatility_20(realized),
        "prior_trend_20_50": _trend(prior_daily),
        "absolute_gap_pct": gap_bucket,
        "premarket_relvol_20": relvol_bucket,
        "premarket_dollar_volume": bucket_premarket_dollar_volume(
            _premarket_dollar_volume(bars, session_date)
        ),
        "opening_range_width_pct": opening_bucket,
        "signal_time_et": signal_bucket,
        "hvd_volume_ratio": hvd_bucket,
        "setup_intensity_dimension": intensity_dimension,
        "setup_intensity_bucket": intensity_bucket,
        "split_crossed_prior_close": crossed,
        "split_free_20": split20,
        "split_free_252": split252,
    }
    fingerprint = _stable_hash(values)
    return B35ConditionSnapshot(**values, snapshot_fingerprint=fingerprint)


def snapshot_to_dict(snapshot: B35ConditionSnapshot) -> dict[str, object]:
    return asdict(snapshot)
