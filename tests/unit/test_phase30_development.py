from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from packages.backtesting.phase30_development import (
    candidate_views,
    chronological_boundaries,
    direction_tail_frame,
    holm_bonferroni,
)
from packages.backtesting.phase30_policy import PHASE30_CANDIDATES


def _candidate(candidate_id: str):
    return next(item for item in PHASE30_CANDIDATES if item.candidate_id == candidate_id)


def test_chronological_boundaries_use_frozen_75_percent_and_three_session_purge() -> None:
    start = date(2022, 1, 3)
    sessions = tuple(start + timedelta(days=index) for index in range(100))
    split = chronological_boundaries(sessions)
    assert split.selection_session_count == 75
    assert split.selection_start == sessions[0]
    assert split.selection_end == sessions[74]
    assert split.purge_sessions == sessions[75:78]
    assert split.internal_session_count == 22
    assert split.internal_start == sessions[78]
    assert split.internal_end == sessions[-1]


def test_fixed_direction_tail_is_ranked_before_reaction_sign_split() -> None:
    session = date(2025, 4, 1)
    frame = pd.DataFrame(
        {
            "as_of_date": [session] * 6,
            "instrument_id": [f"i{index}" for index in range(6)],
            "ticker": [f"T{index}" for index in range(6)],
            "direction": ["bullish"] * 6,
            "news_surprise": [6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
            "d1_return_1": [0.02, -0.02, 0.01, -0.01, 0.03, -0.03],
            "directional_return": [0.10, -0.10, 0.08, -0.08, 0.05, -0.05],
        }
    )

    continuation_predictions, continuation_signals = candidate_views(
        frame, _candidate("news_shock_aligned_continuation_long")
    )
    reversal_predictions, reversal_signals = candidate_views(
        frame, _candidate("news_shock_counterreaction_reversal_long")
    )

    # Six direction rows imply ceil(20% * 6) == 2 fixed tail members: i0 and i1.
    assert set(
        direction_tail_frame(
            frame, _candidate("news_shock_aligned_continuation_long")
        ).loc[lambda value: value["phase30_tail_selected"], "instrument_id"]
    ) == {"i0", "i1"}
    assert set(continuation_predictions["instrument_id"]) == {"i0", "i2", "i4"}
    assert list(continuation_signals["instrument_id"]) == ["i0"]
    assert set(reversal_predictions["instrument_id"]) == {"i1", "i3", "i5"}
    assert list(reversal_signals["instrument_id"]) == ["i1"]


def test_session_direction_with_fewer_than_five_rows_is_excluded() -> None:
    session = date(2025, 4, 2)
    frame = pd.DataFrame(
        {
            "as_of_date": [session] * 4,
            "instrument_id": ["a", "b", "c", "d"],
            "ticker": ["A", "B", "C", "D"],
            "direction": ["bearish"] * 4,
            "news_surprise": [4.0, 3.0, 2.0, 1.0],
            "d1_return_1": [-0.01, -0.02, -0.03, -0.04],
            "directional_return": [0.01, 0.02, 0.03, 0.04],
        }
    )
    ranked = direction_tail_frame(
        frame, _candidate("news_shock_aligned_continuation_short")
    )
    assert ranked.empty


def test_news_surprise_tie_break_uses_instrument_id_not_outcome() -> None:
    session = date(2025, 4, 3)
    frame = pd.DataFrame(
        {
            "as_of_date": [session] * 5,
            "instrument_id": ["E", "D", "C", "B", "A"],
            "ticker": ["E", "D", "C", "B", "A"],
            "direction": ["bullish"] * 5,
            "news_surprise": [2.0] * 5,
            "d1_return_1": [0.01] * 5,
            # A deliberately has the worst future outcome; it must still win the tie.
            "directional_return": [0.50, 0.40, 0.30, 0.20, -0.99],
        }
    )
    ranked = direction_tail_frame(
        frame, _candidate("news_shock_aligned_continuation_long")
    )
    selected = ranked.loc[ranked["phase30_tail_selected"], "instrument_id"].tolist()
    assert selected == ["A"]


def test_holm_bonferroni_is_global_and_step_down() -> None:
    result = holm_bonferroni(
        {"a": 0.005, "b": 0.010, "c": 0.030, "d": 0.040}, alpha=0.05
    )
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is True
    assert result["c"]["rejected_null"] is False
    assert result["d"]["rejected_null"] is False
