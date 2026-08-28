from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from packages.backtesting.phase30_policy import PHASE30_CANDIDATES
from packages.backtesting.phase30_validation import independent_signal_summary


def test_independent_reconstruction_ranks_tail_before_reaction_split() -> None:
    frame = pd.DataFrame(
        [
            {
                "as_of_date": date(2025, 1, 2),
                "instrument_id": "A",
                "ticker": "A",
                "direction": "bullish",
                "news_surprise": 10.0,
                "d1_return_1": -0.02,
                "directional_return": 0.10,
            },
            {
                "as_of_date": date(2025, 1, 2),
                "instrument_id": "B",
                "ticker": "B",
                "direction": "bullish",
                "news_surprise": 9.0,
                "d1_return_1": 0.02,
                "directional_return": 0.20,
            },
            {
                "as_of_date": date(2025, 1, 2),
                "instrument_id": "C",
                "ticker": "C",
                "direction": "bullish",
                "news_surprise": 8.0,
                "d1_return_1": 0.01,
                "directional_return": 0.30,
            },
            {
                "as_of_date": date(2025, 1, 2),
                "instrument_id": "D",
                "ticker": "D",
                "direction": "bullish",
                "news_surprise": 7.0,
                "d1_return_1": 0.01,
                "directional_return": 0.40,
            },
            {
                "as_of_date": date(2025, 1, 2),
                "instrument_id": "E",
                "ticker": "E",
                "direction": "bullish",
                "news_surprise": 6.0,
                "d1_return_1": 0.01,
                "directional_return": 0.50,
            },
        ]
    )
    continuation = PHASE30_CANDIDATES[0]
    reversal = PHASE30_CANDIDATES[2]

    continuation_summary = independent_signal_summary(frame, continuation)
    reversal_summary = independent_signal_summary(frame, reversal)

    assert continuation_summary["raw_rows"] == 0
    assert continuation_summary["signal_sessions"] == 0
    assert reversal_summary["raw_rows"] == 1
    assert reversal_summary["signal_sessions"] == 1
    assert reversal_summary["primary_mean_return"] == pytest.approx(0.099)
