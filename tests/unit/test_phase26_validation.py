from __future__ import annotations

import pandas as pd

from packages.backtesting.phase26_policy import PHASE26_CANDIDATES
from packages.backtesting.phase26_signals import candidate_mask
from packages.backtesting.phase26_validation import independent_candidate_mask


def test_independent_validator_reproduces_candidate_mask_without_signal_engine_helper() -> None:
    candidate = next(
        item for item in PHASE26_CANDIDATES if item.candidate_id == "gap_short_fade"
    )
    frame = pd.DataFrame(
        {
            "direction": ["bearish", "bullish", "bearish", "bearish"],
            "gap_return": [0.03, 0.03, 0.01, 0.04],
            "intraday_return": [-0.03, -0.03, -0.03, -0.01],
            "d1_rsi_14": [65.0, 65.0, 65.0, 70.0],
            "h1_macd_hist_12_26_9": [-0.2, -0.2, -0.2, -0.2],
        }
    )
    expected = candidate_mask(frame, candidate)
    independently_recomputed = independent_candidate_mask(frame, candidate)
    assert independently_recomputed.tolist() == expected.tolist() == [True, False, False, False]


def test_independent_validator_fails_closed_on_nan_candidate_input() -> None:
    candidate = next(
        item for item in PHASE26_CANDIDATES if item.candidate_id == "gap_long_hold"
    )
    frame = pd.DataFrame(
        {
            "direction": ["bullish"],
            "gap_return": [None],
            "intraday_return": [0.03],
            "d1_range_position_20": [0.8],
            "d1_relative_volume_20": [1.5],
        }
    )
    assert independent_candidate_mask(frame, candidate).tolist() == [False]
