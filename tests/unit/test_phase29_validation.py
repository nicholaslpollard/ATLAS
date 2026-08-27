from __future__ import annotations

import numpy as np
import pandas as pd

from packages.backtesting.phase29_validation import (
    _holm,
    _independent_pairs,
    _independent_pca_residuals,
)


def _returns() -> pd.DataFrame:
    rng = np.random.default_rng(290229)
    sessions = 60
    f1 = rng.normal(0.0, 0.01, sessions)
    f2 = rng.normal(0.0, 0.006, sessions)
    return pd.DataFrame(
        {
            f"i-{index}": (0.4 + 0.05 * index) * f1
            + (0.2 - 0.01 * index) * f2
            + rng.normal(0.0, 0.001, sessions)
            for index in range(8)
        }
    )


def test_phase29_independent_pca_is_leave_focal_out() -> None:
    formation = _returns()
    current = pd.Series({column: 0.001 * (index + 1) for index, column in enumerate(formation.columns)})
    baseline = _independent_pca_residuals(formation, current)
    shocked = current.copy()
    shocked["i-0"] += 0.08
    after = _independent_pca_residuals(formation, shocked)

    assert np.isclose(baseline["i-0"][1], after["i-0"][1], rtol=1e-12, atol=1e-12)
    assert after["i-0"][0] > baseline["i-0"][0]


def test_phase29_independent_pair_identity_depends_only_on_formation() -> None:
    x = np.linspace(0.0, 1.0, 60)
    formation = pd.DataFrame(
        {
            "focal": 100.0 * (1.0 + 0.03 * x + 0.002 * np.sin(5 * x)),
            "near": 50.0 * (1.0 + 0.03 * x + 0.0022 * np.sin(5 * x)),
            "far": 80.0 * (1.0 - 0.02 * x + 0.015 * np.cos(4 * x)),
        }
    )
    first = _independent_pairs(
        formation, pd.Series({"focal": 104.0, "near": 52.0, "far": 78.0})
    )
    second = _independent_pairs(
        formation, pd.Series({"focal": 130.0, "near": 40.0, "far": 120.0})
    )

    assert first["focal"][0] == "near"
    assert second["focal"][0] == "near"
    assert np.isclose(first["focal"][1], second["focal"][1])
    assert not np.isclose(first["focal"][2], second["focal"][2])


def test_phase29_independent_holm_stops_after_first_nonrejection() -> None:
    result = _holm({"a": 0.001, "b": 0.02, "c": 0.03, "d": 0.04})
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is False
    assert result["c"]["rejected_null"] is False
    assert result["d"]["rejected_null"] is False
