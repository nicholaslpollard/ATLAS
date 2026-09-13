from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

import numpy as np
import pandas as pd

from packages.features.reference_daily import compute_reference_daily_features
from packages.features.rolling import sma, wilder_average


SUCCESSOR_PRACTITIONER_FEATURE_CONTRACT_VERSION = (
    "successor-practitioner-features-v2-pit-confirmed-patterns-exact-pivot-cross-shared-compute"
)

PIVOT_RADIUS = 2
BOLLINGER_MEAN_REVERSION_RSI_LONG_MAX = 45.0
BOLLINGER_MEAN_REVERSION_RSI_SHORT_MIN = 55.0
ATR_EXPANSION_MULTIPLE = 1.5
PIVOT_BREAKOUT_RELATIVE_VOLUME_MIN = 1.25
HEAD_SHOULDERS_SHOULDER_TOLERANCE = 0.03
HEAD_SHOULDERS_HEAD_PROMINENCE = 0.03
DOUBLE_PATTERN_TOLERANCE = 0.02
DOUBLE_PATTERN_MIN_SEPARATION = 5
DOUBLE_PATTERN_MAX_SEPARATION = 40
FLAG_IMPULSE_MIN_RETURN = 0.08
FLAG_CONSOLIDATION_MAX_IMPULSE_FRACTION = 0.50
TRIANGLE_LOOKBACK = 10
TRIANGLE_MIN_NORMALIZED_SLOPE = 0.001
TRIANGLE_MAX_END_WIDTH_FRACTION = 0.70
ADX_PERIOD = 14
ADX_MIN = 25.0
RELATIVE_STRENGTH_SHORT_SESSIONS = 20
RELATIVE_STRENGTH_MEDIUM_SESSIONS = 63
MARKET_VOLATILITY_LOOKBACK = 252

SUCCESSOR_DAILY_DERIVED_COLUMNS = (
    "plus_di_14",
    "minus_di_14",
    "adx_14",
    "confirmed_pivot_high",
    "confirmed_pivot_low",
    "confirmed_pivot_high_center_position",
    "confirmed_pivot_low_center_position",
    "bollinger_mean_reversion_long",
    "bollinger_mean_reversion_short",
    "atr_volatility_expansion_long",
    "atr_volatility_expansion_short",
    "pivot_sr_breakout_long",
    "pivot_sr_breakout_short",
    "head_shoulders_breakdown_short",
    "inverse_head_shoulders_breakout_long",
    "double_top_breakdown_short",
    "double_bottom_breakout_long",
    "flag_pennant_breakout_long",
    "flag_pennant_breakout_short",
    "triangle_breakout_long",
    "triangle_breakout_short",
    "adx_dmi_continuation_long",
    "adx_dmi_continuation_short",
    "ticker_return_20",
    "ticker_return_63",
    "spy_return_20",
    "spy_return_63",
    "relative_strength_vs_spy_20",
    "relative_strength_vs_spy_63",
    "relative_strength_momentum_long",
    "relative_strength_momentum_short",
    "spy_sma_50",
    "spy_realized_volatility_20",
    "spy_prior_median_realized_volatility_252",
    "overnight_gap",
    "atr_normalized_extension_20",
)


