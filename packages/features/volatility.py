from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from packages.features.momentum import log_return
from packages.features.rolling import as_float_series, rolling_std, sma, wilder_average


def true_range(
    high: pd.Series | Iterable[float | int | None],
    low: pd.Series | Iterable[float | int | None],
    close: pd.Series | Iterable[float | int | None],
) -> pd.Series:
    """Wilder true range, using high-low when no previous close is available."""

    high_s = as_float_series(high, name="high")
    low_s = as_float_series(low, name="low")
    close_s = as_float_series(close, name="close")
    if not (high_s.index.equals(low_s.index) and high_s.index.equals(close_s.index)):
        raise ValueError("high, low, and close must share the same index")

    previous_close = close_s.shift(1)
    components = pd.concat(
        [
            (high_s - low_s).rename("intrabar"),
            (high_s - previous_close).abs().rename("high_gap"),
            (low_s - previous_close).abs().rename("low_gap"),
        ],
        axis=1,
    )
    return components.max(axis=1, skipna=True).rename("true_range")


def atr_wilder(
    high: pd.Series | Iterable[float | int | None],
    low: pd.Series | Iterable[float | int | None],
    close: pd.Series | Iterable[float | int | None],
    period: int = 14,
) -> pd.Series:
    """Average True Range using Wilder recursive smoothing."""

    return wilder_average(true_range(high, low, close), period).rename(f"atr_{period}")


def normalized_atr(
    high: pd.Series | Iterable[float | int | None],
    low: pd.Series | Iterable[float | int | None],
    close: pd.Series | Iterable[float | int | None],
    period: int = 14,
) -> pd.Series:
    close_s = as_float_series(close, name="close")
    atr = atr_wilder(high, low, close_s, period)
    result = atr / close_s
    return result.where(close_s > 0.0).rename(f"natr_{period}")


def bollinger_bands(
    close: pd.Series | Iterable[float | int | None],
    *,
    period: int = 20,
    standard_deviations: float = 2.0,
) -> pd.DataFrame:
    """Population-standard-deviation Bollinger Bands.

    ATLAS explicitly uses ``ddof=0`` so values do not depend on pandas' sample-std
    default. Width is normalized by the middle band; position is 0 at the lower band
    and 1 at the upper band and may exceed that range during breakouts.
    """

    if standard_deviations <= 0:
        raise ValueError("standard_deviations must be greater than zero")
    series = as_float_series(close, name="close")
    middle = sma(series, period).rename(f"bb_mid_{period}")
    std = rolling_std(series, period, ddof=0)
    upper = (middle + standard_deviations * std).rename(f"bb_upper_{period}")
    lower = (middle - standard_deviations * std).rename(f"bb_lower_{period}")
    width = ((upper - lower) / middle).where(middle != 0.0).rename(f"bb_width_{period}")
    denominator = upper - lower
    position = ((series - lower) / denominator).where(denominator != 0.0, 0.5).rename(
        f"bb_position_{period}"
    )
    return pd.concat([middle, upper, lower, width, position], axis=1)


def realized_volatility(
    close: pd.Series | Iterable[float | int | None],
    *,
    period: int = 20,
    annualization_factor: float | None = None,
) -> pd.Series:
    """Rolling population standard deviation of one-bar log returns.

    No annualization is assumed by default because the correct scale depends on the
    bar timeframe. Callers may supply a positive square-root annualization base (for
    example 252 for daily bars).
    """

    returns = log_return(close, 1)
    result = rolling_std(returns, period, ddof=0)
    if annualization_factor is not None:
        if annualization_factor <= 0:
            raise ValueError("annualization_factor must be greater than zero")
        result = result * np.sqrt(float(annualization_factor))
    return result.rename(f"realized_volatility_{period}")
