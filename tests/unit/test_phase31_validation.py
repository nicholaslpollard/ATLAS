from __future__ import annotations

from datetime import date

import pandas as pd

from packages.backtesting.phase31_validation import (
    fails_mandatory_sample_gate,
    independent_sample_summary,
)


def test_phase31_independent_sample_summary_is_deterministic() -> None:
    frame = pd.DataFrame(
        [
            {"decision_session": date(2025, 1, 2), "ticker": "AAA"},
            {"decision_session": date(2025, 1, 2), "ticker": "BBB"},
            {"decision_session": date(2025, 1, 3), "ticker": "AAA"},
            {"decision_session": date(2025, 1, 6), "ticker": "CCC"},
        ]
    )
    summary = independent_sample_summary(frame)
    assert summary["raw_rows"] == 4
    assert summary["signal_sessions"] == 3
    assert summary["unique_tickers"] == 3
    assert summary["max_single_session_row_fraction"] == 0.5
    assert summary["max_single_ticker_row_fraction"] == 0.5


def test_phase31_small_sample_fails_frozen_mandatory_gate() -> None:
    summary = {
        "raw_rows": 1000,
        "signal_sessions": 300,
        "unique_tickers": 249,
        "max_single_session_row_fraction": 0.01,
        "max_single_ticker_row_fraction": 0.01,
    }
    assert fails_mandatory_sample_gate(summary) is True
