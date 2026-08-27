from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from packages.backtesting.phase28_network import (
    Phase28LeaderEdge,
    compute_signal_values,
    cross_sectional_residuals,
    lead_lag_edge,
    oriented_score,
    select_leaders,
)
from packages.backtesting.phase28_policy import (
    PHASE28_CANDIDATES,
    PHASE28_LEAD_LAG_PAIRS,
    PHASE28_MAX_LEADERS,
    PHASE28_MIN_LEADERS,
    PHASE28_MIN_VALID_LAG_PAIRS,
    PHASE28_SIGNAL_TAIL_FRACTION,
    phase28_policy_fingerprint,
)


def _dates(count: int) -> list[date]:
    start = date(2025, 1, 2)
    return [start + timedelta(days=index) for index in range(count)]


def test_phase28_frozen_policy_shape() -> None:
    assert len(PHASE28_CANDIDATES) == 8
    assert PHASE28_LEAD_LAG_PAIRS == 60
    assert PHASE28_MIN_VALID_LAG_PAIRS == 50
    assert PHASE28_MAX_LEADERS == 3
    assert PHASE28_MIN_LEADERS == 2
    assert PHASE28_SIGNAL_TAIL_FRACTION == 0.20
    assert len(phase28_policy_fingerprint()) == 64


def test_cross_sectional_residuals_remove_same_session_median() -> None:
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
    residuals = cross_sectional_residuals(frame)
    assert np.allclose(residuals.median(axis=1).to_numpy(dtype=float), 0.0)
    assert np.isclose(residuals.loc[_dates(2)[0], "a"], -0.02)


def test_cross_sectional_residuals_fail_session_with_too_few_peers() -> None:
    frame = pd.DataFrame(
        {
            "a": [0.01],
            "b": [0.02],
            "c": [0.03],
            "d": [0.04],
            "e": [np.nan],
        },
        index=_dates(1),
    )
    residuals = cross_sectional_residuals(frame)
    assert residuals.iloc[0].isna().all()


def test_lead_lag_edge_detects_asymmetric_peer_lead() -> None:
    rng = np.random.default_rng(280228)
    count = 90
    peer = rng.normal(0.0, 1.0, size=count)
    focal = np.empty(count)
    focal[0] = 0.0
    focal[1:] = peer[:-1] + rng.normal(0.0, 0.03, size=count - 1)
    residuals = pd.DataFrame(
        {"focal": focal, "peer": peer},
        index=_dates(count),
    )
    edge = lead_lag_edge(
        residuals,
        focal_id="focal",
        peer_id="peer",
        estimation_end=_dates(count)[-1],
    )
    assert edge is not None
    assert edge.valid_pairs == 60
    assert edge.forward_corr > 0.99
    assert edge.asymmetry > 0.8


def test_select_leaders_is_bounded_weighted_and_deterministic() -> None:
    rng = np.random.default_rng(42)
    count = 90
    base = rng.normal(0.0, 1.0, size=count)
    focal = np.r_[0.0, base[:-1] + rng.normal(0.0, 0.02, count - 1)]
    peer_a = base
    peer_b = base + rng.normal(0.0, 0.05, count)
    peer_c = base + rng.normal(0.0, 0.10, count)
    noise = rng.normal(0.0, 1.0, count)
    residuals = pd.DataFrame(
        {
            "focal": focal,
            "peer_a": peer_a,
            "peer_b": peer_b,
            "peer_c": peer_c,
            "noise": noise,
        },
        index=_dates(count),
    )
    leaders = select_leaders(
        residuals,
        focal_id="focal",
        peer_ids=["noise", "peer_c", "peer_b", "peer_a", "focal"],
        estimation_end=_dates(count)[-1],
    )
    assert PHASE28_MIN_LEADERS <= len(leaders) <= PHASE28_MAX_LEADERS
    assert np.isclose(sum(edge.weight for edge in leaders), 1.0)
    assert [edge.peer_id for edge in leaders] == [
        edge.peer_id for edge in sorted(leaders, key=lambda item: (-item.asymmetry, item.peer_id))
    ]


def test_compute_signal_values_uses_frozen_leader_weights() -> None:
    count = 25
    dates = _dates(count)
    residuals = pd.DataFrame(
        {
            "focal": np.linspace(-0.01, 0.02, count),
            "leader_a": np.full(count, 0.01),
            "leader_b": np.full(count, 0.03),
        },
        index=dates,
    )
    leaders = (
        Phase28LeaderEdge("leader_a", 0.7, 0.1, 0.6, 60, 0.25),
        Phase28LeaderEdge("leader_b", 0.8, 0.0, 0.8, 60, 0.75),
    )
    signals = compute_signal_values(
        residuals,
        focal_id="focal",
        leaders=leaders,
        observation_date=dates[-1],
    )
    assert signals is not None
    assert np.isclose(signals.peer_lead_1d, 0.025)
    assert np.isclose(signals.peer_lead_5d, 0.125)
    assert np.isclose(signals.peer_diffusion_gap_1d, 0.005)
    assert np.isclose(
        signals.residual_momentum_20d,
        residuals["focal"].tail(20).sum(),
    )


def test_oriented_score_is_directional() -> None:
    assert oriented_score(0.02, direction="LONG") == 0.02
    assert oriented_score(0.02, direction="SHORT") == -0.02
