from __future__ import annotations

import numpy as np
import pandas as pd


SETUP_SCORE_POLICY_VERSION = "setup-score-v1-volatility-normalized-multifamily"

SETUP_FAMILIES = (
    "trend",
    "momentum",
    "breakout",
    "pullback",
    "reversal",
    "mean_reversion",
    "unusual_volume",
    "volatility_expansion",
    "breakdown",
)

REQUIRED_SCORE_COLUMNS = (
    "return_1",
    "rsi_14",
    "true_range",
    "atr_14",
    "natr_14",
    "bb_position_20",
    "relative_volume_20",
    "relative_dollar_volume_20",
    "volume_zscore_20",
    "range_position_20",
    "breakout_distance_20",
    "breakdown_distance_20",
    "ema_20_slope_1",
    "price_distance_ema_20",
    "directional_efficiency_20",
)


def _numeric(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64", name=name)
    return pd.to_numeric(frame[name], errors="coerce").astype("float64")


def _clip01(values: pd.Series) -> pd.Series:
    return values.clip(lower=0.0, upper=1.0)


def _mean(*values: pd.Series) -> pd.Series:
    return pd.concat(values, axis=1).mean(axis=1, skipna=True)


def _positive(values: pd.Series) -> pd.Series:
    return _clip01(values)


def score_timeframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Return normalized setup evidence for one timeframe.

    All outputs are in [0, 1]. Price/return distances are normalized by NATR so the
    same formulas can be used across low- and high-volatility instruments. Missing
    feature warmups remain NaN and are ignored by cross-timeframe aggregation.
    """

    result = pd.DataFrame(index=frame.index)
    if frame.empty:
        return result

    ret = _numeric(frame, "return_1")
    rsi = _numeric(frame, "rsi_14")
    true_range = _numeric(frame, "true_range")
    atr = _numeric(frame, "atr_14")
    natr = _numeric(frame, "natr_14")
    bb_position = _numeric(frame, "bb_position_20")
    relative_volume = _numeric(frame, "relative_volume_20")
    relative_dollar_volume = _numeric(frame, "relative_dollar_volume_20")
    volume_zscore = _numeric(frame, "volume_zscore_20")
    range_position = _numeric(frame, "range_position_20")
    breakout_distance = _numeric(frame, "breakout_distance_20")
    breakdown_distance = _numeric(frame, "breakdown_distance_20")
    ema_slope = _numeric(frame, "ema_20_slope_1")
    price_distance = _numeric(frame, "price_distance_ema_20")
    efficiency = _numeric(frame, "directional_efficiency_20").clip(0.0, 1.0)

    scale = natr.where(natr.abs() > 1e-9)
    return_ratio = ret / scale
    distance_ratio = price_distance / scale
    slope_ratio = ema_slope / scale
    breakout_ratio = breakout_distance / scale
    breakdown_ratio = breakdown_distance / scale

    return_bull = _positive(return_ratio / 2.0)
    return_bear = _positive(-return_ratio / 2.0)
    distance_bull = _positive(distance_ratio / 2.0)
    distance_bear = _positive(-distance_ratio / 2.0)
    slope_bull = _positive(slope_ratio / 0.50)
    slope_bear = _positive(-slope_ratio / 0.50)

    rsi_bull = _positive((rsi - 50.0) / 20.0)
    rsi_bear = _positive((50.0 - rsi) / 20.0)
    oversold = _positive((40.0 - rsi) / 20.0)
    overbought = _positive((rsi - 60.0) / 20.0)

    range_high = _positive((range_position - 0.55) / 0.45)
    range_low = _positive((0.45 - range_position) / 0.45)
    bb_high = _positive((bb_position - 0.75) / 0.50)
    bb_low = _positive((0.25 - bb_position) / 0.50)

    relative_volume_component = _positive((relative_volume - 0.80) / 2.20)
    relative_dollar_component = _positive((relative_dollar_volume - 0.80) / 2.20)
    zscore_component = _positive(volume_zscore / 3.0)
    unusual_volume = _mean(
        relative_volume_component,
        relative_dollar_component,
        zscore_component,
    )

    range_expansion_ratio = true_range / atr.where(atr.abs() > 1e-12)
    volatility_expansion = _positive((range_expansion_ratio - 1.0) / 1.50)

    directional_bull = efficiency * _mean(slope_bull, distance_bull)
    directional_bear = efficiency * _mean(slope_bear, distance_bear)
    trend_bull = _mean(slope_bull, distance_bull, directional_bull, rsi_bull)
    trend_bear = _mean(slope_bear, distance_bear, directional_bear, rsi_bear)

    momentum_bull = _mean(return_bull, rsi_bull, range_high)
    momentum_bear = _mean(return_bear, rsi_bear, range_low)

    breakout_bull = _mean(
        _positive(breakout_ratio / 1.50),
        range_high,
        unusual_volume,
        volatility_expansion,
    )
    breakdown_bear = _mean(
        _positive(-breakdown_ratio / 1.50),
        range_low,
        unusual_volume,
        volatility_expansion,
    )

    pullback_bull_location = _positive(1.0 - (distance_ratio + 0.40).abs() / 1.20)
    pullback_bear_location = _positive(1.0 - (distance_ratio - 0.40).abs() / 1.20)
    pullback_bull_rsi = _positive(1.0 - (rsi - 45.0).abs() / 15.0)
    pullback_bear_rsi = _positive(1.0 - (rsi - 55.0).abs() / 15.0)
    pullback_bull = trend_bull * _mean(pullback_bull_location, pullback_bull_rsi)
    pullback_bear = trend_bear * _mean(pullback_bear_location, pullback_bear_rsi)

    mean_reversion_bull = _mean(oversold, bb_low, range_low, distance_bear)
    mean_reversion_bear = _mean(overbought, bb_high, range_high, distance_bull)
    reversal_bull = 0.65 * mean_reversion_bull + 0.35 * return_bull
    reversal_bear = 0.65 * mean_reversion_bear + 0.35 * return_bear

    coverage = pd.concat(
        [
            ret,
            rsi,
            natr,
            bb_position,
            range_position,
            ema_slope,
            price_distance,
            breakout_distance,
            breakdown_distance,
        ],
        axis=1,
    ).notna().any(axis=1)

    outputs = {
        "trend_bull": trend_bull,
        "trend_bear": trend_bear,
        "momentum_bull": momentum_bull,
        "momentum_bear": momentum_bear,
        "breakout_bull": breakout_bull,
        "breakdown_bear": breakdown_bear,
        "pullback_bull": pullback_bull,
        "pullback_bear": pullback_bear,
        "reversal_bull": reversal_bull,
        "reversal_bear": reversal_bear,
        "mean_reversion_bull": mean_reversion_bull,
        "mean_reversion_bear": mean_reversion_bear,
        "unusual_volume": unusual_volume,
        "volatility_expansion": volatility_expansion,
    }
    for name, values in outputs.items():
        result[name] = _clip01(values).where(coverage)
    result["score_input_available"] = coverage
    return result
