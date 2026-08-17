from __future__ import annotations

import pandas as pd
import pytest

from packages.regimes.threshold_probe import (
    REGIME_SELECTED_CONFIRMATION_SESSIONS,
    REGIME_THRESHOLD_POLICY_NAMES,
    REGIME_THRESHOLD_PROBE_CONTRACT_VERSION,
    REGIME_THRESHOLD_TRAINING_SESSIONS,
    threshold_series,
)


def test_threshold_probe_contract_and_grid_are_locked():
    assert REGIME_THRESHOLD_PROBE_CONTRACT_VERSION == (
        "regime-threshold-probe-v1-prior-only-252-policy-grid"
    )
    assert REGIME_THRESHOLD_TRAINING_SESSIONS == 252
    assert REGIME_THRESHOLD_POLICY_NAMES == (
        "frozen_252",
        "expanding_252",
        "rolling_252",
    )
    assert REGIME_SELECTED_CONFIRMATION_SESSIONS == 2


def test_frozen_252_uses_first_seed_window_and_never_moves():
    series = pd.Series([float(value) for value in range(300)])
    result = threshold_series(series, "frozen_252", 0.75)
    expected = series.iloc[:252].quantile(0.75)
    assert result.iloc[:252].isna().all()
    assert result.iloc[252] == pytest.approx(expected)
    assert result.iloc[-1] == pytest.approx(expected)


def test_expanding_252_threshold_excludes_current_observation():
    values = [float(value) for value in range(252)] + [1_000_000.0]
    series = pd.Series(values)
    result = threshold_series(series, "expanding_252", 0.75)
    expected = pd.Series(values[:252]).quantile(0.75)
    assert result.iloc[252] == pytest.approx(expected)


def test_rolling_252_uses_only_prior_252_observations():
    series = pd.Series([float(value) for value in range(254)])
    result = threshold_series(series, "rolling_252", 0.25)
    assert result.iloc[252] == pytest.approx(series.iloc[:252].quantile(0.25))
    assert result.iloc[253] == pytest.approx(series.iloc[1:253].quantile(0.25))


def test_threshold_series_rejects_unknown_policy():
    with pytest.raises(ValueError, match="unknown threshold policy"):
        threshold_series(pd.Series([1.0, 2.0, 3.0]), "future_leak", 0.25)
