from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd

from packages.portfolio.phase13_policy import (
    PHASE13_CORRELATION_LOOKBACK_SESSIONS,
    PHASE13_CORRELATION_MIN_OVERLAP_SESSIONS,
)


class Phase13CorrelationError(ValueError):
    pass


def max_abs_return_correlation(
    frame: pd.DataFrame,
    *,
    candidate_ticker: str,
    other_tickers: Iterable[str],
) -> float | None:
    """Return the maximum absolute daily-return correlation to existing positions.

    The caller supplies only point-in-time canonical history available at the case date.
    If any requested comparison lacks the preregistered minimum overlapping returns,
    correlation evidence is unavailable rather than extrapolated or guessed.
    """

    required = {"symbol", "timestamp_utc", "close"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise Phase13CorrelationError("correlation input missing columns: " + ", ".join(missing))
    candidate = str(candidate_ticker).strip()
    peers = tuple(dict.fromkeys(str(item).strip() for item in other_tickers if str(item).strip()))
    if not candidate:
        raise Phase13CorrelationError("candidate ticker cannot be blank")
    if not peers:
        return 0.0

    work = frame.loc[frame["symbol"].isin((candidate, *peers)), ["symbol", "timestamp_utc", "close"]].copy()
    work["timestamp_utc"] = pd.to_datetime(work["timestamp_utc"], utc=True, errors="raise")
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    if work["close"].isna().any() or (work["close"] <= 0.0).any():
        raise Phase13CorrelationError("correlation input contains invalid close values")
    if work.duplicated(["symbol", "timestamp_utc"]).any():
        raise Phase13CorrelationError("correlation input contains duplicate symbol/timestamp keys")

    work = work.sort_values(["symbol", "timestamp_utc"], kind="stable")
    retained = (
        work.groupby("symbol", sort=False, observed=True, group_keys=False)
        .tail(PHASE13_CORRELATION_LOOKBACK_SESSIONS + 1)
    )
    prices = retained.pivot(index="timestamp_utc", columns="symbol", values="close").sort_index()
    if candidate not in prices.columns or any(peer not in prices.columns for peer in peers):
        return None
    returns = prices.pct_change(fill_method=None)

    values: list[float] = []
    for peer in peers:
        pair = returns[[candidate, peer]].dropna()
        if len(pair) < PHASE13_CORRELATION_MIN_OVERLAP_SESSIONS:
            return None
        correlation = float(pair[candidate].corr(pair[peer]))
        if not math.isfinite(correlation):
            return None
        values.append(abs(correlation))
    return max(values) if values else 0.0
