from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd


def as_float_series(values: pd.Series | Iterable[float | int | None], *, name: str | None = None) -> pd.Series:
    """Return a float64 Series while preserving an existing index.

    Feature math is intentionally performed in float64. Provider/canonical storage
    types may differ, but the calculation contract must not depend on integer dtype
    coercion or object-array behavior.
    """

    if isinstance(values, pd.Series):
        result = pd.to_numeric(values, errors="coerce").astype("float64")
        if name is not None:
            result = result.rename(name)
        return result
    return pd.Series(list(values), dtype="float64", name=name)


def _validate_period(period: int) -> int:
    if isinstance(period, bool) or not isinstance(period, int) or period < 1:
        raise ValueError("period must be a positive integer")
    return period


def sma(values: pd.Series | Iterable[float | int | None], period: int) -> pd.Series:
    """Simple moving average with explicit full-window warm-up semantics."""

    period = _validate_period(period)
    series = as_float_series(values)
    return series.rolling(window=period, min_periods=period).mean()


def rolling_sum(values: pd.Series | Iterable[float | int | None], period: int) -> pd.Series:
    period = _validate_period(period)
    series = as_float_series(values)
    return series.rolling(window=period, min_periods=period).sum()


def rolling_min(values: pd.Series | Iterable[float | int | None], period: int) -> pd.Series:
    period = _validate_period(period)
    series = as_float_series(values)
    return series.rolling(window=period, min_periods=period).min()


def rolling_max(values: pd.Series | Iterable[float | int | None], period: int) -> pd.Series:
    period = _validate_period(period)
    series = as_float_series(values)
    return series.rolling(window=period, min_periods=period).max()


def rolling_std(
    values: pd.Series | Iterable[float | int | None],
    period: int,
    *,
    ddof: int = 0,
) -> pd.Series:
    """Rolling standard deviation with an explicit denominator convention."""

    period = _validate_period(period)
    if ddof < 0 or ddof >= period:
        raise ValueError("ddof must satisfy 0 <= ddof < period")
    series = as_float_series(values)
    return series.rolling(window=period, min_periods=period).std(ddof=ddof)


def ema(values: pd.Series | Iterable[float | int | None], period: int) -> pd.Series:
    """EMA seeded with the SMA of the first contiguous full period.

    Pandas ``ewm(adjust=False)`` seeds from the first observation, which is a valid
    convention but not the ATLAS convention. ATLAS uses an SMA seed so historical
    and incremental calculations share an explicit, reproducible initialization.
    Values before the seed are NaN.
    """

    period = _validate_period(period)
    series = as_float_series(values)
    data = series.to_numpy(dtype="float64", na_value=np.nan)
    output = np.full(len(data), np.nan, dtype="float64")
    alpha = 2.0 / (period + 1.0)

    valid_run: list[float] = []
    previous = math.nan
    seeded = False
    for idx, value in enumerate(data):
        if math.isnan(value):
            valid_run.clear()
            previous = math.nan
            seeded = False
            continue
        if not seeded:
            valid_run.append(float(value))
            if len(valid_run) < period:
                continue
            if len(valid_run) > period:
                valid_run.pop(0)
            previous = float(sum(valid_run) / period)
            output[idx] = previous
            seeded = True
            continue
        previous = previous + alpha * (float(value) - previous)
        output[idx] = previous

    return pd.Series(output, index=series.index, name=series.name, dtype="float64")


def wilder_average(values: pd.Series | Iterable[float | int | None], period: int) -> pd.Series:
    """Wilder recursive average using an arithmetic-mean seed.

    The first output is emitted only after ``period`` contiguous valid inputs. Later
    values follow ``(previous * (period - 1) + current) / period``. A missing input
    resets the recursion rather than silently bridging a data gap.
    """

    period = _validate_period(period)
    series = as_float_series(values)
    data = series.to_numpy(dtype="float64", na_value=np.nan)
    output = np.full(len(data), np.nan, dtype="float64")

    valid_run: list[float] = []
    previous = math.nan
    seeded = False
    for idx, value in enumerate(data):
        if math.isnan(value):
            valid_run.clear()
            previous = math.nan
            seeded = False
            continue
        if not seeded:
            valid_run.append(float(value))
            if len(valid_run) < period:
                continue
            if len(valid_run) > period:
                valid_run.pop(0)
            previous = float(sum(valid_run) / period)
            output[idx] = previous
            seeded = True
            continue
        previous = (previous * (period - 1) + float(value)) / period
        output[idx] = previous

    return pd.Series(output, index=series.index, name=series.name, dtype="float64")


def rolling_zscore(
    values: pd.Series | Iterable[float | int | None],
    period: int,
    *,
    ddof: int = 0,
) -> pd.Series:
    """Current-value z-score relative to its full rolling window."""

    series = as_float_series(values)
    mean = sma(series, period)
    std = rolling_std(series, period, ddof=ddof)
    result = (series - mean) / std
    return result.where(std != 0.0, 0.0)
