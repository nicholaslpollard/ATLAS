from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from packages.features.rolling import as_float_series, rolling_zscore, sma


def on_balance_volume(
    close: pd.Series | Iterable[float | int | None],
    volume: pd.Series | Iterable[float | int | None],
) -> pd.Series:
    """On-balance volume with an explicit zero seed.

    The first valid bar establishes OBV=0. Later volume is added/subtracted according
    to the sign of the close change. Missing close/volume resets the running state so
    ATLAS does not bridge data gaps invisibly.
    """

    close_s = as_float_series(close, name="close")
    volume_s = as_float_series(volume, name="volume")
    if not close_s.index.equals(volume_s.index):
        raise ValueError("close and volume must share the same index")

    result = np.full(len(close_s), np.nan, dtype="float64")
    previous_close: float | None = None
    running = 0.0
    for position, (close_value, volume_value) in enumerate(zip(close_s.to_numpy(), volume_s.to_numpy(), strict=True)):
        if np.isnan(close_value) or np.isnan(volume_value):
            previous_close = None
            running = 0.0
            continue
        if previous_close is None:
            running = 0.0
        elif close_value > previous_close:
            running += float(volume_value)
        elif close_value < previous_close:
            running -= float(volume_value)
        result[position] = running
        previous_close = float(close_value)
    return pd.Series(result, index=close_s.index, dtype="float64", name="obv")


def relative_volume(
    volume: pd.Series | Iterable[float | int | None],
    period: int = 20,
) -> pd.Series:
    series = as_float_series(volume, name="volume")
    average = sma(series, period)
    return (series / average).where(average > 0.0).rename(f"relative_volume_{period}")


def volume_zscore(
    volume: pd.Series | Iterable[float | int | None],
    period: int = 20,
) -> pd.Series:
    return rolling_zscore(volume, period, ddof=0).rename(f"volume_zscore_{period}")


def dollar_volume(
    close: pd.Series | Iterable[float | int | None],
    volume: pd.Series | Iterable[float | int | None],
) -> pd.Series:
    close_s = as_float_series(close, name="close")
    volume_s = as_float_series(volume, name="volume")
    if not close_s.index.equals(volume_s.index):
        raise ValueError("close and volume must share the same index")
    return (close_s * volume_s).rename("dollar_volume")


def relative_dollar_volume(
    close: pd.Series | Iterable[float | int | None],
    volume: pd.Series | Iterable[float | int | None],
    period: int = 20,
) -> pd.Series:
    dollars = dollar_volume(close, volume)
    average = sma(dollars, period)
    return (dollars / average).where(average > 0.0).rename(f"relative_dollar_volume_{period}")
