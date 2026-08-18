from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from packages.features.rolling import as_float_series


def gap_return(
    open_price: pd.Series | Iterable[float | int | None],
    previous_close: pd.Series | Iterable[float | int | None],
) -> pd.Series:
    """Fractional open-vs-previous-close gap; unavailable for invalid denominators."""

    open_s = as_float_series(open_price, name="open")
    previous_s = as_float_series(previous_close, name="previous_close")
    if not open_s.index.equals(previous_s.index):
        raise ValueError("open_price and previous_close must share the same index")
    return (open_s / previous_s - 1.0).where(previous_s > 0.0).rename("gap_return")


def gap_direction(gap: pd.Series | Iterable[float | int | None]) -> pd.Series:
    """Map a gap to -1/0/+1 while preserving missing values."""

    series = as_float_series(gap, name="gap_return")
    result = pd.Series(pd.NA, index=series.index, dtype="Int8", name="gap_direction")
    valid = series.notna()
    result.loc[valid & (series > 0.0)] = 1
    result.loc[valid & (series < 0.0)] = -1
    result.loc[valid & (series == 0.0)] = 0
    return result
