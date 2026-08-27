from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from packages.backtesting.phase27_research import (
    chronological_boundaries,
    holm_bonferroni,
    selection_checks,
    tranche_metrics,
)


def _economic_fixture(session_count: int = 300) -> tuple[pd.DataFrame, pd.DataFrame]:
    signal_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    start = date(2022, 1, 3)
    for session_index in range(session_count):
        session = start + timedelta(days=session_index)
        fold = min(5, session_index * 6 // session_count)
        # Two losing trades and one larger winner: raw win rate is 1/3, but the
        # same-session mean remains positive after both 10 bps and 25 bps costs.
        for row_index, value in enumerate((-0.001, -0.001, 0.010)):
            signal_rows.append(
                {
                    "as_of_date": session,
                    "instrument_id": f"sig-{session_index:03d}-{row_index}",
                    "directional_return": value,
                    "market_state": "NORMAL",
                    "effective_ticker_state": "NORMAL",
                    "selection_fold": fold,
                }
            )
        for row_index in range(5):
            prediction_rows.append(
                {
                    "as_of_date": session,
                    "instrument_id": f"pred-{session_index:03d}-{row_index}",
                    "directional_return": -0.002 + 0.001 * row_index,
                    "phase27_score": float(row_index),
                    "selection_fold": fold,
                }
            )
    return pd.DataFrame(signal_rows), pd.DataFrame(prediction_rows)


def test_phase27_boundaries_use_exact_three_session_purge() -> None:
    sessions = [date(2024, 1, 1) + timedelta(days=index) for index in range(100)]
    boundaries = chronological_boundaries(sessions)
    assert boundaries.selection_session_count == 75
    assert boundaries.purge_sessions == tuple(sessions[75:78])
    assert boundaries.internal_start == sessions[78]
    assert boundaries.internal_end == sessions[-1]


def test_positive_expectancy_does_not_require_majority_trade_wins() -> None:
    signals, predictions = _economic_fixture()
    metrics = tranche_metrics(
        signals,
        predictions=predictions,
        confidence=0.95,
        fold_field="selection_fold",
        label="unit-positive-expectancy",
        tuning_trial_count=4,
    )
    assert metrics.raw_rows == 900
    assert metrics.signal_sessions == 300
    assert metrics.primary_trade_win_rate is not None
    assert metrics.primary_trade_win_rate < 0.5
    assert metrics.primary_median_trade_return is not None
    assert metrics.primary_median_trade_return < 0
    assert metrics.primary_mean_return is not None and metrics.primary_mean_return > 0
    assert metrics.stress_mean_return is not None and metrics.stress_mean_return > 0
    assert metrics.primary_lcb is not None and metrics.primary_lcb > 0
    assert metrics.positive_folds == 6
    assert metrics.mean_session_spearman_ic is not None
    assert metrics.mean_session_spearman_ic > 0.9
    assert all(selection_checks(metrics).values())


def test_phase27_holm_is_global_and_step_down() -> None:
    p_values = {
        "a": 0.001,
        "b": 0.004,
        "c": 0.020,
        "d": 0.030,
        "e": 0.40,
        "f": 0.50,
        "g": 0.60,
        "h": 0.70,
    }
    result = holm_bonferroni(p_values, alpha=0.05)
    assert len(result) == 8
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is True
    assert result["c"]["rejected_null"] is False
    assert result["d"]["rejected_null"] is False


def test_empty_tranche_is_explicit_not_nan_filled() -> None:
    metrics = tranche_metrics(
        pd.DataFrame(),
        predictions=pd.DataFrame(),
        confidence=0.95,
        fold_field="selection_fold",
        label="unit-empty",
        tuning_trial_count=0,
    )
    assert metrics.raw_rows == 0
    assert metrics.signal_sessions == 0
    assert metrics.primary_mean_return is None
    assert metrics.primary_bootstrap_p_value is None
    assert metrics.fold_means == ()
    assert np.isfinite(float(metrics.tuning_trial_count))
