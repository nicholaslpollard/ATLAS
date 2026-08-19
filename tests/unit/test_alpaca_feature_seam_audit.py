from __future__ import annotations

import numpy as np

from packages.data.alpaca_feature_seam_audit import (
    ALPACA_FEATURE_SEAM_AUDIT_CONTRACT_VERSION,
    ALPACA_FEATURE_SEAM_SYMBOLS,
    ALPACA_VOLUME_FEATURES,
    AlpacaFeatureSeamAudit,
    _feature_summary,
)
from packages.features.feature_registry import CORE_FEATURE_REGISTRY


def test_feature_seam_contract_and_scope_are_locked() -> None:
    assert ALPACA_FEATURE_SEAM_AUDIT_CONTRACT_VERSION == (
        "historical-source-audit-v3-alpaca-volume-feature-model-seam"
    )
    assert ALPACA_FEATURE_SEAM_SYMBOLS == (
        "AAPL",
        "MSFT",
        "NVDA",
        "TSLA",
        "SPY",
        "QQQ",
        "AMZN",
        "GOOG",
    )


def test_only_five_core_features_are_volume_dependent() -> None:
    dependencies = {
        definition.name: set(definition.dependencies)
        for definition in CORE_FEATURE_REGISTRY.all()
    }
    volume_dependent = tuple(
        name for name in sorted(dependencies) if "volume" in dependencies[name]
    )
    assert set(volume_dependent) == set(ALPACA_VOLUME_FEATURES)
    assert len(ALPACA_VOLUME_FEATURES) == 5
    assert len(CORE_FEATURE_REGISTRY.all()) == 33


def test_feature_summary_reports_exact_identity() -> None:
    summary = _feature_summary([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert summary["rows"] == 3
    assert summary["median_abs_diff"] == 0.0
    assert summary["p95_abs_relative_diff"] == 0.0
    assert summary["correlation"] == 1.0


class _FakeModel:
    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        base = np.clip(x[:, 0], 0.0, 1.0)
        p_down = 0.2 + 0.1 * base
        p_up = 0.2 - 0.05 * base
        p_neutral = 1.0 - p_down - p_up
        return np.column_stack((p_down, p_neutral, p_up))


def test_probability_sensitivity_is_zero_for_identical_features() -> None:
    matrix = np.asarray([[0.1, 2.0], [0.4, 3.0], [0.8, 4.0]], dtype=np.float64)
    result = AlpacaFeatureSeamAudit._probability_sensitivity(_FakeModel(), matrix, matrix.copy())
    assert result["rows"] == 3
    assert result["mean_abs_probability_diff"] == 0.0
    assert result["max_row_probability_diff"] == 0.0
    assert result["argmax_change_fraction"] == 0.0
