from __future__ import annotations

import pandas as pd

from packages.risk.correlation import max_abs_return_correlation


def test_correlation_returns_zero_without_existing_positions() -> None:
    frame = pd.DataFrame(columns=["symbol", "timestamp_utc", "close"])
    assert max_abs_return_correlation(frame, candidate_ticker="AAA", other_tickers=[]) == 0.0


def test_correlation_requires_preregistered_overlap_for_every_peer() -> None:
    dates = pd.date_range("2026-01-02", periods=40, freq="B", tz="UTC")
    rows: list[dict[str, object]] = []
    for index, ts in enumerate(dates):
        rows.append({"symbol": "AAA", "timestamp_utc": ts, "close": 100.0 + index})
        rows.append({"symbol": "BBB", "timestamp_utc": ts, "close": 200.0 + 2 * index})
        if index >= 30:
            rows.append({"symbol": "CCC", "timestamp_utc": ts, "close": 50.0 + index})
    frame = pd.DataFrame(rows)
    assert max_abs_return_correlation(frame, candidate_ticker="AAA", other_tickers=["BBB"]) is not None
    assert max_abs_return_correlation(frame, candidate_ticker="AAA", other_tickers=["BBB", "CCC"]) is None