class SuccessorPractitionerFeatureError(ValueError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def successor_practitioner_feature_fingerprint() -> str:
    return _stable_hash(
        {
            "contract_version": SUCCESSOR_PRACTITIONER_FEATURE_CONTRACT_VERSION,
            "derived_columns": SUCCESSOR_DAILY_DERIVED_COLUMNS,
            "parameters": {
                "pivot_radius": PIVOT_RADIUS,
                "bollinger_mean_reversion_rsi_long_max": BOLLINGER_MEAN_REVERSION_RSI_LONG_MAX,
                "bollinger_mean_reversion_rsi_short_min": BOLLINGER_MEAN_REVERSION_RSI_SHORT_MIN,
                "atr_expansion_multiple": ATR_EXPANSION_MULTIPLE,
                "pivot_breakout_relative_volume_min": PIVOT_BREAKOUT_RELATIVE_VOLUME_MIN,
                "head_shoulders_shoulder_tolerance": HEAD_SHOULDERS_SHOULDER_TOLERANCE,
                "head_shoulders_head_prominence": HEAD_SHOULDERS_HEAD_PROMINENCE,
                "double_pattern_tolerance": DOUBLE_PATTERN_TOLERANCE,
                "double_pattern_min_separation": DOUBLE_PATTERN_MIN_SEPARATION,
                "double_pattern_max_separation": DOUBLE_PATTERN_MAX_SEPARATION,
                "flag_impulse_min_return": FLAG_IMPULSE_MIN_RETURN,
                "flag_consolidation_max_impulse_fraction": FLAG_CONSOLIDATION_MAX_IMPULSE_FRACTION,
                "triangle_lookback": TRIANGLE_LOOKBACK,
                "triangle_min_normalized_slope": TRIANGLE_MIN_NORMALIZED_SLOPE,
                "triangle_max_end_width_fraction": TRIANGLE_MAX_END_WIDTH_FRACTION,
                "adx_period": ADX_PERIOD,
                "adx_min": ADX_MIN,
                "relative_strength_short_sessions": RELATIVE_STRENGTH_SHORT_SESSIONS,
                "relative_strength_medium_sessions": RELATIVE_STRENGTH_MEDIUM_SESSIONS,
                "market_volatility_lookback": MARKET_VOLATILITY_LOOKBACK,
            },
            "information_clock": {
                "daily_inputs": "finalized same-session daily close for next-session-open decisions",
                "benchmark_join": "same-session SPY close only; no future benchmark rows",
                "confirmed_pivot": "radius-2 center becomes usable only after both right-side bars have closed",
                "pivot_breakout_cross": "prior and current close are evaluated against the same previously-known confirmed pivot level",
                "pattern_breakout": "pattern geometry must have been known before the breakout bar",
            },
            "shared_compute": (
                "extend compute_reference_daily_features once per instrument group; reuse shared columns "
                "across every successor policy rather than recalculating indicators by strategy"
            ),
        }
    )


def _binary(mask: pd.Series, valid: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=mask.index, dtype="float64")
    result.loc[valid] = mask.loc[valid].astype("float64")
    return result


def adx_dmi(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    period: int = ADX_PERIOD,
) -> pd.DataFrame:
    if period < 1:
        raise ValueError("period must be positive")
    high_s = pd.to_numeric(high, errors="coerce").astype("float64")
    low_s = pd.to_numeric(low, errors="coerce").astype("float64")
    close_s = pd.to_numeric(close, errors="coerce").astype("float64")
    if not (high_s.index.equals(low_s.index) and high_s.index.equals(close_s.index)):
        raise ValueError("high, low and close must share the same index")

    up_move = high_s.diff()
    down_move = -low_s.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0),
        index=high_s.index,
        dtype="float64",
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0),
        index=high_s.index,
        dtype="float64",
    )
    previous_close = close_s.shift(1)
    true_range = pd.concat(
        [
            high_s - low_s,
            (high_s - previous_close).abs(),
            (low_s - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=True)
    atr = wilder_average(true_range, period)
    plus = 100.0 * wilder_average(plus_dm, period) / atr
    minus = 100.0 * wilder_average(minus_dm, period) / atr
    denominator = plus + minus
    dx = (100.0 * (plus - minus).abs() / denominator).where(denominator > 0.0, 0.0)
    adx = wilder_average(dx, period)
    return pd.DataFrame(
        {
            f"plus_di_{period}": plus,
            f"minus_di_{period}": minus,
            f"adx_{period}": adx,
        },
        index=high_s.index,
    )


def confirmed_pivot_levels(
    high: pd.Series,
    low: pd.Series,
    *,
    radius: int = PIVOT_RADIUS,
) -> pd.DataFrame:
    """Most recent strictly confirmed swing levels with an explicit no-lookahead clock."""

    if radius < 1:
        raise ValueError("radius must be positive")
    high_s = pd.to_numeric(high, errors="coerce").astype("float64")
    low_s = pd.to_numeric(low, errors="coerce").astype("float64")
    if not high_s.index.equals(low_s.index):
        raise ValueError("high and low must share the same index")
    n = len(high_s)
    latest_high = math.nan
    latest_low = math.nan
    latest_high_center = math.nan
    latest_low_center = math.nan
    out_high = np.full(n, np.nan, dtype="float64")
    out_low = np.full(n, np.nan, dtype="float64")
    out_high_pos = np.full(n, np.nan, dtype="float64")
    out_low_pos = np.full(n, np.nan, dtype="float64")
    highs = high_s.to_numpy(dtype="float64")
    lows = low_s.to_numpy(dtype="float64")

    for available_position in range(n):
        center = available_position - radius
        if center >= radius:
            start = center - radius
            stop = center + radius + 1
            high_window = highs[start:stop]
            low_window = lows[start:stop]
            if np.isfinite(high_window).all():
                center_high = highs[center]
                others = np.delete(high_window, radius)
                if center_high > float(np.max(others)):
                    latest_high = float(center_high)
                    latest_high_center = float(center)
            if np.isfinite(low_window).all():
                center_low = lows[center]
                others = np.delete(low_window, radius)
                if center_low < float(np.min(others)):
                    latest_low = float(center_low)
                    latest_low_center = float(center)
        out_high[available_position] = latest_high
        out_low[available_position] = latest_low
        out_high_pos[available_position] = latest_high_center
        out_low_pos[available_position] = latest_low_center

    return pd.DataFrame(
        {
            "confirmed_pivot_high": out_high,
            "confirmed_pivot_low": out_low,
            "confirmed_pivot_high_center_position": out_high_pos,
            "confirmed_pivot_low_center_position": out_low_pos,
        },
        index=high_s.index,
    )


def _line_at(left: tuple[int, float], right: tuple[int, float], position: int) -> float:
    if right[0] == left[0]:
        return float(right[1])
    slope = (right[1] - left[1]) / float(right[0] - left[0])
    return float(left[1] + slope * (position - left[0]))


def _between(events: list[tuple[int, float]], left: int, right: int) -> list[tuple[int, float]]:
    return [item for item in events if left < item[0] < right]


def _pattern_signals(group: pd.DataFrame) -> pd.DataFrame:
    n = len(group)
    result = pd.DataFrame(
        0.0,
        index=group.index,
        columns=[
            "head_shoulders_breakdown_short",
            "inverse_head_shoulders_breakout_long",
            "double_top_breakdown_short",
            "double_bottom_breakout_long",
            "flag_pennant_breakout_long",
            "flag_pennant_breakout_short",
            "triangle_breakout_long",
            "triangle_breakout_short",
        ],
        dtype="float64",
    )
    highs = group["high"].to_numpy(dtype="float64")
    lows = group["low"].to_numpy(dtype="float64")
    closes = group["close"].to_numpy(dtype="float64")
    pivot_highs: list[tuple[int, float]] = []
    pivot_lows: list[tuple[int, float]] = []

    for position in range(n):
        # Pattern geometry used by this bar contains only pivots that were fully
        # confirmed before this bar began. The pivot whose right edge is this bar
        # is added only after signal evaluation below.
        if position > 0:
            previous_close = closes[position - 1]
            current_close = closes[position]

            if len(pivot_highs) >= 3:
                h1, h2, h3 = pivot_highs[-3:]
                shoulder_mid = (h1[1] + h3[1]) / 2.0
                shoulder_similar = (
                    shoulder_mid > 0.0
                    and abs(h1[1] - h3[1]) / shoulder_mid <= HEAD_SHOULDERS_SHOULDER_TOLERANCE
                )
                head_prominent = h2[1] >= max(h1[1], h3[1]) * (1.0 + HEAD_SHOULDERS_HEAD_PROMINENCE)
                left_lows = _between(pivot_lows, h1[0], h2[0])
                right_lows = _between(pivot_lows, h2[0], h3[0])
                if shoulder_similar and head_prominent and left_lows and right_lows:
                    left_neck = min(left_lows, key=lambda item: item[1])
                    right_neck = min(right_lows, key=lambda item: item[1])
                    neck_now = _line_at(left_neck, right_neck, position)
                    neck_prev = _line_at(left_neck, right_neck, position - 1)
                    if previous_close >= neck_prev and current_close < neck_now:
                        result.iloc[position, result.columns.get_loc("head_shoulders_breakdown_short")] = 1.0

            if len(pivot_lows) >= 3:
                l1, l2, l3 = pivot_lows[-3:]
                shoulder_mid = (l1[1] + l3[1]) / 2.0
                shoulder_similar = (
                    shoulder_mid > 0.0
                    and abs(l1[1] - l3[1]) / shoulder_mid <= HEAD_SHOULDERS_SHOULDER_TOLERANCE
                )
                head_prominent = l2[1] <= min(l1[1], l3[1]) * (1.0 - HEAD_SHOULDERS_HEAD_PROMINENCE)
                left_highs = _between(pivot_highs, l1[0], l2[0])
                right_highs = _between(pivot_highs, l2[0], l3[0])
                if shoulder_similar and head_prominent and left_highs and right_highs:
                    left_neck = max(left_highs, key=lambda item: item[1])
                    right_neck = max(right_highs, key=lambda item: item[1])
                    neck_now = _line_at(left_neck, right_neck, position)
                    neck_prev = _line_at(left_neck, right_neck, position - 1)
                    if previous_close <= neck_prev and current_close > neck_now:
                        result.iloc[position, result.columns.get_loc("inverse_head_shoulders_breakout_long")] = 1.0

            if len(pivot_highs) >= 2:
                first, second = pivot_highs[-2:]
                separation = second[0] - first[0]
                midpoint = (first[1] + second[1]) / 2.0
                valleys = _between(pivot_lows, first[0], second[0])
                if (
                    DOUBLE_PATTERN_MIN_SEPARATION <= separation <= DOUBLE_PATTERN_MAX_SEPARATION
                    and midpoint > 0.0
                    and abs(first[1] - second[1]) / midpoint <= DOUBLE_PATTERN_TOLERANCE
                    and valleys
                ):
                    valley = min(item[1] for item in valleys)
                    if previous_close >= valley and current_close < valley:
                        result.iloc[position, result.columns.get_loc("double_top_breakdown_short")] = 1.0

            if len(pivot_lows) >= 2:
                first, second = pivot_lows[-2:]
                separation = second[0] - first[0]
                midpoint = (first[1] + second[1]) / 2.0
                peaks = _between(pivot_highs, first[0], second[0])
                if (
                    DOUBLE_PATTERN_MIN_SEPARATION <= separation <= DOUBLE_PATTERN_MAX_SEPARATION
                    and midpoint > 0.0
                    and abs(first[1] - second[1]) / midpoint <= DOUBLE_PATTERN_TOLERANCE
                    and peaks
                ):
                    peak = max(item[1] for item in peaks)
                    if previous_close <= peak and current_close > peak:
                        result.iloc[position, result.columns.get_loc("double_bottom_breakout_long")] = 1.0

            if position >= 16:
                impulse_start = closes[position - 15]
                impulse_end = closes[position - 6]
                if impulse_start > 0.0:
                    impulse_return = impulse_end / impulse_start - 1.0
                    impulse_size = abs(impulse_end - impulse_start)
                    consolidation_high = float(np.max(highs[position - 5 : position]))
                    consolidation_low = float(np.min(lows[position - 5 : position]))
                    consolidation_range = consolidation_high - consolidation_low
                    compact = (
                        impulse_size > 0.0
                        and consolidation_range
                        <= FLAG_CONSOLIDATION_MAX_IMPULSE_FRACTION * impulse_size
                    )
                    if (
                        compact
                        and impulse_return >= FLAG_IMPULSE_MIN_RETURN
                        and consolidation_low
                        >= impulse_end - FLAG_CONSOLIDATION_MAX_IMPULSE_FRACTION * impulse_size
                        and current_close > consolidation_high
                    ):
                        result.iloc[position, result.columns.get_loc("flag_pennant_breakout_long")] = 1.0
                    if (
                        compact
                        and impulse_return <= -FLAG_IMPULSE_MIN_RETURN
                        and consolidation_high
                        <= impulse_end + FLAG_CONSOLIDATION_MAX_IMPULSE_FRACTION * impulse_size
                        and current_close < consolidation_low
                    ):
                        result.iloc[position, result.columns.get_loc("flag_pennant_breakout_short")] = 1.0

            if position >= TRIANGLE_LOOKBACK:
                start = position - TRIANGLE_LOOKBACK
                prior_high = highs[start:position]
                prior_low = lows[start:position]
                prior_close = closes[start:position]
                if np.isfinite(prior_high).all() and np.isfinite(prior_low).all():
                    scale = float(np.mean(prior_close))
                    if scale > 0.0:
                        x = np.arange(TRIANGLE_LOOKBACK, dtype="float64")
                        upper_slope, upper_intercept = np.polyfit(x, prior_high, 1)
                        lower_slope, lower_intercept = np.polyfit(x, prior_low, 1)
                        first_width = float(
                            (upper_intercept + upper_slope * 0.0)
                            - (lower_intercept + lower_slope * 0.0)
                        )
                        end_x = float(TRIANGLE_LOOKBACK - 1)
                        end_width = float(
                            (upper_intercept + upper_slope * end_x)
                            - (lower_intercept + lower_slope * end_x)
                        )
                        projected_upper = float(
                            upper_intercept + upper_slope * TRIANGLE_LOOKBACK
                        )
                        projected_lower = float(
                            lower_intercept + lower_slope * TRIANGLE_LOOKBACK
                        )
                        converging = (
                            upper_slope / scale <= -TRIANGLE_MIN_NORMALIZED_SLOPE
                            and lower_slope / scale >= TRIANGLE_MIN_NORMALIZED_SLOPE
                            and first_width > 0.0
                            and 0.0 < end_width
                            <= TRIANGLE_MAX_END_WIDTH_FRACTION * first_width
                            and projected_upper > projected_lower
                        )
                        if converging and current_close > projected_upper:
                            result.iloc[position, result.columns.get_loc("triangle_breakout_long")] = 1.0
                        if converging and current_close < projected_lower:
                            result.iloc[position, result.columns.get_loc("triangle_breakout_short")] = 1.0

        # Add a radius-2 pivot only after this bar's signal evaluation, so no
        # strategy can break a pattern that required this same bar to define it.
        center = position - PIVOT_RADIUS
        if center >= PIVOT_RADIUS:
            start = center - PIVOT_RADIUS
            stop = center + PIVOT_RADIUS + 1
            high_window = highs[start:stop]
            low_window = lows[start:stop]
            if np.isfinite(high_window).all():
                center_high = highs[center]
                if center_high > float(np.max(np.delete(high_window, PIVOT_RADIUS))):
                    pivot_highs.append((center, float(center_high)))
            if np.isfinite(low_window).all():
                center_low = lows[center]
                if center_low < float(np.min(np.delete(low_window, PIVOT_RADIUS))):
                    pivot_lows.append((center, float(center_low)))

    return result


def _daily_overlay(group: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(index=group.index)
    dmi = adx_dmi(group["high"], group["low"], group["close"], period=ADX_PERIOD)
    result = pd.concat([result, dmi], axis=1)
    pivots = confirmed_pivot_levels(group["high"], group["low"], radius=PIVOT_RADIUS)
    result = pd.concat([result, pivots], axis=1)

    close = group["close"]
    previous_close = close.shift(1)
    result["overnight_gap"] = (group["open"] / previous_close - 1.0).where(previous_close > 0.0)
    result["atr_normalized_extension_20"] = (
        (close - group["ema_20"]) / group["atr_14"]
    ).where(group["atr_14"] > 0.0)

    mean_reversion_valid = (
        previous_close.notna()
        & group["bb_lower_20"].shift(1).notna()
        & group["bb_upper_20"].shift(1).notna()
        & group["bb_lower_20"].notna()
        & group["bb_upper_20"].notna()
        & group["rsi_14"].notna()
    )
    result["bollinger_mean_reversion_long"] = _binary(
        (previous_close < group["bb_lower_20"].shift(1))
        & (close >= group["bb_lower_20"])
        & (group["rsi_14"] <= BOLLINGER_MEAN_REVERSION_RSI_LONG_MAX),
        mean_reversion_valid,
    )
    result["bollinger_mean_reversion_short"] = _binary(
        (previous_close > group["bb_upper_20"].shift(1))
        & (close <= group["bb_upper_20"])
        & (group["rsi_14"] >= BOLLINGER_MEAN_REVERSION_RSI_SHORT_MIN),
        mean_reversion_valid,
    )

    bar_range = group["high"] - group["low"]
    close_location = ((close - group["low"]) / bar_range).where(bar_range > 0.0, 0.5)
    atr_previous = group["atr_14"].shift(1)
    expansion_valid = atr_previous.notna() & group["true_range"].notna() & previous_close.notna()
    result["atr_volatility_expansion_long"] = _binary(
        (group["true_range"] >= ATR_EXPANSION_MULTIPLE * atr_previous)
        & (close_location >= 0.75)
        & (close > previous_close),
        expansion_valid,
    )
    result["atr_volatility_expansion_short"] = _binary(
        (group["true_range"] >= ATR_EXPANSION_MULTIPLE * atr_previous)
        & (close_location <= 0.25)
        & (close < previous_close),
        expansion_valid,
    )

    # The level itself must have been known before the signal session. Compare
    # both sides of the crossover with that exact same frozen level; never mix
    # the previously-known level with an older pivot snapshot.
    known_high = result["confirmed_pivot_high"].shift(1)
    known_low = result["confirmed_pivot_low"].shift(1)
    pivot_valid = group["relative_volume_20"].notna()
    result["pivot_sr_breakout_long"] = _binary(
        known_high.notna()
        & (previous_close <= known_high)
        & (close > known_high)
        & (group["relative_volume_20"] >= PIVOT_BREAKOUT_RELATIVE_VOLUME_MIN),
        pivot_valid & known_high.notna() & previous_close.notna(),
    )
    result["pivot_sr_breakout_short"] = _binary(
        known_low.notna()
        & (previous_close >= known_low)
        & (close < known_low)
        & (group["relative_volume_20"] >= PIVOT_BREAKOUT_RELATIVE_VOLUME_MIN),
        pivot_valid & known_low.notna() & previous_close.notna(),
    )

    plus_di = result["plus_di_14"]
    minus_di = result["minus_di_14"]
    adx_valid = (
        result["adx_14"].notna()
        & plus_di.notna()
        & minus_di.notna()
        & plus_di.shift(1).notna()
        & minus_di.shift(1).notna()
        & group["ema_20"].notna()
    )
    result["adx_dmi_continuation_long"] = _binary(
        (result["adx_14"] >= ADX_MIN)
        & (plus_di.shift(1) <= minus_di.shift(1))
        & (plus_di > minus_di)
        & (close > group["ema_20"]),
        adx_valid,
    )
    result["adx_dmi_continuation_short"] = _binary(
        (result["adx_14"] >= ADX_MIN)
        & (minus_di.shift(1) <= plus_di.shift(1))
        & (minus_di > plus_di)
        & (close < group["ema_20"]),
        adx_valid,
    )

    patterns = _pattern_signals(group)
    result = pd.concat([result, patterns], axis=1)
    return result


def _benchmark_overlay(benchmark_frame: pd.DataFrame) -> pd.DataFrame:
    required = {"session_date", "close"}
    missing = sorted(required.difference(benchmark_frame.columns))
    if missing:
        raise SuccessorPractitionerFeatureError(
            "benchmark frame missing columns: " + ", ".join(missing)
        )
    benchmark = benchmark_frame[["session_date", "close"]].copy()
    benchmark["session_date"] = pd.to_datetime(
        benchmark["session_date"], errors="raise"
    ).dt.date
    benchmark["close"] = pd.to_numeric(benchmark["close"], errors="coerce").astype("float64")
    if benchmark["session_date"].duplicated().any():
        raise SuccessorPractitionerFeatureError("benchmark session_date must be unique")
    if benchmark["close"].isna().any() or (benchmark["close"] <= 0.0).any():
        raise SuccessorPractitionerFeatureError("benchmark closes must be finite and positive")
    benchmark = benchmark.sort_values("session_date", kind="stable").reset_index(drop=True)
    benchmark["spy_return_20"] = benchmark["close"].pct_change(
        RELATIVE_STRENGTH_SHORT_SESSIONS, fill_method=None
    )
    benchmark["spy_return_63"] = benchmark["close"].pct_change(
        RELATIVE_STRENGTH_MEDIUM_SESSIONS, fill_method=None
    )
    benchmark["spy_sma_50"] = sma(benchmark["close"], 50)
    log_return = np.log(benchmark["close"] / benchmark["close"].shift(1))
    benchmark["spy_realized_volatility_20"] = log_return.rolling(
        20, min_periods=20
    ).std(ddof=0)
    benchmark["spy_prior_median_realized_volatility_252"] = (
        benchmark["spy_realized_volatility_20"]
        .shift(1)
        .rolling(MARKET_VOLATILITY_LOOKBACK, min_periods=MARKET_VOLATILITY_LOOKBACK)
        .median()
    )
    return benchmark.rename(columns={"close": "spy_close"})


def compute_successor_daily_features(
    frame: pd.DataFrame,
    *,
    benchmark_frame: pd.DataFrame,
) -> pd.DataFrame:
    """Compute all shared successor daily features once, before any policy evaluates."""

    base = compute_reference_daily_features(frame)
    parts = [
        _daily_overlay(group)
        for _, group in base.groupby("instrument_id", sort=False, observed=True)
    ]
    overlay = pd.concat(parts).sort_index() if parts else pd.DataFrame(index=base.index)
    result = pd.concat([base, overlay], axis=1)

    benchmark = _benchmark_overlay(benchmark_frame)
    result = result.merge(benchmark, on="session_date", how="left", validate="many_to_one", sort=False)
    result["ticker_return_20"] = result.groupby(
        "instrument_id", sort=False, observed=True
    )["close"].pct_change(RELATIVE_STRENGTH_SHORT_SESSIONS, fill_method=None)
    result["ticker_return_63"] = result.groupby(
        "instrument_id", sort=False, observed=True
    )["close"].pct_change(RELATIVE_STRENGTH_MEDIUM_SESSIONS, fill_method=None)
    result["relative_strength_vs_spy_20"] = (
        result["ticker_return_20"] - result["spy_return_20"]
    )
    result["relative_strength_vs_spy_63"] = (
        result["ticker_return_63"] - result["spy_return_63"]
    )

    short_rs = result["relative_strength_vs_spy_20"]
    medium_rs = result["relative_strength_vs_spy_63"]
    prior_short = result.groupby("instrument_id", sort=False, observed=True)[
        "relative_strength_vs_spy_20"
    ].shift(1)
    rs_valid = (
        short_rs.notna()
        & medium_rs.notna()
        & prior_short.notna()
        & result["ema_50"].notna()
    )
    result["relative_strength_momentum_long"] = _binary(
        (prior_short <= 0.0)
        & (short_rs > 0.0)
        & (medium_rs > 0.0)
        & (result["close"] > result["ema_50"]),
        rs_valid,
    )
    result["relative_strength_momentum_short"] = _binary(
        (prior_short >= 0.0)
        & (short_rs < 0.0)
        & (medium_rs < 0.0)
        & (result["close"] < result["ema_50"]),
        rs_valid,
    )

    result.attrs["successor_practitioner_feature_contract_version"] = (
        SUCCESSOR_PRACTITIONER_FEATURE_CONTRACT_VERSION
    )
    result.attrs["successor_practitioner_feature_fingerprint"] = (
        successor_practitioner_feature_fingerprint()
    )
    return result


def successor_common_context_from_row(row: Mapping[str, object]) -> dict[str, object]:
    def finite(name: str) -> float | None:
        value = row.get(name)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if math.isfinite(numeric) else None

    close = finite("close")
    ema20 = finite("ema_20")
    ema50 = finite("ema_50")
    atr = finite("atr_14")
    spy_close = finite("spy_close")
    spy_sma50 = finite("spy_sma_50")
    spy_rv = finite("spy_realized_volatility_20")
    spy_rv_median = finite("spy_prior_median_realized_volatility_252")
    prior_dollar_volume = finite("prior_median_dollar_volume_20")

    if spy_close is None or spy_sma50 is None:
        spy_direction = "UNAVAILABLE"
    else:
        spy_direction = "BULL" if spy_close > spy_sma50 else "BEAR"

    if spy_rv is None or spy_rv_median is None:
        volatility_state = "UNAVAILABLE"
    else:
        volatility_state = "HIGH" if spy_rv > spy_rv_median else "NORMAL"

    if close is None or ema20 is None or ema50 is None:
        ticker_trend = "UNAVAILABLE"
    elif close > ema20 > ema50:
        ticker_trend = "BULL"
    elif close < ema20 < ema50:
        ticker_trend = "BEAR"
    else:
        ticker_trend = "MIXED"

    if close is None:
        price_band = "UNAVAILABLE"
    elif close < 5.0:
        price_band = "LT_5"
    elif close < 10.0:
        price_band = "5_10"
    elif close < 25.0:
        price_band = "10_25"
    elif close < 50.0:
        price_band = "25_50"
    elif close < 100.0:
        price_band = "50_100"
    else:
        price_band = "GE_100"

    if prior_dollar_volume is None:
        liquidity_quality = "UNAVAILABLE"
    elif prior_dollar_volume >= 50_000_000.0:
        liquidity_quality = "HIGH"
    elif prior_dollar_volume >= 20_000_000.0:
        liquidity_quality = "MEDIUM"
    elif prior_dollar_volume >= 5_000_000.0:
        liquidity_quality = "BASE"
    else:
        liquidity_quality = "INELIGIBLE"

    extension = None
    if close is not None and ema20 is not None and atr is not None and atr > 0.0:
        extension = (close - ema20) / atr

    return {
        "market_direction_alignment": spy_direction,
        "market_volatility_state": volatility_state,
        "ticker_relative_strength_vs_spy_short_horizon": finite(
            "relative_strength_vs_spy_20"
        ),
        "ticker_relative_strength_vs_spy_medium_horizon": finite(
            "relative_strength_vs_spy_63"
        ),
        "higher_timeframe_ticker_trend": ticker_trend,
        "atr_normalized_trend_maturity_extension": extension,
        "opening_same_time_volume_participation": "UNAVAILABLE_DAILY",
        "premarket_volume_participation": "UNAVAILABLE_DAILY",
        "prior_dollar_volume_liquidity": prior_dollar_volume,
        "overnight_gap": finite("overnight_gap"),
        "price_band": price_band,
        "signal_time": "DAILY_CLOSE",
        "realized_volatility": finite("realized_volatility_20"),
        "execution_liquidity_quality": liquidity_quality,
    }
