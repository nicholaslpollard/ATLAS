from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from packages.backtesting.phase28_validation import (
    _independent_leaders,
    _independent_residuals,
    _independent_signals,
)


def _dates(count: int) -> list[date]:
    start = date(2025, 1, 2)
    return [start + timedelta(days=index) for index in range(count)]


def test_phase28_independent_residualizer_removes_cross_sectional_median() -> None:
    frame = pd.DataFrame(
        {
            "a": [0.01, 0.02],
            "b": [0.02, 0.01],
            "c": [0.03, 0.03],
            "d": [0.04, 0.05],
            "e": [0.05, 0.04],
        },
        index=_dates(2),
    )
    residuals = _independent_residuals(frame)
    assert np.allclose(residuals.median(axis=1).to_numpy(dtype=float), 0.0)


def test_phase28_independent_validator_reconstructs_asymmetric_leaders() -> None:
    rng = np.random.default_rng(280228)
    count = 90
    base = rng.normal(0.0, 1.0, size=count)
    focal = np.r_[0.0, base[:-1] + rng.normal(0.0, 0.02, count - 1)]
    residuals = pd.DataFrame(
        {
            "focal": focal,
            "peer_a": base,
            "peer_b": base + rng.normal(0.0, 0.05, count),
            "peer_c": base + rng.normal(0.0, 0.10, count),
            "noise": rng.normal(0.0, 1.0, count),
        },
        index=_dates(count),
    )
    leaders = _independent_leaders(
        residuals,
        focal_id="focal",
        estimation_end=_dates(count)[-1],
    )
    assert 2 <= len(leaders) <= 3
    assert np.isclose(sum(float(item["weight"]) for item in leaders), 1.0)
    assert all(float(item["forward_corr"]) > 0.0 for item in leaders)
    assert all(float(item["asymmetry"]) > 0.0 for item in leaders)


def test_phase28_independent_signal_reconstruction_uses_frozen_weights() -> None:
    dates = _dates(25)
    residuals = pd.DataFrame(
        {
            "focal": np.linspace(-0.01, 0.02, 25),
            "leader_a": np.full(25, 0.01),
            "leader_b": np.full(25, 0.03),
        },
        index=dates,
    )
    leaders = (
        {
            "peer_id": "leader_a",
            "forward_corr": 0.7,
            "reverse_corr": 0.1,
            "asymmetry": 0.6,
            "valid_pairs": 60,
            "weight": 0.25,
        },
        {
            "peer_id": "leader_b",
            "forward_corr": 0.8,
            "reverse_corr": 0.0,
            "asymmetry": 0.8,
            "valid_pairs": 60,
            "weight": 0.75,
        },
    )
    signals = _independent_signals(
        residuals,
        focal_id="focal",
        leaders=leaders,
        observation_date=dates[-1],
    )
    assert signals is not None
    assert np.isclose(signals["peer_lead_1d"], 0.025)
    assert np.isclose(signals["peer_lead_5d"], 0.125)
    assert np.isclose(signals["peer_diffusion_gap_1d"], 0.005)
    assert np.isclose(signals["residual_momentum_20d"], residuals["focal"].tail(20).sum())
