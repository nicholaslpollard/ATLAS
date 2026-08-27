from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from packages.backtesting.phase29_policy import PHASE29_CANDIDATES
from packages.backtesting.phase29_research import (
    candidate_predictions,
    chronological_boundaries,
    holm_bonferroni,
    select_fixed_tail,
    tranche_metrics,
)


def test_phase29_chronology_has_exact_three_session_purge() -> None:
    sessions = tuple(date(2025, 1, 2) + timedelta(days=index) for index in range(100))
    boundaries = chronological_boundaries(sessions)
    assert boundaries.selection_session_count == 75
    assert len(boundaries.purge_sessions) == 3
    assert boundaries.internal_session_count == 22
    assert boundaries.selection_end < boundaries.purge_sessions[0] < boundaries.internal_start


def test_phase29_fixed_tail_uses_exact_ceil_twenty_percent_and_lexical_ties() -> None:
    frame = pd.DataFrame(
        {
            "as_of_date": [date(2025, 1, 2)] * 11,
            "instrument_id": [f"i-{index:02d}" for index in range(11)],
            "phase29_score": [1.0] * 11,
        }
    )
    selected = select_fixed_tail(frame)
    assert list(selected["instrument_id"]) == ["i-00", "i-01", "i-02"]


def test_phase29_candidate_direction_and_orientation_are_frozen() -> None:
    frame = pd.DataFrame(
        {
            "direction": ["bullish", "bullish", "bearish"],
            "pca_residual_dislocation": [-2.0, 1.0, 3.0],
            "distance_pair_spread_z": [-1.0, 0.5, 2.0],
        }
    )
    long_candidate = next(
        candidate for candidate in PHASE29_CANDIDATES if candidate.candidate_id == "pca_residual_reversion_long"
    )
    short_candidate = next(
        candidate for candidate in PHASE29_CANDIDATES if candidate.candidate_id == "pca_residual_reversion_short"
    )
    long_rows = candidate_predictions(frame, long_candidate)
    short_rows = candidate_predictions(frame, short_candidate)
    assert list(long_rows["phase29_score"]) == [2.0, -1.0]
    assert list(short_rows["phase29_score"]) == [3.0]


def test_phase29_holm_is_global_across_four_hypotheses() -> None:
    result = holm_bonferroni({"a": 0.001, "b": 0.01, "c": 0.03, "d": 0.2})
    assert len(result) == 4
    assert result["a"]["threshold"] == 0.0125
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is True
    assert result["d"]["rejected_null"] is False


def test_phase29_positive_expectancy_does_not_require_majority_trade_win_rate() -> None:
    rows = []
    predictions = []
    start = date(2024, 1, 2)
    # Each session has four losing rows and one sufficiently large winner. This is
    # intentionally <50% trade win rate but positive session expectancy after costs.
    for index in range(30):
        session = start + timedelta(days=index)
        returns = [-0.002, -0.002, -0.002, -0.002, 0.020]
        for row_index, value in enumerate(returns):
            base = {
                "as_of_date": session,
                "instrument_id": f"i-{row_index}",
                "directional_return": value,
                "market_state": "m",
                "effective_ticker_state": "t",
                "fold": index % 3,
                "phase29_score": float(5 - row_index),
            }
            rows.append(base)
            predictions.append(base.copy())
    metrics = tranche_metrics(
        pd.DataFrame(rows),
        predictions=pd.DataFrame(predictions),
        confidence=0.80,
        fold_field="fold",
        label="phase29-test-positive-expectancy",
    )
    assert metrics.primary_trade_win_rate is not None
    assert metrics.primary_trade_win_rate < 0.50
    assert metrics.primary_mean_return is not None and metrics.primary_mean_return > 0
