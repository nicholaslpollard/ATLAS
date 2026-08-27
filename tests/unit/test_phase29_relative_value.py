from __future__ import annotations

import numpy as np
import pandas as pd

from packages.backtesting.phase29_relative_value import (
    nearest_pair_dislocations,
    oriented_reversion_score,
    pca_residual_dislocations,
)


def _formation_returns(seed: int = 29) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sessions = 60
    factor1 = rng.normal(0.0, 0.01, sessions)
    factor2 = rng.normal(0.0, 0.006, sessions)
    data: dict[str, np.ndarray] = {}
    for index in range(8):
        noise = rng.normal(0.0, 0.0015, sessions)
        data[f"i-{index}"] = (0.5 + index * 0.05) * factor1 + (0.2 - index * 0.02) * factor2 + noise
    return pd.DataFrame(data)


def test_phase29_pca_leave_focal_out_current_factor_reconstruction() -> None:
    formation = _formation_returns()
    current = pd.Series({column: 0.002 + index * 0.0001 for index, column in enumerate(formation.columns)})
    baseline = pca_residual_dislocations(formation, current)

    shocked = current.copy()
    shocked["i-0"] += 0.08
    after = pca_residual_dislocations(formation, shocked)

    # The focal current shock changes the focal residual itself but must not alter
    # the factor reconstruction solved from the other peers' current returns.
    assert np.isclose(
        baseline["i-0"].factor_reconstruction,
        after["i-0"].factor_reconstruction,
        rtol=1e-12,
        atol=1e-12,
    )
    assert after["i-0"].residual_dislocation > baseline["i-0"].residual_dislocation


def _formation_closes() -> pd.DataFrame:
    x = np.linspace(0.0, 1.0, 60)
    return pd.DataFrame(
        {
            "focal": 100.0 * (1.0 + 0.04 * x + 0.002 * np.sin(5 * x)),
            "near": 50.0 * (1.0 + 0.04 * x + 0.0022 * np.sin(5 * x)),
            "far": 80.0 * (1.0 - 0.02 * x + 0.015 * np.cos(4 * x)),
        }
    )


def test_phase29_nearest_pair_is_frozen_before_current_dislocation() -> None:
    formation = _formation_closes()
    current_a = pd.Series({"focal": 105.0, "near": 52.5, "far": 77.0})
    current_b = pd.Series({"focal": 130.0, "near": 40.0, "far": 120.0})

    first = nearest_pair_dislocations(formation, current_a)
    second = nearest_pair_dislocations(formation, current_b)

    assert first["focal"].peer_instrument_id == "near"
    assert second["focal"].peer_instrument_id == "near"
    assert np.isclose(first["focal"].formation_distance, second["focal"].formation_distance)
    assert not np.isclose(first["focal"].spread_z, second["focal"].spread_z)


def test_phase29_nearest_pair_lexical_tie_break() -> None:
    x = np.linspace(0.0, 1.0, 60)
    focal = 100.0 * (1.0 + 0.03 * x + 0.002 * np.sin(3 * x))
    # a-peer and b-peer have identical formation paths, so lexical ID must win.
    peer = 50.0 * (1.0 + 0.03 * x - 0.002 * np.sin(3 * x))
    formation = pd.DataFrame({"focal": focal, "b-peer": peer, "a-peer": peer})
    current = pd.Series({"focal": 104.0, "a-peer": 51.0, "b-peer": 51.0})
    result = nearest_pair_dislocations(formation, current)
    assert result["focal"].peer_instrument_id == "a-peer"


def test_phase29_score_orientation_is_fixed() -> None:
    assert oriented_reversion_score(-2.0, orientation=-1.0) == 2.0
    assert oriented_reversion_score(2.0, orientation=1.0) == 2.0
