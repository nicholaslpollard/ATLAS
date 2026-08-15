from __future__ import annotations

import math
from collections.abc import Iterable


def is_finite_number(value: float | int) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_ohlc(open_: float, high: float, low: float, close: float) -> None:
    values = (open_, high, low, close)
    if not all(is_finite_number(v) for v in values):
        raise ValueError("OHLC values must be finite numbers")
    if low > high:
        raise ValueError("low cannot exceed high")
    if high < max(open_, close, low):
        raise ValueError("high must be >= open, close, and low")
    if low > min(open_, close, high):
        raise ValueError("low must be <= open, close, and high")


def ensure_unique(values: Iterable[object]) -> bool:
    values = list(values)
    return len(values) == len(set(values))
