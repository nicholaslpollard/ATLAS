from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from packages.backtesting.phase27_policy import (
    PHASE27_BASELINE_SCORE_FIELD,
    PHASE27_PREDICTOR_FIELDS,
)
from packages.backtesting.phase27_population import (
    Phase27PopulationError,
    cross_sectional_model_frame,
    transformed_feature_names,
)


def _frame(*, rows_per_direction: int = 5, development: bool = True) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    counter = 0
    for direction in ("bullish", "bearish"):
        for index in range(rows_per_direction):
            record: dict[str, object] = {
                "as_of_date": date(2025, 1, 2),
                "instrument_id": f"ins-{counter:03d}",
                "ticker": f"T{counter:03d}",
                "direction": direction,
                "market_state": "NORMAL",
                "effective_ticker_state": "NORMAL",
                PHASE27_BASELINE_SCORE_FIELD: float(index + 1),
            }
            for feature_index, field in enumerate(PHASE27_PREDICTOR_FIELDS):
                record[field] = float((feature_index + 1) * 10 + index)
            if development:
                raw = 0.01 * (index + 1)
                record["directional_return"] = raw
            records.append(record)
            counter += 1
    return pd.DataFrame.from_records(records)


def test_cross_sectional_transform_is_direction_local_and_bounded() -> None:
    result = cross_sectional_model_frame(_frame(), development=True)
    transformed = list(transformed_feature_names())
    assert len(result) == 10
    assert len(transformed) == 29
    assert np.isfinite(result[transformed].to_numpy(dtype=float)).all()
    assert result[transformed].to_numpy(dtype=float).min() >= -1.0
    assert result[transformed].to_numpy(dtype=float).max() <= 1.0
    first = transformed[0]
    for _, group in result.groupby("direction", sort=True):
        assert group[first].min() == pytest.approx(-0.6)
        assert group[first].max() == pytest.approx(1.0)
        assert group["relative_directional_return"].median() == pytest.approx(0.0)


def test_population_excludes_direction_sessions_below_frozen_minimum() -> None:
    with pytest.raises(Phase27PopulationError, match="population is empty"):
        cross_sectional_model_frame(_frame(rows_per_direction=4), development=True)


def test_population_requires_complete_frozen_predictors() -> None:
    frame = _frame()
    frame.loc[0, PHASE27_PREDICTOR_FIELDS[0]] = np.nan
    result = cross_sectional_model_frame(frame, development=True)
    # The missing bullish predictor drops that direction below the frozen five-name
    # same-session minimum, so the entire bullish side is excluded. The bearish side
    # remains valid with five rows.
    assert len(result) == 5
    assert set(result["direction"].astype(str)) == {"bearish"}
    assert "ins-000" not in set(result["instrument_id"].astype(str))


def test_protected_population_does_not_create_outcomes() -> None:
    result = cross_sectional_model_frame(_frame(development=False), development=False)
    assert "directional_return" not in result.columns
    assert "relative_directional_return" not in result.columns
