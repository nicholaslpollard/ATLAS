from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from packages.features.rolling import as_float_series, ema, wilder_average


def simple_return(
    close: pd.Series | Iterable[float | int | None],
    periods: int = 1,
) -> pd.Series:
    if isinstance(periods, bool) or not isinstance(periods, int) or periods < 1:
        raise ValueError("periods must be a positive integer")
    series = as_float_series(close, name="close")
    return series.pct_change(periods=periods, fill_method=None).rename(f"return_{periods}")


def log_return(
    close: pd.Series | Iterable[float | int | None],
    periods: int = 1,
) -> pd.Series:
    if isinstance(periods, bool) or not isinstance(periods, int) or periods < 1:
        raise ValueError("periods must be a positive integer")
    series = as_float_series(close, name="close")
    shifted = series.shift(periods)
    result = np.log(series / shifted)
    return result.where((series > 0.0) & (shifted > 0.0)).rename(f"log_return_{periods}")


def rsi_wilder(
    close: pd.Series | Iterable[float | int | None],
    period: int = 14,
) -> pd.Series:
    """Relative Strength Index using Wilder's original recursive smoothing.

    ``period`` price changes require ``period + 1`` closes, so RSI14 first becomes
    available on the 15th contiguous close. A flat window yields RSI=50, an all-gain
    window RSI=100, and an all-loss window RSI=0.
    """

    if isinstance(period, bool) or not isinstance(period, int) or period < 1:
        raise ValueError("period must be a positive integer")
    series = as_float_series(close, name="close")
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = wilder_average(gain, period)
    avg_loss = wilder_average(loss, period)

    rsi = pd.Series(np.nan, index=series.index, dtype="float64", name=f"rsi_{period}")
    valid = avg_gain.notna() & avg_loss.notna()
    both_zero = valid & (avg_gain == 0.0) & (avg_loss == 0.0)
    no_loss = valid & (avg_gain > 0.0) & (avg_loss == 0.0)
    no_gain = valid & (avg_gain == 0.0) & (avg_loss > 0.0)
    normal = valid & (avg_gain > 0.0) & (avg_loss > 0.0)

    rsi.loc[both_zero] = 50.0
    rsi.loc[no_loss] = 100.0
    rsi.loc[no_gain] = 0.0
    rs = avg_gain.loc[normal] / avg_loss.loc[normal]
    rsi.loc[normal] = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def macd(
    close: pd.Series | Iterable[float | int | None],
    *,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD using ATLAS SMA-seeded EMAs for all recursive legs."""

    if fast < 1 or slow < 1 or signal < 1:
        raise ValueError("MACD periods must be positive integers")
    if fast >= slow:
        raise ValueError("fast period must be smaller than slow period")
    series = as_float_series(close, name="close")
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    line = (fast_ema - slow_ema).rename(f"macd_{fast}_{slow}")
    signal_line = ema(line, signal).rename(f"macd_signal_{fast}_{slow}_{signal}")
    histogram = (line - signal_line).rename(f"macd_hist_{fast}_{slow}_{signal}")
    return pd.concat([line, signal_line, histogram], axis=1)
