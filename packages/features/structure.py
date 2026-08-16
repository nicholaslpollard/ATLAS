from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from packages.features.rolling import as_float_series, rolling_max, rolling_min


def rolling_range_position(
    close: pd.Series | Iterable[float | int | None],
    high: pd.Series | Iterable[float | int | None],
    low: pd.Series | Iterable[float | int | None],
    period: int = 20,
) -> pd.Series:
    """Close position inside the inclusive rolling high/low range."""

    close_s = as_float_series(close, name="close")
    high_s = as_float_series(high, name="high")
    low_s = as_float_series(low, name="low")
    highest = rolling_max(high_s, period)
    lowest = rolling_min(low_s, period)
    width = highest - lowest
    return ((close_s - lowest) / width).where(width != 0.0, 0.5).rename(
        f"range_position_{period}"
    )


def prior_rolling_high(
    high: pd.Series | Iterable[float | int | None],
    period: int = 20,
) -> pd.Series:
    """Highest high from the *previous* full window, excluding the current bar."""

    series = as_float_series(high, name="high")
    return rolling_max(series.shift(1), period).rename(f"prior_high_{period}")


def prior_rolling_low(
    low: pd.Series | Iterable[float | int | None],
    period: int = 20,
) -> pd.Series:
    """Lowest low from the *previous* full window, excluding the current bar."""

    series = as_float_series(low, name="low")
    return rolling_min(series.shift(1), period).rename(f"prior_low_{period}")


def breakout_distance(
    close: pd.Series | Iterable[float | int | None],
    high: pd.Series | Iterable[float | int | None],
    period: int = 20,
) -> pd.Series:
    """Fractional close distance above/below the prior-window high."""

    close_s = as_float_series(close, name="close")
    level = prior_rolling_high(high, period)
    return (close_s / level - 1.0).where(level > 0.0).rename(f"breakout_distance_{period}")


def breakdown_distance(
    close: pd.Series | Iterable[float | int | None],
    low: pd.Series | Iterable[float | int | None],
    period: int = 20,
) -> pd.Series:
    """Fractional close distance above/below the prior-window low."""

    close_s = as_float_series(close, name="close")
    level = prior_rolling_low(low, period)
    return (close_s / level - 1.0).where(level > 0.0).rename(f"breakdown_distance_{period}")


def drawdown_from_rolling_high(
    close: pd.Series | Iterable[float | int | None],
    period: int = 20,
) -> pd.Series:
    series = as_float_series(close, name="close")
    high = rolling_max(series, period)
    return (series / high - 1.0).where(high > 0.0).rename(f"drawdown_{period}")
