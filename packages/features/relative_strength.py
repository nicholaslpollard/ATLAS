from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from packages.features.rolling import as_float_series


def relative_price_ratio(
    asset_close: pd.Series | Iterable[float | int | None],
    benchmark_close: pd.Series | Iterable[float | int | None],
) -> pd.Series:
    asset = as_float_series(asset_close, name="asset_close")
    benchmark = as_float_series(benchmark_close, name="benchmark_close")
    if not asset.index.equals(benchmark.index):
        raise ValueError("asset_close and benchmark_close must share the same index")
    return (asset / benchmark).where(benchmark > 0.0).rename("relative_price_ratio")


def relative_return(
    asset_close: pd.Series | Iterable[float | int | None],
    benchmark_close: pd.Series | Iterable[float | int | None],
    periods: int = 1,
) -> pd.Series:
    """Asset simple return minus benchmark simple return over identical bars."""

    if isinstance(periods, bool) or not isinstance(periods, int) or periods < 1:
        raise ValueError("periods must be a positive integer")
    asset = as_float_series(asset_close, name="asset_close")
    benchmark = as_float_series(benchmark_close, name="benchmark_close")
    if not asset.index.equals(benchmark.index):
        raise ValueError("asset_close and benchmark_close must share the same index")
    asset_return = asset.pct_change(periods=periods, fill_method=None)
    benchmark_return = benchmark.pct_change(periods=periods, fill_method=None)
    return (asset_return - benchmark_return).rename(f"relative_return_{periods}")


def relative_strength_change(
    asset_close: pd.Series | Iterable[float | int | None],
    benchmark_close: pd.Series | Iterable[float | int | None],
    periods: int = 20,
) -> pd.Series:
    """Fractional change in the asset/benchmark price ratio."""

    ratio = relative_price_ratio(asset_close, benchmark_close)
    return ratio.pct_change(periods=periods, fill_method=None).rename(
        f"relative_strength_change_{periods}"
    )
