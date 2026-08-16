from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from packages.features.rolling import as_float_series, ema, sma


def moving_average_slope(
    values: pd.Series | Iterable[float | int | None],
    *,
    period: int,
    lag: int = 1,
    kind: str = "ema",
) -> pd.Series:
    """Fractional moving-average slope over ``lag`` bars."""

    if isinstance(lag, bool) or not isinstance(lag, int) or lag < 1:
        raise ValueError("lag must be a positive integer")
    series = as_float_series(values)
    if kind == "ema":
        average = ema(series, period)
    elif kind == "sma":
        average = sma(series, period)
    else:
        raise ValueError("kind must be 'ema' or 'sma'")
    prior = average.shift(lag)
    return ((average / prior) - 1.0).where(prior != 0.0).rename(f"{kind}_{period}_slope_{lag}")


def price_distance_from_average(
    close: pd.Series | Iterable[float | int | None],
    *,
    period: int,
    kind: str = "ema",
) -> pd.Series:
    series = as_float_series(close, name="close")
    if kind == "ema":
        average = ema(series, period)
    elif kind == "sma":
        average = sma(series, period)
    else:
        raise ValueError("kind must be 'ema' or 'sma'")
    return (series / average - 1.0).where(average != 0.0).rename(
        f"price_distance_{kind}_{period}"
    )


def directional_efficiency(
    close: pd.Series | Iterable[float | int | None],
    period: int = 20,
) -> pd.Series:
    """Kaufman-style directional efficiency ratio in [0, 1]."""

    if isinstance(period, bool) or not isinstance(period, int) or period < 1:
        raise ValueError("period must be a positive integer")
    series = as_float_series(close, name="close")
    net = (series - series.shift(period)).abs()
    path = series.diff().abs().rolling(period, min_periods=period).sum()
    return (net / path).where(path != 0.0, 0.0).rename(f"directional_efficiency_{period}")
