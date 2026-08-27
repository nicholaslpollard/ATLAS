from __future__ import annotations

import warnings
from datetime import date, timedelta

import numpy as np
import pandas as pd

from packages.backtesting.phase27_models import (
    _complexity_key,
    candidate_param_grid,
    expanding_walk_forward_folds,
    fit_learned_model,
    score_candidate,
    select_fixed_tail,
    tune_hyperparameters,
)
from packages.backtesting.phase27_policy import PHASE27_CANDIDATES
from packages.backtesting.phase27_population import transformed_feature_names


def _candidate(candidate_id: str):
    return next(item for item in PHASE27_CANDIDATES if item.candidate_id == candidate_id)


def _model_frame(session_count: int = 36, rows_per_session: int = 5) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    start = date(2024, 1, 2)
    features = transformed_feature_names()
    for session_index in range(session_count):
        session = start + timedelta(days=session_index)
        for row_index in range(rows_per_session):
            signal = (row_index - 2) / 2.0
            record: dict[str, object] = {
                "as_of_date": session,
                "instrument_id": f"ins-{session_index:03d}-{row_index:02d}",
                "direction": "bullish",
                "priority_score": float(row_index),
                "directional_return": 0.002 * signal + 0.00001 * session_index,
                "relative_directional_return": 0.002 * signal,
            }
            for feature_index, field in enumerate(features):
                record[field] = float(signal if feature_index == 0 else (feature_index % 5 - 2) / 2.0)
            records.append(record)
    return pd.DataFrame.from_records(records)


def test_phase27_candidate_grids_are_finite() -> None:
    assert len(candidate_param_grid(_candidate("priority_tail_long"))) == 1
    assert len(candidate_param_grid(_candidate("ridge_relative_long"))) == 4
    assert len(candidate_param_grid(_candidate("hgb_relative_long"))) == 16
    assert len(candidate_param_grid(_candidate("pairwise_rank_long"))) == 3


def test_regularization_tie_breaks_prefer_simpler_models() -> None:
    ridge = _candidate("ridge_relative_long")
    assert _complexity_key(ridge, {"alpha": 100.0}) < _complexity_key(ridge, {"alpha": 0.01})
    pairwise = _candidate("pairwise_rank_long")
    assert _complexity_key(pairwise, {"C": 0.1}) < _complexity_key(pairwise, {"C": 10.0})


def test_walk_forward_folds_are_chronological_with_purge() -> None:
    sessions = [date(2024, 1, 1) + timedelta(days=index) for index in range(40)]
    folds = expanding_walk_forward_folds(sessions, validation_folds=5)
    assert len(folds) == 5
    for fold in folds:
        assert max(fold.train_sessions) < min(fold.purge_sessions)
        assert max(fold.purge_sessions) < min(fold.validation_sessions)
        assert len(fold.purge_sessions) == 3


def test_ridge_tuning_and_scoring_are_deterministic() -> None:
    frame = _model_frame()
    candidate = _candidate("ridge_relative_long")
    params_a, trials_a = tune_hyperparameters(frame, candidate)
    params_b, trials_b = tune_hyperparameters(frame, candidate)
    assert params_a == params_b
    assert trials_a == trials_b
    assert len(trials_a) == 4
    model = fit_learned_model(frame, candidate, params_a)
    scores = score_candidate(frame, candidate, model=model)
    assert len(scores) == len(frame)
    assert np.isfinite(scores["phase27_score"].to_numpy(dtype=float)).all()


def test_pairwise_rank_model_orders_simple_signal_without_deprecated_api_warning() -> None:
    frame = _model_frame(session_count=10)
    candidate = _candidate("pairwise_rank_long")
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        model = fit_learned_model(frame, candidate, {"C": 1.0})
    scored = score_candidate(frame, candidate, model=model)
    correlations = []
    for _, group in scored.groupby("as_of_date", sort=True):
        correlations.append(group["phase27_score"].corr(group["directional_return"], method="spearman"))
    assert float(np.nanmean(correlations)) > 0.9


def test_fixed_tail_uses_twenty_percent_and_deterministic_ties() -> None:
    frame = _model_frame(session_count=2, rows_per_session=10)
    frame["phase27_score"] = frame.groupby("as_of_date").cumcount().astype(float)
    selected = select_fixed_tail(frame)
    assert len(selected) == 4
    assert selected.groupby("as_of_date").size().tolist() == [2, 2]
