from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from packages.backtesting.phase28_policy import PHASE28_CANDIDATES
from packages.backtesting.phase28_population import (
    PHASE28_REQUIRED_CLOSES,
    PHASE28_REQUIRED_RESIDUAL_RETURNS,
    _crosses_history_split,
    _session_history_bounds,
)
from packages.backtesting.phase28_research import (
    candidate_predictions,
    chronological_boundaries,
    holm_bonferroni,
    select_fixed_tail,
)


def _candidate(candidate_id: str):
    return next(item for item in PHASE28_CANDIDATES if item.candidate_id == candidate_id)


def _sessions(count: int) -> tuple[date, ...]:
    start = date(2025, 1, 2)
    return tuple(start + timedelta(days=index) for index in range(count))


def test_phase28_history_window_is_exactly_63_closes_and_62_returns() -> None:
    sessions = _sessions(100)
    observation = sessions[80]
    bounds = _session_history_bounds(sessions, (observation,))
    assert PHASE28_REQUIRED_CLOSES == 63
    assert PHASE28_REQUIRED_RESIDUAL_RETURNS == 62
    assert bounds[observation] == sessions[18]
    assert 80 - 18 + 1 == 63


def test_phase28_history_split_censor_is_open_on_first_close_and_closed_on_observation() -> None:
    start = date(2025, 1, 2)
    end = date(2025, 4, 1)
    assert not _crosses_history_split((start,), history_start=start, observation_date=end)
    assert _crosses_history_split((date(2025, 2, 1),), history_start=start, observation_date=end)
    assert _crosses_history_split((end,), history_start=start, observation_date=end)


def test_phase28_chronological_split_has_exact_outer_purge() -> None:
    sessions = _sessions(100)
    boundaries = chronological_boundaries(sessions)
    assert boundaries.selection_session_count == 75
    assert boundaries.purge_sessions == sessions[75:78]
    assert boundaries.internal_session_count == 22
    assert boundaries.internal_start == sessions[78]


def test_phase28_fixed_tail_is_twenty_percent_with_deterministic_ties() -> None:
    rows = pd.DataFrame(
        {
            "as_of_date": [date(2026, 1, 2)] * 10,
            "instrument_id": [f"i-{index:02d}" for index in range(10)],
            "phase28_score": [1.0] * 10,
        }
    )
    selected = select_fixed_tail(rows)
    assert len(selected) == 2
    assert selected["instrument_id"].tolist() == ["i-00", "i-01"]


def test_phase28_candidate_orientation_is_fixed_by_direction() -> None:
    frame = pd.DataFrame(
        {
            "as_of_date": [date(2026, 1, 2), date(2026, 1, 2)],
            "instrument_id": ["long", "short"],
            "direction": ["bullish", "bearish"],
            "residual_momentum_20d": [0.02, 0.02],
        }
    )
    long_scored = candidate_predictions(frame, _candidate("residual_momentum_20d_long"))
    short_scored = candidate_predictions(frame, _candidate("residual_momentum_20d_short"))
    assert np.isclose(long_scored.iloc[0]["phase28_score"], 0.02)
    assert np.isclose(short_scored.iloc[0]["phase28_score"], -0.02)


def test_phase28_holm_is_global_step_down() -> None:
    values = {
        "a": 0.001,
        "b": 0.006,
        "c": 0.02,
        "d": 0.03,
        "e": 0.04,
        "f": 0.05,
        "g": 0.06,
        "h": 0.07,
    }
    result = holm_bonferroni(values)
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is True
    assert result["c"]["rejected_null"] is False
    assert all(
        result[key]["rejected_null"] is False
        for key in ("c", "d", "e", "f", "g", "h")
    )
